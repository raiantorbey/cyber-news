# CyberNews Implementation

## Product

CyberNews is a read-only cybersecurity publication. It aggregates source-provided reporting, structured vulnerability data, known-exploitation context, and security tools. Every excerpt is attributed to its publisher and links to the original report.

## Global Constraints

- Standalone self-contained project; it must not depend on the state of any other project on the host.
- FastAPI API, React + TypeScript frontend, PostgreSQL, and Docker Compose.
- No user accounts and no AI or article scraping in the MVP.
- Sanitize source HTML and store both normalized fields and raw source payloads.
- All network ingestion has explicit timeouts, bounded retries, user-agent identification, rate-limit handling, and per-source failure isolation.
- API pagination is bounded. Query inputs are validated. Error responses do not leak internals.
- Responsive at 375, 768, 1024, and 1440 pixels; keyboard accessible; visible focus; reduced motion respected.
- Tests run without live internet access.

## Backend

- SQLAlchemy 2 models and Alembic migration for sources, articles, vulnerabilities, article-CVE links, tools, and ingestion runs.
- Adapters for configurable RSS/Atom sources, NVD CVE API 2.0, CISA KEV JSON, and authenticated GitHub repository search.
- Idempotent upserts using stable external identifiers/canonical URLs.
- Deterministic categorization and title-based duplicate clustering. Extract CVE identifiers from article content and link records.
- Scheduled worker loop with independent schedules and a one-shot CLI ingestion mode.
- Endpoints: `/health`, `/api/v1/overview`, `/api/v1/articles`, `/api/v1/articles/{id}`, `/api/v1/vulnerabilities`, `/api/v1/vulnerabilities/{cve_id}`, `/api/v1/tools`, `/api/v1/sources`.

## Frontend

- Reader-first publication with Stories, Vulnerabilities, and Tools collections.
- Pearl/green themes, a typographic wordmark, locally served editorial fonts, a floating masthead, rounded chronological story previews, and a centered native-dialog reading room.
- Source directory with update status; topic browsing and on-demand filters; helpful loading, empty, and error states.
- URL query parameters preserve active collection, filters, pagination, and open records. Short-lived response caching makes return visits immediate.
- Source-provided excerpts are visibly attributed and external links are marked.

## Operations

- Dockerfiles and Compose services for frontend, API, worker, and Postgres.
- `.env.example`, health checks, persistent Postgres volume, non-root containers where practical.
- README includes setup, source behavior, API keys, ingestion commands, limitations, and attribution policy.
