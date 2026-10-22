from datetime import datetime, timezone

from app.models import Article, IngestionRun, RunStatus, Source, SourceKind, Tool, Vulnerability


def seed(db) -> None:
    source = Source(
        name="Security Feed", kind=SourceKind.RSS, url="https://feed.invalid", config={},
        last_success_at=datetime.now(timezone.utc),
    )
    db.add(source)
    db.flush()
    vulnerability = Vulnerability(
        cve_id="CVE-2025-1234", description="Critical flaw", severity="CRITICAL", cvss_score=9.8,
        published_at=datetime.now(timezone.utc), kev=True, vendor="Acme",
        raw_payload={"nvd": {"id": "CVE-2025-1234"}, "cisa": {"cveID": "CVE-2025-1234"}},
    )
    article = Article(
        source_id=source.id, external_id="a1", canonical_url="https://example.com/a1",
        title="Critical CVE-2025-1234", excerpt="Source excerpt", category="vulnerability",
        duplicate_key="critical cve 2025 1234", published_at=datetime.now(timezone.utc),
        image_bytes=b"image", image_content_type="image/jpeg", raw_payload={},
    )
    article.vulnerabilities.append(vulnerability)
    tool = Tool(
        github_id=1, full_name="acme/scanner", url="https://github.com/acme/scanner",
        description="Scanner", language="Python", stars=500, forks=10, topics=["security"],
        pushed_at=datetime.now(timezone.utc), raw_payload={},
    )
    run = IngestionRun(
        source_id=source.id, status=RunStatus.SUCCEEDED, finished_at=datetime.now(timezone.utc),
        items_seen=1, items_written=1,
    )
    db.add_all([article, tool, run])
    db.commit()


def test_all_read_endpoints(client, session_factory) -> None:
    with session_factory() as db:
        seed(db)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    overview = client.get("/api/v1/overview")
    assert overview.json()["kev_count"] == 1
    articles = client.get("/api/v1/articles", params={"category": "vulnerability", "cve_id": "cve-2025-1234"})
    assert articles.json()["total"] == 1
    assert articles.json()["items"][0]["has_image"] is True
    assert articles.json()["items"][0]["cve_ids"] == ["CVE-2025-1234"]
    assert "duplicate_key" not in articles.json()["items"][0]
    article_id = articles.json()["items"][0]["id"]
    assert client.get(f"/api/v1/articles/{article_id}").json()["vulnerabilities"][0]["cve_id"] == "CVE-2025-1234"
    vulnerabilities = client.get("/api/v1/vulnerabilities", params={"kev": "true", "min_cvss": 9})
    assert vulnerabilities.json()["total"] == 1
    assert {item["source"] for item in vulnerabilities.json()["items"][0]["source_references"]} == {"NVD", "CISA KEV"}
    assert client.get("/api/v1/vulnerabilities/CVE-2025-1234").json()["articles"][0]["id"] == article_id
    assert client.get("/api/v1/tools", params={"language": "Python", "min_stars": 100}).json()["total"] == 1
    assert client.get("/api/v1/sources").json()[0]["latest_run_status"] == "succeeded"


def test_validation_and_not_found_responses(client) -> None:
    assert client.get("/api/v1/articles", params={"page_size": 101}).status_code == 422
    assert client.get("/api/v1/articles", params={"q": "x"}).status_code == 422
    assert client.get("/api/v1/vulnerabilities/not-a-cve").status_code == 422
    assert client.get("/api/v1/articles/999").status_code == 404
    assert client.get("/api/v1/tools", params={"sort": "invalid"}).status_code == 422
    assert client.get("/api/v1/articles", params={"page": 10001}).status_code == 422


def test_search_treats_sql_wildcards_as_literal_text(client, session_factory) -> None:
    with session_factory() as db:
        seed(db)

    assert client.get("/api/v1/articles", params={"q": "%%"}).json()["total"] == 0
    assert client.get("/api/v1/vulnerabilities", params={"q": "__"}).json()["total"] == 0
    assert client.get("/api/v1/tools", params={"q": "%%"}).json()["total"] == 0
    assert client.get("/api/v1/articles", params={"q": "Critical"}).json()["total"] == 1
