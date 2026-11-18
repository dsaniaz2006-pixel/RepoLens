# Source label review — 2026-10-17

Expected files were selected by reading GitHub source at the commits below. These are assistant-reviewed source labels; independent human review is pending. This is not a Gemini report or a measured retrieval result. File SHA-256 values, exact source URLs and relevant line ranges are in `rag_questions.json`.

| Repository | Reviewed revision |
|---|---|
| pallets/flask | `d086db856be187255b8ec61ef409357393020f32` |
| axios/axios | `326843a3902d73c9f6af9bad7b55e2412566a251` |
| pallets/markupsafe | `4e111271b1494995708a9e878a10829b5e10c7ba` |

| # | Question | Expected evidence files |
|---|---|---|
| 1 | Where are routes registered and dispatched? | `src/flask/sansio/app.py`, `src/flask/app.py` |
| 2 | How are application settings loaded and overridden? | `src/flask/config.py` |
| 3 | Where is request context managed? | `src/flask/ctx.py` |
| 4 | How are sessions created and saved? | `src/flask/sessions.py` |
| 5 | Where are request interceptors applied? | `lib/core/Axios.js` |
| 6 | How are default configuration and per-request configuration merged? | `lib/core/Axios.js`, `lib/core/mergeConfig.js` |
| 7 | How does Axios select a transport adapter? | `lib/core/dispatchRequest.js`, `lib/adapters/adapters.js` |
| 8 | Where is a request cancellation handled? | `lib/core/dispatchRequest.js` |
| 9 | Which function escapes unsafe strings for HTML? | `src/markupsafe/__init__.py` |
| 10 | How does the Markup type preserve safe markup? | `src/markupsafe/__init__.py` |
| 11 | How is the __html__ protocol handled? | `src/markupsafe/__init__.py` |
| 12 | Which tests verify escaping and concatenation? | `tests/test_markupsafe.py` |

For each question, a hit means at least one expected file occurs in the top five retrieved chunks. It does not establish answer correctness or coverage of the relevant lines. Flask dispatch and session implementations occur deep in long files; prefix-only snippets may omit them even if the file itself is indexed. Inspect retrieved text and record actual misses before tuning.

Run `python scripts/evaluate_rag.py --live --build-indexes` after configuring Gemini. The tool builds all three labeled commit revisions, then measures hit@5 and recall@5. Existing branch-tip indexes may use different revisions. Do not replace these SHAs with a new tip without reviewing the labels again.

## Completed live measurement

The unchanged twelve-case labels were evaluated against all three exact revisions: baseline 4/12 hit@5; expanded source coverage 10/12; final file-diverse retrieval 11/12. Mean expected-file recall@5 improved from 33.3% to 83.3%. One cancellation dispatcher-file miss remains; see `../LIVE_EVALUATION_RESULTS.md`.
