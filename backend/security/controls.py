"""Small, auditable security controls; never pass repository text as instructions.

Every returned message intended for HTTP responses is bounded and redacted.
No raw request bodies, OAuth tokens, invitation links or DB URLs enter audit logs.
"""
from __future__ import annotations
import os
import re
import unicodedata
from urllib.parse import urlsplit

from backend.github.github_client import parse_github_url


def validate_repository_url(url: str) -> str:
    if not isinstance(url, str) or not 1 <= len(url.strip()) <= 500:
        raise ValueError('Enter a valid GitHub repository URL.')
    normalized = url.strip()
    # GitHub parser prevents host spoofing, SSRF, path traversal and query strings.
    parse_github_url(normalized)
    return normalized


def validate_question(question: str) -> str:
    if not isinstance(question,str) or not question.strip() or len(question) > 4000:
        raise ValueError('Question must contain 1–4000 characters.')
    if any(unicodedata.category(ch) == 'Cc' and ch not in '\n\r\t' for ch in question):
        raise ValueError('Question contains unsupported control characters.')
    return question


def public_error_detail(error: BaseException, fallback: str='Request could not be completed.') -> str:
    """Redact secrets from known-safe validation errors; do not expose SDK tracebacks.

    Raw provider errors and database exceptions are displayed with a fixed message
    by their callers. This function is for bounded user-facing ValueErrors only.
    """
    message = str(error)[:600] or fallback
    # A URL can contain credentials in userinfo or query args: remove the whole URL.
    message = re.sub(r'(?i)\b(?:postgres(?:ql)?(?:\+psycopg)?|https?)://\S+', '[redacted URL]', message)
    # Named secret parameters even in non-URL text.
    message = re.sub(r'(?i)(?:password|api[_-]?key|access[_-]?token|secret|authorization)\s*[=:]\s*\S+', '[redacted credential]', message)
    for key, value in os.environ.items():
        if any(tag in key.upper() for tag in ('KEY','TOKEN','SECRET','PASSWORD','DATABASE_URL')) and len(value) >= 8:
            message = message.replace(value, '[redacted]')
    message = re.sub(r'(?i)\b(?:rl_live_|gh[pousr]_|sk_(?:live|test)_)[a-zA-Z0-9_-]{8,}', '[redacted token]', message)
    return message[:400] or fallback


def validate_production_settings(env: dict[str,str]) -> None:
    if env.get('REPOLENS_ENV') != 'production':
        return
    url = env.get('REPOLENS_BASE_URL','')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Production requires HTTPS REPOLENS_BASE_URL.')
    if len(env.get('REPOLENS_SESSION_SECRET','')) < 32:
        raise ValueError('Production requires a persistent random session secret.')
    for key in ('REPOLENS_AUTH_DATABASE_URL','REPOLENS_DATABASE_URL'):
        if not env.get(key,'').startswith('postgresql+psycopg://'):
            raise ValueError('Production requires PostgreSQL for both auth and application data.')
    providers = ('GOOGLE','GITHUB')
    if not any(all(env.get(p+'_'+suffix,'').strip() and not env[p+'_'+suffix].startswith('YOUR_')
                   for suffix in ('CLIENT_ID','CLIENT_SECRET')) for p in providers):
        raise ValueError('Production requires at least one configured OAuth provider.')


_AUDIT_RULES = (
    ('DELETE',re.compile(r'^/api/conversations/([a-zA-Z0-9_-]{1,100})$'),'conversation:deleted'),
    ('POST',re.compile(r'^/api/workspaces/([a-zA-Z0-9_-]{1,100})/members/[a-zA-Z0-9_-]{1,128}$'),'workspace:role_changed'),
    ('DELETE',re.compile(r'^/api/workspaces/([a-zA-Z0-9_-]{1,100})/members/[a-zA-Z0-9_-]{1,128}$'),'workspace:member_removed'),
    ('POST',re.compile(r'^/api/workspaces/([a-zA-Z0-9_-]{1,100})/invite$'),'workspace:invited'),
    ('POST',re.compile(r'^/api/workspaces/([a-zA-Z0-9_-]{1,100})/repositories$'),'workspace:repository_shared'),
    ('POST',re.compile(r'^/api/workspaces$'),'workspace:created'),
    ('POST',re.compile(r'^/api/analyze$'),'report:generated'),
    ('POST',re.compile(r'^/api/workspaces/join$'),'workspace:joined'),
)


def audit_route(method: str, path: str) -> tuple[str,str|None]|None:
    """Only whitelisted successful mutations; never save request URL or body."""
    for expected_method, pattern, action in _AUDIT_RULES:
        if method == expected_method:
            match = pattern.fullmatch(path)
            if match:
                return action, match.group(1) if match.lastindex else None
    return None
