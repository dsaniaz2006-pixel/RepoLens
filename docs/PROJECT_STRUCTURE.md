# RepoLens source layout — maintained guide

This is the authoritative file map after the November 2026 conservative refactor. Paths are relative to the **RepoLens project root** (the folder containing `start.mjs`). The launcher, OAuth callbacks, HTTPS, migrations and existing API URLs retain their public interfaces.

```text
RepoLens/
├── README.md                    Main entry and setup
├── VERSION                      Existing release identifier (unchanged)
├── start.mjs                    Single-command API + Vite launcher (unchanged)
├── launcher_utils.mjs           Launch helpers
├── .env.example                 Committable placeholders, never credentials
├── requirements.txt
├── action.yml                   Required root GitHub Action manifest
├── Dockerfile                   Root Docker build compatibility
├── compose.postgres.yml         Root local-DB compatibility
├── backend/
│   ├── api/                     FastAPI entry, schemas, product router, shared errors
│   ├── auth/                    OAuth, sessions, account access
│   ├── ai/                      AI provider and prompts
│   ├── rag/                     Indexing, embeddings, retrieval
│   ├── database/                Stores, schemas, migrations
│   ├── github/                  GitHub + local repository access
│   ├── services/                Analysis, pipelines, workflows, reports
│   ├── security/                Trust and usage controls
│   ├── core/                    Config and .env bootstrap
│   └── cli/                     Command-line entry
├── frontend/
│   ├── src/
│   │   ├── main.jsx             Stable authenticated dashboard entry
│   │   ├── auth.jsx             Stable OAuth UI entry
│   │   ├── apiClient.js         Backwards-compatible API facade
│   │   ├── features/            Home, knowledge, chat, settings, gallery, usage, checklist
│   │   ├── components/          Shared presentation and auth UI
│   │   ├── hooks/               Motion and workspace navigation hooks
│   │   ├── state/               Pure validated workspace-page state rules
│   │   ├── services/            HTTP/stream API client and safe error formatting
│   │   ├── lib/                 Shared motion timing and utilities
│   │   └── *.css                Existing stable style entry points
│   ├── public/                  Public assets, gallery snapshots, site scripts
│   ├── site/                    Public-site scripts
│   ├── tests/                   Node tests
│   └── e2e/                     Playwright tests
├── scripts/                     Invoked verification and operations scripts
├── tests/                       Python tests
├── tests-js/                    Root JS tests
├── deployment/                  Production Compose / Caddy / Dockerfile
├── config/                      Environment conventions (no secrets)
├── docs/
│   ├── guides/                  Active setup guides
│   ├── history/                 Historical change descriptions
│   ├── verification/            Verification reports
│   └── *.md                     Established release, section, and setup notes
└── evaluation/                  Evaluation fixtures and evidence
```

## Ownership rules

| Purpose | Location | Usage |
|---|---|---|
| New dashboard page | `frontend/src/features/<feature>/` | UI + its feature-local view logic |
| Shared reusable visual UI | `frontend/src/components/` | Props in, callbacks out |
| Browser hooks | `frontend/src/hooks/` | React hooks and effects |
| Navigation validation | `frontend/src/state/` | Pure logic; no network |
| HTTP, SSE, and server errors | `frontend/src/services/` | No JSX |
| New FastAPI router | `backend/api/` | Validate inputs, call a service, return response |
| Business logic | `backend/services/` | Data processing, no UI |
| Runtime settings | `backend/core/` and root `.env` | Private credentials are never bundled |
| Database schema change | `backend/database/migrations_*` | Use an audited migration, don't rewrite existing revisions |

## Safe extension example

Add a `backend/api/my_feature.py` with an `APIRouter`, implement computation in `backend/services/my_feature.py`, mount the router from `backend/api/api.py`, and add Python API/unit tests. On the frontend, put the page in `frontend/src/features/my_feature/`, call `services/apiClient.js`, and use local React state or a feature-specific hook. Do not put provider tokens into React code.

## Kept for compatibility

`frontend/src/main.jsx`, `frontend/src/auth.jsx`, `frontend/src/apiClient.js`, `start.mjs`, the root Dockerfile and Compose file, and root `action.yml` remain in place intentionally. Root Python modules were already absent and were not introduced. `backend/api/api.py` remains the ASGI import target (`uvicorn backend.api.api:app`).

## Read next

- [Environment configuration](ENVIRONMENT.md)
- [API boundaries](API_ARCHITECTURE.md)
- [Navigation and state](FRONTEND_STATE.md)
- [Verification and migration](REFACTOR_REPORT.md)
