> Historical delivery notes. Current results and pending acceptance work: `VERIFICATION_STATUS.md` and `EVALUATION_LOG.md` (2026-10-17).

# RepoLens API key loading fix

## Root cause
The CLI `main.py` called `load_dotenv()`, but `uvicorn backend.api.api:app` imports `api.py` directly, so `main.py` did not execute. `api.py` did not load `.env`, leaving `GEMINI_API_KEY` and `GITHUB_TOKEN` unavailable to analyzer.py/github_client.py.

## Fix
`api.py` now runs `load_dotenv(dotenv_path=Path(__file__).resolve().parent / '.env')` before importing pipeline modules. This loads keys from the application root regardless of which directory Uvicorn was started from.

## Verification
- 82 Python unit tests passed.
- Imported api.py from another directory with placeholder keys in a temporary .env; both variables loaded correctly.
- Live GitHub/Gemini end-to-end analysis has NOT been run here; this must be checked using your local .env.

## Setup
1. Unzip into a new folder.
2. Copy your OWN `.env` from the old project into the new project's root; the archive deliberately excludes it. Keep it private.
3. Make a Python venv: `python3 -m venv .venv && source .venv/bin/activate`
4. Install packages: `python -m pip install -r requirements.txt`
5. Run backend: `python -m uvicorn backend.api.api:app --reload --port 8000`
6. In another terminal: `cd frontend && npm install && npm run dev`
7. Analyze https://github.com/pallets/flask in the web interface.

Do not publish your .env or API tokens.
