import asyncio
import logging
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters import CISAAdapter, GitHubAdapter, NVDAdapter, RSSAdapter
from app.adapters.base import HTTPClient
from app.config import Settings
from app.defaults import DEFAULT_SOURCES
from app.models import Article, IngestionRun, RunStatus, Source, SourceKind
from app.persistence import apply_cisa_catalog, upsert_article, upsert_tool, upsert_vulnerability

logger = logging.getLogger(__name__)
ADVISORY_LOCK_NAMESPACE = 1397311319
VULNERABILITY_LOCK_KEY = 0


def seed_sources(session: Session) -> None:
    for item in DEFAULT_SOURCES:
        if session.scalar(select(Source).where(Source.url == item["url"])) is None:
            session.add(Source(**{**item, "kind": SourceKind(item["kind"])}))
    session.commit()


class IngestionService:
    def __init__(self, session_factory: Callable[[], Session], settings: Settings):
        self.session_factory = session_factory
        self.settings = settings
        self.http = HTTPClient(settings)
        self._source_locks: dict[int, asyncio.Lock] = {}
        self._vulnerability_lock = asyncio.Lock()
        self._seed_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(self.settings.ingestion_concurrency)

    async def run(self, kinds: set[SourceKind] | None = None) -> list[IngestionRun]:
        async with self._seed_lock:
            with self.session_factory() as session:
                try:
                    seed_sources(session)
                except IntegrityError:
                    session.rollback()
                statement = select(Source.id).where(Source.enabled.is_(True))
                if kinds:
                    statement = statement.where(Source.kind.in_(kinds))
                source_ids = list(session.scalars(statement))

        async def bounded_run(source_id: int) -> IngestionRun:
            async with self._semaphore:
                return await self.run_source(source_id)

        return list(await asyncio.gather(*(bounded_run(source_id) for source_id in source_ids)))

    async def run_source(self, source_id: int) -> IngestionRun:
        with self.session_factory() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise ValueError("source does not exist")
            vulnerability_provider = source.kind in {SourceKind.NVD, SourceKind.CISA}
        lock = self._source_locks.setdefault(source_id, asyncio.Lock())
        if lock.locked():
            return self._skipped_run(source_id)
        await lock.acquire()
        try:
            if vulnerability_provider:
                if self._vulnerability_lock.locked():
                    return self._skipped_run(source_id, "vulnerability ingestion is already running")
                await self._vulnerability_lock.acquire()
                try:
                    return await self._run_source_locked(source_id)
                finally:
                    self._vulnerability_lock.release()
            return await self._run_source_locked(source_id)
        finally:
            lock.release()

    def _skipped_run(
        self,
        source_id: int,
        error: str = "source ingestion is already running",
    ) -> IngestionRun:
        with self.session_factory() as session:
            if session.get(Source, source_id) is None:
                raise ValueError("source does not exist")
            run = IngestionRun(
                source_id=source_id,
                status=RunStatus.SKIPPED,
                finished_at=datetime.now(timezone.utc),
                error=error,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    async def _run_source_locked(self, source_id: int) -> IngestionRun:
        with self.session_factory() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise ValueError("source does not exist")
            run = IngestionRun(source_id=source.id, status=RunStatus.RUNNING)
            session.add(run)
            session.commit()
            run_id = run.id
            completed_through = run.started_at
        try:
            with self.session_factory() as session:
                source = session.get(Source, source_id)
                if source is None:
                    raise ValueError("source does not exist")
                if session.get_bind().dialect.name == "postgresql":
                    acquired = session.scalar(
                        text("SELECT pg_try_advisory_xact_lock(:namespace, :source_id)"),
                        {"namespace": ADVISORY_LOCK_NAMESPACE, "source_id": source_id},
                    )
                    if not acquired:
                        run = session.get(IngestionRun, run_id)
                        run.status = RunStatus.SKIPPED
                        run.finished_at = datetime.now(timezone.utc)
                        run.error = "source ingestion is already running"
                        session.commit()
                        session.refresh(run)
                        return run
                    if source.kind in {SourceKind.NVD, SourceKind.CISA}:
                        vulnerability_acquired = session.scalar(
                            text("SELECT pg_try_advisory_xact_lock(:namespace, :lock_key)"),
                            {"namespace": ADVISORY_LOCK_NAMESPACE, "lock_key": VULNERABILITY_LOCK_KEY},
                        )
                        if not vulnerability_acquired:
                            run = session.get(IngestionRun, run_id)
                            run.status = RunStatus.SKIPPED
                            run.finished_at = datetime.now(timezone.utc)
                            run.error = "vulnerability ingestion is already running"
                            session.commit()
                            session.refresh(run)
                            return run
                records = await self._fetch(source)
                written = self._persist(session, source, records)
                run = session.get(IngestionRun, run_id)
                run.status = RunStatus.SUCCEEDED
                run.finished_at = datetime.now(timezone.utc)
                run.items_seen = len(records)
                run.items_written = written
                source.last_success_at = completed_through
                session.commit()
                if source.kind == SourceKind.RSS:
                    await self._fetch_missing_article_images(source_id=source.id)
                session.refresh(run)
                return run
        except Exception as exc:
            logger.warning("Ingestion failed for source %s: %s", source_id, exc)
            with self.session_factory() as session:
                run = session.get(IngestionRun, run_id)
                run.status = RunStatus.FAILED
                run.finished_at = datetime.now(timezone.utc)
                run.error = str(exc)[:1000]
                session.commit()
                session.refresh(run)
                return run

    async def _fetch(self, source: Source):
        if source.kind == SourceKind.RSS:
            return await RSSAdapter(self.http).fetch(source.url)
        if source.kind == SourceKind.NVD:
            return await NVDAdapter(self.http, self.settings.nvd_api_key).fetch(source.last_success_at)
        if source.kind == SourceKind.CISA:
            return await CISAAdapter(self.http).fetch()
        if source.kind == SourceKind.GITHUB:
            adapter = GitHubAdapter(self.http, self.settings.github_token, self.settings.github_query)
            return await adapter.fetch(source.last_success_at)
        raise ValueError(f"unsupported source kind: {source.kind}")

    @staticmethod
    def _persist(session: Session, source: Source, records: list) -> int:
        if source.kind == SourceKind.RSS:
            return sum(upsert_article(session, source, record) for record in records)
        if source.kind == SourceKind.NVD:
            return sum(upsert_vulnerability(session, record, "nvd") for record in records)
        if source.kind == SourceKind.CISA:
            return apply_cisa_catalog(session, records)
        if source.kind == SourceKind.GITHUB:
            return sum(upsert_tool(session, record) for record in records)
        raise ValueError(f"unsupported source kind: {source.kind}")

    async def _fetch_missing_article_images(self, source_id: int | None = None, concurrency: int | None = None) -> int:
        adapter = RSSAdapter(self.http)
        workers = min(concurrency or 1, 4)
        semaphore = asyncio.Semaphore(workers)

        with self.session_factory() as session:
            statement = (
                select(Article)
                .join(Source)
                .where(Source.kind == SourceKind.RSS, Article.image_bytes.is_(None))
                .order_by(Article.published_at.desc())
                .limit(200)
            )
            if source_id is not None:
                statement = statement.where(Article.source_id == source_id)
            pending = [
                (article.id, article.canonical_url, article.image_url)
                for article in session.scalars(statement)
            ]

        async def attach(article_id: int, canonical_url: str, image_url: str | None) -> bool:
            async with semaphore:
                await asyncio.sleep(0.3)
                if image_url:
                    result = await adapter.fetch_image(image_url)
                    resolved = image_url if result else None
                else:
                    await asyncio.sleep(1)
                    og = await adapter.fetch_og_image(canonical_url)
                    result = og[:2] if og else None
                    resolved = og[2] if og else None
            if result is None:
                return False
            with self.session_factory() as session:
                article = session.get(Article, article_id)
                if article is None:
                    return False
                article.image_bytes, article.image_content_type = result
                article.image_url = resolved
                session.commit()
                return True

        attached = sum(
            await asyncio.gather(*(attach(article_id, canonical_url, image_url) for article_id, canonical_url, image_url in pending))
        )
        if attached:
            logger.info("Cached %d article images", attached)
        return attached
