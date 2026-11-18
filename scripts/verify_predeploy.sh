#!/usr/bin/env bash
# Pre-deployment verification. Run only in a disposable source checkout.
# No production database, OAuth provider or external model is required.
set -uo pipefail
cd "$(dirname "$0")/.."

# Tests launch their own isolated web servers.
if command -v lsof >/dev/null 2>&1; then
  occupied="$(lsof -nP -iTCP:8000 -iTCP:5173 -iTCP:5175 -sTCP:LISTEN 2>/dev/null || true)"

  if [[ -n "$occupied" ]]; then
    echo 'BLOCKED: Ports 8000, 5173 or 5175 already have listeners.'
    echo 'Stop the previous server with Ctrl+C.'
    printf '%s\n' "$occupied"
    exit 2
  fi
fi

scratch="$(mktemp -d "${TMPDIR:-/tmp}/repolens-predeploy.XXXXXX")" || exit 1
trap 'rm -rf "$scratch"' EXIT
# Keep tests away from a developer's live PostgreSQL/Neon account.
if [[ -n "${REPOLENS_TEST_POSTGRES_URL:-}" ]]; then
  echo 'INFO: Skipping any live PostgreSQL test URL; use a disposable branch in a separate run.'
fi
# An explicit empty value also blocks python-dotenv from loading a live test
# database URL from a copied .env file (load_dotenv uses override=False).
export REPOLENS_TEST_POSTGRES_URL=''
export REPOLENS_AUTH_DIR="$scratch/auth"
export REPOLENS_REPORT_DIR="$scratch/reports"
export REPOLENS_INDEX_JOBS_DB="$scratch/index_jobs.sqlite3"
export REPOLENS_EMBED_CACHE_DIR="$scratch/embeddings"
export REPOLENS_AUTH_DATABASE_URL="sqlite:///$scratch/auth.sqlite3"
export REPOLENS_DATABASE_URL="sqlite:///$scratch/app.sqlite3"
export REPOLENS_MIGRATION_TARGET_URL="sqlite:///$scratch/migrate.sqlite3"

failures=0
run_gate() {
  local label="$1"; shift
  echo
  printf '\n========== %s ==========\n' "$label"
  if "$@"; then
    echo "PASS: $label"
  else
    echo "FAIL/BLOCKED: $label (see command output above)"
    failures=$((failures + 1))
  fi
}
run_frontend() { (cd frontend && "$@"); }

run_gate 'A1 — backend unit tests' python -m pytest -q tests/test_file_selector.py tests/test_github_client.py tests/test_analyzer.py tests/test_retrieval_fix.py tests/test_public_gallery_route_tdd.py
run_gate 'A2 — frontend unit tests' run_frontend npm test
run_gate 'B — offline integration tests' python -m pytest -q tests/test_offline_end_to_end.py tests/test_section9_public_routes.py tests/test_refactor_api_boundary.py
run_gate 'D — test-driven core regressions' python -m pytest -q tests/test_predeploy_rag_tdd.py
# The backend serves built public pages through frontend/dist; build before the full-suite route assertions.
run_gate 'Frontend production build' run_frontend npm run build
# Full-suite skips must not be mislabeled as approval. Keep this log in the
# disposable directory; test output can contain local paths or error traces.
full_log="$scratch/full_python.log"
echo
printf '\n========== Full Python regression suite ==========\n'
if python -m pytest -q -rs > "$full_log" 2>&1; then
  cat "$full_log"
  if grep -Eq '(^|[[:space:]])[1-9][0-9]* skipped' "$full_log"; then
    echo 'BLOCKED: Full Python regression suite contains skipped tests; review the missing external gates.'
    failures=$((failures + 1))
  else
    echo 'PASS: Full Python regression suite'
  fi
else
  cat "$full_log"
  echo 'FAIL/BLOCKED: Full Python regression suite (see error details above)'
  failures=$((failures + 1))
fi
run_gate 'C1 — isolated browser UI end-to-end tests' run_frontend npm run test:browser
# Unlike UI-mocked tests this spins up a real loopback FastAPI process with
# disposable SQLite URLs and a local HTTPS Vite proxy. A trusted mkcert cert
# must already be installed. Do not reuse an existing production web server.
run_gate 'C2 — real local HTTPS browser end-to-end tests' node scripts/verify_local_https_browser.mjs

printf '\nSummary: %d failed or blocked gates.\n' "$failures"
if (( failures )); then
  echo 'DEPLOYMENT NOT APPROVED. Resolve failures/skips and rerun using a disposable test environment.'
  exit 1
fi
echo 'Automated gates passed. Still verify real OAuth, external provider quota, production TLS and deployment configuration separately.'
