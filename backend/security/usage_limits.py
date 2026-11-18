"""Section 4: centralized cost and rate-limit policy.

Authenticated requests are charged BEFORE executing expensive work; provider
failures still consume a request because GitHub/Gemini work may already occur.
Policy is intentionally internal; billing/webhook validation will eventually
own user_plans rather than accepting a client-supplied plan.
"""
from __future__ import annotations
import re

PLAN_LIMITS = {
    'free': {'analyze': 5, 'ask': 20, 'index': 2},
    'pro': {'analyze': 50, 'ask': 500, 'index': 20},
    'team': {'analyze': 200, 'ask': 2000, 'index': 100},
}
HOURLY_LIMITS = {'analyze': 10, 'ask': 60, 'index': 5}

_EXACT = {
    '/api/analyze': 'analyze',
    '/api/analyze/stream': 'analyze',
    '/api/interview': 'analyze',
    '/api/contribution': 'analyze',
    '/api/diff': 'analyze',
    '/api/security-scan': 'analyze',
    '/api/flow': 'analyze',
    '/api/checklists': 'analyze',
    '/api/ask': 'ask',
    '/api/index': 'index',
    '/api/index/jobs': 'index',
    '/api/local/index': 'index',
}

def action_for_request(method: str, path: str) -> str | None:
    """Only charge costly POST endpoints, not progress polling or normal CRUD."""
    if method != 'POST':
        return None
    if path in _EXACT:
        return _EXACT[path]
    if re.fullmatch(r'/api/local/repositories/[^/]+/ask', path):
        return 'ask'
    return None
