# Pre-deployment browser E2E repair — 14 November 2026

## Supplied failure log

The user's macOS `verify_predeploy.sh` output reported **49 passed, 8 failed** from 57 Chromium cases. These were concentrated in three causes rather than eight unrelated application defects:

1. **Five dashboard tests:** the mocked response was attached to legacy `/api/analyze`, but the React workbench now calls `/api/analyze/stream`. As a result, requests leaked to the unstarted FastAPI port 8000 (`ECONNREFUSED`), so the report text never appeared. The browser fixture also lacked default mocks for initial authenticated GETs. Fixed in `frontend/e2e/dashboard.spec.js` using the existing deny-by-default API fixture and an actual SSE-shaped response.
2. **Two HTTPS tests:** the default Playwright configuration starts plain HTTP at port 5175 without FastAPI. The TLS-specific spec therefore could never prove HTTPS and its proxied auth endpoint returned a proxy error instead of the intended 401. Fixed by separating the offline UI suite from `playwright.https.config.js`, which starts the real HTTPS launcher and FastAPI on the loopback interface using isolated test database configuration. The HTTPS gate now runs separately in `scripts/verify_predeploy.sh`.
3. **Invitation HTML test:** Vite's `'/join'` proxy prefix also matched `/join.html` and `/join.js`, sending local static assets to the missing backend. The new anchored `JOIN_PROXY_PATTERN` proxies only `/join` and `/join?token=...`, and allows direct loading of the static invitation HTML and external JS.

## Test-driven verification

A new `frontend/tests/predeploy_e2e_regressions.test.mjs` was written before the fixes, and initially failed because `frontend/config/proxyRoutes.mjs` was missing. Its three checks now pass: scoped invitation proxy, SSE fixture, and distinct HTTPS Playwright gate.

**Checks run in the repair environment:**

- Full frontend Node suite: **91/91 passed**.
- Focused Python unit/integration/RAG/predeploy regression suite: **70/70 passed**.
- Node/JS syntax checks and ZIP integrity checks: passed.

**Not executed here:** frontend production Vite build, Chromium Playwright UI/E2E, full Python regression suite, and real external provider/OAuth workflows. The container does not have the project npm packages or complete Python dependencies, and npm installation timed out. The reported 8 browser failures are fixed in source but remain **unverified by a real browser rerun**. The other blocked gate in the user's output appears to be the full Python suite; the uploaded log does not include its detailed errors. Do not deploy on these test results alone.

## Mac verification

From a clean extraction of this archive (not the older RepoLens 23 folder):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npx playwright install chromium
npm test
npm run build
npm run test:browser                 # UI-mocked offline suite (55 tests)
cd ..
```

Configure local mkcert TLS first if needed (`brew install mkcert; node scripts/setup_local_https.mjs`). Stop older RepoLens servers, then run real HTTPS E2E with the dedicated config:

```bash
cd frontend
npx playwright test --config=playwright.https.config.js
cd ..
```

For the **full pre-deployment gate**, use `bash scripts/verify_predeploy.sh` after stopping any old server on ports 8000 and 5173. This script isolates database paths, executes unit/integration/TDD tests, runs the production build, then runs **both** browser suites. It will fail if an expected gate fails or is unavailable.

Do not use production Neon databases, external OAuth accounts, or a live deployment for these automated checks. Live OAuth and Gemini provider acceptance still require separate manual verification.
