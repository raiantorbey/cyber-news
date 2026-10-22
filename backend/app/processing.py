import html
import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import bleach


CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
CATEGORIES = (
    ("ransomware", ("ransomware", "extortion")),
    ("vulnerability", ("cve-", "vulnerability", "zero-day", "zero day", "exploit")),
    ("malware", ("malware", "trojan", "botnet", "backdoor", "infostealer")),
    ("breach", ("breach", "data leak", "stolen data", "compromised")),
    ("phishing", ("phishing", "social engineering")),
    ("policy", ("regulation", "legislation", "sanction", "government")),
    ("research", ("research", "analysis", "report")),
)


def plain_text(value: str | None) -> str | None:
    if not value:
        return None
    without_tags = bleach.clean(value, tags=[], attributes={}, strip=True)
    normalized = re.sub(r"\s+", " ", html.unescape(without_tags)).strip()
    return normalized or None


def canonicalize_url(value: str) -> str:
    validate_http_url(value)
    parts = urlsplit(value.strip())
    query = urlencode(
        sorted(
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
        )
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def validate_http_url(value: str) -> str:
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        raise ValueError("URL must be an absolute HTTP(S) URL")
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ValueError("URL must have a valid hostname and port") from exc
    if parts.scheme.lower() not in {"http", "https"} or not hostname:
        raise ValueError("URL must be an absolute HTTP(S) URL")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("URL port is out of range")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("URL hostname is invalid") from exc
        labels = ascii_hostname.rstrip(".").split(".")
        if any(
            not label or len(label) > 63 or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
            for label in labels
        ):
            raise ValueError("URL hostname is invalid")
    return value


def extract_cves(*values: str | None) -> list[str]:
    return sorted({match.upper() for value in values if value for match in CVE_PATTERN.findall(value)})


def categorize(title: str, excerpt: str | None = None) -> str:
    content = f"{title} {excerpt or ''}".lower()
    for category, terms in CATEGORIES:
        if any(term in content for term in terms):
            return category
    return "general"


def duplicate_key(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]", " ", title.lower())
    ignored = {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with"}
    words = [word for word in normalized.split() if word not in ignored]
    return " ".join(words[:16])[:500]


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            result = datetime.strptime(normalized, "%Y-%m-%d")
        except ValueError:
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)
