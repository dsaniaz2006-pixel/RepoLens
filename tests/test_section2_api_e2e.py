"""Full browser-free HTTP E2E: secure token lifecycle via FastAPI + SQLAlchemy.

Does not simulate real Google/GitHub consent or query private Neon credentials.
"""
from fastapi.testclient import TestClient
from backend.auth.auth import AuthManager, COOKIE
from backend.api.api import app
from backend.database.schema_migrations import upgrade_databases


def test_http_e2e_account_security_on_sqlalchemy_database(tmp_path, monkeypatch):
    auth_url='sqlite:///'+str(tmp_path/'pg_like_auth.sqlite3')
    app_url='sqlite:///'+str(tmp_path/'pg_like_app.sqlite3')
    upgrade_databases(auth_url, app_url)
    mgr=AuthManager(directory=tmp_path/'auth',environ={'REPOLENS_AUTH_DATABASE_URL':auth_url})
    monkeypatch.setattr(app.state,'auth',mgr)
    alice=mgr.upsert_user('github','alice','Alice')
    bob=mgr.upsert_user('github','bob','Bob')
    alice_cookie=mgr.new_session(alice['id'],ip_address='127.0.0.1',user_agent='Integration Browser')
    bob_cookie=mgr.new_session(bob['id'],ip_address='127.0.0.2')
    browser=TestClient(app)
    browser.cookies.set(COOKIE,alice_cookie)
    browser.headers['X-CSRF-Token']=mgr.authenticate(alice_cookie)['csrf']
    assert browser.get('/api/auth/me').json()['user']['id']==alice['id']
    issued=browser.post('/api/auth/keys',json={'name':'CI test key'})
    assert issued.status_code==201
    raw=issued.json()['key']
    cli=TestClient(app)
    assert cli.get('/api/history',headers={'Authorization':'Bearer '+raw}).status_code==200
    assert cli.post('/api/conversations',json={},headers={'Authorization':'Bearer '+raw}).status_code!=401
    assert cli.get('/api/auth/keys',headers={'Authorization':'Bearer '+raw}).status_code==401
    other=TestClient(app)
    other.cookies.set(COOKIE,bob_cookie)
    other.headers['X-CSRF-Token']=mgr.authenticate(bob_cookie)['csrf']
    assert other.get('/api/auth/keys').json()['keys']==[]
    assert other.delete('/api/auth/keys/'+issued.json()['id']).status_code==404
    assert browser.get('/api/auth/sessions').json()['sessions'][0]['current'] is True
    assert browser.delete('/api/auth/keys/'+issued.json()['id']).status_code==200
    assert cli.get('/api/history',headers={'Authorization':'Bearer '+raw}).status_code==401
    assert browser.delete('/api/auth/sessions/all').status_code==200
    assert browser.get('/api/auth/me').status_code==401
    assert other.get('/api/auth/me').status_code==200
