#!/usr/bin/env bash
# Offline tests do not replace live generation, reviewer sign-off, or deployment.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
printf '\n[1/5] Phase 10 unit, TDD and HTTP integration tests\n'
python -m pytest -q tests/test_phase10_release_tdd.py tests/test_phase10_integration.py tests/test_phase6_10_tdd.py -k 'phase10 or gallery'
printf '\n[2/5] Regenerate public pages with current validated status\n'
python scripts/prebuild_gallery.py
printf '\n[3/5] Frontend unit tests\n'
(cd frontend && npm test)
printf '\n[4/5] Production build and browser E2E tests\n'
(cd frontend && npm run build && npm run test:browser)
printf '\n[5/5] Actual generation and review status\n'
python scripts/prebuild_gallery.py --status
if [[ "${REPOLENS_REQUIRE_20_AI_REPORTS:-0}" == "1" ]]; then
  python scripts/prebuild_gallery.py --require-reviewed
else
  printf '\nNot claiming a Phase 10 release: set REPOLENS_REQUIRE_20_AI_REPORTS=1 for the strict 20-report gate.\n'
fi
