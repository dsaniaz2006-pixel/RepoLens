# RepoLens — faster RAG indexing (November 2026)

## What changed

The **default** indexing profile is now `quick`: up to 24 selected files, up to
35,000 characters per file, and a total source budget of 90,000 characters.
The former coverage is available as `full` (60 files / 120,000 per file /
600,000 total). An intermediate `balanced` setting indexes 40 files and
250,000 total characters. File selection and secret filters are unchanged.

The default *local* Gemini limiter still uses 10 requests/minute and 20,000
estimated tokens/minute unless your `.env` overrides them. Previously it
charged **one token per UTF-8 byte** and made small request groups. It now
estimates tokens heuristically from about two UTF-8 bytes per token, gives
room for request framing, and can batch up to 32 unique chunks. These are
only estimates — Gemini server-side quotas, daily limits, and HTTP 429s
remain authoritative. Do not inflate RPM/TPM beyond the limits shown for
your Google project.

The embedding cache now reads and saves vectors in SQLite batches. Completed
indexes are detected by commit SHA and settings, so repeating Build / Refresh
on an unchanged commit reuses the already-completed index without another
source fetch or embedding request. **Quick, balanced, and full indexes use
separate ChromaDB collections** to avoid mixing source coverage. Your older
indexes and embedding caches are not deleted; switching profiles will need
one initial index build for the selected profile.

## On your Mac

1. Extract the new project ZIP into a new folder. Keep your original as a
   backup; copy only your existing `.env` and *backed-up* runtime databases
   into the new project if you need to retain them. Never paste keys in chat.
2. Create `.venv` if missing and install `requirements.txt`, install
   frontend dependencies with `npm ci`, and use `node start.mjs` from the root.
3. From the RepoLens project root, run:

   ```bash
   source .venv/bin/activate
   python scripts/rag_speed_preflight.py
   ```

4. The default is `quick` even if the `.env` has no profile entry. To select
   more coverage, add ONE of these lines to the project's root `.env`:

   ```dotenv
   REPOLENS_RAG_INDEX_PROFILE=quick
   # or: REPOLENS_RAG_INDEX_PROFILE=balanced
   # or: REPOLENS_RAG_INDEX_PROFILE=full
   ```

   Restart the backend after editing `.env`. Use only one active value, not
   multiple conflicting copies of the variable.

5. Open **Conversations**, index `https://github.com/pallets/flask` and check
   progress. The completed response identifies the selected profile. Click
   Build / Refresh again with **no new commits**: it should reuse the index.
6. Check citations and try a follow-up. Quick mode has **limited source
   coverage**. If an important file/function is missing, choose `balanced`
   or `full` and rebuild. All profiles retain source citations for indexed
   files; no unsupported answer should be presented as verified.

## Diagnosing a slow build

- **Downloading source files:** network/GitHub response speed; optional
  `GITHUB_TOKEN` is useful if GitHub's anonymous rate limit is a problem.
- **Local embedding budget waiting:** the local limit is active, even if
  Gemini has not sent an HTTP 429. Check your actual project quota before
  changing `REPOLENS_EMBED_RPM` or `REPOLENS_EMBED_TPM`.
- **Gemini HTTP 429:** server-side limit; the code retries transient failures,
  stops on known daily exhaustion or long retry delays, and retains cached
  vectors. Increasing the local limits cannot solve this.
- **Rebuilding the same commit:** ensure the same `REPOLENS_RAG_INDEX_PROFILE`,
  `.repolens_chroma`, and completed-index metadata are retained. A profile
  switch intentionally creates a new index.
- **Repeated retries after moving ZIPs:** preserve `.repolens_cache`
  (backed up before moving) so previously embedded chunks are reused.

## Verification status

The fast indexing code has offline regression tests in
`tests/test_fast_indexing.py`, including profile isolation, cache batching,
conservative token estimates, current-commit reuse, and private-repo denial.
The full frontend/browser suite and live Gemini indexing require your local
Mac environment and account and must be verified before claiming a measured
performance improvement. There is no guaranteed build duration, because
first-time runtime depends on repository size, GitHub latency, Gemini quota,
and network availability.
