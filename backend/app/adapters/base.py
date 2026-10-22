import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Awaitable, Callable

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

_placeholder_warning_emitted = False


@dataclass
class ArticleRecord:
    external_id: str
    canonical_url: str
    title: str
    excerpt: str | None
    author: str | None
    published_at: datetime
    raw_payload: dict[str, Any]
    image_url: str | None = None


@dataclass
class VulnerabilityRecord:
    cve_id: str
    description: str | None = None
    severity: str | None = None
    cvss_score: float | None = None
    published_at: datetime | None = None
    modified_at: datetime | None = None
    kev: bool | None = None
    vendor: str | None = None
    product: str | None = None
    date_added: datetime | None = None
    due_date: datetime | None = None
    required_action: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolRecord:
    github_id: int
    full_name: str
    url: str
    description: str | None
    language: str | None
    stars: int
    forks: int
    topics: list[str]
    pushed_at: datetime | None
    raw_payload: dict[str, Any]


class HTTPClient:
    def __init__(self, settings: Settings, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        global _placeholder_warning_emitted
        self.settings = settings
        self.sleep = sleep
        if not _placeholder_warning_emitted and settings.user_agent_is_placeholder:
            _placeholder_warning_emitted = True
            logger.warning(
                "SIGNALWATCH_USER_AGENT is still the placeholder %r. NVD and GitHub "
                "require a User-Agent that identifies the application and provides a "
                "real operator contact URL. Set SIGNALWATCH_USER_AGENT in .env before "
                "sustained ingestion, or your requests may be throttled or refused.",
                settings.user_agent,
            )

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        headers = {"User-Agent": self.settings.user_agent, **kwargs.pop("headers", {})}
        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for attempt in range(self.settings.request_retries + 1):
                try:
                    response = await client.get(url, headers=headers, **kwargs)
                    if response.status_code not in {403, 429, 500, 502, 503, 504}:
                        response.raise_for_status()
                        return response
                    if attempt == self.settings.request_retries:
                        response.raise_for_status()
                    delay = self._retry_delay(response.headers.get("Retry-After"), attempt)
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_error = exc
                    if attempt == self.settings.request_retries:
                        raise
                    delay = 0.25 * (2**attempt)
                await self.sleep(delay)
        raise RuntimeError("request failed") from last_error

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 30.0)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    return min(max((retry_at - datetime.now(timezone.utc)).total_seconds(), 0.0), 30.0)
                except (TypeError, ValueError, OverflowError):
                    pass
        return 0.25 * (2**attempt)


class IncompleteProviderResponse(RuntimeError):
    """A provider response ended before all advertised records were received."""
