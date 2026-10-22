# CyberNews publication frontend

React 19 + TypeScript publication for source-attributed cybersecurity reporting, vulnerability context, and open-source tools. The interface uses self-hosted DM Sans and Lora, a pearl/green color system, a typographic wordmark, rounded story previews, and a native-dialog reading room.

The design specification is in [`../design-system/README.md`](../design-system/README.md). Presentation lives in `src/ui/`, page composition in `src/pages/`, and API/navigation utilities in `src/lib/`. `src/theme.css` centralizes visual tokens and `src/publication.css` defines layouts and interactions.

## Local development

```bash
npm install
npm run dev
```

Vite proxies `/api` and `/health` to `http://localhost:8000`. Set `VITE_API_BASE_URL` at build time only when the API is not served at `/api/v1` on the same origin.

## Verification

```bash
npm test
npm run build
```

## Container

The multi-stage image serves the built SPA on port `8080`. nginx proxies API requests to `API_UPSTREAM`, which defaults to `backend:8000` and can be overridden at runtime.

```bash
docker build -t cybernews-publication .
docker run --rm -p 8080:8080 --add-host=host.docker.internal:host-gateway -e API_UPSTREAM=host.docker.internal:8000 cybernews-publication
```

All source excerpts are rendered as plain text and visibly attributed. External links open in a new tab with `noopener noreferrer`.
