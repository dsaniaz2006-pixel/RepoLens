#!/usr/bin/env bash
# Phase 11 all local suites + evidence, including failures and skipped tests.
# Live OAuth/HTTPS/Gemini/Ollama/20-report gates remain external and BLOCKED.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python scripts/phase11_verify.py --output-dir "${1:-$ROOT/reports/phase11-local-$(date +%Y%m%d-%H%M%S)}"
