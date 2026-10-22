from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.adapters.base import ArticleRecord, ToolRecord, VulnerabilityRecord
from app.adapters.rss import extract_entry_image
from app.models import Article, ArticleCVELink, Source, Tool, Vulnerability
from app.processing import categorize, duplicate_key, extract_cves, plain_text, validate_http_url


def _placeholder_insert(cve_id: str, dialect_name: str):
    values = {"cve_id": cve_id, "raw_payload": {"placeholder": True}}
    if dialect_name == "postgresql":
        return postgresql_insert(Vulnerability).values(**values).on_conflict_do_nothing(
            index_elements=[Vulnerability.cve_id]
        )
    if dialect_name == "sqlite":
        return sqlite_insert(Vulnerability).values(**values).on_conflict_do_nothing(
            index_elements=[Vulnerability.cve_id]
        )
    return None


def _ensure_placeholder(session: Session, cve_id: str) -> None:
    statement = _placeholder_insert(cve_id, session.get_bind().dialect.name)
    if statement is not None:
        session.execute(statement)
    elif session.get(Vulnerability, cve_id) is None:
        session.add(Vulnerability(cve_id=cve_id, raw_payload={"placeholder": True}))
        session.flush()


def upsert_article(session: Session, source: Source, record: ArticleRecord) -> bool:
    validate_http_url(record.canonical_url)
    article = session.scalar(
        select(Article).where(
            (Article.source_id == source.id) & (Article.external_id == record.external_id)
        )
    )
    if article is None:
        article = session.scalar(
            select(Article).where(
                (Article.source_id == source.id) & (Article.canonical_url == record.canonical_url)
            )
        )
    created = article is None
    if created:
        article = Article(source_id=source.id, external_id=record.external_id, canonical_url=record.canonical_url)
        session.add(article)
    article.canonical_url = record.canonical_url
    article.title = record.title
    article.excerpt = record.excerpt
    article.author = record.author
    article.published_at = record.published_at
    article.category = categorize(record.title, record.excerpt)
    article.duplicate_key = duplicate_key(record.title)
    if record.image_url:
        article.image_url = record.image_url
    article.raw_payload = record.raw_payload
    session.flush()
    cve_ids = set(extract_cves(record.title, record.excerpt))
    obsolete = delete(ArticleCVELink).where(ArticleCVELink.article_id == article.id)
    if cve_ids:
        obsolete = obsolete.where(ArticleCVELink.cve_id.not_in(cve_ids))
    session.execute(obsolete)
    for cve_id in cve_ids:
        _ensure_placeholder(session, cve_id)
        if session.get(ArticleCVELink, (article.id, cve_id)) is None:
            session.add(ArticleCVELink(article_id=article.id, cve_id=cve_id))
    return created


def backfill_article_image_urls(session: Session) -> int:
    updated = 0
    statement = select(Article).join(Source).where(
        (Source.kind == "rss")
        & Article.image_url.is_(None)
        & (Article.raw_payload.is_not(None))
    )
    for article in session.scalars(statement):
        url = extract_entry_image(article.raw_payload or {})
        if url:
            article.image_url = url
            updated += 1
    return updated


def upsert_vulnerability(session: Session, record: VulnerabilityRecord, payload_key: str) -> bool:
    vulnerability = session.get(Vulnerability, record.cve_id)
    created = vulnerability is None
    if created:
        vulnerability = Vulnerability(cve_id=record.cve_id)
        session.add(vulnerability)
    raw = dict(vulnerability.raw_payload or {})
    raw[payload_key] = record.raw_payload
    vulnerability.raw_payload = raw
    if payload_key == "nvd":
        for field in ("severity", "cvss_score", "published_at", "modified_at"):
            setattr(vulnerability, field, getattr(record, field))
    elif payload_key == "cisa":
        vulnerability.kev = True
        for field in ("date_added", "due_date", "required_action"):
            setattr(vulnerability, field, getattr(record, field))
    else:
        raise ValueError(f"unsupported vulnerability source: {payload_key}")
    _apply_descriptive_fields(vulnerability, record if payload_key == "nvd" else None)
    return created


def _apply_descriptive_fields(
    vulnerability: Vulnerability,
    nvd_record: VulnerabilityRecord | None = None,
) -> None:
    raw = vulnerability.raw_payload or {}
    if nvd_record is None and isinstance(raw.get("nvd"), dict):
        from app.adapters.nvd import NVDAdapter

        nvd_record = NVDAdapter._record(raw["nvd"])
    cisa = raw.get("cisa") if isinstance(raw.get("cisa"), dict) else {}
    vulnerability.description = (
        nvd_record.description if nvd_record and nvd_record.description is not None
        else plain_text(cisa.get("shortDescription"))
    )
    vulnerability.vendor = (
        nvd_record.vendor if nvd_record and nvd_record.vendor is not None
        else plain_text(cisa.get("vendorProject"))
    )
    vulnerability.product = (
        nvd_record.product if nvd_record and nvd_record.product is not None
        else plain_text(cisa.get("product"))
    )


def apply_cisa_catalog(session: Session, records: list[VulnerabilityRecord]) -> int:
    if not records:
        raise ValueError("CISA KEV catalog cannot be empty")
    current_ids = {record.cve_id for record in records}
    for vulnerability in session.scalars(select(Vulnerability)):
        if vulnerability.cve_id not in current_ids and (
            vulnerability.kev or "cisa" in (vulnerability.raw_payload or {})
        ):
            vulnerability.kev = False
            vulnerability.date_added = None
            vulnerability.due_date = None
            vulnerability.required_action = None
            raw = dict(vulnerability.raw_payload or {})
            raw.pop("cisa", None)
            vulnerability.raw_payload = raw
            _apply_descriptive_fields(vulnerability)
    return sum(upsert_vulnerability(session, record, "cisa") for record in records)


def upsert_tool(session: Session, record: ToolRecord) -> bool:
    validate_http_url(record.url)
    tool = session.scalar(select(Tool).where(Tool.github_id == record.github_id))
    created = tool is None
    if created:
        tool = Tool(github_id=record.github_id, full_name=record.full_name)
        session.add(tool)
    tool.full_name = record.full_name
    tool.url = record.url
    tool.description = record.description
    tool.language = record.language
    tool.stars = record.stars
    tool.forks = record.forks
    tool.topics = record.topics
    tool.pushed_at = record.pushed_at
    tool.raw_payload = record.raw_payload
    return created
