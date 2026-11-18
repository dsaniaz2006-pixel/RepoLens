> Current verification and acceptance steps are in `VERIFICATION_STATUS.md` and `EVALUATION_LOG.md` (2026-10-17). Older setup notes below may describe earlier runs.

# RepoLens — final project setup and verification

This project extends the supplied October 2026 Python CLI with RAG, optional interview/contribution modes, a FastAPI HTTP interface and a React/Vite dashboard. It intentionally does not include the original `.env` or virtual environment from the uploaded ZIP.

## Prerequisites

- macOS/Linux, Python 3.11+, Node.js 20+ and npm
- GitHub public repository access and a Google Gemini API key with the configured models enabled
- Internet access for live GitHub/Gemini operations and dependency installation

## Python installation

```bash
cd RepoLens
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` **locally**: set `GEMINI_API_KEY` and optionally `GITHUB_TOKEN`. Never commit or share `.env`. The original uploaded ZIP included a `.env` file: it is intentionally excluded from this deliverable. Consider rotating keys if the original ZIP was shared beyond your control.

The PDF proposes `gemini-3.5-flash-lite` and `gemini-embedding-2`, used as defaults in `config.py`. **Verify these models exist for your API key; change `GEMINI_MODEL` and `EMBEDDING_MODEL` in `config.py` if required.** This environment could not validate live model access or pricing.

## CLI examples

```bash
python -m pytest -q
python -m backend.cli.main https://github.com/pallets/flask
python -m backend.cli.main https://github.com/pallets/flask --interview
python -m backend.cli.main https://github.com/pallets/flask --contribution
python -m backend.cli.main https://github.com/pallets/flask --index
python -m backend.cli.main https://github.com/pallets/flask --ask "Where is the Flask app created?"
```

`--index` must finish before `--ask`. An index is stored for the **current commit SHA**, so re-index after the default branch changes. The index includes only already-approved, budget-limited source snippets: it is not guaranteed to cover every file in a repository. Chroma indexes are stored locally in `.repolens_chroma/` (ignored by Git).

## Dashboard

Use two separate terminals, both starting in the root `RepoLens` directory.

**Terminal 1 (Python API):**

```bash
source .venv/bin/activate
python -m uvicorn backend.api.api:app --host 127.0.0.1 --port 8000
```

**Terminal 2 (React UI):**

```bash
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. Vite forwards `/api` to the local FastAPI process. The UI supports public repository analysis, report tabs, Markdown/PDF download, locally saved analysis history, revision-index creation and cited RAG Q&A. The share-link button currently copies the current page URL only; it does not publish reports to the internet.

### API overview

- `GET /api/health`: API availability
- `POST /api/analyze` with `{ "url": "https://github.com/owner/repo" }`
- `POST /api/index` with repository URL
- `POST /api/ask` with repository URL and question
- `GET /api/history`: locally stored analyses
- `GET /api/history/{owner}/{repo}`: saved structured analysis
- `GET /api/report/{owner}/{repo}`: download Markdown
- `GET /api/report/{owner}/{repo}/pdf`: download PDF

The API is designed for *local development*, not public hosting. Before deploying on the internet add authentication, per-user isolation, request rate limits, bounded jobs/worker queues, persistent secure storage, quotas, HTTPS and separate credential management. Do not expose this development server to untrusted users.

## What was verified

- The pre-existing Python suite passed before changes (68 tests).
- The current Python suite passed **135 tests**; see `VERIFICATION_STATUS.md` for the full scope.
- Python compilation and FastAPI route imports completed.

## What is NOT verified

- Live GitHub and Gemini behavior, including whether both default model IDs are enabled for your account.
- Accuracy of sample reports against Flask, Axios and a third repository. Do those manual checks and log at least one real issue/fix.
- Live provider/browser integration remains pending. The production Vite build and three Chromium tests with simulated API responses passed on 2026-10-17.
- Production security or end-to-end deployment.

## Good next steps

1. Configure a fresh API key and run the CLI on Flask.
2. Run `--index` and `--ask` on the same repository.
3. Install frontend npm dependencies; run `npm run build` and then launch the dashboard.
4. Verify generated paths and facts against source; add 10–15 RAG evaluation questions to `EVALUATION_LOG.md`.
5. Add more robust code-aware chunking and hybrid (symbol + semantic) retrieval if evaluation reveals misses.

The original 14-page MVP build guide and 7-page RAG/dashboard supplement remain the requirements baseline; enhancements here are additive to the original source.
