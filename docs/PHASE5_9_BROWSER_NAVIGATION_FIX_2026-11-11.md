# RepoLens Phase 5 / Phase 9 browser navigation fix — 11 November 2026

## User-observed failures

- Phase 5: Playwright timed out waiting for the `Your workspaces` dropdown in `frontend/e2e/phase1_5.spec.js`.
- Phase 9: Playwright could not locate the `Saved snapshot` dropdown in `frontend/e2e/phase6_10.spec.js`.
- Previous Mac run: 9 of 11 browser tests passed; these two failed.

## Diagnosis

There were TWO independent timing hazards:

1. The Phase 5 test overrode `/api/workspaces` AFTER its `beforeEach` hook navigated to `/dashboard/`. React could fetch the initial workspace list before the test-specific mock was registered, leaving the list empty for that page instance.
2. Knowledge Hub's `choose(tab)` function used the same `run()` mutation lock as its asynchronous startup refresh. A tab click arriving while that lock was owned could be ignored instead of updating the selected tab. The test could then wait for a dropdown that was never mounted. This affected Teams and Local Repositories and was a real UI responsiveness defect, not merely a Playwright selector issue.

## Applied source changes

- `frontend/src/features/knowledge/KnowledgeHub.jsx`: Tab selection is now synchronous and independent of the background mutation lock. Tab-specific fetches are asynchronous, and stale responses from previously selected tabs are discarded. Tab buttons expose `aria-pressed`. Outstanding result creation cannot overwrite another tab after navigation.
- `frontend/e2e/phase1_5.spec.js`: Route fixtures register before `page.goto`; both Phase 2/3 and Phase 5 tests use `openDashboard`. Phase 5 asserts the selected Teams tab and the workspace selector.
- `frontend/e2e/phase6_10.spec.js`: Phase 9 verifies that Local Repositories is the selected tab and that the actual local panel is mounted before interacting with the snapshot selector. Added an extra browser regression test that switches tabs during a delayed repository refresh.
- `frontend/tests/phase6_10_test_setup.test.mjs`: Three additional Node source-contract regression checks verify the API mocking order, nonblocking navigation, and explicit local-panel checks.
- `scripts/verify_phase5_9_browser.sh`: Targeted sequential tests followed by the full parallel browser suite.

## Tests actually executed in the packaging environment

- Frontend Node tests: 26 passed, 0 failed.
- GitHub comment Node tests: 3 passed, 0 failed.
- React JSX source: successfully parsed using the TypeScript JSX parser.
- Browser test JavaScript syntax: passed.
- Python backend/scripts/tests compilation: passed.
- ZIP integrity: verified after packaging.

## Important verification limitation

The full Playwright suite and Vite build **could not be executed** in the packaging environment because npm's package cache does not include Vite or Playwright packages; offline `npm ci` failed and network installation timed out. An attempt to open the local test server with Chromium was also blocked by the environment's browser administrator policy. Therefore, 12/12 browser tests is NOT claimed here. The Mac verification below remains essential. The new browser stress scenario brings the expected test count from 11 to 12.

## Verification on Mac

From the extracted project's root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npx playwright install chromium
npm test
npm run build
cd ..
bash scripts/verify_phase5_9_browser.sh
```

The script runs targeted Phase 1–5 and Phase 6–10 browser scenarios serially, then the full suite with five workers. Stop an old process on port 5175 before running: Playwright is configured not to reuse another server. Do NOT copy old `node_modules` or `frontend/dist` without reinstalling and rebuilding. Restore `.env` securely from your previous working project; this ZIP intentionally excludes secrets and runtime databases.

If browser failures remain, share the complete failing test output and `frontend/test-results/.../error-context.md`. Do not treat mocked browser tests as proof that external GitHub, Gemini, or Ollama integrations are live-verified.
