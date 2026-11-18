#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"
echo '[1/3] Unit + theme integration + TDD regressions'
npm test
echo '[2/3] Vite production build'
npm run build
echo '[3/3] Public colour-mode browser E2E'
npx playwright test e2e/site_theme.spec.js
