#!/usr/bin/env python3
"""Live Phase 6 provider/checklist smoke test without GitHub or saved data.

Requires .env and consumes a small amount of configured model quota.
Never logs API keys, full model text, or local repository source.
"""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from backend.ai.model_provider import ModelResponseError, provider
from backend.services.onboarding import generate

SAMPLE = {
    'repo_id': 'repolens/safe-diagnostic', 'revision': '0' * 40,
    'records': [
        {'path': 'demo/app.py', 'content':
         'def register_route(path):\n    return {"path": path}\n\n'
         'def dispatch_request(route):\n    return route["path"]\n'},
        {'path': 'demo/test_app.py', 'content':
         'def test_route():\n    assert register_route("/items")\n'},
    ],
}

if __name__ == '__main__':
    print('RepoLens Phase 6 provider smoke test')
    print('Configured provider:', provider())
    print('This tests JSON generation and source validation, not GitHub access.')
    try:
        result = generate(SAMPLE)
    except ModelResponseError as exc:
        print('PROVIDER FAILURE:', str(exc))
        print('Category:', exc.kind, 'HTTP status:', exc.status or 'not available')
        sys.exit(2)
    except ValueError as exc:
        # Validation errors generated in the application have safe fixed text.
        print('CHECKLIST VALIDATION FAILURE:', str(exc))
        sys.exit(3)
    print('SUCCESS: JSON model and source-cited checklist generation passed.')
    print('Validated tasks:', len(result['tasks']))
    print('No repository, account, or database was modified.')
