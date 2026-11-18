"""Section 2 security acceptance tests (TDD: authored before implementation).

These tests use an isolated SQLite auth DB. Hosted Neon tests must use a disposable branch.
"""
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.auth.auth import AuthManager, COOKIE
from backend.api.api import app
from backend.database.schema_migrations import upgrade_databases, migration_status
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def user_client(tmp_path, monkeypatch):
    manager = AuthManager(directory=tmp_path/'auth', environ={})
    monkeypatch.setattr(app.state, 'auth', manager)
    user = manager.upsert_user('github','section2-1','Alice','alice@example.org')
    token = manager.new_session(user['id'], ip_address='127.0.0.1', user_agent='Section2 Test')
    client = TestClient(app)
    client.cookies.set(COOKIE, token)
    client.headers['X-CSRF-Token'] = manager.authenticate(token)['csrf']
    return manager, user, token, client


def test_tdd_api_keys_hashed_unique_revoke_and_scoped(user_client):
    manager,user,token,client = user_client
    created = client.post('/api/auth/keys',json={'name':'My Mac CLI'})
    assert created.status_code==201, created.text
    raw = created.json()['key']
    assert raw.startswith('rl_live_') and len(raw)>30
    with manager.connect() as c:
        row = c.execute('SELECT key_hash,key_prefix FROM api_keys WHERE user_id=?',(user['id'],)).fetchone()
        assert raw not in (row['key_hash'], row['key_prefix'])
        assert len(row['key_hash']) == 64
    listing=client.get('/api/auth/keys')
    assert listing.status_code==200
    assert raw not in listing.text
    key_id=listing.json()['keys'][0]['id']
    assert manager.authenticate_api_key(raw)['id']==user['id']
    assert client.delete('/api/auth/keys/'+key_id).status_code==200
    assert manager.authenticate_api_key(raw) is None
    assert client.delete('/api/auth/keys/'+key_id).status_code==404


def test_tdd_bearer_auth_works_without_csrf_and_invalid_bearer_fails_closed(user_client):
    manager,user,token,client = user_client
    raw=client.post('/api/auth/keys',json={'name':'service'}).json()['key']
    api_client=TestClient(app)
    assert api_client.get('/api/history',headers={'Authorization':'Bearer '+raw}).status_code==200
    assert api_client.post('/api/conversations',headers={'Authorization':'Bearer '+raw},json={}).status_code!=401
    assert api_client.get('/api/history',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert api_client.get('/api/auth/keys',headers={'Authorization':'Bearer '+raw}).status_code==401
    # Invalid bearer must not silently fall back to a valid cookie.
    assert client.get('/api/history',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert client.post('/api/auth/keys',json={'name':'csrf-bypass'},headers={'X-CSRF-Token':'wrong'}).status_code==403


def test_tdd_sessions_list_revoke_all_is_user_scoped(user_client):
    manager,user,token,client=user_client
    second=manager.new_session(user['id'],ip_address='127.0.0.2',user_agent='Another device')
    other=manager.upsert_user('google','different','Bob')
    other_token=manager.new_session(other['id'])
    response=client.get('/api/auth/sessions')
    assert response.status_code==200
    assert len(response.json()['sessions'])==2
    assert sum(bool(s['current']) for s in response.json()['sessions'])==1
    assert token not in response.text and second not in response.text
    assert client.delete('/api/auth/sessions/all').status_code==200
    assert manager.authenticate(token) is None and manager.authenticate(second) is None
    assert manager.authenticate(other_token) is not None
    assert client.get('/api/auth/sessions').status_code==401


def test_tdd_login_lockout_and_recovery(user_client, monkeypatch):
    manager,_,_,client=user_client
    ip='198.51.100.123'
    for _ in range(10):manager.record_login_failure(ip)
    assert manager.login_locked(ip) is True
    assert manager.login_locked('198.51.100.124') is False
    with manager.connect() as c:
        c.execute('UPDATE login_attempts SET locked_until=? WHERE ip_address=?',(int(time.time())-1,ip))
    assert manager.login_locked(ip) is False
    manager.record_login_success(ip)
    with manager.connect() as c:
        assert c.execute('SELECT ip_address FROM login_attempts WHERE ip_address=?',(ip,)).fetchone() is None


def test_tdd_alembic_incremental_migration_preserves_existing_users(tmp_path):
    from backend.database.schema_migrations import _config
    from alembic import command
    auth_url='sqlite:///'+str(tmp_path/'auth.sqlite3')
    app_url='sqlite:///'+str(tmp_path/'app.sqlite3')
    command.upgrade(_config('auth',auth_url),'auth_0001')
    with create_engine(auth_url).begin() as c:
        c.execute(text("INSERT INTO users VALUES ('before','github','old','Before',NULL,100)"))
        c.execute(text("INSERT INTO sessions VALUES ('sessionhash','before','csrf',9999999999)"))
    upgrade_databases(auth_url,app_url)
    with create_engine(auth_url).connect() as c:
        assert c.scalar(text("SELECT name FROM users WHERE id='before'"))=='Before'
        assert c.scalar(text("SELECT user_id FROM sessions WHERE token_hash='sessionhash'"))=='before'
        assert 'api_keys' in inspect(c).get_table_names()
        assert 'login_attempts' in inspect(c).get_table_names()
        assert {'token_hash','ip_address','user_agent','created_at'} <= {x['name'] for x in inspect(c).get_columns('session_devices')}
    assert migration_status(auth_url,app_url)['auth']['current']=='auth_0005'


def test_tdd_other_account_cannot_list_or_revoke_keys(user_client):
    manager,user,token,client=user_client
    first=client.post('/api/auth/keys',json={'name':'Alice only'}).json()
    other=manager.upsert_user('github','section2-bob','Bob')
    bob_token=manager.new_session(other['id'])
    bob=TestClient(app)
    bob.cookies.set(COOKIE,bob_token)
    bob.headers['X-CSRF-Token']=manager.authenticate(bob_token)['csrf']
    assert bob.get('/api/auth/keys').json()=={'keys':[]}
    assert bob.delete('/api/auth/keys/'+first['id']).status_code==404
    assert manager.authenticate_api_key(first['key'])['id']==user['id']
    # A bearer token must never manage an account even if the underlying API key is valid.
    assert bob.get('/api/auth/sessions',headers={'Authorization':'Bearer '+first['key']}).status_code==401


def test_tdd_revoke_all_requires_csrf_and_cannot_revoke_others(user_client):
    manager,user,token,client=user_client
    bob=manager.upsert_user('github','section2-bob','Bob')
    bob_token=manager.new_session(bob['id'])
    assert client.delete('/api/auth/sessions/all',headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert manager.authenticate(token)
    assert client.delete('/api/auth/sessions/all').status_code==200
    assert manager.authenticate(bob_token)


def test_tdd_active_key_count_and_no_raw_reveal_after_first_creation(user_client):
    manager,user,token,client=user_client
    for i in range(10):
        assert client.post('/api/auth/keys',json={'name':f'Key {i}'}).status_code==201
    overflow=client.post('/api/auth/keys',json={'name':'eleventh'})
    assert overflow.status_code==400
    listing=client.get('/api/auth/keys').json()['keys']
    assert len(listing)==10
    assert all('key' not in obj and 'key_hash' not in obj for obj in listing)
    assert client.post('/api/auth/keys',json={'name':'   '}).status_code==400
    assert client.delete('/api/auth/keys/'+listing[0]['id']).status_code==200
    assert client.post('/api/auth/keys',json={'name':'replacement'}).status_code==201


def test_tdd_sqlalchemy_adapter_auth_security_tables(tmp_path):
    from backend.database.schema_migrations import upgrade_databases
    auth_url='sqlite:///'+str(tmp_path/'prodlike.sqlite3')
    app_url='sqlite:///'+str(tmp_path/'app.sqlite3')
    upgrade_databases(auth_url,app_url)
    manager=AuthManager(directory=tmp_path/'adapter',environ={'REPOLENS_AUTH_DATABASE_URL':auth_url})
    user=manager.upsert_user('github','sqlalchemy','Adapter')
    token=manager.new_session(user['id'],ip_address='127.0.0.1',user_agent='Adapter Test')
    assert manager.list_sessions(user['id'],token)[0]['user_agent']=='Adapter Test'
    raw=manager.create_api_key(user['id'],'SQL adapter')['key']
    assert manager.authenticate_api_key(raw)['id']==user['id']
    manager.record_login_failure('127.0.0.1')
    assert manager.login_locked('127.0.0.1') is False
    manager.revoke_all_sessions(user['id'])
    assert manager.authenticate(token) is None
    assert manager.authenticate_api_key(raw) is not None  # API keys aren't browser sessions.


def test_tdd_oauth_begin_denies_locked_ip_before_redirect(tmp_path,monkeypatch):
    manager=AuthManager(directory=tmp_path/'oauth',environ={'GITHUB_CLIENT_ID':'mock-app','GITHUB_CLIENT_SECRET':'mock-secret'})
    monkeypatch.setattr(app.state,'auth',manager)
    for _ in range(10):manager.record_login_failure('testclient')
    response=TestClient(app).get('/api/auth/login/github',follow_redirects=False)
    assert response.status_code==303
    assert response.headers['location']=='/login/?error=too_many_attempts'


def test_tdd_security_credentials_do_not_leak_in_bad_responses(user_client):
    _,_,_,client=user_client
    response=client.post('/api/auth/keys',json={'name':'demo'})
    secret=response.json()['key']
    assert client.get('/api/auth/sessions').status_code==200
    assert secret not in client.get('/api/auth/sessions').text
    assert secret not in client.get('/api/auth/keys').text
    assert client.get('/api/history',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert secret not in client.get('/api/history',headers={'Authorization':'Bearer invalid'}).text


def test_tdd_security_records_survive_new_process_like_manager(tmp_path):
    auth_url='sqlite:///'+str(tmp_path/'persistent.sqlite3')
    app_url='sqlite:///'+str(tmp_path/'app.sqlite3')
    upgrade_databases(auth_url,app_url)
    opts={'REPOLENS_AUTH_DATABASE_URL':auth_url}
    a=AuthManager(directory=tmp_path/'auth',environ=opts)
    u=a.upsert_user('google','persistent-user','Persisted User')
    token=a.new_session(u['id'],user_agent='MacBook Browser')
    key=a.create_api_key(u['id'],'Saved CLI')['key']
    a.sql_database.engine.dispose()
    b=AuthManager(directory=tmp_path/'auth',environ=opts)
    assert b.authenticate(token)['id']==u['id']
    assert b.authenticate_api_key(key)['id']==u['id']
    assert b.list_sessions(u['id'],token)[0]['user_agent']=='MacBook Browser'
    b.revoke_all_sessions(u['id'])
    assert b.authenticate(token) is None
    b.sql_database.engine.dispose()
    c=AuthManager(directory=tmp_path/'auth',environ=opts)
    assert c.authenticate(token) is None
    assert c.authenticate_api_key(key)['id']==u['id']
    c.sql_database.engine.dispose()
