# RepoLens — Site-wide charcoal & blue styling

Source: `RepoLens_3D_Charcoal_Blue_Glass_Auth_2026-11-13.zip`.
The changes deliberately preserve the existing backend, auth API, RAG, database and routes.

## Theme

- Main background: `#121416` (near-black charcoal)
- Panels: `#222528`, with supporting graphite `#252B30`
- Primary button/navigation: `#28547A` and hover `#356E9A`
- Text: `#F5F5F3`; secondary text: `#ABB7C1`
- Small text/icon detail: cool blue `#87BCE2`; no lime/purple/orange decoration
- Light mode: restrained slate-white surfaces, accessible blue controls

## Coverage

- Dashboard, repository analysis, Knowledge Hub, chat, security settings, usage and saved reports: `frontend/src/style.css` updated, plus the accessible React `CinematicThemeSwitch.jsx` and `theme-switch.css`.
- Public gallery, documentation, access/usage, blog, examples, demo: `frontend/public/site-theme.css` and `frontend/site/theme.js` shared across all pages.
- Landing page and OAuth screens already use the requested charcoal-and-blue cinematic palette and are left visually intact, rather than disrupting their own 3D/glass treatment.
- User preference is stored locally as `repolens-theme`; dark is default, light is optional. This is only a display preference and does not change authorization.

## Verification on Mac

From the extracted project root, copy your previous local `.env`, activate your Python environment and install dependencies if needed. Then:

```bash
cd frontend
npm ci
npx playwright install chromium
cd ..
bash scripts/verify_site_theme.sh
node start.mjs
```

Expected manual checks: theme switcher works on `/dashboard/`, `/docs/`, `/gallery/`, `/pricing/`; your preference survives a refresh and follows you from docs to gallery. Verify no text becomes unreadable in either mode. Confirm Google/GitHub sign-in and RAG flows as before.

The public landing and OAuth pages remain dark by design as a branded cinematic surface. Other pages support optional light mode.
