> Historical documentation only. The current wheel-navigation feature has been removed in RepoLens 21; see `CALM_MOTION_UPDATE.md`.

# RepoLens 20 — Sequential, smooth workspace scroll + refreshed browser tab icon

## Scope
- Based on the prior RepoLens 19 (Task 5 first-gesture fix). Existing HTTPS,
  OAuth, database, RAG and UI components are unchanged.
- Wheel order **matches the sidebar exactly**: Home -> Analyze Repo ->
  Knowledge Hub -> Conversations -> Past Analyses -> Settings -> Public Gallery.
- Reverse scrolling traverses that order backwards.
- One workspace view is mounted at once, never stacked with the next view.
- On long pages, wheel/touchpad scrolls the current page normally until the
  edge; on its edge an intentional gesture changes views. Nested scroll areas,
  form controls and modifier-key zoom retain normal behavior.
- The new view appears immediately with a 340ms fade-and-slide entrance.
  Motion preferences are respected; fast wheel momentum cannot jump multiple
  pages with a single gesture, and scroll position resets to the top of a new
  page before paint.
- Every HTML entrypoint, including 20 static public reports, uses the
  cache-busted `/favicon-v2.svg?v=20`. The sidebar image matches. Legacy
  `/favicon.svg` and `/favicon.ico` are updated for older browser fallbacks.

## Verify on your Mac
From the project root, after copying `.env`, installing Python requirements,
`cd frontend && npm ci && npx playwright install chromium && cd ..`, run:

```sh
bash scripts/verify_smooth_navigation.sh
```

For a targeted browser test:

```sh
cd frontend
npx playwright test e2e/tasks2_9_workspace.spec.js -g 'Task 5:'
```

Run the existing local HTTPS launcher after checking for occupied ports:

```sh
node scripts/setup_local_https.mjs
node start.mjs --https
```

If Chrome still shows the previous tab icon, do a hard reload (Cmd+Shift+R)
with the new site running and confirm `/favicon-v2.svg?v=20` returns the blue
mark. The new filename bypasses the old favicon cache.

## Verification notes
- Node and Python source tests can run offline; full Vite/Playwright tests
  require the frontend packages installed locally.
- All real logins still require the previously configured matching OAuth
  callback URIs on Google and GitHub.
