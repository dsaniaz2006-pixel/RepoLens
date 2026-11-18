# RepoLens cinematic depth landing upgrade

## Scope

This release adds the missing three-dimensional look to the **public landing page only** (`/`) from the previous charcoal/blue Relay-inspired RepoLens ZIP. It does not change existing backend, authentication, dashboard, API, database, RAG, or Gallery behavior.

## Changes

- `frontend/site/depth-ribbons.js` — original mathematically projected 3D filament ribbons converging at a focal portal; drifting light particles, soft bloom, depth-sorted strands. Canvas rendering stays local and makes no API calls. Capped to ~24 fps with reduced rendering cost and stops off-screen or when the tab is hidden. Reduced Motion draws one static frame only.
- `frontend/site/landing.js` — pointer-driven CSS perspective tilt and backing-plane parallax, without altering preview buttons or auth. First-viewport hero content is revealed immediately even on slow devices.
- `frontend/index.html` — decorative portal/field, two translucent depth planes behind the source-analysis window. All illustrations are labelled previews.
- `frontend/public/relay-landing.css` — layered 3D glass surfaces, blue atmospheric field, a perspective code graph and dashboard, mobile masking to keep ribbons off body text, and reduced-motion safe styling.
- `frontend/tests/relay_landing.test.mjs` — new regression guard for depth scene, route preservation, scope and network independence.
- `frontend/e2e/relay_landing.spec.js` — new pointer-parallax and reduced-motion browser cases.

Reference: user-supplied Relay screen recording. This is an original implementation inspired by the observed effect, not a pixel-identical copy of proprietary code/assets and not an imported 3D/WebGL package.

## Theme

Charcoal #121416, dark gray #1c2024, navy/blue #3177ac and related blue glow. Sand is not used on the hero.

## Start and test on your Mac

1. Unzip the archive, open the `RepoLens` directory and copy your trusted `.env` from your older RepoLens project. Do not upload or share credentials.
2. From the root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npx playwright install chromium
npm test
npm run build
npx playwright test e2e/relay_landing.spec.js
cd ..
node start.mjs
```

3. Visit `http://127.0.0.1:5173/`. Hover the source-analysis glass card. Scroll down to the platform graph and dashboard illustration. On mobile or with system Reduce Motion, 3D movement is intentionally suppressed.

## Checks performed while preparing this ZIP

- Node frontend unit & regression tests: **53/53 passed**.
- `node --check` on the updated JavaScript modules: **passed**.
- Chromium in-memory desktop smoke at 1440x900: **no JS errors**, no horizontal overflow; live canvas rendered, CSS 3D transform present, pointer parallax changed 2.40deg, Code flow preview worked.
- Chromium in-memory 390x844 smoke: **no JS errors**, no horizontal overflow, 3D tilt correctly disabled for mobile.
- Vite full build / Playwright suite not run in this container; npm dependencies and the test web server are not available in a usable Linux installation here. Run the Mac commands above for full browser acceptance.

The preview is an illustration, not a live code analysis.
