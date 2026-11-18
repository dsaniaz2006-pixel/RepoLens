# React UI, state, and API ownership

RepoLens uses React 18 + Vite and ordinary React hooks; it does **not** require Next.js, shadcn, Redux, or TypeScript migration to keep the current website working.

- `frontend/src/main.jsx` authenticates the user and composes workspace views.
- `frontend/src/features/*/` contains business-specific UI screens; Home is no longer defined inline in `main.jsx`.
- `frontend/src/components/layout/` provides the site theme and welcome sequence.
- `frontend/src/hooks/` contains reusable animation and navigation effects.
- `frontend/src/state/workspaceNavigation.mjs` validates dashboard pages. `useWorkspaceNavigation` keeps the page state inside the workspace and rejects unknown page names.
- `frontend/src/services/apiClient.js` owns cookies, CSRF, timeouts, retries, streaming and request cancellation. `services/errors.mjs` normalizes user-visible HTTP failures. The root `apiClient.js` is a compatibility re-export.
- `frontend/src/lib/motionTiming.mjs` is pure timing logic shared between welcome and reveal hooks.

## Interaction boundaries

Only one workspace view renders at a time. The sidebar controls page changes. Trackpad scrolling stays within the active page and must never automatically switch to the next workspace view. The signed-in Public Gallery uses the dashboard shell; the public gallery stays accessible anonymously.

Avoid global mutable application state unless multiple independent components need the same value. For each feature, prefer local `useState`, a reducer for a complex feature, or an isolated hook. Server responses remain the source of truth for authentication, quotas, history, and workspace membership; do not duplicate those rules in the browser.

A 4.2-second welcome sequence and a 40 ms stagger / 950 ms text reveal remain the active motion settings. Respect `prefers-reduced-motion`, avoid excessive timers/WebGL contexts, and ensure inputs stay usable while text animates.
