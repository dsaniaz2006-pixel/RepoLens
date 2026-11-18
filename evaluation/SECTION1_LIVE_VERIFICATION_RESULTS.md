# RepoLens Section 1 — Actual verification results (2026-11-12)

## Scope

Audit of the source snapshot `RepoLens_Section1_Neon_PostgreSQL_Alembic_Ready.zip` in this environment, plus a new read-only Neon verification tool and tests. The owner's Mac/Neon database is **not reachable in this environment** and no credentials were received.

## Results actually executed

| Check | Observed result | Notes |
|---|---|---|
| Section 1 migration + new verification regression tests | **15 passed, 1 skipped** | Local SQLite end-to-end; skip is the real Postgres integration test (no `REPOLENS_TEST_POSTGRES_URL`) |
| Broader backend/database/feature regression run | **54 passed, 1 skipped, 15 setup errors** | Missing Python `authlib` package prevented the HTTP tests from initializing; these were not assertion failures |
| Frontend JavaScript unit tests | **28 passed** | Run before attempting dependency reinstall |
| Focused ownership/workspace authorization regression | **2 passed, 29 deselected** | These are included in previous test families and are not additive totals |
| Frontend production build | **Blocked in this container** | `vite: not found`; attempts to install missing packages failed due unavailable npm registry. User's Mac had previously shown a successful build. |
| Playwright browser E2E | **Not run here** | Missing npm dependencies after install attempt; existing browser tests use mocked API endpoints |
| Real Neon read-only inspection | **Not run here** | Requires private credentials stored on the user's Mac. A read-only verifier is provided. |
| Live Google/GitHub login + chat/workspace persistence | **Not independently tested** | Requires the running local website with the user's authenticated session |

## New test/verification files

- `scripts/verify_section1_neon.py`: SELECT-only inspection of the Neon PostgreSQL auth/app databases; compares source backup counts and identity keys to current online records, verifies both Alembic histories, refuses local SQLite URLs in normal usage, redacts private data.
- `tests/test_section1_live_verify.py`: three isolated regression tests including deliberately altered user identity and rejection of accidental SQLite configuration.
- `docs/SECTION1_NEON_FINAL_ACCEPTANCE.md`: exact Mac-side commands for read-only audit, UI persistence, Playwright and isolated-branch PostgreSQL integration.

## Interpretation

**Section 1 implementation is present and local migration logic passes its tests, but Section 1 is not yet fully live-verified.** A successful `SELECT 1` and `up_to_date: true` establish connectivity/schema compatibility only. Complete the real data verification and browser/Neon integration steps before closing the section.

A snapshot of the old user's migration preview contained one user and one session, but zero chats and zero conversation messages. These counts cannot prove conversation/workspace persistence by themselves.
