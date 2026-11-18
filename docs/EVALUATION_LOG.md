> Historical evidence. References below to reports/evaluation, raw generations, adjacent *.evidence.json and reviewed-analysis files are not included in this source release. Do not treat them as available verification. Current evidence is in evaluation/CACHED_RETRIEVAL_2026_10_25.json and evaluation/HTTP_ACCEPTANCE_2026_10_25.json; see RELEASE_2026_10_25.md.

# Evaluation log — 2026-10-17

The previously pending live work is completed for the three evaluation repositories and 12 labeled questions. See `LIVE_EVALUATION_RESULTS.md` for the measured baseline/retest, exact revisions, source review and practical limits; `VERIFICATION_STATUS.md` is the current status.

## Execution sequence

1. Loaded the original user-supplied configuration into process memory, without logging keys or writing a project `.env`.
2. Verified generation access; discovered that the initial single-input embedding probe did not exercise batch cardinality.
3. Live indexing exposed Embedding 2 input aggregation. Changed request structure and prefixes; a two-input live probe passed.
4. Generated Flask, Axios and MarkupSafe reports at the labeled revisions. Preserved first-pass output.
5. Ran the 12-question baseline against the original report-sized index collection limits: 4/12 file hits at five.
6. Expanded only RAG source coverage, included source paths in embedding inputs, and separated its collection namespace with index format 3.
7. Observed a real 429 rate limit on the broader embedding workload. Added bounded short-delay retry handling and regression cases.
8. Regenerated the reports with tighter source-grounding instructions; preserved raw generations and corrected delivered reports after assistant source review.
9. Completed the wider-index retrieval retest, live Q&A, unsupported-question check and fresh-process persistence validation. The actual results are retained under `reports/`.
10. Latest Python suite: 147 passed. Frontend source was unchanged; earlier 6 client tests, production build and 3 simulated-response Chromium tests remain documented as earlier checks.

## Original reliability repairs retained

Oversized chunk lines; malformed JSON objects; Chroma error translation; evaluation .env loading; full request budgeting; overly aggressive source filters; supplied-evidence citation validation; and repository-bound dashboard state were repaired in the preceding update. Those changes and their tests remain in this package.

## Artifact provenance

The original uploaded Flask report and analysis JSON remain historical, with their original generation provenance unverified. The new reviewed reports under `reports/evaluation/` have recorded exact revisions and supplied source snapshots. Earlier claims that no Flask artifact existed were incorrect; neither the old artifact's presence nor structural validation alone proves accuracy.

## Final resumed run

Quota access passed on resumption. Reused Flask's 478 chunks, completed Axios (322) and MarkupSafe (86), and measured every labeled question. Expanded coverage reached 10/12; a real README-crowding failure motivated file-diverse candidate selection, which reached 11/12 with unchanged labels. The cancellation dispatcher-file miss remains explicitly recorded. Full live Q&A covered all three repositories and a fresh unsupported question. Citation ranges were normalized to complete supplied passages after validating their bounds. All 886 vectors were exported, restored to a fresh store, reopened and queried in another process; no embedding requests were used for restoration. Latest Python suite: 147 passed. Historical quota-failure and narrow-citation records remain under `reports/history/`.
