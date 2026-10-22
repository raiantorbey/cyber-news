# SignalWatch Backend

Python 3.12 FastAPI service and ingestion worker for source-attributed cybersecurity intelligence.

## Setup

Install the project, set `SIGNALWATCH_DATABASE_URL`, and apply the schema:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/alembic upgrade head
```

Run the API with `uvicorn app.main:app`, one ingestion pass with `signalwatch-ingest`, or the scheduled process with `signalwatch-worker`. Restrict a one-shot run with repeated options such as `signalwatch-ingest --source rss --source cisa`.

## Sources And Keys

The worker seeds reputable RSS sources plus NVD API 2.0, CISA KEV, and GitHub repository search records. RSS sources remain configurable in the `sources` table. GitHub ingestion is intentionally disabled without `SIGNALWATCH_GITHUB_TOKEN`; an NVD API key is optional but recommended. Every HTTP request has a configured timeout, bounded retries, and an identifying user agent.

SignalWatch reads feed payloads only and never requests linked article pages. Feed descriptions are source-provided excerpts: normalized excerpts are stripped to plain text, while original feed objects remain in `raw_payload`. All displayed reporting must retain its source and external URL attribution.

## Configuration

Copy values from `.env.example` into the process environment. `SIGNALWATCH_CORS_ORIGINS` accepts a JSON list or comma-separated origins. Interval and freshness values are seconds.

## Tests

```bash
pytest -q
```

Tests use in-memory SQLite and mocked responses; they require no live internet or PostgreSQL service.

## Limitations

Categorization, title duplicate keys, and CVE extraction are deterministic heuristics. GitHub discovery depends on the configured search query and fails when a query exceeds GitHub's 1,000-result search limit. NVD uses bounded seven-day windows and at most ten pages per window; an incomplete window fails without advancing source freshness. Watermarks overlap by five minutes. If NVD freshness is older than its 120-day API range limit, ingestion logs a warning and resumes from that boundary, omitting older changes. The API is public/read-only with no user accounts.
