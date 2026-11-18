# RepoLens 22 — Pre-deployment audit and repairs

**Audit date:** 2026-11-14. **Source:** `RepoLens_22_Clean_Architecture_Refactor_2026-11-14.zip`.

## Current deployment decision

**NOT APPROVED FOR PRODUCTION YET.** This is a repaired release candidate, not a confirmed production release. The local environment cannot install the missing Authlib, Tree-sitter, ChromaDB, psycopg or npm/Vite packages because external package registries are unavailable. The local Chromium browser is blocked from loopback HTTP by the environment's administrator. No real OAuth login, Neon migration, Gemini API, full Vite build, or dashboard browser E2E has been confirmed here. Do not label these as passed.

## Actual test evidence

- **JavaScript unit/regressions:** 91/91 passed before changes; rerun after the fixes using `node --test frontend/tests/*.test.mjs tests-js/*.test.mjs`.
- **Targeted RAG + HTTP static public + release tests:** 108/108 passed after fixes, including new failure-path checks and local HTTP server integration.
- **Broader Python suite:** 382 passed, 9 skipped, 7 failed, 27 errors. Most failures/errors are from missing Authlib; three flow tests require Tree-sitter native parsers. This count is *not* a clean pass. The missing dependencies are already declared in `requirements.txt`.
- **Browser E2E:** not passed here. `npm ci --offline` fails (`ENOTCACHED`, Vite not cached). Python Playwright Chromium attempt could launch but HTTP localhost navigation was blocked (`ERR_BLOCKED_BY_ADMINISTRATOR`). Do not substitute the static Python tests for the frontend browser suite.
- **No real external API calls were made** in these tests. Repository samples used synthetic data and previously bundled public files.

## TDD: red test -> root cause -> fix -> regression

### 1. Outdated source retained after rebuilding a RAG index

**Red:** `test_rebuilding_same_revision_drops_obsolete_chunks` failed: `['old', 'keep']` remained instead of `['keep']`.

**Cause:** `backend/rag/rag_store.py` used Chroma `upsert` only. When a rebuild contained fewer or different IDs, old code remained in the collection for the exact same repo/revision/model. That could contaminate AI evidence and violate the reported number of indexed chunks.

**Fix:** Before inserting the new index, read existing IDs without reading source bodies, remove only obsolete IDs in bounded batches, and leave the collection `repolens_complete=False` until the replacement finishes. Failed removals raise a bounded `StoreError`. A regression verifies the index remains unqueryable after a removal failure.

**Green:** New stale-ID, idempotency and failure tests pass along with existing RAG/retrieval tests. Existing in-memory Chroma test doubles were updated to implement `get`/`delete`, and a lexical cache test now accounts for the necessary additional ID read.

### 2. Invalid questions called GitHub before validation

**Red:** `test_invalid_question_does_not_fetch_github` failed because `ask_repo` called `fetch_repo_metadata` for whitespace-only questions.

**Cause:** input validation was deferred to retrieval, after GitHub metadata and revision lookups.

**Fix:** validate question type and non-whitespace content at the `ask_repo` gateway before network access or conversation creation. Tested for empty, whitespace and `None` questions.

### 3. Missing static sample assets

**Red (pre-existing):** `test_demo_links_to_real_bundled_public_sample` failed and the static HTTP integration returned 404 for `/reports/pallets-flask-report.md`.

**Cause:** RepoLens 22's frontend demo still links to static Markdown samples, but the `frontend/public/reports/` sample assets were not included in the refactored source archive.

**Fix:** restored 20 source-snapshot Markdown samples plus review notes from the prior RepoLens Phase 11 source archive. These are **historical deterministic source snapshots**, not independently reviewed AI architecture reports. Do not upgrade their review labels. Local static route tests now pass.

### 4. Release metadata mismatch

**Red (pre-existing):** `test_phase11_release_docs_and_version_are_present` expected `1.1.0-rc.1`, but root `VERSION` said `21-calm-motion`.

**Fix:** restored `VERSION` to `1.1.0-rc.1`, consistent with backend API and frontend package versions. A new release should receive a coordinated version bump after all gates pass.

### 5. Stale gallery navigation assertion

A legacy Phase 10 source test expected a direct dashboard anchor to `/gallery/`. The signed-in gallery has since been integrated into the dashboard as a sidebar button. Updated the test to require both the actual in-dashboard navigation and the independent public `/gallery/` route. No dashboard behaviour was changed for this test.

## Gate A — Unit tests

Run `cd frontend && npm ci && npm test`; run `python -m pytest -q` from the project root once Python requirements are installed. Check **no unexpected skips**, no regressions and error messages that do not reveal secrets. Tests using `REPOLENS_TEST_POSTGRES_URL` must use a **disposable** PostgreSQL database/branch (the tests create and drop schemas).

## Gate B — Integration tests

Verify authenticated API endpoints via FastAPI TestClient, cookie/CSRF expiry/revocation, synthetic RAG end-to-end retrieval, index replacement, independent owner scoping, migrations on disposable database, and local static routes. The included `scripts/verify_predeploy.sh` sets temporary local SQLite paths and disables optional external PostgreSQL tests.

## Gate C — Browser end-to-end tests

From `frontend/` run `npm ci`, `npx playwright install chromium`, `npm run build`, `npm run test:browser`. Exercise login/OAuth against registered HTTPS callbacks; Analyze Repo; Build/Refresh index; Knowledge Hub; Conversations; Settings; Gallery; and logout. Some E2E fixtures intentionally mock auth/API responses; these do not replace a separate real OAuth/provider smoke test. Check actual browser console and API logs for failures.

## Gate D — Test-driven development

Preserve the new `tests/test_predeploy_rag_tdd.py` suite and use **red -> fix -> green -> full regression** for each future defect. The new RAG bug reproductions failed on the source before being fixed. The successful targeted suite alone does not approve production deployment.

## Exact verification command

From the project root after installing Python and Node dependencies:

```bash
bash scripts/verify_predeploy.sh
```

The script runs backend/frontend units, offline integration, new TDD regressions, full Python suite, Vite build and Playwright browser E2E. It returns a nonzero exit code if any gate fails or is blocked. Review skipped tests explicitly. Real OAuth, Gemini quota, production TLS, GitHub Actions and database backup/restore remain separate operational release gates.
