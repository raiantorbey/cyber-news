from datetime import datetime, timedelta, timezone
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.adapters.base import HTTPClient, IncompleteProviderResponse
from app.adapters.cisa import CISAAdapter
from app.adapters.github import GitHubAdapter
from app.adapters.nvd import NVDAdapter
from app.adapters.rss import RSSAdapter
from app.config import Settings


class FakeHTTP:
    def __init__(self, response: httpx.Response | list[httpx.Response]):
        self.responses = response if isinstance(response, list) else [response]
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]


def response(*, content: bytes | None = None, json=None) -> httpx.Response:
    request = httpx.Request("GET", "https://mock.invalid")
    return httpx.Response(200, content=content, json=json, request=request)


@pytest.mark.asyncio
async def test_rss_adapter_uses_feed_only_and_sanitizes() -> None:
    feed = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
    <item><guid>one</guid><title>CVE-2025-1234 &amp; update</title>
    <link>https://example.com/a?utm_source=rss</link><description><![CDATA[<b>Source</b> excerpt]]></description>
    <pubDate>Mon, 01 Sep 2025 10:00:00 GMT</pubDate></item></channel></rss>'''
    http = FakeHTTP(response(content=feed))
    records = await RSSAdapter(http).fetch("https://feed.invalid/rss")
    assert len(http.calls) == 1
    assert records[0].canonical_url == "https://example.com/a"
    assert records[0].excerpt == "Source excerpt"
    assert records[0].published_at.tzinfo is not None


@pytest.mark.asyncio
async def test_rss_adapter_prefers_amp_page_for_bleepingcomputer_images() -> None:
    image = BytesIO()
    Image.new("RGB", (16, 9), "navy").save(image, format="PNG")
    html = b'<meta property="og:image" content="https://cdn.invalid/cover.png">'
    http = FakeHTTP([response(content=html), response(content=image.getvalue())])

    result = await RSSAdapter(http).fetch_og_image(
        "https://www.bleepingcomputer.com/news/security/example-story/"
    )

    assert http.calls[0][0].endswith("/example-story/amp/")
    assert http.calls[1][0] == "https://cdn.invalid/cover.png"
    assert result is not None
    assert result[1] == "image/jpeg"


@pytest.mark.asyncio
async def test_structured_adapters_parse_mocked_payloads() -> None:
    nvd_payload = {"totalResults": 1, "vulnerabilities": [{"cve": {
        "id": "CVE-2025-1234", "published": "2025-01-01T00:00:00.000Z",
        "lastModified": "2025-01-02T00:00:00.000Z",
        "descriptions": [{"lang": "en", "value": "A flaw"}],
        "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.8, "baseSeverity": "CRITICAL"}}]},
        "configurations": [{"nodes": [{"cpeMatch": [{"criteria": "cpe:2.3:a:vendor:product:1:*:*:*:*:*:*:*"}]}]}],
    }}]}
    nvd = await NVDAdapter(FakeHTTP(response(json=nvd_payload)), "key").fetch(datetime.now(timezone.utc))
    assert (nvd[0].cvss_score, nvd[0].vendor, nvd[0].product) == (9.8, "vendor", "product")

    cisa_payload = {"count": 1, "vulnerabilities": [{
        "cveID": "CVE-2025-1234", "shortDescription": "Used in attacks", "vendorProject": "Vendor",
        "product": "Product", "dateAdded": "2025-01-03", "dueDate": "2025-01-24",
        "requiredAction": "Apply updates",
    }]}
    cisa = await CISAAdapter(FakeHTTP(response(json=cisa_payload))).fetch()
    assert cisa[0].kev is True
    assert cisa[0].required_action == "Apply updates"
    assert (cisa[0].description, cisa[0].vendor, cisa[0].product) == ("Used in attacks", "Vendor", "Product")

    github_payload = {"total_count": 1, "items": [{
        "id": 42, "full_name": "acme/scanner", "html_url": "https://github.com/acme/scanner",
        "description": "<b>Fast</b> scanner", "language": "Python", "stargazers_count": 12,
        "forks_count": 3, "topics": ["security"], "pushed_at": "2025-01-04T00:00:00Z",
    }]}
    github = await GitHubAdapter(FakeHTTP(response(json=github_payload)), "token", "topic:security pushed:>={since}").fetch()
    assert github[0].description == "Fast scanner"
    assert github[0].stars == 12


@pytest.mark.asyncio
async def test_github_allows_public_search_without_authentication() -> None:
    http = FakeHTTP(response(json={"total_count": 0, "incomplete_results": False, "items": []}))

    records = await GitHubAdapter(http, None, "test").fetch()

    assert records == []
    assert "Authorization" not in http.calls[0][1]["headers"]


@pytest.mark.asyncio
async def test_http_client_retries_bounded_transient_failures(monkeypatch) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.headers["User-Agent"] == "SignalWatch/test"
        return httpx.Response(503 if attempts == 1 else 200, request=request, text="ok")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.adapters.base.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("app.adapters.base.asyncio.sleep", no_sleep)
    client = HTTPClient(
        Settings(database_url="sqlite://", user_agent="SignalWatch/test", request_retries=1, request_timeout_seconds=2)
    )
    result = await client.get("https://provider.invalid/data")
    assert result.text == "ok"
    assert attempts == 2


@pytest.mark.asyncio
async def test_http_client_retries_403_and_respects_retry_after(monkeypatch) -> None:
    attempts = 0
    delays = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        headers = {"Retry-After": "2.5"} if attempts == 1 else {}
        return httpx.Response(403 if attempts == 1 else 200, request=request, headers=headers)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.adapters.base.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    client = HTTPClient(Settings(database_url="sqlite://", request_retries=1), sleep=record_sleep)
    assert (await client.get("https://provider.invalid/data")).status_code == 200
    assert delays == [2.5]


@pytest.mark.asyncio
async def test_nvd_paginates_with_unauthenticated_pacing(monkeypatch) -> None:
    monkeypatch.setattr(NVDAdapter, "PAGE_SIZE", 2)
    sleeps = []

    async def no_sleep(delay: float) -> None:
        sleeps.append(delay)

    def cve(number: int):
        return {"cve": {"id": f"CVE-2025-{number:04d}", "descriptions": [], "metrics": {}}}

    http = FakeHTTP([
        response(json={"totalResults": 3, "vulnerabilities": [cve(1), cve(2)]}),
        response(json={"totalResults": 3, "vulnerabilities": [cve(3)]}),
    ])
    records = await NVDAdapter(http, sleep=no_sleep).fetch(datetime.now(timezone.utc) - timedelta(minutes=1))
    assert len(records) == 3
    assert [call[1]["params"]["startIndex"] for call in http.calls] == [0, 2]
    assert sleeps == [NVDAdapter.UNAUTHENTICATED_DELAY_SECONDS]


@pytest.mark.asyncio
async def test_nvd_fails_incomplete_bounded_window(monkeypatch) -> None:
    monkeypatch.setattr(NVDAdapter, "PAGE_SIZE", 2)
    monkeypatch.setattr(NVDAdapter, "MAX_PAGES_PER_WINDOW", 2)

    async def no_sleep(_: float) -> None:
        return None

    def cve(number: int):
        return {"cve": {"id": f"CVE-2025-{number:04d}", "descriptions": [], "metrics": {}}}

    http = FakeHTTP([
        response(json={"totalResults": 5, "vulnerabilities": [cve(1), cve(2)]}),
        response(json={"totalResults": 5, "vulnerabilities": [cve(3), cve(4)]}),
    ])
    with pytest.raises(IncompleteProviderResponse, match="bounded pagination"):
        await NVDAdapter(http, sleep=no_sleep).fetch(datetime.now(timezone.utc) - timedelta(minutes=1))


@pytest.mark.asyncio
async def test_github_paginates_and_fails_on_incomplete_results(monkeypatch) -> None:
    monkeypatch.setattr(GitHubAdapter, "PAGE_SIZE", 2)

    def repository(number: int):
        return {
            "id": number, "full_name": f"acme/tool-{number}",
            "html_url": f"https://github.com/acme/tool-{number}", "description": None,
            "language": None, "stargazers_count": 0, "forks_count": 0, "topics": [], "pushed_at": None,
        }

    complete_http = FakeHTTP([
        response(json={"total_count": 3, "items": [repository(1), repository(2)]}),
        response(json={"total_count": 3, "items": [repository(3)]}),
    ])
    records = await GitHubAdapter(complete_http, "token", "topic:test pushed:>={since}").fetch()
    assert len(records) == 3
    assert [call[1]["params"]["page"] for call in complete_http.calls] == [1, 2]

    incomplete_http = FakeHTTP([
        response(json={"total_count": 3, "items": [repository(1), repository(2)]}),
        response(json={"total_count": 3, "items": []}),
    ])
    with pytest.raises(IncompleteProviderResponse, match="ended before"):
        await GitHubAdapter(incomplete_http, "token", "topic:test pushed:>={since}").fetch()

    flagged_http = FakeHTTP(response(json={"total_count": 1, "incomplete_results": True, "items": [repository(1)]}))
    with pytest.raises(IncompleteProviderResponse, match="marked search results as incomplete"):
        await GitHubAdapter(flagged_http, "token", "topic:test pushed:>={since}").fetch()

    over_limit_http = FakeHTTP(response(json={"total_count": 1001, "items": [repository(1)]}))
    with pytest.raises(IncompleteProviderResponse, match="1000-result API limit"):
        await GitHubAdapter(over_limit_http, "token", "topic:test pushed:>={since}").fetch()


@pytest.mark.asyncio
async def test_nvd_clamps_old_watermark_and_uses_incremental_overlap() -> None:
    async def no_sleep(_: float) -> None:
        return None

    http = FakeHTTP(response(json={"totalResults": 0, "vulnerabilities": []}))
    before = datetime.now(timezone.utc)
    records = await NVDAdapter(http, "key", sleep=no_sleep).fetch(before - timedelta(days=500))
    assert records == []
    first_start = datetime.fromisoformat(http.calls[0][1]["params"]["lastModStartDate"])
    assert before - NVDAdapter.MAX_LOOKBACK - timedelta(seconds=1) <= first_start
    assert first_start <= datetime.now(timezone.utc) - NVDAdapter.MAX_LOOKBACK

    recent_http = FakeHTTP(response(json={"totalResults": 0, "vulnerabilities": []}))
    watermark = datetime.now(timezone.utc) - timedelta(hours=1)
    await NVDAdapter(recent_http, "key", sleep=no_sleep).fetch(watermark)
    request_start = datetime.fromisoformat(recent_http.calls[0][1]["params"]["lastModStartDate"])
    assert abs(request_start - (watermark - NVDAdapter.WATERMARK_OVERLAP)) < timedelta(milliseconds=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"count": 0, "vulnerabilities": []}, {"count": 1, "vulnerabilities": [{}]}])
async def test_cisa_rejects_incomplete_catalog(payload) -> None:
    with pytest.raises(ValueError, match="CISA KEV"):
        await CISAAdapter(FakeHTTP(response(json=payload))).fetch()
