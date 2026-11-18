> Historical document from an earlier build. See COMPLETION_REPORT.md for current implementation and verification status.

# Repeated-answer retrieval fix

## Apply without reinstalling

1. Stop the running project with Ctrl+C.
2. Back up these four files in your existing project, then replace them with the
   versions from this ZIP: retriever.py, rag_store.py, conversations.py, qa.py.
3. Keep your existing .env, .venv, node_modules, auth directory, and vector index.
4. Restart using your usual `node start.mjs` command.
5. Open Conversations and click New chat. Ask the routing question below.

No dependency installation, frontend rebuild, or re-index is required for this patch.
Previously saved answers remain unchanged; ask again to generate a fresh answer.

## Findings and changes

The uploaded Chroma index is marked complete and contains 478 nonempty chunks.
It includes src/flask/sansio/app.py and add_url_rule beginning in the chunk at
line 597. The missing answer is not explained by an empty saved index.

The original retriever used only vector similarity, with a two-chunk-per-file
limit even when the question explicitly named that file. It also combined every
question with the previous three questions, including unrelated topics.

This patch combines semantic ranking with BM25-style lexical ranking over the
same revision's stored chunks. Exact file paths receive priority and can occupy
the evidence window. Standalone questions do not inherit earlier questions;
pronoun-based follow-ups include the most recent user question. Citation checks
remain in place: missing citations never become an unsupported factual answer.

The UI now receives distinct explanations for no passages versus passages that
failed to produce a cited answer. The latter lists the retrieved files. These
messages diagnose failure; they are not successful answers.

## Verification and limits

202 Python tests passed. A test against the real uploaded Flask index forced a
semantic miss (README only); lexical retrieval recovered the add_url_rule source
chunk in the five-passage evidence window. This verifies local evidence recovery,
not a live Gemini-generated answer or semantic embedding quality.

Automatic approval review blocked the live Gemini probe because it would send
repository evidence to Google using the supplied credential. No successful live
Gemini test is claimed. The precise cause of the original Gemini abstention is
not confirmed. Browser execution was not performed; this patch changes backend
Python only. Large indexes over 20,000 chunks are explicitly rejected by the
bounded lexical scan instead of being silently truncated.

Retest question:
How does Flask implement URL routing in src/flask/sansio/app.py? Identify the
relevant methods and cite the source code.

Then ask:
What calls it, and how is the endpoint registered?

Verify each cited source range. A file missing from retrieved passages is not
proof that the file is absent from the repository.

The full source ZIP excludes credentials, account/session data, environments,
and vector databases. Apply the four-file patch above to retain your local setup.
