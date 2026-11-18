# RepoLens 21 — Calm motion, regular scrolling

## Change 1: natural scrolling
Mac trackpad / mouse wheel / keyboard scroll now scrolls **only within the open view**. It no longer navigates between Home, Analyze Repo, Knowledge Hub, etc. Click the normal sidebar buttons or existing action buttons to change views. The new view starts at the top. One view remains mounted at a time.

## Change 2: calm welcome
A versioned one-session welcome key ensures the new animation plays once after upgrading. The canvas welcome lasts ~4.2 seconds instead of 2.2 seconds, using a time-driven 360ms ring hold and 2500ms particle morph, followed by a gentle fade. Reduced-motion viewers see a static version that exits after 500ms.

## Change 3: slower revealing of text and data
Dashboard and public-page headings, paragraphs, list items, and read-only information rows/cards reveal over **950ms**, with **40ms stagger** between nearby elements. This interprets the requested `0.04` as stagger, not entire duration. The website does not rewrite text nodes. Interactive controls, alerts, code, and live statuses are left untouched. The reduced-motion preference removes decorative transitions.

## Reference behavior
Inspired by the restrained blur/stagger concept in the linked 21st.dev reveal example and reduced-motion guidance from MDN, without installing Framer Motion or reworking the current React/Vite architecture.

## Verify
From `frontend`: `npm ci && npx playwright install chromium && npm test && npm run build && npx playwright test e2e/tasks2_9_workspace.spec.js e2e/phase10_gallery.spec.js`.
Then from project root run `node start.mjs --https` after copying `.env` and regenerating local certificates as needed.
