"""Section 5 real FastAPI HTTP/database integration (remote AI/GitHub mocked).

The OAuth client is not exercised in these tests. On stripped-offline runners
without Authlib, a test-only OAuth constructor replaces that dependency;
production sign-in must still be tested with actual Authlib on the user's Mac.
"""
import sys
from types import ModuleType
import pytest
from fastapi.testclient import TestClient

SHA='b'*40
REPO='pallets/flask'
ANSWER={'answer':'The route is defined here.',
        'citations':[{'path':'src/flask/app.py','start_line':11,'end_line':13}],
        'uncertain':False}


@pytest.fixture
def http_demo(tmp_path,monkeypatch):
    try:
        from authlib.integrations.starlette_client import OAuth  # noqa: F401
    except ImportError:
        # Strictly testing app APIs with synthetic sessions, never OAuth flows.
        for key in ('authlib','authlib.integrations','authlib.integrations.starlette_client'):
            module=ModuleType(key)
            if key.endswith('starlette_client'):
                module.OAuth=type('DisabledOAuthForOfflineTest', (),
                    {'register':lambda *a,**k:None})
            monkeypatch.setitem(sys.modules,key,module)
    # Install disposable DB environment BEFORE importing api.py, which
    # initializes the auth manager eagerly. Never touch the user's real Neon.
    database='sqlite:///'+str(tmp_path/'application.sqlite3')
    monkeypatch.setenv('REPOLENS_DATABASE_URL',database)
    monkeypatch.setenv('REPOLENS_AUTH_DATABASE_URL','sqlite:///'+str(tmp_path/'startup_auth.sqlite3'))
    monkeypatch.setenv('REPOLENS_ENV','development')
    monkeypatch.setenv('REPOLENS_BASE_URL','http://127.0.0.1:5173')
    from backend.api.api import app
    from backend.auth.auth import AuthManager, COOKIE
    import backend.services.pipeline as pipeline
    from backend.database.conversations import store_for
    import backend.database.conversations as conversation_db

    mgr=AuthManager(directory=tmp_path/'auth',environ={})
    monkeypatch.setattr(app.state,'auth',mgr)
    monkeypatch.setattr(pipeline,'fetch_repo_metadata',lambda *args:{'default_branch':'main','private':False})
    monkeypatch.setattr(pipeline,'fetch_commit_sha',lambda *args:SHA)
    monkeypatch.setattr(pipeline,'resume_completed_index',lambda *args:True)
    retrievals=[];contexts=[]
    monkeypatch.setattr(pipeline,'retrieve',lambda repo,revision,question:retrievals.append((repo,revision,question)) or [{'path':'src/flask/app.py','start_line':11,'end_line':13,'text':'def route(): pass'}])
    monkeypatch.setattr(pipeline,'answer_question',lambda question,evidence,history:contexts.append(history) or ANSWER)
    users=[mgr.upsert_user('github',uid,uid) for uid in ('alice','bob')]
    clients=[]
    for user in users:
        token=mgr.new_session(user['id'])
        client=TestClient(app)
        client.cookies.set(COOKIE,token)
        client.headers['X-CSRF-Token']=mgr.authenticate(token)['csrf']
        clients.append(client)
    yield mgr,app,clients,users,retrievals,contexts,database
    store_for.cache_clear()


def test_api_two_users_cannot_list_read_ask_or_delete_each_others_chats(http_demo):
    mgr,app,clients,users,retrievals,contexts,db=http_demo
    alice,bob=clients
    new=alice.post('/api/conversations',json={'url':f'https://github.com/{REPO}'})
    assert new.status_code==200,new.text
    cid=new.json()['id']
    reply=alice.post('/api/ask',json={'url':f'https://github.com/{REPO}',
        'question':'Where is the route?','conversation_id':cid,'version':0})
    assert reply.status_code==200,reply.text
    assert len(reply.json()['messages'])==2
    assert reply.json()['messages'][1]['citations']==ANSWER['citations']
    assert all(x['id']!=cid for x in bob.get('/api/conversations').json())
    for method,url,kwargs in [
        (bob.get,f'/api/conversations/{cid}/messages',{}),
        (bob.delete,f'/api/conversations/{cid}',{}),
        (bob.post,'/api/ask',{'json':{'url':f'https://github.com/{REPO}',
                                     'conversation_id':cid,'version':2,'question':'What did they say?'}})]:
        response=method(url,**kwargs)
        assert response.status_code==404,response.text
    assert len(retrievals)==1
    assert alice.get(f'/api/conversations/{cid}/messages').json()['version']==2


def test_api_refresh_and_restart_retain_messages_and_pinned_citations(http_demo, tmp_path, monkeypatch):
    mgr,app,clients,users,retrievals,contexts,db=http_demo
    alice=clients[0]
    cid=alice.post('/api/conversations',json={'url':f'https://github.com/{REPO}'}).json()['id']
    for version,question in [(0,'Where is the route?'),(2,'How does it handle dispatch?')]:
        response=alice.post('/api/ask',json={'url':f'https://github.com/{REPO}',
            'question':question,'conversation_id':cid,'version':version})
        assert response.status_code==200,response.text
    assert 'Previous question: Where is the route?' in retrievals[1][2]
    from backend.database.conversations import store_for
    store_for.cache_clear()  # Simulate process restart, not an in-memory cache hit.
    after=alice.get(f'/api/conversations/{cid}/messages')
    assert after.status_code==200
    assert after.json()['version']==4
    assert after.json()['revision']==SHA
    assert [m['role'] for m in after.json()['messages']]==['user','assistant','user','assistant']
    assert after.json()['messages'][3]['citations']==ANSWER['citations']
    assert any(x['id']==cid for x in alice.get('/api/conversations').json())
    # A stale browser version is never allowed to overwrite saved turns.
    conflict=alice.post('/api/ask',json={'url':f'https://github.com/{REPO}',
        'question':'Stale','conversation_id':cid,'version':0})
    assert conflict.status_code==409
    assert alice.get(f'/api/conversations/{cid}/messages').json()['version']==4


def test_sessionless_attempts_do_not_expose_conversations(http_demo):
    mgr,app,clients,users,retrievals,contexts,db=http_demo
    cid=clients[0].post('/api/conversations',json={'url':f'https://github.com/{REPO}'}).json()['id']
    outsider=TestClient(app)
    assert outsider.get('/api/conversations').status_code==401
    assert outsider.get(f'/api/conversations/{cid}/messages').status_code==401
    assert outsider.post('/api/ask',json={'url':f'https://github.com/{REPO}',
        'question':'what?','conversation_id':cid,'version':0}).status_code==401
    assert retrievals==[]
