# RepoLens environment configuration

**Source of truth:** the private `.env` in the project root, alongside `start.mjs`. `.env.example` is the committed template. `backend/core/environment.py` anchors loading to the project root even when a command starts elsewhere, without overwriting process environment variables. `config/README.md` describes environments; it is **not** automatically sourced.

## Local Mac usage

1. Extract the updated ZIP into a new folder; retain your old working folder as a backup.
2. Copy **only** your existing private `.env` into the new project root. Do not paste it into chat, GitHub, logs, or a ZIP.
3. Keep your previously generated `.certs` and local runtime data separately. You may rerun `node scripts/setup_local_https.mjs` to generate a new local certificate.
4. Start with `source .venv/bin/activate && node start.mjs --https` after installation.

## Logical configuration groups

| Group | Examples | Behavior |
|---|---|---|
| OAuth and sessions | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `REPOLENS_SESSION_SECRET`, `REPOLENS_BASE_URL` | Used by FastAPI only; callback origin must match the registered OAuth client |
| AI and GitHub | `GEMINI_API_KEY`, `GITHUB_TOKEN`, `REPOLENS_MODEL_PROVIDER` | Never expose to frontend bundles |
| Database | `REPOLENS_DATABASE_URL`, `REPOLENS_AUTH_DATABASE_URL`, `REPOLENS_MIGRATION_TARGET_URL` | Keep database passwords private; existing migrations are unchanged |
| RAG | `REPOLENS_RAG_INDEX_PROFILE`, `REPOLENS_RAG_TOP_K`, `REPOLENS_CHROMA_PATH`, `REPOLENS_EMBED_CACHE_DIR` | Choose index scope, retrieval depth (1–12) and persistent storage locations |
| Runtime | `REPOLENS_ENV`, `REPOLENS_BACKEND_PORT`, `REPOLENS_FRESHNESS_SCHEDULER` | Local defaults retain compatibility |
| HTTPS | Public origin `https://127.0.0.1:5173`, mkcert `.certs/` | Local trusted HTTPS; not a public deployment certificate |

Production uses environment variables supplied by the deployment environment. See `deployment/compose.production.yml` and the Phase 11 operations guide. **Never** store real provider secrets under `config/` or commit `.env`.

No keys, credentials, or existing database records were included or migrated by this code refactor.
