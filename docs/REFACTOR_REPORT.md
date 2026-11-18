# RepoLens 22 — conservative source organization report

**Input:** the user-provided `RepoLens_21_Natural_Scrolling_Calm_Welcome_Slow_Reveal_2026-11-14(1).zip` (14 November 2026).

## Implemented

1. Moved 13 root upgrade notes into `docs/history/`, `docs/guides/` or `docs/verification/`, keeping `README.md` at the root. Updated linked Markdown paths and references to moved frontend source.
2. Moved 22 frontend modules into `features/`, `components/layout/`, `hooks/`, `services/`, and `lib/`. Extracted the Home view from the dashboard entry point into `features/home/Home.jsx`.
3. Added a pure `state/workspaceNavigation.mjs` and reusable `hooks/useWorkspaceNavigation.js` for validated navigation state. Kept the application state local and existing click-only navigation.
4. Moved the real HTTP/SSE client into `services/apiClient.js`, preserving `src/apiClient.js` as a compatibility re-export. Consolidated HTTP message formatting and added an actionable streaming connection error.
5. Created `backend/api/errors.py` and `backend/api/schemas.py` to separate validated request models from existing report and product endpoint failure mappings, including safe 422 validation responses. The ASGI entry and URL paths are unchanged.
6. Added `backend/core/environment.py` so API and CLI load the root `.env` consistently; removed duplicate CLI dotenv loading.
7. Removed `backend/database/schema_definitions.py.backup`, which was an outdated backup missing the newest OAuth table. Removed exact unused duplicate `deployment/action.yml` and `deployment/compose.postgres.yml`; required **root** action/Compose files remain.
8. Added architecture, API, state, environment and verification documentation, plus safety tests.

## Deliberately unchanged

- OAuth implementations, session cookies, CSRF controls, database schema and Alembic revisions.
- ChromaDB/RAG indexes, embedding cache, quotas, Gemini/GitHub integration, backend services, and their persistence contracts.
- Existing public API URLs, React HTML entry paths, Vite build inputs, production deployment target, CSS theme and animation design.
- Root `Dockerfile` and production `deployment/Dockerfile` remain duplicates for compatibility with their separate build entry points. Do not remove one without updating downstream consumers.

## Verification and limitations

Use `bash scripts/verify_refactor.sh` after installing dependencies. It runs Node tests, Python refactor tests, offline UI integration checks, and source compilation. It also runs `npm run build` when `frontend/node_modules` is present. Browser E2E requires Playwright Chromium and must be run on the user's Mac.

The new tests establish import/layout and boundary contracts; they cannot prove every OAuth, external API, database, or RAG scenario works in production. A complete rewrite of all legacy state management or exception handling would be a high-risk follow-up. This update is intentionally incremental, not an unverified full rewrite.

## Migration from RepoLens 21

1. Keep RepoLens 21 intact as a fallback. Extract RepoLens 22 to its own folder.
2. Copy the old `.env` into the new root; never bundle it with the project.
3. Use the same Neon/PostgreSQL settings, or explicitly point persistent RAG/auth storage paths at existing data if those paths are local-relative. Don't delete the old data directories.
4. Create a fresh `.venv`, install `requirements.txt`, and run `cd frontend && npm ci`.
5. Run `bash scripts/verify_refactor.sh` and then `cd frontend && npm run test:browser`.
6. Run `node scripts/setup_local_https.mjs` if certificates are absent, then `node start.mjs --https`. Keep Google/GitHub HTTPS callbacks registered.
7. Verify login, analysis, RAG build, conversation, Settings, Public Gallery and scroll behavior against your original project.

There is no automatic data migration in this ZIP. Local databases, stored reports, and RAG indexes are **not** copied from the previous project.

## Verification performed in the packaging environment

- Original baseline: 86 JavaScript tests passed before changes.
- Refactored frontend/root JavaScript: **91 tests passed**.
- Focused Python tests (GitHub client, file selection, analyzer, URL parser, API boundary): **62 passed**.
- Offline UI integration: **5 passed**.
- JavaScript/JSX syntax parse: **57 files, 0 syntax errors** (TypeScript parser).
- Local Markdown links: **43 checked, 0 broken**.
- Full Vite build, all Python API integration tests and browser E2E were **not run** here because this environment lacks a usable frontend dependency installation and some backend dependencies such as Authlib/ChromaDB. Those are required acceptance checks on your Mac.
