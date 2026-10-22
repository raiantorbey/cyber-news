from app.processing import canonicalize_url, categorize, duplicate_key, extract_cves, plain_text


def test_source_excerpt_is_sanitized_to_plain_text() -> None:
    value = '<p>Alert &amp; update <script>alert("x")</script><a href="bad">here</a></p>'
    assert plain_text(value) == 'Alert & update alert("x")here'


def test_deterministic_normalization() -> None:
    assert canonicalize_url("HTTPS://Example.COM/post/?utm_source=x&b=2&a=1#top") == "https://example.com/post?a=1&b=2"
    assert extract_cves("CVE-2025-1234 and cve-2024-99999", "CVE-2025-1234") == [
        "CVE-2024-99999", "CVE-2025-1234"
    ]
    assert categorize("Critical CVE-2025-1234 exploited in the wild") == "vulnerability"
    assert duplicate_key("The Major Breach: At Example, Inc!") == "major breach at example inc"
