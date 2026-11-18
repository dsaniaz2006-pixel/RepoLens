#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo '== 1. Integration (HTTPS, gallery, navigation) =='
python3 scripts/test_tasks2_9_integration.py
echo '== 2. Frontend unit / regression suite =='
cd frontend
npm test
echo '== 3. Vite production build =='
npm run build
echo '== 4. Playwright: native scroll and updated favicon =='
npx playwright test e2e/tasks2_9_workspace.spec.js -g 'Task 5 revised:|Tasks 6-9:|welcome and text reveal'
echo 'Native scroll and calm motion checks finished.'
