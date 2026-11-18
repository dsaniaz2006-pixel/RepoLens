"""Real ASGI integration for production host, secure headers, CSRF and cookies.

Requires the same authlib dependencies installed in the documented Python venv.
"""
import pytest
pytest.importorskip('authlib')
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.auth.auth import install_auth, COOKIE


def test_production_host_headers_and_authenticated_csrf(monkeypatch,tmp_path):
    monkeypatch.setenv('REPOLENS_ENV','production')
    monkeypatch.setenv('REPOLENS_BASE_URL','https://repolens.example.test')
    monkeypatch.setenv('REPOLENS_SESSION_SECRET','x'*48)
    monkeypatch.setenv('REPOLENS_AUTH_DIR',str(tmp_path/'auth'))
    # Never silently use real developer OAuth providers in this isolated test.
    for name in ('GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GITHUB_CLIENT_ID','GITHUB_CLIENT_SECRET'):
        monkeypatch.delenv(name,raising=False)
    # Section 3 enforces PostgreSQL + a configured provider in real production.
    # This isolated test checks host headers/cookies without a cloud database;
    # strict production configuration is tested separately in Section 3.
    monkeypatch.setattr('backend.auth.auth.validate_production_settings', lambda env: None)
    app=FastAPI()
    install_auth(app)
    @app.get('/api/health')
    def health():return {'status':'ok'}
    @app.post('/api/private')
    def private():return {'status':'ok'}
    with TestClient(app,base_url='https://repolens.example.test') as client:
        health=client.get('/api/health')
        assert health.status_code==200
        assert health.headers['strict-transport-security']=='max-age=31536000'
        assert health.headers['x-frame-options']=='DENY'
        assert health.headers['permissions-policy'].startswith('camera=()')
        assert client.get('/api/health',headers={'Host':'evil.example.test'}).status_code==400
        assert client.post('/api/private').status_code==401
        user=app.state.auth.upsert_user('github','1234','Test User')
        token=app.state.auth.new_session(user['id'])
        csrf=app.state.auth.authenticate(token)['csrf']
        client.cookies.set(COOKIE,token)
        assert client.post('/api/private',headers={'X-CSRF-Token':'bad'}).status_code==403
        assert client.post('/api/private',headers={'X-CSRF-Token':csrf,'Origin':'https://evil.example.test'}).status_code==403
        response=client.post('/api/private',headers={'X-CSRF-Token':csrf,'Origin':'https://repolens.example.test'})
        assert response.status_code==200
