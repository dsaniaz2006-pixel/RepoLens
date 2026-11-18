#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo '1/4: Unit tests for HTTPS launcher and certificate validation'
node --test frontend/tests/local_https.test.mjs frontend/tests/launcher.test.mjs
echo '2/4: Existing frontend regression suite (includes test-first HTTPS tests)'
(cd frontend && npm test)
echo '3/4: Frontend production build'
(cd frontend && npm run build)
echo '4/4: Full browser HTTPS smoke (starts server if ports free)'
(cd frontend && npx playwright test --config=playwright.https.config.js)
echo 'HTTPS test runner completed. OAuth provider-console setup and live auth still require manual checking.'
