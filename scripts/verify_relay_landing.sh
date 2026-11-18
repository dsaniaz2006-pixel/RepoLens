#!/usr/bin/env bash
# Run from any directory after installing the frontend packages.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT/frontend"
echo '==> Frontend regression & unit tests'
npm test
echo '==> Production frontend build'
npm run build
echo '==> Landing and existing public-site browser E2E'
npx playwright test e2e/relay_landing.spec.js e2e/section9_public_site.spec.js
echo '==> Landing verification passed'
