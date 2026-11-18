# Python package reorganization — 1 November 2026

All 36 root Python forwarding files were removed. Implementation remains grouped in backend/api, auth, database, ai, rag, github, services, core, and cli. All source, script, and test imports now use package-qualified paths. Package __init__.py files are present.

Start from the extracted RepoLens directory:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
node start.mjs
```

Reuse an existing compatible virtual environment or create one with `python3 -m venv .venv`. Install frontend dependencies with `npm ci --prefix frontend` when needed. Keep your private `.env` in the root beside requirements.txt. It is excluded from this archive.

Backend alone: `python -m uvicorn backend.api.api:app --port 8000`
CLI: `python -m backend.cli.main --help`
Migration: `python -m backend.database.migrate_database --help`
Update preview: `python -m backend.cli.apply_update /path/to/existing/RepoLens`

Old commands such as `uvicorn api:app` and `python main.py` no longer apply to this clean package. Launchers, Dockerfiles, GitHub Action and documentation were updated. The updater accepts both legacy and packaged target layouts; it preserves existing files rather than deleting legacy files in an older installation. Use a fresh extracted directory for a completely clean root.

Validation: 270 Python tests passed; one unconfigured PostgreSQL integration test skipped. 17 frontend tests passed. Vite production build passed. Real HTTP smoke checks passed including authentication gating, invitation replay, assignment permissions, share revocation and restart persistence using synthetic accounts. CLI, updater and migration help commands succeeded. Real OAuth/provider calls and browser interaction were not tested.

Requirements constrain pytest to version 8: pytest 9.2.0 removed Starlette State attributes during monkeypatch teardown in this environment; 8.4.2 passed the suite. Application resource paths were verified against the project root. See docs/PROJECT_STRUCTURE.md for the complete layout.
