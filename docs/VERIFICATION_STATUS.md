# Current delivery

See [RELEASE_2026_10_25.md](./RELEASE_2026_10_25.md) for the authoritative implementation matrix, current test evidence, and exact remaining live steps.

---

## Historical notes (superseded)

> Historical document from an earlier build. See COMPLETION_REPORT.md for current implementation and verification status.

> Latest workspace repair: see [WORKSPACE_VERIFICATION.md](./WORKSPACE_VERIFICATION.md) for 19 October 2026 results and [WORKSPACE_UPDATE.md](./WORKSPACE_UPDATE.md) for installation.

> Website authentication was added on 2026-10-18. See [AUTH_VERIFICATION.md](./AUTH_VERIFICATION.md) and [AUTH_SETUP.md](./AUTH_SETUP.md) for current authentication checks and live setup requirements. The earlier pipeline evaluation below remains historical evidence.

# Verification status — 2026-10-17

Current results supersede historical setup notes. Detailed evidence and limits are in `LIVE_EVALUATION_RESULTS.md`.

| Check | Result | Evidence / scope |
|---|---|---|
| Python suite | **147 passed** | Latest backend, embedding retry, source coverage and existing regressions |
| Frontend API-client tests | **6 passed previously** | Frontend unchanged in this live-evaluation update |
| Vite build | **Passed previously** | Frontend unchanged |
| Chromium dashboard tests | **3 passed previously** | Real browser, simulated provider responses; frontend unchanged |
| Live model access | **Passed** | `reports/model-access.json`; generation and two-input embedding probes |
| Three live reports | **Generated and source-reviewed** | `reports/evaluation/`; raw generations and reviewed outputs retained |
| Retrieval labels | **12 source-reviewed at exact SHAs** | `evaluation/rag_questions.json`; labels unchanged during tuning |
| Retrieval hit@5 | **4/12 → 11/12** | `reports/rag-baseline.json`, `reports/rag-retest.json` |
| Mean expected-file recall@5 | **33.3% → 83.3%** | File-level recall; retrieved passages included for review |
| Real miss → fix → retest | **Completed** | Broader safe indexing and path-aware document inputs; see question table |
| Live indexed Q&A | **3 source-checked (partial scope noted) + 1 unsupported checked** | `reports/qa-evaluation.json`; assistant source review included |
| Actual Gemini vector persistence | **Passed** | `reports/live-chroma-check.json`; fresh process, vector queries, repeat writes and repo metadata isolation |
| Offline revision isolation | **Passed** | Existing cross-process Chroma checks and current regression suite |

## Changes discovered during live verification

- Separate Content objects prevent Embedding 2 from combining all input chunks into one vector. Task prefixes replace its legacy task_type parameter. Requests are bounded, and short 429 retry delays are honored.
- RAG has independent 60-file / 120,000-character-per-file / 600,000-character-total limits and up to four safe fetch workers. Report prompts retain their smaller budgets.
- Index format 3 requires rebuilding earlier indexes. The shared ZIP omits credentials, dependencies, working caches and binary stores; portable completed checkpoints for the three evaluated repositories are included.
- Evaluation report evidence is saved with exact revision and supplied snippets. Raw generations remain available alongside assistant-reviewed reports.

## Practical limits

This is a fixed, small development evaluation. File hits and valid citations do not independently prove semantic accuracy. The three reported Q&A answers (including any partial answers) and report claims were checked against source; independent human review was not performed. New report generations still require review. Large or truncated repositories can exceed the bounded collector; the GitHub tree fallback remains shallow. The dashboard's previously verified browser tests used simulated API responses; the new live checks exercise the Python provider pipelines.

Credentials from the original user-supplied ZIP were read only into process memory for the authorized live evaluations. Their values are not included in any output.

One strict cancellation-file miss remains in the measured 11/12 result; expected-file recall@5 is 83.3%. See `LIVE_EVALUATION_RESULTS.md` for the exact paths and file-diversity policy. The earlier quota block is resolved. All three checkpoints (886 chunks) passed fresh-process restoration and querying. Q&A citations cover validated complete supplied passages; they are not proof of every future model claim.
