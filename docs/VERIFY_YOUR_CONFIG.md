# RepoLens: fix repeated missing Gemini key error

The previous fixed ZIP excludes `.env` to protect your secrets. Your original local `.env` must be copied to the **new extracted project root**, in the project root (alongside requirements.txt). No secret values are included here.

1. In the project you are actually running, verify `.env` exists in the project root (alongside requirements.txt). It must contain `GEMINI_API_KEY=...` and optionally `GITHUB_TOKEN=...` (not empty placeholders).
2. Stop old uvicorn and Vite processes with Ctrl+C. Be sure VS Code is opened to this extracted folder, not the old `RepoLens 2` project.
3. In terminal from project root: `source .venv/bin/activate` then `python -m uvicorn backend.api.api:app --reload --port 8000`. Create the environment and install requirements first if needed.
4. Open http://127.0.0.1:8000/api/config-status. Expected: `env_file_exists: true`, `gemini_key_configured: true`, `github_token_configured: true` if you added both keys. This endpoint deliberately never returns secret values.
5. In a separate terminal run `cd frontend && npm install && npm run dev`. Reopen the URL printed by Vite and try Analyze Repository.
6. If config-status reports true but the dashboard says the key is missing, your browser is likely talking to an older backend on port 8000. Shut down both running versions and relaunch from the correct folder. You can check the listening process on macOS: `lsof -nP -iTCP:8000 -sTCP:LISTEN`.

Note: The health endpoint `/api/health` reports only server liveness, not API credentials or third-party API success.
