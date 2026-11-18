# RepoLens Phase 6–10: Playwright Browser E2E Reliability Fix

## Reported Mac run

- 8 / 11 browser E2E tests passed.
- Phase 8 flow-diagram assertion selected a hidden SVG `<title>` before the visible source-evidence row.
- Phase 6 workspace and Phase 9 local-snapshot tests timed out waiting for dropdowns.

## Changes made

1. `frontend/e2e/phase6_10.spec.js`:
   - All test-specific API mocks are now installed **before** opening `/dashboard/`. Previously `beforeEach` navigated before these mocks were installed, permitting in-flight requests to hit the real API and cause redirect/race conditions.
   - Flow assertions locate the visible evidence-table row, not the hidden SVG `<title>`.
   - The assignment test now checks the optimistic UI update, waits for a delayed save, reloads the page, and checks persisted progress.
   - The local snapshot test verifies the local API result and asserts the public `/api/ask` endpoint was not called by the browser. This does **not** verify that the backend never calls cloud providers; a separate live/privacy acceptance test is needed.
2. `frontend/playwright.config.js`: Set `reuseExistingServer: false`. The test run now requires Playwright to launch the dev server itself rather than silently attaching to an outdated Vite server already using port 5175. An occupied port will produce a clear failure.
3. `frontend/tests/phase6_10_test_setup.test.mjs`: Added Node regressions to protect the test harness from these changes regressing.

## Tests run in the audit environment

- `node --test tests/*.test.mjs`: **23/23 passed**.
- `node --check e2e/phase6_10.spec.js`: passed.
- `node --check playwright.config.js`: passed.
- ZIP integrity check: passed.

The Playwright browser suite was **not executed** in the audit environment because its Vite and Playwright Node modules were not fully installable there. Do not count this as 11/11 passing until your Mac confirms it.

## Mac verification

Keep the old working project folder as a backup. Extract this ZIP in a new folder, then copy the previous `.env` to the new `RepoLens` root. From that root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npx playwright install chromium
npm test
npm run build
npm run test:browser
cd ..
python -m pytest -q
```

If Playwright reports port 5175 occupied:

```bash
lsof -nP -iTCP:5175 -sTCP:LISTEN
```

Stop only the old Vite/RepoLens development server you own (Ctrl+C in its terminal) and rerun the browser tests.

## Remaining live-service acceptance gates

Browser API mocks cannot certify a real Ollama inference, secure local-only operation, GitHub advisory correctness, or 20 reviewed AI gallery reports. Complete the live Phase 6–10 acceptance checklist before sign-off.
