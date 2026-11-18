# Phase 0 — implementation and verification record

Date: 11 November 2026. Input: `RepoLens4_TwoStage_Fixed_Source(2).zip`.

## Separation of responsibilities

The requested implementation and testing responsibilities were handled as **two sequential workstreams**. There were **no separately running autonomous AI subagents** in this execution environment. Results below are from commands actually executed against this source, not simulated or promised runs.

### Workstream 1 — code inspection and implementation

The project already included an RAG pipeline, persistent embedding cache, API-authenticated index jobs, GitHub/OAuth work, a single-command launcher and tests. The following concrete reliability issues were addressed without replacing those existing features:

1. **Restart-safe background indexing:** `backend/rag/index_jobs.py` now saves job receipts, progress and cancellation to a private SQLite database in `.repolens_auth/index_jobs.sqlite3` (configurable with `REPOLENS_INDEX_JOBS_DB`). Jobs are owner-scoped; another user cannot look up or cancel them. The previous in-memory-only job status was lost on each server restart. A restarted API identifies interrupted jobs and resumes them using the existing persistent per-chunk embedding cache. Previously requested cancellations are not restarted. Jobs that were already completed remain queryable after reopening the job store.
2. **API startup recovery:** `backend/api/api.py` re-enqueues interrupted jobs in lifespan startup, including repository-tracking database writes, unless `REPOLENS_INDEX_AUTO_RESUME=false`. The API remains single-worker by design. A normal browser refresh remains able to query the same job ID.
3. **Quota diagnostics:** `backend/rag/embeddings.py` now distinguishes a recognized *daily* 429 quota failure from a transient 429. The former fails immediately with an actionable safe error instead of waiting repeatedly. Bounded retries also cover transient provider 5xx failures, and the original cause is not exposed in API responses.
4. **Embedding-cache integrity:** `backend/rag/embedding_cache.py` now validates dimensions even when **every** vector is loaded from cache; previously the no-network path could return mixed vector sizes.
5. **Portable preflight:** `scripts/phase0_preflight.py` checks required Python modules, JavaScript tooling, frontend dependencies and optionally local API health. It prints no credential values. The `.env.example` contains the restart recovery controls.

These changes retain current authentication/session/CSRF behavior and all existing frontend UI/source code.

### Workstream 2 — tests, including test-driven development

| Type | Actual execution | Result |
| --- | --- | --- |
| TDD | New `tests/test_phase0_tdd.py` first demonstrated two failing cases: mixed dimensions from an all-cached batch and unnecessary waiting after daily quota exhaustion. Then source was changed and tests rerun. | **RED: 2 failures**; **GREEN: 5 passed** |
| Unit | Relevant embedding vectors, quota/retry, background jobs and cache regression tests. | Passed as part of the 84-test targeted run. |
| Integration | File-backed SQLite job persistence/recovery, owner checks, cached quota budgets and existing RAG/store integration. | Passed as part of the 84-test targeted run. |
| End-to-end | `tests/test_offline_end_to_end.py` executes the backend repository/report/index/retrieval/evidence pipeline with simulated external GitHub/Gemini boundaries. This is a **backend E2E simulation**, not a real-browser or live-provider test. | Passed; real services not verified. |
| Targeted Python tests | `python -m pytest -q tests/test_phase0_tdd.py tests/test_rag_upgrade.py tests/test_index_jobs.py tests/test_quota_wait_diagnostics.py tests/test_offline_end_to_end.py tests/test_tdd_embedding_vectors.py tests/test_reliability_regressions.py -k 'not api_auth and not missing_gemini'` | **84 passed, 2 deselected** |
| Frontend unit suite | `cd frontend && npm test` | **17 passed, 0 failed** |
| Other release-regression suite | `python -m pytest -q tests/test_release_workflows.py -k 'not migration'` | **11 passed, 1 deselected** |
| Source compilation | `python -m compileall -q backend scripts tests`; `node --check start.mjs` and `node --check frontend/src/apiClient.js` | Passed |
| Unfiltered Python suite | `python -m pytest -q --continue-on-collection-errors` | **218 passed, 7 failed, 19 errors, 3 skipped**. Failures/errors arose from absent Authlib and unavailable native JS/TS/Go parser modules. Not a successful full run. |
| Frontend production build | `cd frontend && npm run build` | **Blocked:** Vite is not installed in this sandbox (`node_modules` missing). |
| Browser E2E | `cd frontend && npm run test:browser` | **Blocked:** Playwright package/browser not installed in this sandbox. |
| Dependency setup | `python -m pip install authlib chromadb google-genai tree-sitter ...` | **Blocked:** network DNS resolution unavailable to package index. No installed dependencies or production files were altered. |

## Remaining Phase 0 acceptance gates (NOT complete)

- [ ] On the user's macOS environment, create `.venv` and install all packages in `requirements.txt` (including Authlib, ChromaDB, Gemini SDK, PostgreSQL driver and Tree-sitter grammars).
- [ ] In `frontend/`, run `npm ci`, `npm test`, `npm run build`, `npx playwright install chromium`, and `npm run test:browser` with a usable browser environment.
- [ ] Run the full Python suite with **zero failures** (without deselecting tests).
- [ ] Run real Google and GitHub OAuth sign-in/logout, CSRF and workspace access checks using the intended redirect origin and configured credentials.
- [ ] Verify actual SQLite and PostgreSQL migrations, persistence and restoration. Use a disposable database for migration testing.
- [ ] Run live GitHub + Gemini repository index end-to-end, check file citations, quota failures, cancellation, interruption/restart, cache recovery, and a second query after server restart.
- [ ] Run `node start.mjs --check` and `node start.mjs` from the project root on the Mac; verify the app starts and does not conflict with existing ports.
- [ ] Capture a successful deployment/browser acceptance log before claiming Phase 0 complete.

**Verdict: Phase 0 has additional verified code fixes, but remains BLOCKED for final sign-off until the above real-environment tests pass.** Neither automatic recovery nor quota messages can increase a provider's actual daily quota.

## Run from zero on macOS

```bash
cd /path/to/extracted/RepoLens
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp -n .env.example .env   # fill secrets locally; do NOT send .env in chat
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:browser
cd ..
python scripts/phase0_preflight.py
python -m pytest -q
node start.mjs --check
node start.mjs
```

Your `.env` should be configured using `docs/AUTH_SETUP.md` and `.env.example`. For **real index verification**, make sure a working `GEMINI_API_KEY` has enough embedding quota or choose and configure local Ollama. Do not place credentials in ZIP files or test reports.

## Security and scope

Only statuses and public GitHub repository URLs are written to the new job database. Private credentials, source text, generated reports and account databases are excluded by the existing source-release packaging rules. The current `start.mjs` and container Dockerfile use one API process (required for these in-process workers); multi-worker deployment would need a separate central job queue and durable lease mechanism.
