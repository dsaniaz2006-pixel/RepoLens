#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"
node --check src/hooks/useTextReveal.js
node --check public/site/reveal.js
npm test
npm run build
npx playwright test e2e/tasks2_9_workspace.spec.js e2e/phase10_gallery.spec.js
