# Phase 0 follow-up: browser test and gallery route fixes

## Starting point
User's Mac verified: 288 backend tests passed, 1 skipped; 17 frontend unit tests passed; Vite production build passed; browser tests 3/5 passed. `node start.mjs` could not bind port 8000 because an existing listener occupied it.

## Changes made
- `frontend/e2e/dashboard.spec.js`: stub GET `/api/checklists/onboarding-1/share` with `{active:false}`. Checklist UI requests share status automatically; without this mock, the local real API could answer 401 and the browser would redirect to `/login/?reason=expired` while running an otherwise isolated fixture test.
- `frontend/gallery/index.html`: all twenty links now target explicit `/gallery/<slug>/index.html` files instead of relying on a dev server to resolve a directory-index URL. All twenty targets were confirmed present in the project.
- `frontend/e2e/dashboard.spec.js`: gallery E2E now checks navigation to the explicit file and tests the page's `<pre>` contents. This makes the failure more diagnostic.
- `frontend/tests/gallery-links.test.mjs`: new zero-dependency unit/regression test ensures twenty gallery links resolve to real HTML files with the expected source-snapshot disclaimer.

## Tests observed in this environment
- `node --test tests/*.test.mjs`: 18 passed, 0 failed.
- `node --check frontend/e2e/dashboard.spec.js`: passed.
- Gallery target validation: 20/20 paths exist.
- Full Python pytest: blocked at collection, `authlib` not installed in this execution environment. The user's macOS run independently recorded 288 passed, 1 skipped.
- Browser Playwright rerun and Vite build: not run here; `npm ci` did not finish with this environment's package-network availability. Do not claim these browser failures fixed until rerun on macOS.

## Next steps on macOS
From the extracted RepoLens root:
```sh
source .venv/bin/activate
cd frontend
npm ci
npm test
npm run build
npm run test:browser
cd ..
python -m pytest -q
lsof -nP -iTCP:8000 -sTCP:LISTEN
node start.mjs --backend-port 8001
```
Use the `--backend-port 8001` option only if 8000 is in use and the selected OAuth callback origin is configured correctly. Do not kill unrelated processes.

## Phase 0 remaining acceptance gates
- On Mac, prove all five browser E2E tests pass.
- Start backend and frontend successfully.
- Perform one live repository indexing and ask an evidence-backed question with correct paths and citations; check cancellation/recovery and quota failures.
- Verify Google and GitHub OAuth against registered redirect origins, database persistence and migration behavior with real configured services.
- Check one persistence/restart cycle and make sure job status survives a restart.

The added changes are targeted repairs and do not constitute full Phase 0 sign-off.
