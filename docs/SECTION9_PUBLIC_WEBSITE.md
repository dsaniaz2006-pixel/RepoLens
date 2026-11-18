# Section 9 — Public product website

Section 8 (payments) intentionally omitted by project owner. The site does not integrate Stripe, process payments, or advertise purchasable Pro/Team subscriptions.

## Public pages

| Route | Content | Notes |
|---|---|---|
| `/` | Existing landing / onboarding example | Now links to all five product pages |
| `/docs/` | Install, launch, CLI, API access, troubleshooting | **Slash required:** existing protected FastAPI Swagger remains at `/docs` |
| `/demo/` | Read-only sample linking an existing Flask Markdown report | No Gemini request, quota charge or auth bypass |
| `/examples/` | Clearly labeled reports / snapshots | Gallery currently has 20 source snapshots and zero manually approved AI architecture reports |
| `/pricing/` | Honest account limits (Free) and internal plan explanation | No payment or upgrade action |
| `/blog/` | Engineering notes about commit-pinned evidence and reliability | No fictional release/news claims |
| `/gallery/` | Existing 20-entry gallery | Left intact |

Vite has distinct HTML build entry points in `frontend/vite.config.js`. New pages use the existing palette in `frontend/public/styles.css` plus `frontend/public/product.css`. Page assets reside entirely in the public build output.

## Security and evidence decisions

- Protected dashboard and existing OAuth/session policies are unchanged.
- The existing FastAPI `/docs` endpoint remains authenticated (as covered by older auth tests). Public getting-started docs are at `/docs/` to avoid weakening that protection.
- `/demo/` is an offline sample, not a live anonymous analysis endpoint. No new API endpoints or credentials.
- `/examples/` repeats the gallery's 20 snapshots / 0 reviewed AI architecture report counts. Do not call snapshots reviewed reports.
- `/pricing/` shows actual configured Free limits (5 analyses, 20 asks, 2 indexes per UTC day) and explicitly notes billing is not implemented. Higher internal quota levels are not for sale.
- Run final live OAuth/domain/HTTPS/mobile checks separately before deployment.

## Tests

```bash
# From project root
python -m pytest -q tests/test_section9_public_routes.py
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:browser -- e2e/section9_public_site.spec.js
```

The Python integration tests serve static source files over a local HTTP server (no private credentials). The Node unit suite validates build entrypoints/HTML/content. Playwright tests use the existing Vite test server and verify navigation, read-only demo, and mobile rendering. The project was rendered separately in Chromium from static HTML/CSS in the authoring environment; this is not equivalent to running the full Vite Playwright suite.
