from datetime import datetime, timedelta, timezone

from app.adapters.base import HTTPClient, IncompleteProviderResponse, ToolRecord
from app.processing import plain_text, parse_datetime, validate_http_url


class GitHubAdapter:
    URL = "https://api.github.com/search/repositories"
    PAGE_SIZE = 100
    MAX_RESULTS = 1000
    WATERMARK_OVERLAP = timedelta(minutes=5)

    def __init__(self, http: HTTPClient, token: str | None, query: str):
        self.http = http
        self.token = token
        self.query = query

    async def fetch(self, since: datetime | None = None) -> list[ToolRecord]:
        since = since or datetime.now(timezone.utc) - timedelta(days=7)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        since -= self.WATERMARK_OVERLAP
        query = self.query.format(since=since.date().isoformat())
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        records: list[ToolRecord] = []
        repository_ids: set[int] = set()
        total: int | None = None
        for page in range(1, 11):
            response = await self.http.get(
                self.URL,
                params={"q": query, "sort": "updated", "order": "desc", "per_page": self.PAGE_SIZE, "page": page},
                headers=headers,
            )
            payload = response.json()
            items = payload.get("items")
            advertised = payload.get("total_count")
            if payload.get("incomplete_results") is True:
                raise IncompleteProviderResponse("GitHub marked search results as incomplete")
            if not isinstance(items, list) or not isinstance(advertised, int) or advertised < 0:
                raise IncompleteProviderResponse("GitHub returned an invalid search payload")
            if advertised > self.MAX_RESULTS:
                raise IncompleteProviderResponse("GitHub search exceeds the 1000-result API limit")
            if total is None:
                total = advertised
            elif advertised != total:
                raise IncompleteProviderResponse("GitHub result count changed during pagination")
            for item in items:
                if item.get("id") in repository_ids:
                    raise IncompleteProviderResponse("GitHub returned duplicate repositories across pages")
                url = validate_http_url(item["html_url"])
                repository_ids.add(item["id"])
                records.append(ToolRecord(
                    github_id=item["id"], full_name=item["full_name"], url=url,
                    description=plain_text(item.get("description")), language=item.get("language"),
                    stars=item.get("stargazers_count", 0), forks=item.get("forks_count", 0),
                    topics=item.get("topics", []), pushed_at=parse_datetime(item.get("pushed_at")),
                    raw_payload=item,
                ))
            if len(records) >= total:
                return records[:total]
            if not items:
                raise IncompleteProviderResponse("GitHub pagination ended before all retrievable results")
        raise IncompleteProviderResponse("GitHub search exceeded the 1000-result pagination limit")
