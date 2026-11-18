#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/test_tasks2_9_integration.py
cd frontend
echo 'RepoLens Tasks 2–9: unit, integration, and test-first regressions'
node --test tests/*.test.mjs
echo 'Frontend production build'
npm run build
echo 'New browser acceptance tests'
npx playwright test e2e/tasks2_9_workspace.spec.js e2e/phase10_gallery.spec.js
