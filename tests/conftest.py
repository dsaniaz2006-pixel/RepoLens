import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def auth_manager(tmp_path, monkeypatch):
    import backend.api.api as api
    from backend.auth.auth import AuthManager
    manager = AuthManager(directory=tmp_path/'auth', environ={})
    monkeypatch.setattr(api.app.state, 'auth', manager)
    monkeypatch.setattr(api, 'REPORT_DIR', tmp_path/'reports')
    return manager

@pytest.fixture
def signed_in_client(auth_manager):
    from backend.api.api import app
    from backend.auth.auth import COOKIE
    user = auth_manager.upsert_user('github', '123', 'Test user', 'user@example.com')
    token = auth_manager.new_session(user['id'])
    client = TestClient(app)
    client.cookies.set(COOKIE, token)
    client.headers['X-CSRF-Token'] = auth_manager.authenticate(token)['csrf']
    return client
