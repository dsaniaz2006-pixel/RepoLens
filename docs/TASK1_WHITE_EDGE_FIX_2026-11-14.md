# Task 1 — Remove the white line exposed around the dashboard

## Scope
This release changes only the dashboard document background and adds focused tests. Other requested UI changes (Knowledge Hub buttons, Settings redesign, gallery integration, scroll navigation, liquid controls, logo colour, welcome canvas and reveal text) are **not** implemented in this ZIP; they are future individual tasks.

## Root cause and fix
In the user screenshots, a bright white horizontal band appears at the top in one screenshot and at the bottom in another. The dashboard `.app` had a dark background, but the enclosing `html`, `body` and `#root` did not. On a Mac, trackpad rubber-band scrolling may reveal the default white document background.

The fix in `frontend/src/style.css`:
- Defines near-black (`#121416`) on `html`, `body`, and `#root`.
- Prevents vertical overscroll chaining with `overscroll-behavior-y: none`.
- Covers the viewport via `#root { min-height: 100dvh; }` with `100vh` fallback.
- Matches the existing light theme (`#eef2f4`) using `data-repolens-theme` on `html`.

## Tests
- TDD: `frontend/tests/task1-white-edge.test.mjs` was red before the fix (2 failures), then green after.
- `cd frontend && npm test` — 68/68 passed in the development environment.
- `node --check frontend/e2e/task1_white_edge.spec.js` — passed.
- Browser E2E script: `frontend/e2e/task1_white_edge.spec.js` is included but must be executed on the user's Mac with `npm ci && npx playwright install chromium && npx playwright test e2e/task1_white_edge.spec.js`.
- Live Mac overscroll behaviour was not available for direct verification in the build environment.

## Run locally
From the extracted `RepoLens` project root, copy the `.env` from your previous project, install Python/npm dependencies as needed, and start with your existing HTTPS flow: `node start.mjs --https`.

In Chrome on your Mac, use the trackpad to scroll past the top and bottom of `/dashboard/` and confirm no white line appears. Test both dark and light themes.
