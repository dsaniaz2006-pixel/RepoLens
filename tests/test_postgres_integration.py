"""Runs automatically in CI's real PostgreSQL service; opt-in locally."""
import os,uuid
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

@pytest.mark.skipif(not os.getenv('REPOLENS_TEST_POSTGRES_URL'),reason='No PostgreSQL test service configured')
def test_real_postgres_auth_chat_workspace_and_migration(tmp_path):
    from backend.auth.auth import AuthManager
    from backend.database.conversations import ConversationStore
    from backend.database.migrate_database import migrate
    from backend.database.schema_migrations import upgrade_databases, migration_status
    from backend.database.product_store import workspace,invite,join,role
    root=os.environ['REPOLENS_TEST_POSTGRES_URL'];admin=create_engine(root);schema='test_'+uuid.uuid4().hex
    with admin.begin() as c:c.execute(text('CREATE SCHEMA '+schema))
    target=make_url(root).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    try:
        source=tmp_path/'original';auth=AuthManager(directory=source,environ={});user=auth.upsert_user('github','original','Owner');token=auth.new_session(user['id'])
        original=ConversationStore('sqlite:///'+str(source/'conversations.sqlite3'));chat=original.create(user['id'],'pallets/flask','a'*40)
        _,lease,_=original.begin(user['id'],chat['id'],'pallets/flask',0);original.finish(chat['id'],lease,0,'Question',{'answer':'Answer','citations':[],'uncertain':True})
        assert migrate(source,target,apply=True)['applied']
        # Both independent Alembic histories must be current, even in one schema.
        statuses = upgrade_databases(target, target)
        assert statuses['auth']['up_to_date'] and statuses['app']['up_to_date']
        assert migration_status(target, target) == statuses
        postgres_auth=AuthManager(directory=tmp_path/'new',environ={'REPOLENS_AUTH_DATABASE_URL':target})
        assert postgres_auth.authenticate(token)['id']==user['id']
        postgres_auth.revoke(token);assert postgres_auth.authenticate(token) is None
        store=ConversationStore(target);assert store.get(user['id'],chat['id'])['version']==2
        wid=workspace(store.engine,user['id'],'Team');member=postgres_auth.upsert_user('google','member','Member')
        assert join(store.engine,member['id'],invite(store.engine,wid,user['id']))==wid
        assert role(store.engine,wid,member['id'])=='member'
        store.remove(user['id'],chat['id'])
        postgres_auth.sql_database.engine.dispose();store.engine.dispose()
    finally:
        with admin.begin() as c:c.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        admin.dispose()

@pytest.mark.skipif(not os.getenv('REPOLENS_TEST_POSTGRES_URL'), reason='No disposable PostgreSQL test service configured')
def test_real_postgres_section2_api_key_revoke_all_and_migration(tmp_path, monkeypatch):
    """Runs only against isolated, disposable PostgreSQL schema in CI or test branch."""
    from backend.auth.auth import AuthManager, COOKIE
    from backend.api.api import app
    from fastapi.testclient import TestClient
    from backend.database.schema_migrations import upgrade_databases
    root=os.environ['REPOLENS_TEST_POSTGRES_URL']; admin=create_engine(root)
    schema='auth2_'+uuid.uuid4().hex
    with admin.begin() as c: c.execute(text('CREATE SCHEMA '+schema))
    target=make_url(root).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    try:
        upgrade_databases(target,target)
        manager=AuthManager(directory=tmp_path/'auth',environ={'REPOLENS_AUTH_DATABASE_URL':target})
        monkeypatch.setattr(app.state,'auth',manager)
        user=manager.upsert_user('github','integration','Test')
        session=manager.new_session(user['id'])
        client=TestClient(app)
        client.cookies.set(COOKIE,session)
        client.headers['X-CSRF-Token']=manager.authenticate(session)['csrf']
        issued=client.post('/api/auth/keys',json={'name':'CI Postgres'})
        assert issued.status_code==201, issued.text
        token=issued.json()['key']
        assert TestClient(app).get('/api/history',headers={'Authorization':'Bearer '+token}).status_code==200
        assert client.delete('/api/auth/keys/'+issued.json()['id']).status_code==200
        assert manager.authenticate_api_key(token) is None
        assert client.delete('/api/auth/sessions/all').status_code==200
        assert manager.authenticate(session) is None
        manager.sql_database.engine.dispose()
    finally:
        with admin.begin() as c: c.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        admin.dispose()
