# RepoLens — UI Tasks 1–9 handoff (14 November 2026)

This release builds on the previously delivered **Task 1 white-edge fix** in `RepoLens_Task1_White_Line_Fixed_2026-11-14.zip`. Tasks 2–9 were implemented in sequence, without changing FastAPI, database migrations, API contracts, RAG logic, or OAuth endpoints.

| Task | Implementation | Where to verify |
| --- | --- | --- |
| 1 | Preserved graphite document background and overscroll guard | Overscroll top/bottom of dashboard |
| 2 | Knowledge Hub capsule tabs and blue-glass grouped action buttons | Dashboard → Knowledge Hub, each tab |
| 3 | Settings overview: hero, AI/GitHub/credential cards, provider status and privacy notice | Dashboard → Settings |
| 4 | Public Gallery integrated into dashboard shell; 20 published catalog entries dynamically read from actual `/gallery/` page; report preview inside sandboxed iframe; shareable link. Standalone `/gallery/` remains public | Dashboard → Public Gallery; inspect a repository |
| 5 | At a document-edge wheel gesture, switch *one distinct view at a time*, starting Home → Knowledge Hub; regular scrolling within long content stays native. Transition animation targets 30 ms; actual rendering latency depends on device/browser. | Scroll to end of Home and scroll down once; back up at start |
| 6 | One gently animated waterline moving between sidebar items and light liquid-style ripple/reflection on ordinary buttons; lightweight CSS fallback rather than a WebGL shader per button | Click sidebar, buttons, tab actions |
| 7 | Recoloured `/favicon.svg` to navy and light blue | Sidebar, tab icon, public pages |
| 8 | Authenticated, non-blocking particle-canvas welcome screen shown once per session | Sign in or clear session storage and reload |
| 9 | Blur/slide text reveals in workspace and public pages; appears on entering sections; supports reduced-motion | Navigate between pages and scroll through headings |

## Published gallery caveat

The current 20 gallery entries are **source snapshots** with AI review pending, *not* 20 approved AI architecture reports. The UI reflects the actual publication state; no reports are automatically approved.

## Testing record

- **Test-first regressions:** 8 new Node tests initially red, then 8/8 green.
- **Full frontend Node suite:** 76/76 green.
- **Static integration:** 5/5 checks green (gallery links exist, public scripts/styles published, auth pages and HTTPS launcher preserved, separate-view scroll contract).
- **Browser E2E:** 6+ new cases and updated gallery tests included; **not run in this environment**, because install of required npm/Vite/Playwright packages failed.
- **Production Vite build:** not verified here for the same dependency reason.
- **Live OAuth, Neon, GitHub/Gemini, and real HTTPS:** not touched; require testing on your Mac with existing private credentials and certificate.

## Run on Mac

1. Extract the new ZIP as `~/Downloads/RepoLens 18`.
2. Open `~/Downloads/RepoLens 18/RepoLens` (the directory with `start.mjs`).
3. Copy your prior private `.env` file. Do **not** publish it or put provider secrets into frontend files.
4. If `.venv` is missing, `python3 -m venv .venv && source .venv/bin/activate && python -m pip install -r requirements.txt`.
5. `cd frontend && npm ci && npx playwright install chromium && cd ..`.
6. `bash scripts/verify_tasks2_9.sh` (includes the build and targeted E2E tests).
7. If trusted local certificate files are absent, run `node scripts/setup_local_https.mjs`. Check your Google/GitHub OAuth authorized redirect URIs still match.
8. Stop any old RepoLens process on ports 8000/5173 and run `node start.mjs --https`.
9. Open `https://127.0.0.1:5173/dashboard/` and manually validate each page.

The ZIP intentionally excludes private `.env`, TLS private key, `.venv`, `node_modules`, local ChromaDB indexes, databases, and caches.
