from typing import Any

from app.adapters.base import HTTPClient, VulnerabilityRecord
from app.processing import CVE_PATTERN, parse_datetime, plain_text


class CISAAdapter:
    URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

    def __init__(self, http: HTTPClient):
        self.http = http

    async def fetch(self) -> list[VulnerabilityRecord]:
        response = await self.http.get(self.URL)
        payload = response.json()
        items = payload.get("vulnerabilities") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not items:
            raise ValueError("CISA KEV catalog is missing or empty")
        if not isinstance(payload.get("count"), int) or payload["count"] != len(items):
            raise ValueError("CISA KEV catalog count does not match its entries")
        records = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("CISA KEV catalog contains a malformed entry")
            required = ("cveID", "dateAdded", "dueDate", "requiredAction")
            if any(not isinstance(item.get(field), str) or not item[field].strip() for field in required):
                raise ValueError("CISA KEV catalog entry is missing required fields")
            cve_id = item["cveID"].upper()
            if not CVE_PATTERN.fullmatch(cve_id) or cve_id in seen:
                raise ValueError("CISA KEV catalog contains an invalid or duplicate CVE")
            record = self._record(item)
            if record.date_added is None or record.due_date is None:
                raise ValueError("CISA KEV catalog contains an invalid date")
            seen.add(cve_id)
            records.append(record)
        return records

    @staticmethod
    def _record(item: dict[str, Any]) -> VulnerabilityRecord:
        return VulnerabilityRecord(
            cve_id=item["cveID"].upper(), description=plain_text(item.get("shortDescription")), kev=True,
            vendor=plain_text(item.get("vendorProject")), product=plain_text(item.get("product")),
            date_added=parse_datetime(item.get("dateAdded")), due_date=parse_datetime(item.get("dueDate")),
            required_action=item.get("requiredAction"), raw_payload=item,
        )
