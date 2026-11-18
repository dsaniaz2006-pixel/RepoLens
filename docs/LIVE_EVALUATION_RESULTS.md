> Historical evidence. References below to reports/evaluation, raw generations, adjacent *.evidence.json and reviewed-analysis files are not included in this source release. Do not treat them as available verification. Current evidence is in evaluation/CACHED_RETRIEVAL_2026_10_25.json and evaluation/HTTP_ACCEPTANCE_2026_10_25.json; see RELEASE_2026_10_25.md.

# Live acceptance results — 2026-10-17

The previously pending live report reviews, retrieval measurement, real miss/fix/retest and indexed Q&A have now been exercised. The raw measurements and reviewed report artifacts are included.

## Results

| Check | Result |
|---|---|
| Gemini generation and two-input embedding probes | Passed; models from the guide retained |
| Flask, Axios and MarkupSafe live reports | Three structural passes; all source-reviewed by the assistant with corrections recorded |
| Retrieval baseline | 4/12 questions hit an expected file in the top five (33.3%) |
| Retrieval retest | 11/12 questions hit an expected file in the top five (91.7%) |
| Mean expected-file recall@5 | 33.3% before; 83.3% after |
| Live indexed Q&A | Three source-grounded answers (partial scope noted) plus one unsupported question checked |
| Persisted live Gemini vectors | Reopened and requeried in a fresh process; repeat upserts and repository metadata isolation passed |
| Python suite after code changes | 147 passed |

## Reproducible source revisions and final indexes

| Repository | Revision | Indexed files | Chunks |
|---|---|---:|---:|
| pallets/flask | `d086db856be187255b8ec61ef409357393020f32` | 48 | 478 |
| axios/axios | `326843a3902d73c9f6af9bad7b55e2412566a251` | 60 | 322 |
| pallets/markupsafe | `4e111271b1494995708a9e878a10829b5e10c7ba` | 44 | 86 |

No question labels or expected paths were changed to improve the score. File hit@5 means at least one labeled file appears among five retrieved chunks; recall@5 measures the fraction of labeled files retrieved per question. These are file-level metrics, not proof that every relevant line or claim was retrieved. `reports/rag-retest.json` also retains actual passages, line ranges, distances and overlap with labeled evidence ranges.

## Actual retrieval miss, fix and retest

The baseline missed Flask settings, request context and sessions, all four Axios questions, and the MarkupSafe test question. The Flask baseline index had only eight files and omitted `config.py`, `ctx.py` and `sessions.py`. It reused the report collector's 30,000-character total budget and 8,000-character file prefixes. The failure therefore involved missing/deep source coverage, not merely wording of the questions.

Indexing now has independent bounded limits: 60 files, 120,000 characters per file and 600,000 source characters in total. Safe file downloads use at most four workers and retain deterministic ranking/order, filtering and line numbers. Document embeddings include the repository path. Report generation keeps its original smaller limits. Index format 3 separates the new indexes from the baseline collections.

| # | Repository | Question | Baseline | Retest |
|---|---|---|---|---|
| 1 | pallets/flask | Where are routes registered and dispatched? | Hit | Hit |
| 2 | pallets/flask | How are application settings loaded and overridden? | Miss | Hit |
| 3 | pallets/flask | Where is request context managed? | Miss | Hit |
| 4 | pallets/flask | How are sessions created and saved? | Miss | Hit |
| 5 | axios/axios | Where are request interceptors applied? | Miss | Hit |
| 6 | axios/axios | How are default configuration and per-request configuration merged? | Miss | Hit |
| 7 | axios/axios | How does Axios select a transport adapter? | Miss | Hit |
| 8 | axios/axios | Where is a request cancellation handled? | Miss | Miss |
| 9 | pallets/markupsafe | Which function escapes unsafe strings for HTML? | Hit | Hit |
| 10 | pallets/markupsafe | How does the Markup type preserve safe markup? | Hit | Hit |
| 11 | pallets/markupsafe | How is the __html__ protocol handled? | Hit | Hit |
| 12 | pallets/markupsafe | Which tests verify escaping and concatenation? | Miss | Hit |

This is a fixed 12-question development evaluation, not an unseen generalization benchmark. It records a real provider-backed failure and retest rather than a simulated miss.

## Provider defects found live

The first index attempt failed because Embedding 2 aggregated a list of strings into one vector. Requests now use a separate Content object per input, model-appropriate task prefixes, and bounded groups. The updated probe checks two independent vectors, and regression tests cover count/order handling. The implementation follows the [Gemini embedding documentation](https://ai.google.dev/gemini-api/docs/embeddings).

A broader-index attempt returned HTTP 429 with a short retry delay. Embedding requests now honor short server delays with bounded retries; permission errors and long quota delays are not retried automatically. The successful retest used the same configured model and credentials. SDK verified here: google-genai 2.31.0; Chroma 1.5.9.

## Report review

See `reports/evaluation/REPORT_SOURCE_REVIEW.md`. Adjacent files preserve the raw generated Markdown, exact supplied source snippets, source manifests and reviewed structured analysis. The delivered reports correct the Axios CommonJS mapping/documentation advice and clarify MarkupSafe import-time fallback behavior and test-coverage limits. Flask and Axios request flows remain explicitly unsupported under the small report context; the tool does not invent one. These are assistant source reviews, not independent human sign-off.

## Live Q&A

| Repository | Question | Source review |
|---|---|---|
| pallets/flask | How are sessions created and saved? | Partial answer with citations and uncertainty |
| axios/axios | Where are request interceptors applied? | Answered with source-checked citations |
| pallets/markupsafe | Which function escapes unsafe strings for HTML? | Answered with source-checked citations |
| pallets/markupsafe | What is the verified internal production deployment hostname used by the maintainers? | Insufficient evidence, no citations |

Full answers and retrieved passages are in `reports/qa-evaluation.json`; `reports/QA_SOURCE_REVIEW.md` records the checked claims. The unsupported question is intentionally unanswerable from the indexed repository and must not invent a deployment hostname.

## Rerun from the project root

Keep your local `.env` in the project root (alongside requirements.txt); it is excluded from the shared ZIP. Activate your existing project environment and install the updated requirements, then run:

```bash
python scripts/check_models.py --live --probe
python scripts/evaluate_repositories.py --live
python scripts/restore_evaluation_indexes.py
python scripts/evaluate_rag.py --live --build-indexes --resume --batch-queries --output reports/rag-retest.json
python scripts/evaluate_qa.py --live
python scripts/verify_live_persistence.py
```

Live commands consume provider quota. Regenerated reports need a fresh source review; they do not automatically inherit the review included here. Rebuild older indexes because index format 3 and embedding instructions changed. Working binary stores are excluded from the ZIP. Portable completed checkpoints for all three repositories and the raw evaluation evidence are included; restore them before reusing the recorded indexes.

## Retrieval crowding and the remaining miss

Expanded source coverage alone reached 10/12 hit@5 and 75.0% mean expected-file recall@5 (`reports/rag-expanded-coverage.json`). The interceptor question returned five README passages, leaving its labeled implementation outside the window.

Retrieval now requests up to 25 semantic candidates for a five-passage answer and selects at most two passages per file on its first pass, filling unused slots from the original ranking when too few distinct files exist. This general file-diversity policy increased the same unchanged evaluation to 11/12 hit@5 and 83.3% mean expected-file recall@5. Question embeddings were generated with the same configured model and query instructions; the batch option checkpoints them for repeatable policy comparisons.

The remaining strict miss is Axios request cancellation. Its five selected passages contain `lib/cancel/CancelToken.js`, `lib/cancel/isCancel.js`, `README.md` and `lib/cancel/CanceledError.js`; they do not include the gold label `lib/core/dispatchRequest.js`. That dispatcher is present among the larger semantic candidate pool but outside the selected five. No label was broadened to turn this miss into a hit. This is a recorded quality limit, not an unmeasured or skipped test.

## Citation scope

Live source review found model-selected subranges that were narrower than their surrounding claims. Production Q&A now validates each proposed range, expands it only to its complete supplied passage, and deduplicates citations. It never expands into source absent from the retrieved evidence. Raw first-pass answers are retained under `reports/history/`; the final answers and full passage citations were source-checked. Long-line fragments still represent only the supplied text, not an unseen remainder of the original line.

The earlier daily-quota interruption is historical. It was resolved in the resumed live run; full results are now measured. Portable checkpoint exports contain 886 actual embedded chunks across the three repositories and were restored and queried in a fresh process without new model calls.

The twelve provider-generated query vectors and their question ordering are retained in `evaluation/query-embeddings.json.gz` for audit. This is separate from the portable document-index checkpoints.
