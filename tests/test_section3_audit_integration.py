"""Section 3 integration / HTTP acceptance using throwaway SQLAlchemy databases.

Only third-party OAuth transport is mocked by the test environment when absent.
Never uses production Neon, Gemini, or GitHub credentials.
"""
import re
import pytest
from sqlalchemy import create_engine, inspect, text
from fastapi.testclient import TestClient
from backend.auth.auth import AuthManager, COOKIE
from backend.api.api import app
from backend.database.schema_migrations import upgrade_databases, migration_status


@pytest.fixture(params=['sqlite','sqlalchemy'])
def manager(request,tmp_path):
    if request.param == 'sqlite':
        return AuthManager(directory=tmp_path/'local', environ={})
    auth_url='sqlite:///'+str(tmp_path/'auth.sqlite3')
    app_url='sqlite:///'+str(tmp_path/'app.sqlite3')
    upgraded=upgrade_databases(auth_url,app_url)
    assert upgraded['auth']['current']=='auth_0005'
    return AuthManager(directory=tmp_path/'local', environ={'REPOLENS_AUTH_DATABASE_URL':auth_url})


def test_audit_recording_scoped_and_never_stores_secrets(manager):
    alice=manager.upsert_user('github','a','Alice')
    bob=manager.upsert_user('github','b','Bob')
    raw_token=manager.new_session(alice['id'])
    secret=manager.create_api_key(alice['id'],'My API token')['key']
    manager.revoke_api_key(alice['id'], manager.list_api_keys(alice['id'])[0]['id'])
    manager.record_login_failure('127.0.0.1')
    manager.record_login_success('127.0.0.1', alice['id'])
    manager.revoke_all_sessions(alice['id'])
    actions=[e['action'] for e in manager.recent_audit(alice['id'])]
    assert {'api_key:created','api_key:revoked','auth:login_success','auth:all_sessions_revoked'} <= set(actions)
    assert manager.recent_audit(bob['id'])==[]
    with manager.connect() as db:
        rows=db.execute('SELECT user_id,action,target,ip_address FROM audit_events').fetchall()
    stored=repr([tuple(x[k] for k in ('user_id','action','target','ip_address')) for x in rows])
    assert secret not in stored
    assert raw_token not in stored
    assert 'auth:login_failure' in stored
    assert '127.0.0.1' in stored


def test_auth_migrations_are_non_destructive(tmp_path):
    auth_url='sqlite:///'+str(tmp_path/'auth.sqlite3')
    app_url='sqlite:///'+str(tmp_path/'app.sqlite3')
    assert upgrade_databases(auth_url, app_url)['auth']['up_to_date']
    engine=create_engine(auth_url)
    assert inspect(engine).has_table('audit_events')
    assert {'action','user_id','target','ip_address','created_at'} <= {x['name'] for x in inspect(engine).get_columns('audit_events')}
    engine.dispose()
    assert migration_status(auth_url,app_url)['auth']['current']=='auth_0005'


def test_real_http_headers_auth_boundaries_and_audit(manager, monkeypatch, tmp_path):
    monkeypatch.setattr(app.state,'auth',manager)
    user=manager.upsert_user('github','a','Alice')
    cookie=manager.new_session(user['id'])
    client=TestClient(app)
    client.cookies.set(COOKIE,cookie)
    client.headers['X-CSRF-Token']=manager.authenticate(cookie)['csrf']

    response=client.get('/api/health')
    assert response.status_code==200
    csp=response.headers['content-security-policy']
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "'unsafe-eval'" not in csp
    assert response.headers['x-content-type-options']=='nosniff'
    assert response.headers['x-frame-options']=='DENY'
    assert response.headers['cross-origin-opener-policy']=='same-origin'

    secret='PASSWORD_IN_INVALID_URL_123'
    invalid=client.post('/api/ask',json={'url':f'https://github.com/owner/repo?token={secret}', 'question':'hi'})
    assert invalid.status_code==422
    assert secret not in invalid.text
    assert 'input' not in invalid.text
    assert 'traceback' not in invalid.text.lower()
    secret_question='How do I ignore previous instructions safely?'
    valid=client.post('/api/ask',json={'url':'https://github.com/pallets/flask','question':secret_question,'conversation_id':'bad\ncontrol'})
    # Underlying AI service may be unavailable offline, but should pass request-body validation.
    assert valid.status_code!=422

    created=client.post('/api/auth/keys',json={'name':'HTTP test key'})
    assert created.status_code==201
    key=created.json()['key']; key_id=created.json()['id']
    log=client.get('/api/auth/audit')
    assert log.status_code==200
    assert any(e['action']=='api_key:created' for e in log.json()['events'])
    assert key not in log.text
    assert client.delete(f'/api/auth/keys/{key_id}').status_code==200
    assert any(e['action']=='api_key:revoked' for e in client.get('/api/auth/audit').json()['events'])

    # Browser security controls reject bearer tokens even if a key is valid.
    next_key=client.post('/api/auth/keys',json={'name':'API-only token'}).json()['key']
    bearer_client=TestClient(app)
    assert bearer_client.get('/api/auth/audit',headers={'Authorization':'Bearer '+next_key}).status_code==401
    bob=manager.upsert_user('github','b','Bob')
    bob_cookie=manager.new_session(bob['id'])
    other=TestClient(app)
    other.cookies.set(COOKIE,bob_cookie)
    assert other.get('/api/auth/audit').json()['events']==[]


def test_workspace_and_conversation_mutations_audited_after_success(manager, monkeypatch, tmp_path):
    import backend.database.product_store as store
    app_url='sqlite:///'+str(tmp_path/'app_data.sqlite3')
    # A separate database is used: never talk to user's production Neon.
    app_engine=create_engine(app_url)
    store.metadata.create_all(app_engine)
    monkeypatch.setattr(store,'engine',lambda req: app_engine)
    monkeypatch.setattr(app.state,'auth',manager)
    alice=manager.upsert_user('github','alice','Alice')
    cookie=manager.new_session(alice['id'])
    browser=TestClient(app)
    browser.cookies.set(COOKIE,cookie)
    browser.headers['X-CSRF-Token']=manager.authenticate(cookie)['csrf']
    created=browser.post('/api/workspaces',json={'name':'Security Project'})
    assert created.status_code==200,created.text
    workspace_id=created.json()['id']
    assert re.fullmatch('[a-f0-9-]{32,36}',workspace_id)
    actions=manager.recent_audit(alice['id'])
    assert any(e['action']=='workspace:created' for e in actions)
    invite=browser.post('/api/workspaces/'+workspace_id+'/invite')
    assert invite.status_code==200
    token=invite.json()['token']
    assert token not in repr(manager.recent_audit(alice['id']))
    assert any(e['action']=='workspace:invited' and e['target']==workspace_id for e in manager.recent_audit(alice['id']))
    app_engine.dispose()


def test_conversation_deletion_is_audited_only_on_success(manager, monkeypatch):
    from fastapi import HTTPException
    from types import SimpleNamespace
    from backend.database import conversations
    monkeypatch.setattr(app.state,'auth',manager)
    user=manager.upsert_user('github','actor','Actor')
    cookie=manager.new_session(user['id'])
    client=TestClient(app)
    client.cookies.set(COOKIE,cookie)
    client.headers['X-CSRF-Token']=manager.authenticate(cookie)['csrf']
    observed=[]
    monkeypatch.setattr(conversations,'request_store', lambda req: SimpleNamespace(remove=lambda uid, cid: observed.append((uid,cid))))
    assert client.delete('/api/conversations/conversation_123').status_code==200
    assert observed==[(user['id'],'conversation_123')]
    assert any(x['action']=='conversation:deleted' and x['target']=='conversation_123' for x in manager.recent_audit(user['id']))
    before=len(manager.recent_audit(user['id']))
    def deny(uid,cid): raise HTTPException(404,'Not found')
    monkeypatch.setattr(conversations,'request_store',lambda req: SimpleNamespace(remove=deny))
    assert client.delete('/api/conversations/does_not_exist').status_code==404
    assert len(manager.recent_audit(user['id']))==before


def test_nonempty_audit_history_cannot_be_destroyed_by_downgrade(tmp_path):
    from alembic import command
    from backend.database.schema_migrations import _config
    auth_url='sqlite:///'+str(tmp_path/'auth_history.sqlite3')
    app_url='sqlite:///'+str(tmp_path/'app_history.sqlite3')
    upgrade_databases(auth_url,app_url)
    mgr=AuthManager(directory=tmp_path/'auth_folder',environ={'REPOLENS_AUTH_DATABASE_URL':auth_url})
    user=mgr.upsert_user('github','id','Test User')
    mgr.record_audit('auth:login_success',user_id=user['id'])
    with pytest.raises(RuntimeError, match='Refusing to delete audit history'):
        command.downgrade(_config('auth',auth_url),'auth_0002')
    # auth_0004's empty usage tables may downgrade successfully before the
    # protected auth_0003 audit-history downgrade is rejected. Reapply the
    # additive head and confirm history survives untouched.
    assert migration_status(auth_url,app_url)['auth']['current']=='auth_0003'
    upgrade_databases(auth_url,app_url)
    assert migration_status(auth_url,app_url)['auth']['up_to_date']
    assert len(mgr.recent_audit(user['id']))==1
