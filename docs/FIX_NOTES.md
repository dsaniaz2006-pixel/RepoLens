> Historical delivery notes. Current results and pending acceptance work: `VERIFICATION_STATUS.md` and `EVALUATION_LOG.md` (2026-10-17).

# RepoLens repair notes

- Fixed: uploaded `frontend/src/main.jsx` was truncated at line 96, immediately after its outer `div` opened. Restored complete JSX from the previous working project snapshot, retaining the safer `apiClient.js` response handler.
- Preserved Python API, Gemini, GitHub, RAG and existing React styling.
- Prevented an optional history refresh from hiding a successful analysis.
- Excluded `.env`, `node_modules`, `.venv`, caches, and other machine-specific files from this ZIP. Transfer your `.env` securely to the project root on your machine.
- Start backend from project root: `python -m uvicorn backend.api.api:app --reload --port 8000`. Start frontend from `frontend/`: `npm install && npm run dev`.
- Test frontend with `cd frontend && npm run build`; test Python with `python -m pytest -q`.

Live Gemini/GitHub API processing has not been validated with private credentials.
