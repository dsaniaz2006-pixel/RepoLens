# RepoLens 4 — corrected source, 10 November 2026

This is a **clean source archive**, not a copy of the original bulky macOS `.venv`/`node_modules` folders. Use it as a separate project folder; reinstall dependencies locally and use your own `.env` based on `.env.example`.

- Read `docs/SUBAGENT_1_HANDOFF.md` for file-level failed-test diagnosis and the handoff.
- Read `docs/TWO_STAGE_DEBUG_REPORT.md` for corrected files, actual test results, and Mac instructions.
- Changed code: `backend/rag/embeddings.py`, `backend/services/flow_symbols.py`.
- Added tests: `tests/test_tdd_embedding_vectors.py`, `tests/test_flow_without_native_parser.py`.
- Current environment: **278 runnable Python passes + 17 frontend unit passes**, while native JS/TS/Go parser tests require macOS dependency installation.
- Original project ZIP remains unchanged.
