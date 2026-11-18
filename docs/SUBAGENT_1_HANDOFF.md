# RepoLens 4 — Stage 1: error-finding handoff

Audit date: 2026-11-10. Input: `RepoLens 4.zip`.

## Original reproducible baseline

- `PYTHONPATH=/mnt/data/repolens_audit_deps:. python -m pytest -q --tb=line`: **268 passed, 6 failed, 3 skipped** (full Linux audit environment with temporary pure-Python Authlib/JoseRFC import path).
- `node --test frontend/tests/*.test.mjs` from `frontend`: **17 passed**.
- Three additional embedding-validation tests, run against unmodified source: **3 failed**. This is the red phase, not a preexisting CI failure.

## Issue A — unconditional native parser import

**File:** `backend/services/flow_symbols.py`, originally lines 4–7.

**Call chain:** `backend/services/pipeline.py` -> `backend/services/code_flow.py:trace` -> `backend/services/flow_symbols.py:extract` -> `from tree_sitter import Language, Parser`.

**Exception:** `ModuleNotFoundError: No module named 'tree_sitter'`.

**Original failures (6):**

1. `tests/test_completion.py::test_python_import_alias_and_method_flow` — Python-only, should not need JavaScript/Go parsers.
2. `tests/test_completion.py::test_non_python_flow_is_explicitly_inferred[main.js…]` — JS parser genuinely required.
3. `tests/test_completion.py::test_non_python_flow_is_explicitly_inferred[main.ts…]` — TS parser genuinely required.
4. `tests/test_completion.py::test_non_python_flow_is_explicitly_inferred[main.go…]` — Go parser genuinely required.
5. `tests/test_offline_end_to_end.py::test_real_pipeline_with_faked_external_boundaries` — Python-only pipeline should not need native parsers.
6. `tests/test_product_upgrade.py::test_flow_marks_cross_file_calls_inferred_and_does_not_execute` — Python-only should not need native parsers.

**Diagnosis:** Source bug: `flow_symbols.extract` imports native parsers before even checking whether JavaScript/TypeScript/Go files are present. Environment problem: Tree-sitter and language grammars are already declared in `requirements.txt` but are missing in this sandbox; this also explains why JS/TS/Go graph assertions cannot be verified here.

**Repair specification:** Do not import native modules for Python-only records; when a non-Python grammar is unavailable, report missing analysis in `unresolved` instead of inventing graph edges. Retain existing AST/Tree-sitter behavior where dependencies are installed; do not weaken existing JS/TS/Go assertions. Do not invent a regex parser as a test workaround.

## Issue B — missing embedding validation

**File:** `backend/rag/embeddings.py` originally around lines 66–101.

**TDD red reproduction:**

1. Invalid vector with NaN accepted as a successful API response.
2. Mixed-dimension vectors accepted even though downstream vector-store ingestion will fail.
3. A corrupted checkpoint vector containing NaN is reused without regeneration.

**Diagnosis:** A validator `valid_vector` already exists in `backend/rag/embedding_cache.py`, but direct/injected-client and checkpoint paths do not consistently apply it.

**Repair specification:** Reuse `valid_vector`; require consistent dimensions in provider batches, checkpoints, and across resumed batches; validate before writing progress. Preserve valid checkpoints and the previous quota/retry logic. Add tests for malformed responses, corrupted checkpoints, resume behavior, and cross-batch dimensions.

## Issue C — external test limits (no source fix justified)

- The Linux sandbox cannot retrieve the missing Tree-sitter packages over the network. These dependencies are already listed in `requirements.txt`; macOS can verify with a fresh local virtual environment and `python -m pip install -r requirements.txt`.
- Chromium E2E testing previously stopped at navigation with `ERR_BLOCKED_BY_ADMINISTRATOR`. Do not falsely attribute this environment-policy block to a frontend component.
- One PostgreSQL and two ChromaDB integration tests are skipped in this sandbox; they need configured services/dependencies.
- The shared `.env` was explicitly described by the owner as fake/test data; it is not the cause of the six Python test failures.

**Handoff to Stage 2:** Modify only the two production-code files named above, add regression tests and documentation, and rerun the full test suite. Clearly distinguish true code repairs from tests that remain dependent on external native packages or services.
