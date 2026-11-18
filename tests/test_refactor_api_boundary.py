"""Refactor safety tests that do not need live OAuth, Gemini or a database."""
import asyncio
import json

from fastapi import HTTPException
from backend.api.errors import validation_error_response, safe_product_call
from backend.core.environment import PROJECT_ROOT, ENV_FILE


class SensitiveInput:
    def errors(self):
        return [{'loc': ('body', 'token'), 'msg': 'secret-password=not-for-client',
                 'input': {'password': 'secret-password'}}]


def test_validation_errors_do_not_echo_sensitive_input():
    response = asyncio.run(validation_error_response(None, SensitiveInput()))
    assert response.status_code == 422
    assert response.headers['cache-control'] == 'no-store'
    text = response.body.decode()
    assert 'secret-password' not in text
    assert json.loads(text)['detail'][0]['field'] == 'body.token'


def test_product_boundary_preserves_success_and_http_status():
    assert safe_product_call(lambda: {'ok': True}) == {'ok': True}
    try:
        safe_product_call(lambda: (_ for _ in ()).throw(HTTPException(403, 'Forbidden')))
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == 'Forbidden'
    else:
        raise AssertionError('Original 403 was swallowed')


def test_product_boundary_does_not_leak_unexpected_exception():
    try:
        safe_product_call(lambda: (_ for _ in ()).throw(RuntimeError('secret=abc123')))
    except HTTPException as exc:
        assert exc.status_code == 500
        assert 'abc123' not in exc.detail
    else:
        raise AssertionError('Internal exception was swallowed')


def test_local_environment_path_anchored_at_repository_root():
    assert ENV_FILE == PROJECT_ROOT / '.env'
    assert (PROJECT_ROOT / 'start.mjs').is_file()
