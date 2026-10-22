# CyberNews

CyberNews is a local, read-only cybersecurity publication, powered internally by the SignalWatch services. It combines attributed RSS/Atom reporting, NVD CVEs, CISA Known Exploited Vulnerabilities, and optionally GitHub security-tool discovery. The service does not scrape linked articles, generate AI content, or provide user accounts.

## Naming

CyberNews is the publication — the name that appears in the interface, the API title, and this repository. SignalWatch is the internal engine: the original working name of this codebase, which survives in the backend package, the `SIGNALWATCH_*` environment variables, the PostgreSQL database and volume, the `signalwatch-ingest` and `signalwatch-worker` commands, and the `signalwatch` container user. The two layers are deliberately distinct, and SignalWatch is not a separate product or a third-party service.

Stories open in publication-time order, with twelve reports per page and the last seven days selected initially. Topic navigation, search, publisher selection, and an all-dates option provide access to the archive. Article excerpts, vulnerability advisories, and source freshness open in the centered reading room. See [the publication design system](design-system/README.md) for the interface specification.

## Architecture

Docker Compose runs five services:

| Service | Role | Host exposure |
| --- | --- | --- |
| `db` | PostgreSQL 16 with the persistent `signalwatch-db` volume | None |
| `migrate` | One-shot `alembic upgrade head` gate | None |
| `backend` | FastAPI read-only API | None; reached through nginx |
| `worker` | Independent scheduled ingestion loop | None |
| `frontend` | React static build and nginx API proxy | `127.0.0.1:3000` only |

PostgreSQL must be healthy before migrations run. A successful migration is required before the API and worker start, and the API must be healthy before the frontend starts. Only nginx is published to the host.

## Start

Requirements: Docker Engine with Docker Compose v2.24 or newer.

```bash
cp .env.example .env
# Optionally edit .env to set API keys and an identifying contact URL.
docker compose up --build -d
docker compose ps
docker compose logs -f worker
```

Open <http://127.0.0.1:3000>. Check the proxied service health at <http://127.0.0.1:3000/health>.

The worker starts its first pass immediately after migration and then uses each configured interval. It processes sources independently, so one failed provider does not stop the others. Initial NVD and CISA loads can take time; the UI may initially be empty and `/health` reports ingestion as `never`, then `fresh` after any successful source run. RSS, NVD, and CISA need no account. GitHub records a failed source run until `SIGNALWATCH_GITHUB_TOKEN` is configured. An NVD key is optional but recommended for higher rate limits.

Stop containers without deleting data:

```bash
docker compose down
```

## One-Shot Ingestion

With the stack running, invoke the CLI in an ephemeral backend container. Valid source values are `rss`, `nvd`, `cisa`, and `github`; repeat `--source` to combine them. Runs are idempotent upserts, although stopping the scheduled worker avoids overlapping provider requests.

```bash
docker compose run --rm --no-deps backend signalwatch-ingest --source rss
docker compose run --rm --no-deps backend signalwatch-ingest --source cisa --source nvd
docker compose run --rm --no-deps backend signalwatch-ingest --source github
docker compose run --rm --no-deps backend signalwatch-ingest
```

## API

All application calls normally use the frontend's same-origin nginx proxy.

- `GET /health`
- `GET /api/v1/overview`
- `GET /api/v1/articles` and `GET /api/v1/articles/{id}`
- `GET /api/v1/vulnerabilities` and `GET /api/v1/vulnerabilities/{cve_id}`
- `GET /api/v1/tools`
- `GET /api/v1/sources`
- `GET /docs` and `GET /openapi.json` exist on the internal API service but are not proxied by the local nginx configuration

List endpoints support bounded pagination and endpoint-specific filters. The internal OpenAPI schema documents exact query validation.

## Configuration

Compose reads root `.env`; root `.env.example` contains all local settings. Recreate affected containers after changes with `docker compose up -d --build`.

| Setting | Purpose |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Local database initialization and backend connection |
| `SIGNALWATCH_GITHUB_TOKEN` | Enables authenticated GitHub repository search |
| `SIGNALWATCH_NVD_API_KEY` | Optional NVD API key for improved limits |
| `SIGNALWATCH_GITHUB_QUERY` | Search query template; defaults to `topic:cybersecurity pushed:>={since}` and must retain `{since}` for time scoping |
| `SIGNALWATCH_CORS_ORIGINS` | JSON array of direct API browser origins |
| `SIGNALWATCH_USER_AGENT` | Provider-facing identity sent to every upstream. Required for sustained ingestion: NVD and GitHub both require an application name plus a real operator contact. The shipped default is a non-resolving placeholder, and the worker logs a warning while it is in use |
| `SIGNALWATCH_REQUEST_TIMEOUT_SECONDS`, `SIGNALWATCH_REQUEST_RETRIES` | Bounded provider request behavior |
| `SIGNALWATCH_*_INTERVAL_SECONDS` | Per-source worker schedules; minimum 60 seconds |
| `SIGNALWATCH_FRESHNESS_THRESHOLD_SECONDS` | Age after which health reports ingestion as stale |

Do not commit `.env`. Tokens are passed as container environment variables, so for a public or shared deployment use a secrets manager rather than this local setup.

## Provider Etiquette

The bundled sources are public APIs and feeds, and their operators give them away to anyone who asks politely. A shared public instance should keep it that way.

- **Set a real `SIGNALWATCH_USER_AGENT`.** NVD requires a User-Agent that identifies the application and provides a way to contact the operator; GitHub requires the same. The shipped value is a non-resolving placeholder and the worker warns while it is set. Point it at a page that reaches you.
- **Request your own API keys.** `SIGNALWATCH_NVD_API_KEY` and `SIGNALWATCH_GITHUB_TOKEN` are per-operator credentials. The rate limits belong to the key holder, so obtain your own rather than reusing someone else's.
- **Do not shorten the intervals to poll harder.** The defaults are already conservative, and `SIGNALWATCH_*_INTERVAL_SECONDS` has a floor of 60 seconds. Polling a public feed faster spends another operator's uptime.
- **Keep attribution and outbound links intact.** Every excerpt is shown with its publisher and a canonical link. Removing either breaks the terms under which most of these feeds are offered.
- **Honour a takedown.** If a publisher asks for their material to be removed, disable their source and delete the stored records rather than debating it.

None of this is legal advice, and each provider's own terms are the authority. The points above are the subset that keeps a shared instance from being a bad citizen.

## Attribution And Licensing

SignalWatch displays source-provided metadata and plain-text excerpts with the source name and an external canonical link. It does not claim third-party reporting as original work and does not fetch linked article bodies. Raw provider payloads are retained for normalization and auditability, not as a license to redistribute them.

Operators are responsible for each provider's terms, API policies, trademarks, attribution requirements, and content licenses. Keep attribution and outbound links intact. NVD, CISA, GitHub, and each feed publisher have distinct policies; a repository's license governs its code, not its appearance in GitHub metadata. Do not publicly republish stored payloads or excerpts without confirming the applicable rights.

The repository license covers the source code only. It grants no rights to third-party reporting, imagery, structured data, or any other content fetched from a provider, and it is not permission to redistribute provider payloads.

## Tests

Backend tests use mocked HTTP and in-memory SQLite, so they do not require live internet or PostgreSQL:

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest -q
```

Frontend verification:

```bash
cd frontend
npm ci
npm test
npm run build
```

Return to the repository root before running Compose commands.

## License

The source code in this repository is released under the MIT License; see [LICENSE](LICENSE). The bundled fonts are licensed separately under the SIL Open Font License 1.1: [DM Sans](frontend/public/dm-sans-OFL.txt) and [Lora](frontend/public/lora-OFL.txt). Provider content is not covered by the repository license.

## Backup And Reset

Create a logical backup while PostgreSQL is running:

```bash
docker compose exec -T db sh -c 'pg_dump --clean --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB"' > signalwatch.sql
```

Restore after stopping API and worker writes. The backup's cleanup statements replace existing schema objects:

```bash
docker compose stop backend worker
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"' < signalwatch.sql
docker compose up -d backend worker frontend
```

To permanently erase the database and rebuild from migrations, use `docker compose down -v` followed by `docker compose up --build -d`. The `-v` operation is destructive.

## Troubleshooting

- `docker compose ps` shows lifecycle and health; `docker compose logs migrate` diagnoses schema failures.
- `docker compose logs backend worker frontend db` shows service errors. Provider failures are also visible through `/api/v1/sources`.
- A degraded `/health` with `database: ok` means ingestion is stale or has never succeeded, not that the API is unreachable.
- GitHub ingestion works without a token but receives lower public rate limits. Add a token to `.env` for sustained ingestion.
- NVD `403`/`429` responses usually indicate public rate limiting; add `SIGNALWATCH_NVD_API_KEY` or wait for the next interval.
- A changed `POSTGRES_PASSWORD` does not alter credentials inside an existing volume. Restore/reset the volume or revert the setting.
- Port conflicts on `3000` require changing the host side of the frontend `ports` mapping; do not publish backend or database ports merely to debug them.

## Public Deployment Limitations

This Compose setup is intentionally local. It has a known default database password, environment-based secrets, no TLS or authentication, per-instance rather than distributed rate limiting, no network allowlist, no automated backups, no centralized logging/metrics, and a single database/API/worker instance. The nginx CSP, security headers, request limits, and localhost bind reduce local exposure but are not a complete public deployment boundary. Before public deployment, rotate the database password through a secrets manager or managed PostgreSQL service, terminate HTTPS at a trusted ingress, enable HSTS there, add distributed access/rate controls if horizontally scaled, configure backups and monitoring, set resource limits, maintain an image-vulnerability update process, add a canonical-domain sitemap, and review every upstream provider's redistribution terms.
