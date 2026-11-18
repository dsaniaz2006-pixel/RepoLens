#!/usr/bin/env bash
# Run from any directory after installing Python/Node/Playwright dependencies.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! python -c 'import pytest, fastapi, sqlalchemy, authlib, chromadb, google.genai, tree_sitter' >/dev/null 2>&1; then
  echo 'Missing Python dependencies. Activate .venv and run: python -m pip install -r requirements.txt' >&2
  exit 1
fi
if [[ ! -d frontend/node_modules ]]; then
  echo 'Missing frontend packages. Run: (cd frontend && npm ci && npx playwright install chromium)' >&2
  exit 1
fi
printf '\n[1/8] Phase 0 preflight\n'
python scripts/phase0_preflight.py
printf '\n[2/8] Gallery snapshot/review page integrity\n'
python scripts/prebuild_gallery.py
printf '\n[3/8] All Python tests, including Phase 6-10 TDD/integration\n'
python -m pytest -q
printf '\n[4/8] GitHub workflow and comment tests\n'
node --test tests-js/*.test.mjs
printf '\n[5/8] Frontend unit tests\n'
(cd frontend && npm test)
printf '\n[6/8] Frontend production build\n'
(cd frontend && npm run build)
printf '\n[7/8] Browser E2E tests (mocked provider responses)\n'
(cd frontend && npm run test:browser)
printf '\n[8/8] Gallery review/publish status\n'
python scripts/prebuild_gallery.py --status
if [[ "${REPOLENS_VERIFY_OLLAMA:-0}" == "1" ]]; then
  echo 'Live Ollama probe (requires local daemon and models)'
  python scripts/check_ollama.py --live
fi
if [[ "${REPOLENS_VERIFY_GALLERY:-0}" == "1" ]]; then
  echo 'Strict gallery gate: requires 20 reviewed, approved, published AI reports'
  python scripts/prebuild_gallery.py --require-reviewed
fi
printf '\nOffline tests passed. Real GitHub advisory, user-session, local Ollama, and publication acceptance are separate required checks.\n'
