# Section 4 implementation and test report — 2026-11-13

## Two review tracks

1. **Implementation track:** audit existing backend authentication, SQLAlchemy/Alembic migrations, costly API paths, API client and React UI; add atomic quotas and metering without changing existing OAuth or ChromaDB behavior.
2. **Verification track:** write missing-feature tests first (RED), implement (GREEN), exercise unit/database/HTTP E2E/JS tests, and independently run the broad regression suite against both the updated and original ZIPs.

These are separate development/review workstreams, not external cloud agents connected to the user's Neon account. A zero-bug guarantee is not possible without real-environment acceptance.

## Changes

- `backend/security/usage_limits.py` defines daily plan policy, IP hourly limits and metered routes.
- `backend/auth/auth.py` reserves usage atomically and fails closed if quota storage is missing. New SQLite local schema additions are backward compatible.
- `backend/database/schema_definitions.py` / `backend/database/migrations_auth/versions/auth_0004_usage_limits.py` define additive PostgreSQL migrations.
- `backend/database/migrate_database.py` includes all new usage tables in the guarded SQLite copy tool.
- `backend/api/api.py` adds authenticated `GET /api/usage`.
- `frontend/src/features/usage/UsagePanel.jsx`, `usageDisplay.mjs`, existing `main.jsx`/`style.css` add the responsive Home + Settings usage UI.
- New Python/Node/Playwright/opt-in PostgreSQL tests and GitHub CI checks.

## Tests executed in this sandbox

| Discipline | Result | Scope |
| --- | --- | --- |
| TDD RED | Observed import failure (missing usage policy module) | `tests/test_section4_limits_red.py`, before implementation |
| TDD GREEN | 2 passed after implementation | Same tests |
| Focused unit + integration + HTTP E2E | **26 passed, 1 skipped** | Both SQLite native and SQLAlchemy SQLite, quotas, concurrency, 429/503, account isolation, migration/retention and API cost boundaries |
| Frontend unit tests | **30 passed** | Full existing Node tests and new usage display utility |
| Python compileall | Passed | Modified backend modules |
| React JSX parser | 9 components parsed with 0 syntax errors | TypeScript parser; this is NOT a Vite production build |
| GitHub Action JavaScript tests | **3 passed** | Existing action regression |
| Full backend regression, excluding OAuth module | **398 passed, 4 failed, 5 skipped** (final run) | Four failures match untouched baseline, not new Section 4 changes |
| Original Section 3 baseline failure reproduction | **4 failed** on exact same cases | Three JS/TS/Go code-flow parser cases; anonymous `/gallery/` API route case |
| Real PostgreSQL integration | **Skipped** | No disposable PostgreSQL server / `psycopg` installed in sandbox. Test code is added to CI using isolated PostgreSQL 17 service |
| Browser Playwright E2E | **Written, not executed** | Offline npm cache lacks Vite; frontend dependencies cannot install here, although Chromium exists |
| Real Gemini/GitHub OAuth/production Neon | **Not executed** | Requires user's live account/server, avoided using personal Neon secrets |

**Important:** The test environment lacked `authlib` and could not fetch it; HTTP/unit tests used a minimal **test-only OAuth import stub** that is NOT packaged in the output. This is sufficient for mocked session/quota routes but not real OAuth verification. `tests/test_auth.py` was excluded from the broad run for that reason. Do not consider this full auth certification.

HTTP E2E refers to `TestClient` exercising the real FastAPI middleware with synthetic users and mocked expensive providers; it is not a Playwright browser run.

## Known inherited failures (not introduced by Section 4)

- `test_completion.py::test_non_python_flow_is_explicitly_inferred` fails in three language variants (JS, TS, Go) because the optional native parser does not produce edges in this sandbox.
- `test_product_upgrade.py::test_public_gallery_is_accessible_without_account` fails because `/gallery/` is not served by the FastAPI-only test app.
- Both signatures were independently reproduced against the **untouched Section 3 input ZIP**.

## Remaining user-side acceptance

1. Make a recovery copy of the live Neon branch, then run `schema_migrations upgrade` and `verify`: expected `auth_0004` / `app_0001`.
2. Build and start the frontend on the user's Mac, verify Home/Settings displays counters and Refresh works.
3. Test safe quotas using the synthetic HTTP tests; avoid consuming production Gemini quota to force a 429.
4. Run the disposable PostgreSQL test and Playwright browser E2E. Verify live OAuth, existing Section 3 audit events, and persistence after restart.

Implementation is packaged, focused tests pass, and outstanding live acceptance is clearly pending. Do not label the feature zero-bug or fully production-certified before these checks.
