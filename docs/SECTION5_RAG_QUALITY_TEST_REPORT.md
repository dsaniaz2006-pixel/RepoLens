# RAG quality and speed — verification report (2026-11-13)

## Fixed behaviors

- RED→GREEN: new tests first failed on missing excerpt selection, lexical
  relevance, ordinal follow-up, Chroma read cache and safe code-flow fallback.
- New regression checks include lines beyond the old prefix cap, long docstring
  call sites, original line ranges, symbol scoring, cache invalidation, old-index read compatibility, API
  privacy, persistence and a three-question Flask-style uncited-model scenario.
- Model denial fallback generates *only* partial statements backed by exact
  retrieved function definitions and actual calls; uncertain=true for missing
  graph edges. It does not fabricate a complete execution flow.

## Automated results

- Focused Python RAG/conversation test selection: **88 passed**.
- All Python tests except the Authlib OAuth module, using a test-only Authlib
  compatibility stub: **416 passed, 4 failed, 6 skipped**. Four failures match
  inherited earlier issues: three JS/TS/Go code-flow parser expectations and
  one public gallery route test. These are unrelated to modified RAG files.
- Node frontend unit suite: **33 passed, 0 failed**.
- Backend Python modules compiled successfully.
- Browser Playwright E2E: **not run here** (Vite/Playwright missing from offline
  environment); prior user-reported browser pass applies to the earlier ZIP,
  not this new version.
- Actual Gemini/Neon live calls: **not run here** (no user's private tokens or
  live backend connection available).

## Synthetic comparison — not a live speed benchmark

Using sixteen identical mock Python files containing a very large header and
one late `dispatch_request()` function, the previous 90k-character prefix
selection indexed 4 files, 90k source characters and 71 chunks, with the late
function visible in 2 files. The new Quick mode selected 16 files, 6.4k source
characters and 32 chunks, with the late function visible in all 16. The test
illustrates avoiding wasted embeddings on repetitive text; it is *not* a
prediction of real-world speed or coverage for Flask.

## Expected acceptance on Mac

- Real `pallets/flask` RAG build completes using pinned version-4 Quick index.
- Stage timing is visible; compare total with the reported prior 314 seconds.
- Real Gemini answers all three source-grounded follow-ups with cited code.
- Refresh/restart persists messages; second-account isolation passes.
- Re-running targeted pytest and Playwright suites in the user environment
  yields no failures. Any failures must be investigated before sign-off.
