#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
printf '\n[1/5] Python syntax and package source\n'
python -m compileall -q backend scripts tests
printf '\n[2/5] Refactor API boundary tests\n'
python -m pytest -q tests/test_refactor_api_boundary.py tests/test_github_client.py tests/test_file_selector.py tests/test_analyzer.py tests/test_url_parser.py
printf '\n[3/5] Frontend Node regression suite\n'
node --test frontend/tests/*.test.mjs tests-js/*.test.mjs
printf '\n[4/5] Offline frontend integration\n'
python scripts/test_tasks2_9_integration.py
printf '\n[5/5] Frontend build\n'
if [ -d frontend/node_modules ] && [ -x frontend/node_modules/.bin/vite ]; then
  (cd frontend && npm run build)
else
  echo 'PENDING: npm run build — install frontend dependencies with cd frontend && npm ci'
fi
printf '\nBrowser E2E remains a separate check: cd frontend && npx playwright test\n'
