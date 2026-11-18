#!/usr/bin/env bash
# Run from anywhere inside the Phase 1–5 source release after installing deps.
# Do not conceal failures or count mocked acceptance as a live-service check.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v python >/dev/null; then
  echo 'Python virtual environment is not activated. Run: source .venv/bin/activate' >&2
  exit 1
fi
python scripts/phase0_preflight.py
python -m pytest -q
node --test tests-js/*.test.mjs
(
  cd frontend
  npm test
  npm run build
  npm run test:browser
)
echo 'Local suites passed. Complete the separate REAL-SERVICE acceptance gates documented in docs/PHASE1_5_HANDOFF.md.'
