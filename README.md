# RepoLens — source organization update (14 November 2026)

**Pre-deployment browser E2E repair:** [root causes, code changes, and Mac commands](docs/PREDEPLOY_E2E_FIX_2026-11-14.md). This change separates offline UI tests from the real local HTTPS/loopback FastAPI checks. Deployment approval remains pending until all gates pass.

This archive reorganizes code and documentation **without changing** the existing HTTPS, OAuth, database or RAG behavior. The root stays small; UI lives in `frontend/src/features/`, shared React hooks in `frontend/src/hooks/`, and HTTP handling in `frontend/src/services/`. The existing launcher and API URLs remain compatible.

**New developer guides:** [Project structure](docs/PROJECT_STRUCTURE.md) · [API architecture](docs/API_ARCHITECTURE.md) · [Frontend state](docs/FRONTEND_STATE.md) · [Environment](docs/ENVIRONMENT.md) · [Refactor / migration report](docs/REFACTOR_REPORT.md).

After copying your own `.env` and installing dependencies, run `bash scripts/verify_refactor.sh`, then start with `node start.mjs --https`. Local browser checks are still required.

---

> **Phase 11 release candidate (1.1.0-rc.1):** See [Phase 11 operations](./docs/PHASE_11_OPERATIONS.md), [four-test verification guide](./docs/PHASE_11_VERIFICATION.md) and [final release evidence](./docs/FINAL_RELEASE_VERIFICATION.md). Run `bash scripts/verify_phase11.sh` with the project virtual environment activated and frontend dependencies installed. This is **NOT FULLY VERIFIED** for production until live gates and 20 human-reviewed gallery reports pass.

> Updated 25 October 2026: start with [release status and setup](./docs/RELEASE_2026_10_25.md). Live acceptance is incomplete; no production-ready claim.

> **Current release:** read [RELEASE_READINESS.md](./docs/RELEASE_READINESS.md), [START_HERE.md](./docs/START_HERE.md) and [FINISH_SETUP.md](./docs/FINISH_SETUP.md).

> Start with [START_HERE.md](./docs/START_HERE.md) for the in-place update and [UPGRADE_STATUS.md](./docs/UPGRADE_STATUS.md) for the current audit status. Older verification files are historical.

> New in this ZIP: persistent codebase conversations. Read [CHAT_UPGRADE.md](./docs/CHAT_UPGRADE.md) for setup, verification, and remaining live checks.

## Local HTTPS upgrade (14 November 2026)

RepoLens now supports **trusted local HTTPS** for the entire browser-facing
website, API proxy, and OAuth callback flow. Read [LOCAL_HTTPS_SETUP.md](./docs/guides/LOCAL_HTTPS_SETUP.md)
for the Mac setup, mkcert trust installation, provider callback URLs and
verification instructions. Quick commands (after Python/frontend setup):

```bash
brew install mkcert
node scripts/setup_local_https.mjs
node start.mjs --https
```

Visit `https://127.0.0.1:5173/`. The internal FastAPI process remains on the
loopback interface; do not confuse local mkcert TLS with a public deployment.

# RepoLens — AI Codebase Onboarding Assistant

RepoLens helps someone new to a public GitHub repository find the important files, understand a likely code flow, and ask source-grounded questions using Gemini + ChromaDB. It is a Python CLI first; the React/FastAPI dashboard is an optional front-end.

**Verification matters:** See [`VERIFICATION_STATUS.md`](./docs/VERIFICATION_STATUS.md) for the exact distinction between implemented features, passing tests, and completed live checks and their limits. A mocked test is not a verified live run.

**19 October workspace update:** see [WORKSPACE_UPDATE.md](./docs/WORKSPACE_UPDATE.md) for upgrading your existing project and [WORKSPACE_VERIFICATION.md](./docs/WORKSPACE_VERIFICATION.md) for current checks and limits.

## Features currently implemented

- GitHub public repository URL parsing, metadata/tree retrieval, truncated-tree fallback and source filtering.
- Bounded code context, structured Gemini analysis, evidence-path validation, and Markdown reports.
- `--interview` with five source-backed questions and `--contribution` with an unverified first-task candidate.
- RAG indexing with line-preserving chunks, Gemini embeddings, revision-isolated ChromaDB, and cited question answering.
- FastAPI routes for reports/history, downloads, index, ask, interview, and contribution.
- React dashboard for those features; safe client API error handling and a macOS/Windows Node launcher.
- Offline Python, frontend API-client, and report/RAG evaluation tests. Three Chromium dashboard state regressions passed with simulated API responses. Live report/Q&A source reviews and the full twelve-question retrieval results are recorded in `LIVE_EVALUATION_RESULTS.md`.

## Setup

Use Python 3.11+ and Node.js 18+.

**macOS** (from the project root):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend && npm ci && cd ..
```

**Windows PowerShell** (from the project root):

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

Copy `.env.example` to `.env` in the main project folder; fill in your real `GEMINI_API_KEY` and optionally `GITHUB_TOKEN`. Do **not** commit or upload `.env`. The shipped ZIP deliberately contains no credentials.

Start both FastAPI (port 8000) and Vite (port 5173) with **one command** from the project folder on either system:

```bash
node start.mjs
```

For the trusted HTTPS setup, visit `https://127.0.0.1:5173/` for the landing page, `/login/` for the login UI, and `/dashboard/` for the dashboard. The browser-facing API is on the same HTTPS origin at `/api/...`; the FastAPI worker remains on the localhost-only backend port. HTTP-only local development remains available via `node start.mjs --http`.

## CLI

After activating the venv (or substituting its Python path):

```bash
python -m backend.cli.main https://github.com/pallets/flask
python -m backend.cli.main https://github.com/pallets/flask --overwrite
python -m backend.cli.main https://github.com/pallets/flask --interview
python -m backend.cli.main https://github.com/pallets/flask --contribution
python -m backend.cli.main https://github.com/pallets/flask --index
python -m backend.cli.main https://github.com/pallets/flask --ask "Where is routing handled?"
```

Build the index before asking questions. RAG is pinned to the GitHub branch-tip commit, so re-index when it changes. The CLI sends approved public source snippets to Google; use only code you have permission to share and review Google API data-use terms.

## Test and evaluation commands

```bash
python -m pytest -q
cd frontend && npm run test && npm run build && cd ..
python scripts/check_chroma.py
python scripts/check_models.py --live --probe
python scripts/evaluate_repositories.py --live
```

`check_models.py --live --probe` uses a small Gemini generation and embedding request. `evaluate_repositories.py --live` can incur real Gemini API charges; it saves structural audit results for Flask, Axios and the smaller MarkupSafe repo. The audit verifies source-manifest membership and required sections, **not** correctness of architectural explanations. Results record the fetched commit SHA. Review every claim against the corresponding source files, update `EVALUATION_LOG.md` with observed failures and fixes, and rerun.

For RAG evaluation, `evaluation/rag_questions.json` now contains **12 source-reviewed labels at exact commit SHAs**, with source links, evidence lines and hashes. Independent human review was not performed. Build the labeled indexes and measure retrieval with:

```bash
python scripts/evaluate_rag.py --live --build-indexes
```

Both evaluation scripts load the project-root `.env`. They never contact providers without `--live`. The full live retest measured **11/12 hits at five**, improving the original **4/12** baseline. Mean expected-file recall@5 improved from 33.3% to 83.3%. One strict cancellation-file miss remains documented. Index format 3 and completed checkpoints for all three evaluated repositories are included; see `LIVE_EVALUATION_RESULTS.md`.

## Browser regression tests

From `frontend/`, run:

```bash
npx playwright install chromium
npm run test:browser
```

The tests start Vite and simulate API responses. They verify repository selection, clearing stale Q&A and guarding duplicate requests; they do not consume Gemini quota. An existing Chromium can be selected with the `REPOLENS_CHROMIUM_EXECUTABLE` environment variable.

## Architecture

Reports flow through GitHub retrieval, file selection and budgeting, Gemini analysis with source-manifest validation, then Markdown output. RAG splits approved snippets, embeds and stores them in repository/revision/model-specific Chroma collections, retrieves top-k chunks and validates Q&A citations. The optional React/Vite dashboard calls shared Python modules through FastAPI.

## Known limitations

- Only public GitHub repositories are supported in the initial design; rate limits and truncated trees can reduce coverage.
- The report context is limited by `config.py`: 20 files, 8,000 chars per file, 30,000 source chars, 8,000 tree JSON chars, 60,000 prompt chars and 70,000 serialized request chars including schema. Half the source budget is reserved for implementation when implementation files are selected. These are character limits, not tokens. Indexing uses the same selected prefixes and can miss code deep in files.
- Truncated-tree fallback examines root files and immediate selected source directories; it does not recursively recover the whole repository.
- Semantic retrieval can miss exact symbols or fail to prove function-call relationships.
- Production implementation citations must reference source actually included in the prompt; supported flows require at least two nonempty source-backed steps. This does not prove an AI claim or call relationship.
- Gemini model access, quotas, pricing and data treatment depend on your account and current provider terms.
- Latest backend suite: **147 passed**. Three live reports, the complete retrieval baseline/retest, live Q&A for all three repositories, fresh unsupported-question handling and actual-vector restoration/persistence are verified with recorded limits. Earlier frontend checks passed (6 client tests, production build, 3 simulated-response Chromium tests); frontend source is unchanged.
- A saved Flask report is included from the upload. Its generation history, revision and accuracy remain unverified.
- `reports/`, vector indexes and `.env` are local artifacts and ignored by Git.

See [`EVALUATION_LOG.md`](./docs/EVALUATION_LOG.md), [`VERIFICATION_STATUS.md`](./docs/VERIFICATION_STATUS.md), and the original PDF guide for next steps.

## Restore the recorded evaluation indexes

The three portable checkpoints contain public source passages and actual Gemini vectors, without API credentials. Restore them to avoid repeating the recorded embedding work:

```bash
python scripts/restore_evaluation_indexes.py
python scripts/evaluate_rag.py --live --build-indexes --resume --batch-queries --output reports/rag-retest.json
python scripts/evaluate_qa.py --live
python scripts/verify_live_persistence.py
```

A rerun must use the matching revisions and settings. Query vectors are checkpointed by the batch option. New model requests still use provider quota. See `LIVE_EVALUATION_RESULTS.md` for the single remaining strict file-label miss and the source-review scope.

## Website and authentication

- `/`: landing page. **Get started** opens signup; the broken placeholder GitHub CTA has been removed. A real source link appears in the footer when configured in `frontend/site/config.js`.
- `/signup/`: first-time account creation through Google or GitHub.
- `/login/`: returning-user sign-in through either provider.
- `/dashboard/`: authenticated workspace, with sign-out and account-isolated report history.

**Required setup:** follow [AUTH_SETUP.md](./docs/AUTH_SETUP.md) to register both OAuth apps and add their client IDs/secrets to the server environment. Real provider credentials are not included. Without setup, sign-in remains unavailable and the workspace remains locked; there is no guest bypass.

Install updated Python requirements and run `node start.mjs` as before. Development uses exactly `http://127.0.0.1:5173` for cookie/callback consistency. Production can serve the built frontend directly from FastAPI. The supplied Dockerfile prepares this single-origin deployment; persistent storage and HTTPS are required.

The static hosted preview does not deploy the Python authentication service. Live provider consent has not been verified. See [AUTH_VERIFICATION.md](./docs/AUTH_VERIFICATION.md) for implemented behavior, test evidence, and remaining live checks.

### Section 1 — PostgreSQL and Alembic schema versions

The database upgrade retains the existing auth/session and conversation/workspace records. Use two independent Alembic migration histories for the auth and application stores, even when both point to one PostgreSQL database:

```bash
python -m backend.database.schema_migrations status
python -m backend.database.schema_migrations upgrade
python -m backend.database.schema_migrations verify
```

For existing SQLite records, **back up and stop the old server** first, then use the offline dry run and `--apply` copy described in the [online Neon setup guide](./docs/SECTION1_NEON_ONLINE_SETUP.md) (recommended) or the [Mac/Docker alternative](./docs/SECTION1_EXTERNAL_SETUP_MAC.md). Production Docker runs these schema upgrades before starting the API. Never use `downgrade` as a recovery tool for live data.

## Section 9 — Public website (billing skipped)

The public website now includes `/docs/`, `/demo/`, `/examples/`, `/pricing/`, and `/blog/` as separate Vite pages, plus the existing `/` and `/gallery/`. Read [Section 9 website notes](./docs/SECTION9_PUBLIC_WEBSITE.md) for evidence labels, run commands, and security notes. No payments or checkout are implemented. The previous protected FastAPI Swagger `/docs` remains protected, while public setup docs are at `/docs/`.
