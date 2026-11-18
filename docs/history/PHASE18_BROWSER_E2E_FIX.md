# RepoLens 18 — browser E2E authentication-loop fix

## Why six browser checks failed

The initial Home dashboard sends `GET /api/usage`. The earlier task-specific
Playwright fixtures intercepted `/api/auth/me` but did not intercept usage and
some other background API reads. With an old or unauthenticated FastAPI server
listening on port 8000, those calls returned HTTP 401. RepoLens correctly
redirects on HTTP 401 to `/login/?reason=expired`. Playwright then saw buttons
become detached, failed to find headings, and timed out after repeated
`/dashboard/` / `/login/` navigation.

## What is fixed

- `frontend/e2e/helpers/mockAuthenticatedWorkspace.mjs` now provides stable,
  explicit, safe responses for all initial GET requests in the affected tests.
- Unexpected requests fail with diagnostic HTTP 501 rather than reaching the
  user's real backend. Tests assert no unexpected requests occurred.
- The five `tasks2_9_workspace.spec.js` tests and authenticated
  `phase10_gallery.spec.js` test share this fixture.
- Production code, actual OAuth/session verification, and the 401 login
  redirect behavior have **not** been changed.
- Added three Node regression tests for the test API isolation.

## Mac verification

From the extracted RepoLens project root:

```bash
cd frontend
npm ci
npx playwright install chromium
node --test tests/*.test.mjs
npm run build
npx playwright test e2e/tasks2_9_workspace.spec.js e2e/phase10_gallery.spec.js
npm run test:browser
```

The first Playwright command targets seven browser scenarios (five Task 2–9
and two Phase 10). A passing result should be **7 passed, 0 failed**.
The full suite may contain further independent failures, which must be
investigated separately. The browser tests run their own port 5175 Vite
instance and do not require external OAuth credentials. They test mocked UI
behavior, not production authentication or provider availability.
