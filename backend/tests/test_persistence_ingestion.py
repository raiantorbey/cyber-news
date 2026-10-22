from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

import asyncio

from app.adapters.base import ArticleRecord, IncompleteProviderResponse, ToolRecord, VulnerabilityRecord
from app.config import Settings
from app.ingestion import IngestionService
from app.models import Article, ArticleCVELink, IngestionRun, RunStatus, Source, SourceKind, Vulnerability
from app.persistence import (
    _ensure_placeholder, _placeholder_insert, apply_cisa_catalog, upsert_article,
    upsert_tool, upsert_vulnerability,
)


def article_record() -> ArticleRecord:
    return ArticleRecord(
        external_id="stable-1", canonical_url="https://example.com/report", title="CVE-2025-1234 exploited",
        excerpt="<not html after adapter>", author="Reporter", published_at=datetime.now(timezone.utc),
        raw_payload={"source": "payload"},
    )


def test_article_upsert_is_idempotent_and_links_cve(db) -> None:
    source = Source(name="Feed", kind=SourceKind.RSS, url="https://feed.invalid", config={})
    db.add(source)
    db.flush()
    assert upsert_article(db, source, article_record()) is True
    assert upsert_article(db, source, article_record()) is False
    db.commit()
    assert db.scalar(select(func.count(Article.id))) == 1
    assert db.scalar(select(func.count(ArticleCVELink.article_id))) == 1
    assert db.get(Vulnerability, "CVE-2025-1234") is not None


def test_article_upsert_does_not_clear_existing_image_metadata(db) -> None:
    source = Source(name="Feed", kind=SourceKind.RSS, url="https://feed.invalid", config={})
    db.add(source)
    db.flush()
    record = article_record()
    upsert_article(db, source, ArticleRecord(**{**record.__dict__, "image_url": "https://cdn.invalid/cover.jpg"}))

    upsert_article(db, source, record)
    article = db.scalar(select(Article))

    assert article.image_url == "https://cdn.invalid/cover.jpg"


def test_postgresql_placeholder_insert_is_conflict_safe() -> None:
    statement = _placeholder_insert("CVE-2025-1234", "postgresql")
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (cve_id) DO NOTHING" in sql


def test_sqlite_placeholder_creation_is_idempotent(db) -> None:
    _ensure_placeholder(db, "CVE-2025-1234")
    _ensure_placeholder(db, "CVE-2025-1234")
    db.flush()
    assert db.scalar(select(func.count(Vulnerability.cve_id))) == 1


@pytest.mark.asyncio
async def test_sources_fail_independently(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        good = Source(name="Good", kind=SourceKind.RSS, url="https://good.invalid", config={})
        bad = Source(name="Bad", kind=SourceKind.RSS, url="https://bad.invalid", config={})
        session.add_all([good, bad])
        session.commit()
        good_id, bad_id = good.id, bad.id

    service = IngestionService(session_factory, Settings(database_url="sqlite://", github_token="x"))

    async def fake_fetch(source):
        if source.id == bad_id:
            raise RuntimeError("provider unavailable")
        return [article_record()]

    monkeypatch.setattr(service, "_fetch", fake_fetch)
    good_run = await service.run_source(good_id)
    bad_run = await service.run_source(bad_id)
    assert good_run.status == RunStatus.SUCCEEDED
    assert bad_run.status == RunStatus.FAILED
    assert bad_run.error == "provider unavailable"
    with session_factory() as session:
        assert session.scalar(select(func.count(Article.id))) == 1
        assert session.scalar(select(func.count(IngestionRun.id))) == 2


def test_same_canonical_url_is_preserved_per_source_and_links_reconcile(db) -> None:
    first = Source(name="First", kind=SourceKind.RSS, url="https://first.invalid", config={})
    second = Source(name="Second", kind=SourceKind.RSS, url="https://second.invalid", config={})
    db.add_all([first, second])
    db.flush()
    record = article_record()
    upsert_article(db, first, record)
    upsert_article(db, second, ArticleRecord(**{**record.__dict__, "external_id": "other"}))
    db.flush()
    assert db.scalar(select(func.count(Article.id))) == 2
    upsert_article(db, first, ArticleRecord(**{**record.__dict__, "external_id": "changed-id"}))
    db.flush()
    assert db.scalar(select(func.count(Article.id))) == 2

    refreshed = ArticleRecord(**{
        **record.__dict__, "title": "CVE-2025-9999 update", "excerpt": "No longer references the old CVE",
    })
    upsert_article(db, first, refreshed)
    db.flush()
    first_article = db.scalar(select(Article).where(Article.source_id == first.id))
    linked = set(db.scalars(select(ArticleCVELink.cve_id).where(ArticleCVELink.article_id == first_article.id)))
    assert linked == {"CVE-2025-9999"}


def test_vulnerability_field_ownership_and_authoritative_cisa_removal(db) -> None:
    nvd = VulnerabilityRecord(
        cve_id="CVE-2025-1234", description="NVD description", severity="HIGH", cvss_score=8.1,
        published_at=datetime.now(timezone.utc), modified_at=datetime.now(timezone.utc),
        vendor="nvd vendor", product="nvd product", raw_payload={
            "id": "CVE-2025-1234", "descriptions": [{"lang": "en", "value": "NVD description"}],
            "metrics": {}, "configurations": [{"nodes": [{"cpeMatch": [{
                "criteria": "cpe:2.3:a:nvd_vendor:nvd_product:1:*:*:*:*:*:*:*"
            }]}]}],
        },
    )
    upsert_vulnerability(db, nvd, "nvd")
    cisa = VulnerabilityRecord(
        cve_id="CVE-2025-1234", description="CISA must not own this", vendor="CISA vendor", kev=True,
        date_added=datetime.now(timezone.utc), due_date=datetime.now(timezone.utc),
        required_action="Patch", raw_payload={
            "cveID": "CVE-2025-1234", "shortDescription": "CISA fallback",
            "vendorProject": "CISA vendor", "product": "CISA product",
        },
    )
    second = VulnerabilityRecord(
        cve_id="CVE-2025-9999", kev=True, date_added=datetime.now(timezone.utc),
        due_date=datetime.now(timezone.utc), required_action="Mitigate", raw_payload={"cveID": "CVE-2025-9999"},
    )
    apply_cisa_catalog(db, [cisa, second])
    vulnerability = db.get(Vulnerability, nvd.cve_id)
    assert (vulnerability.description, vulnerability.vendor, vulnerability.required_action) == (
        "NVD description", "nvd vendor", "Patch"
    )

    upsert_vulnerability(db, VulnerabilityRecord(cve_id=nvd.cve_id, raw_payload={"id": nvd.cve_id}), "nvd")
    assert vulnerability.description == "CISA fallback"
    assert vulnerability.kev is True
    assert vulnerability.required_action == "Patch"

    apply_cisa_catalog(db, [second])
    assert vulnerability.kev is False
    assert vulnerability.date_added is None
    assert vulnerability.required_action is None
    assert "cisa" not in vulnerability.raw_payload


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/plain,bad", "https:///missing-host", "https://bad host/x"])
def test_persistence_rejects_unsafe_outbound_urls(db, url) -> None:
    source = Source(name="Feed", kind=SourceKind.RSS, url="https://feed.invalid", config={})
    db.add(source)
    db.flush()
    record = ArticleRecord(**{**article_record().__dict__, "canonical_url": url})
    with pytest.raises(ValueError, match="URL"):
        upsert_article(db, source, record)
    tool = ToolRecord(1, "acme/tool", url, None, None, 0, 0, [], None, {})
    with pytest.raises(ValueError, match="URL"):
        upsert_tool(db, tool)


@pytest.mark.asyncio
async def test_overlapping_source_run_is_truthfully_skipped(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        source = Source(name="Feed", kind=SourceKind.RSS, url="https://feed.invalid", config={})
        session.add(source)
        session.commit()
        source_id = source.id
    service = IngestionService(session_factory, Settings(database_url="sqlite://"))
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_fetch(_):
        started.set()
        await release.wait()
        return []

    monkeypatch.setattr(service, "_fetch", slow_fetch)
    first = asyncio.create_task(service.run_source(source_id))
    await started.wait()
    second = await service.run_source(source_id)
    release.set()
    first_result = await first
    assert first_result.status == RunStatus.SUCCEEDED
    assert second.status == RunStatus.SKIPPED
    assert "already running" in second.error


@pytest.mark.asyncio
async def test_incomplete_provider_run_does_not_advance_watermark(session_factory, monkeypatch) -> None:
    previous = datetime(2025, 1, 1, tzinfo=timezone.utc)
    with session_factory() as session:
        source = Source(
            name="NVD", kind=SourceKind.NVD, url="https://nvd.invalid", config={}, last_success_at=previous,
        )
        session.add(source)
        session.commit()
        source_id = source.id
    service = IngestionService(session_factory, Settings(database_url="sqlite://", nvd_api_key="key"))

    async def incomplete(_):
        raise IncompleteProviderResponse("truncated window")

    monkeypatch.setattr(service, "_fetch", incomplete)
    run = await service.run_source(source_id)
    assert run.status == RunStatus.FAILED
    with session_factory() as session:
        stored = session.get(Source, source_id)
        assert stored.last_success_at.replace(tzinfo=timezone.utc) == previous


@pytest.mark.asyncio
async def test_success_watermark_is_prefetch_boundary(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        source = Source(name="GitHub", kind=SourceKind.GITHUB, url="https://github.invalid", config={})
        session.add(source)
        session.commit()
        source_id = source.id
    service = IngestionService(session_factory, Settings(database_url="sqlite://", github_token="token"))

    async def long_fetch(_):
        await asyncio.sleep(0.01)
        return []

    monkeypatch.setattr(service, "_fetch", long_fetch)
    run = await service.run_source(source_id)
    with session_factory() as session:
        watermark = session.get(Source, source_id).last_success_at
    assert watermark == run.started_at
    assert watermark < run.finished_at


@pytest.mark.asyncio
async def test_vulnerability_providers_share_busy_lock(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        nvd = Source(name="NVD", kind=SourceKind.NVD, url="https://nvd.invalid", config={})
        cisa = Source(name="CISA", kind=SourceKind.CISA, url="https://cisa.invalid", config={})
        session.add_all([nvd, cisa])
        session.commit()
        nvd_id, cisa_id = nvd.id, cisa.id
    service = IngestionService(session_factory, Settings(database_url="sqlite://", nvd_api_key="key"))
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_fetch(source):
        if source.kind == SourceKind.NVD:
            started.set()
            await release.wait()
        return []

    monkeypatch.setattr(service, "_fetch", slow_fetch)
    nvd_task = asyncio.create_task(service.run_source(nvd_id))
    await started.wait()
    cisa_run = await service.run_source(cisa_id)
    release.set()
    nvd_run = await nvd_task
    assert nvd_run.status == RunStatus.SUCCEEDED
    assert cisa_run.status == RunStatus.SKIPPED
    assert "already running" in cisa_run.error


def test_cisa_fallback_and_nvd_ownership_are_order_independent(db) -> None:
    def cisa_record(cve_id: str) -> VulnerabilityRecord:
        return VulnerabilityRecord(
            cve_id=cve_id, description="CISA description", vendor="CISA vendor", product="CISA product",
            kev=True, date_added=datetime.now(timezone.utc), due_date=datetime.now(timezone.utc),
            required_action="Patch", raw_payload={
                "cveID": cve_id, "shortDescription": "CISA description",
                "vendorProject": "CISA vendor", "product": "CISA product",
            },
        )

    def nvd_record(cve_id: str, descriptive: bool = True) -> VulnerabilityRecord:
        raw = {
            "id": cve_id,
            "descriptions": [{"lang": "en", "value": "NVD description"}] if descriptive else [],
            "metrics": {},
            "configurations": [{"nodes": [{"cpeMatch": [{
                "criteria": "cpe:2.3:a:nvd_vendor:nvd_product:1:*:*:*:*:*:*:*"
            }]}]}] if descriptive else [],
        }
        return VulnerabilityRecord(
            cve_id=cve_id, description="NVD description" if descriptive else None,
            vendor="nvd vendor" if descriptive else None, product="nvd product" if descriptive else None,
            raw_payload=raw,
        )

    first_id = "CVE-2025-1111"
    upsert_vulnerability(db, cisa_record(first_id), "cisa")
    first = db.get(Vulnerability, first_id)
    assert (first.description, first.vendor, first.product) == (
        "CISA description", "CISA vendor", "CISA product"
    )
    upsert_vulnerability(db, nvd_record(first_id), "nvd")
    assert (first.description, first.vendor, first.product) == (
        "NVD description", "nvd vendor", "nvd product"
    )
    upsert_vulnerability(db, nvd_record(first_id, descriptive=False), "nvd")
    assert (first.description, first.vendor, first.product) == (
        "CISA description", "CISA vendor", "CISA product"
    )

    second_id = "CVE-2025-2222"
    upsert_vulnerability(db, nvd_record(second_id), "nvd")
    upsert_vulnerability(db, cisa_record(second_id), "cisa")
    second = db.get(Vulnerability, second_id)
    assert (second.description, second.vendor, second.product) == (
        "NVD description", "nvd vendor", "nvd product"
    )
    assert set(second.raw_payload) == {"nvd", "cisa"}
    assert {reference["source"] for reference in second.source_references} == {"NVD", "CISA KEV"}
