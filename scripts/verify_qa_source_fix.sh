#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo 'Checking Python source-grounded Q&A regressions'
python -m pytest -q \
  tests/test_qa_source_grounding_tdd.py \
  tests/test_rag_upgrade.py \
  tests/test_retrieval_fix.py \
  tests/test_reliability_regressions.py \
  tests/test_conversations.py
echo 'Checking frontend unit tests'
(cd frontend && npm test)
echo 'Q&A regressions passed. Still verify live Gemini and browser scenarios separately.'
