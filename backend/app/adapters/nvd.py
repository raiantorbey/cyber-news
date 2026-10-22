import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from app.adapters.base import HTTPClient, IncompleteProviderResponse, VulnerabilityRecord
from app.processing import parse_datetime, plain_text

logger = logging.getLogger(__name__)


class NVDAdapter:
    URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    PAGE_SIZE = 2000
    MAX_PAGES_PER_WINDOW = 10
    WINDOW = timedelta(days=7)
    MAX_LOOKBACK = timedelta(days=120)
    WATERMARK_OVERLAP = timedelta(minutes=5)
    UNAUTHENTICATED_DELAY_SECONDS = 6.0

    def __init__(
        self,
        http: HTTPClient,
        api_key: str | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.http = http
        self.api_key = api_key
        self.sleep = sleep

    async def fetch(self, since: datetime | None = None) -> list[VulnerabilityRecord]:
        end = datetime.now(timezone.utc)
        since = since or end - timedelta(days=1)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        since = since.astimezone(timezone.utc) - self.WATERMARK_OVERLAP
        oldest_supported = end - self.MAX_LOOKBACK
        if since < oldest_supported:
            logger.warning(
                "NVD watermark predates the 120-day API limit; clamping and omitting older changes"
            )
            since = oldest_supported
        headers = {"apiKey": self.api_key} if self.api_key else {}
        records: dict[str, VulnerabilityRecord] = {}
        request_count = 0
        window_start = since
        while window_start < end:
            window_end = min(window_start + self.WINDOW, end)
            received = 0
            total: int | None = None
            window_cves: set[str] = set()
            for page in range(self.MAX_PAGES_PER_WINDOW):
                if request_count and not self.api_key:
                    await self.sleep(self.UNAUTHENTICATED_DELAY_SECONDS)
                params: dict[str, Any] = {
                    "lastModStartDate": window_start.isoformat(timespec="milliseconds"),
                    "lastModEndDate": window_end.isoformat(timespec="milliseconds"),
                    "resultsPerPage": self.PAGE_SIZE,
                    "startIndex": page * self.PAGE_SIZE,
                }
                response = await self.http.get(self.URL, params=params, headers=headers)
                request_count += 1
                payload = response.json()
                items = payload.get("vulnerabilities")
                advertised = payload.get("totalResults")
                if not isinstance(items, list) or not isinstance(advertised, int) or advertised < 0:
                    raise IncompleteProviderResponse("NVD returned an invalid pagination payload")
                if total is None:
                    total = advertised
                elif total != advertised:
                    raise IncompleteProviderResponse("NVD result count changed during pagination")
                for item in items:
                    if not isinstance(item, dict) or not isinstance(item.get("cve"), dict):
                        raise IncompleteProviderResponse("NVD returned a malformed vulnerability")
                    record = self._record(item["cve"])
                    if record.cve_id in window_cves:
                        raise IncompleteProviderResponse("NVD returned duplicate records within a window")
                    window_cves.add(record.cve_id)
                    records[record.cve_id] = record
                received += len(items)
                if received > total:
                    raise IncompleteProviderResponse("NVD returned more records than totalResults")
                if received >= total:
                    break
                if not items:
                    raise IncompleteProviderResponse("NVD pagination ended before totalResults")
            if total is None or received < total:
                raise IncompleteProviderResponse("NVD window exceeds bounded pagination capacity")
            window_start = window_end
        return list(records.values())

    @staticmethod
    def _record(cve: dict[str, Any]) -> VulnerabilityRecord:
        descriptions = cve.get("descriptions", [])
        description = plain_text(next((item["value"] for item in descriptions if item.get("lang") == "en"), None))
        metrics = cve.get("metrics", {})
        metric = next(
            (items[0] for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2") if (items := metrics.get(key))),
            {},
        )
        cvss = metric.get("cvssData", {})
        severity = cvss.get("baseSeverity") or metric.get("baseSeverity")
        vendor, product = NVDAdapter._affiliation(cve)
        return VulnerabilityRecord(
            cve_id=cve["id"].upper(), description=description, severity=severity,
            cvss_score=cvss.get("baseScore"), published_at=parse_datetime(cve.get("published")),
            modified_at=parse_datetime(cve.get("lastModified")), vendor=vendor, product=product,
            raw_payload=cve,
        )

    @staticmethod
    def _affiliation(cve: dict[str, Any]) -> tuple[str | None, str | None]:
        pairs: list[tuple[str, str]] = []

        def remember(vendor: object, product: object) -> None:
            if not isinstance(vendor, str) or not isinstance(product, str):
                return
            if vendor.strip() and product.strip():
                pairs.append((vendor.replace("_", " ").strip(), product.replace("_", " ").strip()))

        for configuration in cve.get("configurations", []) or []:
            if not isinstance(configuration, dict):
                continue
            for node in configuration.get("nodes", []) if isinstance(configuration.get("nodes"), list) else []:
                if not isinstance(node, dict):
                    continue
                for match in node.get("cpeMatch", []):
                    if not isinstance(match, dict):
                        continue
                    criteria = match.get("criteria", "").split(":")
                    if len(criteria) > 4:
                        remember(criteria[3], criteria[4])
        for affected in cve.get("affected", []) or []:
            if not isinstance(affected, dict):
                continue
            remember(affected.get("vendor"), affected.get("product"))
            for group in affected.get("affectedData", []) if isinstance(affected.get("affectedData"), list) else []:
                if not isinstance(group, dict):
                    continue
                remember(group.get("vendor"), group.get("product"))
                for cpe in group.get("cpes", []) if isinstance(group.get("cpes"), list) else []:
                    if not isinstance(cpe, dict):
                        continue
                    criteria = cpe.get("criteria", "").split(":")
                    if len(criteria) > 4:
                        remember(criteria[3], criteria[4])
        return next(((vendor, product) for vendor, product in pairs if vendor and product), (None, None))
