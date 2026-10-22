import calendar
import json
import re
from datetime import datetime, timezone
from html import unescape
from io import BytesIO
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser
from PIL import Image, ImageOps

from app.adapters.base import ArticleRecord, HTTPClient
from app.processing import canonicalize_url, plain_text

MAX_FETCH_IMAGE_BYTES = 4_000_000
MAX_EXPORT_WIDTH = 1280
_IMAGE_URL_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)
_IMAGE_TYPE_RE = re.compile(r"image/(?:jpe?g|png|webp|gif|avif)", re.I)
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
_OG_PATTERNS = (
    rb'<meta[^>]+property=["\']og:image:secure_url["\']\s+content=["\']([^"\']+)["\']',
    rb'<meta[^>]+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
    rb'<meta[^>]+content=["\']([^"\']+)["\']\s+property=["\']og:image:secure_url["\']',
    rb'<meta[^>]+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
    rb'<meta[^>]+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']',
    rb'<meta[^>]+content=["\']([^"\']+)["\']\s+name=["\']twitter:image["\']',
)


def extract_entry_image(entry: dict) -> str | None:  # noqa: C901
    media = entry.get("media_content") or []
    if isinstance(media, list):
        for item in media:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            kind = f'{item.get("medium") or ""} {item.get("type") or ""}'
            if isinstance(url, str) and url.startswith("http") and (kind.startswith("image") or _IMAGE_TYPE_RE.search(kind)):
                return url
    thumbnails = entry.get("media_thumbnail") or []
    if isinstance(thumbnails, list):
        for item in thumbnails:
            url = item.get("url") if isinstance(item, dict) else None
            if isinstance(url, str) and url.startswith("http"):
                return url
    enclosures = entry.get("enclosures") or []
    if isinstance(enclosures, list):
        for item in enclosures:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or item.get("href")
            if isinstance(url, str) and url.startswith("http") and "image" in f'{item.get("type") or ""}':
                return url
    for key in ("content", "summary", "description"):
        value = entry.get(key)
        if not value:
            continue
        parts: list[str] = []
        if key == "content" and isinstance(value, list):
            parts = [unescape(v.get("value") or "") if isinstance(v, dict) else unescape(str(v)) for v in value]
        elif isinstance(value, str):
            parts = [value]
        for html_text in parts:
            match = _IMAGE_URL_RE.search(html_text)
            if match:
                url = unescape(match.group(1)).strip()
                if url.startswith("//"):
                    return f"https:{url}"
                if url.startswith("http"):
                    return url
    return None


def downscale_image(data: bytes, content_type: str) -> tuple[bytes, str] | None:
    try:
        image = Image.open(BytesIO(data))
        image = ImageOps.exif_transpose(image)
        image.thumbnail((MAX_EXPORT_WIDTH, MAX_EXPORT_WIDTH))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        output = BytesIO()
        image.save(output, format="JPEG", quality=82, optimize=True, progressive=True)
        return output.getvalue(), "image/jpeg"
    except Exception:
        return None


class RSSAdapter:
    def __init__(self, http: HTTPClient):
        self.http = http

    def parse(self, content: bytes) -> list[ArticleRecord]:
        feed = feedparser.parse(content)
        if feed.bozo and not feed.entries:
            raise ValueError(f"invalid feed: {feed.bozo_exception}")
        records: list[ArticleRecord] = []
        for entry in feed.entries:
            link = entry.get("link")
            title = plain_text(entry.get("title"))
            if not link or not title:
                continue
            parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
            published = (
                datetime.fromtimestamp(calendar.timegm(parsed_time), tz=timezone.utc)
                if parsed_time
                else datetime.now(timezone.utc)
            )
            entry_obj = entry
            entry_dict = dict(entry)
            raw: dict[str, Any] = json.loads(json.dumps(entry_dict, default=str))
            records.append(
                ArticleRecord(
                    external_id=str(entry.get("id") or canonicalize_url(link)),
                    canonical_url=canonicalize_url(link),
                    title=title,
                    excerpt=plain_text(entry.get("summary") or entry.get("description")),
                    author=plain_text(entry.get("author")),
                    published_at=published,
                    raw_payload=raw,
                    image_url=extract_entry_image(entry_obj),
                )
            )
        return records

    async def fetch(self, url: str) -> list[ArticleRecord]:
        response = await self.http.get(url)
        return self.parse(response.content)

    async def fetch_image(self, url: str) -> tuple[bytes, str] | None:
        try:
            response = await self.http.get(url, headers={"User-Agent": BROWSER_UA})
        except Exception:
            return None
        data = response.content
        if len(data) > MAX_FETCH_IMAGE_BYTES:
            return None
        content_type = self._content_type(response.headers.get("content-type") or "", data)
        if content_type is None:
            return None
        processed = downscale_image(data, content_type)
        if processed is None:
            return None
        return processed

    async def fetch_og_image(self, article_url: str) -> tuple[bytes, str, str] | None:
        page_urls = [article_url]
        if urlparse(article_url).hostname == "www.bleepingcomputer.com":
            page_urls.insert(0, f"{article_url.rstrip('/')}/amp/")
        for page_url in page_urls:
            try:
                page = await self.http.get(page_url, headers={"User-Agent": BROWSER_UA})
            except Exception:
                continue
            for pattern in _OG_PATTERNS:
                match = re.search(pattern, page.content, re.I)
                if not match:
                    continue
                url = unescape(match.group(1).decode("utf-8", "ignore")).strip()
                if url.startswith("//"):
                    url = "https:" + url
                elif not url.startswith("http"):
                    url = urljoin(page_url, url)
                result = await self.fetch_image(url)
                if result:
                    data, content_type = result
                    return data, content_type, url
        return None

    @staticmethod
    def _content_type(raw: str, data: bytes) -> str | None:
        declared = raw.split(";")[0].strip().lower()
        if declared.startswith("image/"):
            return declared
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if data.startswith(b"\x89PNG"):
            return "image/png"
        if data.startswith(b"GIF8"):
            return "image/gif"
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "image/webp"
        return None
