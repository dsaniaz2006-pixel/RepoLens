"""HTTPS OAuth security smoke tests. No live provider calls or secrets needed."""
import pytest
pytest.importorskip('authlib')
from fastapi import HTTPException
from backend.auth.auth import AuthManager


def test_https_origin_enforces_secure_session_config_and_csrf(tmp_path):
    auth = AuthManager(directory=tmp_path/'secure', environ={
        'REPOLENS_BASE_URL':'https://127.0.0.1:5173',
        'REPOLENS_ENV':'development',
    })
    assert auth.secure is True
    assert auth.base_url == 'https://127.0.0.1:5173'
    user = {'csrf':'test-csrf-token'}

    class Request:
        headers = {'origin':'https://127.0.0.1:5173', 'x-csrf-token': 'test-csrf-token'}

    auth.check_csrf(Request(), user)
    Request.headers = {'origin':'http://127.0.0.1:5173', 'x-csrf-token':'test-csrf-token'}
    with pytest.raises(HTTPException) as error:
        auth.check_csrf(Request(), user)
    assert error.value.status_code == 403


def test_local_http_remains_explicit_fallback(tmp_path):
    auth = AuthManager(directory=tmp_path/'http', environ={'REPOLENS_BASE_URL':'http://127.0.0.1:5173'})
    assert auth.secure is False
