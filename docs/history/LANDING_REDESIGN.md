# RepoLens landing page — cinematic charcoal / blue edition

## Scope

Only the **public landing page** at `/` was redesigned. The dashboard, authentication pages, API, database, indexing and public gallery are unchanged.

The design uses an original implementation inspired by the structure and motion of the Relay landing page on GetLayers. It does not include the premium Relay template source, paid prompt, logo, recordings or assets.

### Design

- Background: near-black charcoal `#121416`
- Panels: charcoal `#1c2024` and `#22282d`
- Interaction: muted navy and blue `#3177ac` / `#28547a`
- Sand: used sparingly (`#c0ac8f` CSS token only)
- Typography: system sans with serif italics for display headings
- Motion: canvas flow lines, reveal-on-scroll, gentle pointer tilt, subtle decorative movement
- Accessibility: `prefers-reduced-motion`, link focus states, skip link, responsive layout, labelled preview tabs

### Files changed

- `frontend/index.html`: new landing sections and real product navigation
- `frontend/public/relay-landing.css`: page-scoped responsive styling
- `frontend/site/landing.js`: decorative animations, interactive previews, reduced-motion support
- `frontend/tests/relay_landing.test.mjs`: source-level regression checks
- `frontend/e2e/relay_landing.spec.js`: browser acceptance checks
- `scripts/verify_relay_landing.sh`: frontend test/build/browser verification

### Run on macOS from scratch

1. Unzip the project and `cd RepoLens`.
2. Copy your trusted private `.env` from your previous RepoLens project into this directory; **never upload your real secrets**. Existing runtime data and Neon database configuration are not moved automatically.
3. Create a Python environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

4. Install frontend packages:

   ```bash
   cd frontend
   npm ci
   npx playwright install chromium
   cd ..
   ```

5. Verify landing page and frontend:

   ```bash
   bash scripts/verify_relay_landing.sh
   ```

6. Start the website:

   ```bash
   node start.mjs
   ```

7. Open `http://127.0.0.1:5173/`.

### Acceptance checklist

- [ ] Desktop hero, blue flow lines and source panel render without errors.
- [ ] On mobile, no sideways scrolling and all product links are usable.
- [ ] Preview buttons switch between Overview, Code flow and Evidence.
- [ ] Sign-up and log-in buttons open their original pages.
- [ ] Workspace, docs, examples, pricing/access, blog and gallery navigation still work.
- [ ] In Reduce Motion mode, animations stop and text remains visible.
- [ ] Existing authentication, database, RAG and dashboard functionality is unchanged.

### Verification performed during packaging

- Frontend Node tests: **52 passed**.
- Static HTML parser: successful; CSS parsing: zero errors.
- Browser smoke with Chromium using in-memory HTML/assets: desktop + 390px mobile rendered, all 19 scroll-reveal elements became visible, no browser page errors, no horizontal overflow, preview tabs responded.
- Full Vite build / Playwright web-server E2E suite: **not executed in this Linux environment**. The upload included macOS `node_modules` binaries that cannot be used for a Linux Vite build, and the browser blocked navigation to the local development server. Run the above verification script on your Mac to complete those checks.

*The glass-window content and showcase charts are explicitly illustrative; they are not live repository analyses or fabricated report results.*
