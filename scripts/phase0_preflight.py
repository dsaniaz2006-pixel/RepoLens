"""Read-only Phase 0 environment diagnostic; never prints credentials.

Run from project root: python scripts/phase0_preflight.py
Use --live only while a RepoLens backend is already running.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    'fastapi': 'FastAPI', 'authlib': 'Google/GitHub OAuth',
    'chromadb': 'ChromaDB RAG store', 'google.genai': 'Gemini client',
    'sqlalchemy': 'SQLAlchemy database', 'httpx': 'HTTP testing',
    'dotenv': 'Root .env loading', 'psycopg': 'PostgreSQL adapter',
    'tree_sitter': 'native parser core',
    'tree_sitter_javascript': 'JavaScript parser',
    'tree_sitter_typescript': 'TypeScript parser',
    'tree_sitter_go': 'Go parser',
    'reportlab': 'PDF reporting',
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Check an already running local backend')
    parser.add_argument('--port', type=int, default=int(os.getenv('REPOLENS_BACKEND_PORT', '8000')))
    args = parser.parse_args(argv)
    failures = []
    print('RepoLens Phase 0 prerequisite check')
    print('Python:', platform.python_version(), 'Platform:', platform.system(), platform.machine())
    if sys.version_info < (3, 11):
        failures.append('Python 3.11 or newer is required')
    for module, description in MODULES.items():
        try:
            installed = importlib.util.find_spec(module) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            installed = False
        print(f'{"OK" if installed else "MISSING"}: {description} ({module})')
        if not installed:
            failures.append(module)
    for executable in ('node', 'npm'):
        installed = bool(shutil.which(executable))
        print(f'{"OK" if installed else "MISSING"}: {executable}')
        if not installed:
            failures.append(executable)
    print('Root .env:', 'exists' if (ROOT / '.env').is_file() else 'missing (copy .env.example)')
    print('Frontend node_modules:', 'exists' if (ROOT / 'frontend' / 'node_modules').is_dir()
          else 'missing (run cd frontend && npm ci)')
    if not (ROOT / 'frontend' / 'node_modules').is_dir():
        failures.append('frontend dependencies')
    if args.live:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/health', timeout=3) as response:
                healthy = response.status == 200 and json.load(response).get('status') == 'ok'
        except Exception:
            healthy = False
        print('Backend /api/health:', 'OK' if healthy else 'UNAVAILABLE')
        if not healthy:
            failures.append('backend health')
    print('\nResult:', 'READY for full verification' if not failures else
          f'{len(failures)} prerequisite(s) still require attention')
    if failures:
        print('Incomplete:', ', '.join(failures))
        print('Install requirements into your virtual environment: python -m pip install -r requirements.txt')
    return 0 if not failures else 1


if __name__ == '__main__':
    raise SystemExit(main())
