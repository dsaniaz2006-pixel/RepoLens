# RepoLens — Section 7 Streaming & Background Jobs: Mac Verification

## Install without touching the working Section 6 project

1. Back up your Section 6 folder. Keep your Neon recovery branch available.
2. Extract this ZIP into a new folder named `RepoLens 7` under Downloads.
3. Copy only your private `.env` from the working Section 6 project into the root of `RepoLens 7`. Do not upload `.env` or paste tokens into chat.
4. From the VS Code terminal:

```bash
cd "$HOME/Downloads/RepoLens 7"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
npm test
npx playwright install chromium
npm run test:browser -- e2e/section7_streaming.spec.js
cd ..
python -m backend.database.schema_migrations verify
python -m pytest -q tests/test_section7_streaming.py tests/test_release_workflows.py tests/test_index_jobs.py
```

Database versions should remain `auth_0004` and `app_0002` (both up to date). No Section 7 migration is needed.

## Start from zero and resolve old servers

Stop earlier RepoLens servers via Ctrl+C in their terminals. Inspect the ports:

```bash
lsof -nP -iTCP:8000 -iTCP:5173 -sTCP:LISTEN
```

For each PID, inspect with `ps -p PID -o pid=,command=` and stop only an old RepoLens process using `kill -15 PID`. Don't terminate unrelated services. Then:

```bash
cd "$HOME/Downloads/RepoLens 7"
source .venv/bin/activate
node start.mjs
```

Open `http://127.0.0.1:5173/dashboard/`. Sign in; select Analyze Repo; enter `https://github.com/pallets/flask`; click **Analyze Repository**. You should see GitHub fetch, source selection, Gemini analysis, report-saving and code-flow stages update without waiting for a single blocking response. The analysis report should render at completion and appear in Past Analyses after refreshing. A report can take time because external Gemini/GitHub calls remain blocking inside the worker thread.

**Quota warning:** Section 4 charges the `/api/analyze/stream` request one analysis allowance; if Free-plan quota is exhausted, the UI shows the existing 429 message. Do not change production quotas to force testing.

## Run manual network verification

In Chrome DevTools > Network > Fetch/XHR, inspect `/api/analyze/stream`. The response should have `text/event-stream`, `Cache-Control: no-cache, no-transform`, and messages of the form `data: {"status":"progress",...}` followed by `data: {"status":"done","result":...}`. API errors sent after streaming begins are `status:error` events. HTTP 401/429/422/503 responses are ordinary JSON and are shown as errors in the UI.

Use **Stop waiting** to disconnect and verify it returns control to the interface. If a Gemini HTTP request has already started, it may continue until its next progress boundary; disconnection is cooperative, not an instant termination of remote computation.

## Freshness worker verification

The existing worker is preserved (not replaced by APScheduler): it polls every 300 seconds, checks tracked repositories after 6 hours, retries errors sooner, and uses a persistent lease to prevent overlapping workers. Test without accessing your production data:

```bash
python -m pytest -q tests/test_release_workflows.py tests/test_product_upgrade.py -k 'freshness or worker or lease'
```

In the real website, open Knowledge Hub > Freshness for an indexed tracked repository, verify the checked/stale status, restart the backend and verify the status persists. `REPOLENS_FRESHNESS_SCHEDULER=internal` enables the worker (default). If set to an external scheduler, internal background checking is deliberately disabled.

## Outstanding final checks

Live Gemini/GitHub streaming, real OAuth, your online Neon deployment, and the browser E2E suite must be verified on your Mac. Never run destructive tests against your production Neon branch. Existing `/api/analyze` remains available for older clients, while RAG indexing continues using its established job/status polling APIs.
