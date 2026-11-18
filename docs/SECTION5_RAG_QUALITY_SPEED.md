# Section 5 — RAG answer quality and Quick index speed

This source archive is based on RepoLens Section 5 (2026-11-13). It **does not**
change the Neon database schema or OAuth credentials. It does not delete old
ChromaDB indexes or embedding caches.

## What changed

- **Quick indexing includes source code from anywhere within a long file.**
  Previously the character budget truncated files from the beginning. Now a
  bounded set of actual function declarations and important call sites is
  selected with its original line numbers. Separate excerpts cannot be
  accidentally cited as a continuous source line range.
- **More relevant source paths.** Quick RAG prioritizes route/dispatch/request/
  middleware/auth source while retaining the safe file filter and README.
- **Lower first-build embedding work.** Quick has a 60,000-character collection
  budget instead of the previous 90,000-character effective allowance. Content
  is selected from more files rather than spending the whole allowance on the
  beginning of two or three files. Balanced and Full retain their existing
  budgets. Provider throttling and real network latency still apply.
- **Retrieval improvements.** Natural terms like “routes” and “request handling”
  can match code symbols including `add_url_rule` and `dispatch_request`.
  Cached ChromaDB index text is reused for repeated questions at the same
  immutable repo revision; updating an index invalidates that cache.
- **Follow-up improvements.** References like “the second question” or
  “question 2” resolve actual stored turns. “Question 7” as the user's
  standalone question is **not** mistaken for a reference.
- **Evidence-only fallback.** When Gemini supplies no citations but retrieved
  source shows multiple actual function definitions, RepoLens can provide a
  conservative partial, cited explanation. It labels unproven call-flow edges
  uncertain instead of inventing connections.
- **Build timing details.** Index results now expose `timings_seconds.fetch`,
  `.chunk`, `.embedding` and `.vector_storage`; the main workbench shows build,
  fetch and embedding durations. Do not interpret these as guaranteed targets.

The index format version changes **3 → 4** to prevent mixing old prefix-only
vectors with line-accurate Quick excerpts. This intentionally requires **one
new build** for a repository to benefit from the faster excerpt-based index.
Existing version-3 indexes can still be **read** for old pinned conversations
until the version-4 index is built. Rebuilding the same
repo/revision/settings afterward reuses the completed version-4 index.

## Start from zero on macOS

1. Keep your old working `RepoLens 5` folder untouched.
2. Extract the provided ZIP. Rename the extracted **project root folder**
   (the one containing `start.mjs`) to `RepoLens RAG Fixed` in Downloads.
3. Open that folder in VS Code and run:

```bash
cd "$HOME/Downloads/RepoLens RAG Fixed"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

4. Copy your existing **private** `.env` (do not share or commit it):

```bash
cp "$HOME/Downloads/RepoLens 5/.env" .env
```

5. Optional: reuse local embedding vectors (only if this old directory exists):

```bash
if [ -d "$HOME/Downloads/RepoLens 5/.repolens_cache" ]; then
  cp -R "$HOME/Downloads/RepoLens 5/.repolens_cache" .
fi
```

6. Check `.env` has `REPOLENS_RAG_INDEX_PROFILE=quick` (add it if needed).
   Keep your existing Neon, Gemini, Google/GitHub OAuth variables. Run:

```bash
python -m backend.database.schema_migrations verify
cd frontend
npm ci
npm run build
npm test
npx playwright install chromium
npm run test:browser -- e2e/section5_conversations.spec.js
cd ..
```

Expected migrations: `auth_0004` and `app_0001` with `up_to_date: true`.
No new migration is required by this RAG patch.

7. Make sure old servers are stopped in their respective terminals with
   `Ctrl+C`. Inspect conflicts with:

```bash
lsof -nP -iTCP:8000 -iTCP:5173 -sTCP:LISTEN
```

If a listening PID belongs to a *previous RepoLens server*, inspect it with
`ps -p PID -o pid=,command=` and stop with `kill -15 PID`. Never kill an
unrelated process. Then:

```bash
node start.mjs
```

Open `http://127.0.0.1:5173/dashboard/` (or the exact URL from the launcher).

## Run Section 5 backend and retrieval regression tests

From the project root with `.venv` active:

```bash
python -m pytest -q \
  tests/test_section5_quality_speed_tdd.py \
  tests/test_section5_tdd.py \
  tests/test_section5_api_integration.py \
  tests/test_conversations.py \
  tests/test_retrieval_fix.py \
  tests/test_qa_source_grounding_tdd.py \
  tests/test_fast_indexing.py \
  tests/test_rag_upgrade.py \
  tests/test_github_client.py
```

## Website acceptance

1. Sign in with the existing Google/GitHub account.
2. Go to **Analyze Repo**, analyze `https://github.com/pallets/flask` if
   necessary to activate the workbench.
3. Open **Conversations** and **Build / Refresh RAG Index**. This is the first
   version-4 build, not a reuse of the previous version-3 index. Avoid
   repeated clicks: Section 4 has daily indexing quotas.
4. Record **build time** and, when shown, **fetch and embedding durations**.
   The old report was 314 s; actual new results depend on provider limits.
5. Start a new conversation and ask these three questions in order:

   - Where does Flask register routes, and which functions are involved?
   - How do those functions connect to Flask's request handling?
   - Explain the second question in more detail and cite the relevant files.

6. Verify that the response identifies the functions actually evidenced in
   the indexed source. In Flask, useful passages typically occur in
   `src/flask/sansio/scaffold.py`, `src/flask/sansio/app.py` and
   `src/flask/app.py`. Exact functions/lines depend on the pinned commit.
7. Click citations; they must open the same repository **at the pinned SHA**,
   at the cited original source line ranges. A linked file is not enough: the
   passage should support the adjacent factual claim.
8. Refresh, reopen the conversation, restart the backend and confirm it
   still exists in Neon. Check a follow-up referring to the second question.
9. Test a second signed-in account to ensure it cannot read or delete the
   first account's conversation.
10. For real PostgreSQL concurrency tests, use a **disposable Neon branch**, not
    the production database. See the Section 5 baseline test guide.

## Troubleshooting slow builds

- If **embedding** dominates, check the progress log for HTTP 429, server
  retry delays, quota waits and the selected indexing profile. Do not raise
  provider budgets blindly: actual Gemini quotas vary by account/model.
- If **fetch** dominates, inspect GitHub API availability and token limits.
- If a build says **reused**, it should not send new embedding batches, but
  repository SHA lookups may still require GitHub requests.
- If source evidence is missing, try `REPOLENS_RAG_INDEX_PROFILE=balanced`,
  restart the backend and build again; it costs more indexing resources.
- Do **not** delete `.repolens_cache`, `.repolens_chroma`, old backups or
  Neon data to solve a latency issue.

## Limits of this release verification

Offline tests use local synthetic source and injected AI responses. No live
Gemini, GitHub, Neon or Playwright browser tests were completed in this build
environment. Full acceptance requires the macOS commands above and review of
real source citations. A faster first build is expected, not guaranteed.
