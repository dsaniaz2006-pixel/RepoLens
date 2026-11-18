# RepoLens 4 — Two-stage diagnosis and repair report

Date: 10 November 2026  
Scope: Python backend, RAG embedding checkpoint path, source-flow extraction, frontend unit suite, and relevant integration paths.

## Execution model

The requested two subagent responsibilities were executed as two **sequential, independently reported workstreams**: Stage 1 diagnosed and handed off specific file-level failures; Stage 2 changed only the confirmed files, added regression tests, and reran checks. **No separate autonomous AI subagents were available** in this session. Every pass/fail number below comes from an actual test execution, not a claimed delegation.

## Stage 1: diagnosis/handoff

Full findings, failure-to-file mapping, and repair specifications: `docs/SUBAGENT_1_HANDOFF.md`.

| Source | Before | Root cause |
|---|---|---|
| `backend/services/flow_symbols.py` | 6 Python test failures in this Linux environment | Unconditional native parser import. Three Python-only failures were avoidable in source; three JS/TS/Go cases require actual packages. |
| `backend/rag/embeddings.py` | 3 new regression checks failed (TDD red) | Invalid/non-finite vectors, inconsistent dimensions, and corrupted checkpoint data were accepted. |
| Browser Playwright | 5 existing specs blocked in earlier audit | Browser policy rejected all initial navigation (`ERR_BLOCKED_BY_ADMINISTRATOR`), not proven application defects. |

## Stage 2: completed code repairs

1. **`backend/services/flow_symbols.py`** — Detects relevant JS/TS/Go files before importing Tree-sitter, loads only grammars actually needed, and annotates unsupported parsing as `unresolved` if a dependency is absent. Python-only flow, report generation, and flow tests now run without unrelated native modules. The original grammar extraction logic is preserved for correctly configured environments.
2. **`backend/rag/embeddings.py`** — Reuses the existing finite-vector validator; checks vector lengths and dimensions in checkpoints, across provider batches, and before persisting to disk. Invalid provider responses raise `EmbeddingError` while valid partial batches remain resumable.
3. **`tests/test_flow_without_native_parser.py`** — Adds two regression cases: confirmed Python-only flow and honest missing-parser diagnostics.
4. **`tests/test_tdd_embedding_vectors.py`** — Adds five regression cases: nonfinite vectors, mixed dimensions, checkpoint corruption, dimension changes between batches, and checkpoint reuse without provider calls.

## Recorded validation

| Test command or stage | Original ZIP source | Corrected source |
|---|---:|---:|
| Complete Python pytest suite (no test selection) | 268 passed, 6 failed, 3 skipped | **278 passed, 3 failed, 3 skipped** (three JS/TS/Go cases require missing native parser) |
| Runnable Python suite without the three external-grammar cases | — | **278 passed, 3 skipped, 3 deselected** |
| Frontend Node unit suite | 17 passed | **17 passed** |
| Backend API acceptance smoke checks | 14 passed in previous audit | **14/14 passed again** |
| New embedding regression (red) | 3 failed | **5 passed** |
| New parser-resilience tests | Not present | **2 passed** |
| Python `compileall` | — | **Passed** |

Tests were run with an isolated audit import path containing Authlib/JoseRFC Python modules. The system environment did not have usable Linux-native Tree-sitter or ChromaDB wheels. The 14 API checks covered public health/gallery routes, anonymous-route protection, CSRF/origin protection, workspace creation, and cross-user isolation. No live Gemini, GitHub OAuth, provider quota, PostgreSQL server, or real-browser E2E behavior was verified.

**Important: The three remaining JS/TS/Go test failures are not claimed to be fixed.** They assert nonempty graph edges, which require native Tree-sitter parsers. Their Python source test assertions have *not* been disabled or changed. On macOS, install the dependencies listed in `requirements.txt` and run all tests to verify the native extraction path.

## How to use the corrected ZIP on your Mac

1. Extract `RepoLens4_TwoStage_Fixed_Source.zip` as a **new folder**, separate from your original. The original ZIP was not altered.
2. Open Terminal and `cd` into the extracted `RepoLens` folder.
3. Create your environment only once in that new folder: `python3 -m venv .venv`, then `source .venv/bin/activate`.
4. Install backend requirements with `python -m pip install -r requirements.txt` (this includes native Tree-sitter grammars on macOS).
5. Run `python -m pytest -q` from the project root. **Target:** no failures after dependencies are installed; environmental skips may remain.
6. Run `cd frontend && npm ci && npm test && npm run build && npm run test:browser`. Browser tests need a runnable Chromium/Playwright setup (`npx playwright install chromium` if needed).
7. Move back to the project root (`cd ..`), create `.env` from `.env.example` with your chosen local settings, and run `node start.mjs`. Real Gemini/OAuth tests require valid credentials and quota; the test ZIP intentionally does not include `.env` or local databases.

**What was intentionally not changed:** existing tests requiring JS/TS/Go edges, the RAG quota limiter, OAuth behavior, the prebuilt frontend assets, storage schema, and frontend UI. Those were not conclusively shown to be defective by the recorded failures.

## Release verdict

**Improved; not fully verified.** The two confirmed source bugs have passing regression coverage and the runnable Python/frontend test suites pass. Native JS/TS/Go, Chromium browser flows, Chroma/Postgres, and live provider indexing still need proper environment validation before a production sign-off.
