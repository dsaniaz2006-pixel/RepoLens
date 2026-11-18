# RAG quota-wait update

The screenshot shows the local limiter, not a confirmed Gemini 429 error. Your uploaded configuration allows 30 requests and 15,000 conservative estimated tokens per minute. The saved embedding database contains 30 vectors and two recent reservations totaling 14,551 estimated tokens. Those reservations normally expire after 60 seconds. The archive does not include evidence that proves why the running browser showed the same message for 30 minutes; the existing backend has a 15-minute cooperative job timeout and frontend has a 16-minute polling limit.

Changes:
- Show current local request/token usage, time until enough budget is released, and elapsed wait.
- Stop one continuously blocked local reservation after 90 seconds with a useful retry message.
- Detect future-dated quota records, which can otherwise extend waits after a clock change.
- Show cached chunk counts and distinguish sending a provider request from local waiting.
- Preserve local limiter errors rather than replacing them with a generic API-key/quota error.
- Preserve all completed cached vectors; no quota increase or cache reset.

## Apply to your existing project
1. Click Cancel indexing, then stop RepoLens with Ctrl+C in its terminal.
2. Extract this ZIP separately.
3. Copy these two files into the matching folders of your existing RepoLens 3 directory, replacing the originals:
   - backend/rag/embedding_cache.py
   - backend/rag/embeddings.py
4. Keep your existing .env, virtual environment and .repolens_cache directory.
5. From your existing project root, run `node start.mjs` and refresh the browser.
6. Click Build / Refresh RAG Index once. Already cached embeddings will be reused when their model/task/content matches.

No dependency reinstall or frontend rebuild is required for this backend-only patch. Do not raise your quota settings without checking your actual provider allowance. This update improves bounded waiting and diagnosis; it does not increase provider quota or prove that a live indexing run will complete. No live API call was made with your credentials.

Validation: 276 Python tests passed; one unconfigured PostgreSQL test skipped. Six new regression tests cover local quota recovery, future timestamps, contention timeout, cancellation, user-facing errors, and cache preservation.
