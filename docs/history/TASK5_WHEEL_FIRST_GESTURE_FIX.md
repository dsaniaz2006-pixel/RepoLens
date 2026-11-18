> Historical documentation only. The current wheel-navigation feature has been removed in RepoLens 21; see `CALM_MOTION_UPDATE.md`.

# RepoLens Task 5 — First-Wheel Navigation Fix

## Bug
`useWorkspaceWheelNavigation` previously initialized `lastChange` to zero. Because `performance.now()` is measured from the page's navigation start, the first wheel gesture could arrive before 550 ms and incorrectly be throttled even though no prior workspace change had occurred. This caused the browser E2E test to stay on Home instead of navigating to Knowledge Hub.

## Fix
- Start the cooldown with no previous transition (`null`).
- Use a pure `canChangeWorkspaceOnWheel` helper that always permits the first gesture, and enforces the 550 ms limit only after an actual transition.
- Add two Node regression checks covering immediate first gestures and subsequent throttling.
- Keep scroll-edge detection and nested report/form scrolling unchanged.

## Tests available in this build
- `cd frontend && npm test`: 81 passing Node tests.
- `python3 scripts/test_tasks2_9_integration.py`: 5 passing integration checks.
- JavaScript syntax checks: passed.
- **Playwright browser E2E:** not run here; execute on the user's Mac.

## Mac verification
From the existing RepoLens project root (not `frontend`):

```bash
cd frontend
npm test
npx playwright test e2e/tasks2_9_workspace.spec.js -g 'Task 5:'
npx playwright test e2e/tasks2_9_workspace.spec.js e2e/phase10_gallery.spec.js
cd ..
```

Expected Task 5 outcome: the first wheel gesture at the bottom of Home displays Knowledge Hub, with Home unmounted.
