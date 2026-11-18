# RepoLens RAG: question relevance, broader retrieval and diagnostics (15 November 2026)

## Diagnosis of repeated answers

A question about how **RepoLens** fetches GitHub commits, selects files, or chunks
source cannot be answered from an index containing only **Flask** source code.
The safe, correct behavior is to abstain. Indexing more Flask files will not
prove how RepoLens works. Ask about Flask functions (`route`, `add_url_rule`,
`dispatch_request`) or index the RepoLens source repository itself.

The old UI repeated a generic message when Gemini returned no citations. That
can also happen for genuinely in-scope questions when the relevant source is
absent from the limited Quick index, retrieval misses it, or Gemini fails to
return a valid citation. We deliberately **do not** attach unsupported
citations or present invented answers.

## Targeted changes

- Default answer retrieval is **8 source chunks** instead of 5, to cover
  multi-file questions without changing stored embeddings.
- `.env` can set `REPOLENS_RAG_TOP_K` between 1 and 12. Larger values increase
  context and provider costs; use 8 initially, 10 if needed. Changing it needs
  a server restart but **does not** require reindexing.
- The answer prompt requests a useful 2–5 sentence, source-supported
  explanation and handles statement-shaped inputs conservatively.
- Failure responses now repeat the actual question and explain the distinction
  between the indexed repository and RepoLens's own implementation. They keep
  the source-evidence restrictions intact.
- `scripts/qa_index_diagnostics.py --probe-retrieval` can inspect the actual
  hybrid top-k results; without the flag diagnostics remain local and do not
  consume embedding quota.

## Correct macOS operation

1. Back up your working RepoLens 27 and copy your existing `.env`. Do not delete
   your persistent `.repolens_chroma` or `.repolens_cache`.
2. Restart after adding `REPOLENS_RAG_TOP_K=8` to `.env`.
3. Use a **new chat** about the Flask repository; saved old messages do not
   change automatically.
4. Ask specific, relevant questions:
   - `Where does Flask define the route decorator? Cite the path and source.`
   - `Which function registers a URL rule? Cite source.`
   - `How does Flask dispatch an incoming HTTP request? Name verified functions.`
   - `Explain the relation between route registration and request dispatch,
      separating proven calls from inferences.`
5. Diagnose the local index (loads public GitHub revision unless `--revision`
   is supplied):

   ```bash
   python scripts/qa_index_diagnostics.py https://github.com/pallets/flask \
     --question 'Which function registers a URL rule?'
   ```

6. If a matching source declaration is absent, set
   `REPOLENS_RAG_INDEX_PROFILE=balanced` (up to 40 files / 250k indexed chars)
   in `.env`, restart, and click **Build / Refresh RAG Index**. A changed
   profile creates its own revision-isolated Chroma collection and requires
   embedding more source; do this only within your actual Gemini quota.
7. To test the live retrieval ranking **after** a successful index build,
   add `--probe-retrieval` to the diagnostic command. This uses one live query
   embedding but **does not** call the answer model.
8. If the right path appears in the retrieved evidence but the answer still
   abstains, the remaining problem is citation generation or evidence
   interpretation; capture a redacted diagnostic and investigate the model
   response. Do **not** remove citation validation to force a response.

## Evaluation scope

The included offline regression tests prove output safety and a wider source
window, not the quality of live Gemini responses. For quality claims, run the
labeled `scripts/evaluate_rag.py` against pinned commits, then separately
score grounded AI answer correctness using independently verified labels.
No live GitHub/Gemini evaluation is claimed here.
