#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  echo 'Frontend packages not installed. Run: cd frontend && npm ci' >&2
  exit 1
fi
printf '\n--- Frontend unit tests ---\n'
npm test
printf '\n--- Vite production build ---\n'
npm run build
printf '\n--- Targeted browser tests (serial) ---\n'
./node_modules/.bin/playwright test e2e/phase1_5.spec.js e2e/phase6_10.spec.js --workers=1
printf '\n--- Full browser suite (parallel) ---\n'
./node_modules/.bin/playwright test --workers=5
