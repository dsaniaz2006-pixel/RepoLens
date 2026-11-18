# Section 7 — Test evidence (2026-11-13)

## Implemented

- New authenticated, CSRF-protected `POST /api/analyze/stream`, using one existing Section 4 quota reservation per request.
- Server-Sent Events stage progress and heartbeats; final report payload mirrors `/api/analyze`.
- Existing report history persistence reused; errors sanitized before SSE delivery.
- Disconnect handled cooperatively at progress boundaries. In-flight provider HTTP calls are not force-killed.
- Frontend incremental SSE parsing, partial network chunk support, split CRLF handling, safe 429 handling, visible analysis progress and Stop waiting action.
- Legacy blocking analyze and RAG indexing job/polling endpoints preserved.
- Existing freshness scheduler and persistent worker leases unchanged; regression tests used to verify them.

## Four requested testing disciplines

1. TDD RED: New four-case backend tests were executed against unchanged Section 6 source: **4 failed** (missing `/api/analyze/stream`, missing quota mapping). GREEN: **4 passed** after implementation.
2. Unit: Frontend Node test suite **39 passed, 0 failed**; 4 new SSE tests. Backend policy test included in targeted run.
3. Integration: Section 7 TestClient SSE tests, plus indexing/freshness/migration regression subset: **39 passed** (one unrelated inherited gallery case deselected). Full compatible backend regression: **431 passed, 4 failed, 7 skipped**. The four failures are inherited non-Python code-flow assertions (3) and unserved gallery route (1), present before Section 7. `authlib` is not installed in this environment; the broad suite used a **test-only OAuth stub** that is excluded from release ZIP.
4. End to end: Local API lifecycle SSE test **passed**, including persisted history and quota accounting. The Playwright browser test is authored and JavaScript syntax-checked but **NOT executed here** because Vite and Playwright dependencies are missing from the offline npm cache (`npm ci --offline` failed for Vite). Live Gemini/GitHub, two-account OAuth, and production Neon tests were not run.

## Source integrity & known limits

No Neon migration required; `auth_0004`, `app_0002` should remain current. Python bytecode compilation passed. Frontend React production build requires the user's Mac. Timing and provider request duration are not guaranteed improved: streaming improves progress visibility, not raw Gemini latency. Background freshness is already persistent and lease-protected; no new scheduling provider is required. AI quotas remain enforced by the existing middleware.
