import pytest
from fastapi import HTTPException
from backend.database.conversations import ConversationStore, answer_turn

@pytest.fixture
def store(tmp_path): return ConversationStore('sqlite:///'+str(tmp_path/'chat.sqlite3'))

ANSWER={'answer':'Source-backed answer','citations':[{'path':'app.py','start_line':1,'end_line':4}],'uncertain':False}

@pytest.mark.parametrize('repo',['pallets/flask','fastapi/fastapi','encode/httpx'])
def test_followups_persist_and_pin_revision(store,monkeypatch,repo):
    import backend.services.pipeline as pipeline
    chat=store.create('alice',repo,'a'*40)
    calls=[]
    monkeypatch.setattr(pipeline,'retrieve',lambda r,rev,q: calls.append((r,rev,q)) or [{'path':'app.py'}])
    histories=[]
    monkeypatch.setattr(pipeline,'answer_question',lambda q,c,history: histories.append(history) or ANSWER)
    for turn in range(8):
        chat=answer_turn(store,'alice',chat['id'],'https://github.com/'+repo,'Question '+str(turn),chat['version'])
    assert len(chat['messages'])==16
    assert len(histories[-1])==12
    assert [m['position'] for m in histories[-1]]==list(range(3,15))
    assert all(r==repo and rev=='a'*40 for r,rev,q in calls)
    assert calls[-1][2]=='Question 7'
    reopened=ConversationStore(str(store.engine.url)).get('alice',chat['id'])
    assert reopened==chat

def test_ownership_stale_version_and_delete(store):
    c=store.create('alice','o/r','a'*40)
    assert store.listing('bob')==[]
    for action in [lambda:store.get('bob',c['id']),lambda:store.remove('bob',c['id']),lambda:store.begin('bob',c['id'],'o/r',0)]:
        with pytest.raises(HTTPException) as e: action()
        assert e.value.status_code==404
    row,token,_=store.begin('alice',c['id'],'o/r',0)
    with pytest.raises(HTTPException): store.begin('alice',c['id'],'o/r',0)
    store.finish(c['id'],token,0,'first',ANSWER)
    with pytest.raises(HTTPException): store.begin('alice',c['id'],'o/r',0)
    _,token,_=store.begin('alice',c['id'],'o/r',2)
    store.remove('alice',c['id'])
    with pytest.raises(HTTPException): store.finish(c['id'],token,2,'next',ANSWER)
    assert store.listing('alice')==[]

def test_failure_releases_request_without_partial_messages(store,monkeypatch):
    import backend.services.pipeline as pipeline
    c=store.create('alice','o/r','a'*40)
    def fail(*args): raise ValueError('Provider unavailable')
    monkeypatch.setattr(pipeline,'retrieve',fail)
    with pytest.raises(ValueError): answer_turn(store,'alice',c['id'],'https://github.com/o/r','hello',0)
    result=store.get('alice',c['id'])
    assert result['messages']==[] and not result['pending'] and result['version']==0
    with pytest.raises(HTTPException): store.begin('alice',c['id'],'another/repo',0)

def test_api_auth_create_chat_and_delete(signed_in_client,monkeypatch):
    import backend.services.pipeline as pipeline
    monkeypatch.setattr(pipeline,'fetch_repo_metadata',lambda *a:{'default_branch':'main'})
    monkeypatch.setattr(pipeline,'fetch_commit_sha',lambda *a:'a'*40)
    monkeypatch.setattr(pipeline,'resume_completed_index',lambda *a: {'chunks':2})
    monkeypatch.setattr(pipeline,'retrieve',lambda *a:[{}])
    monkeypatch.setattr(pipeline,'answer_question',lambda *a,**k:ANSWER)
    client=signed_in_client
    c=client.post('/api/conversations',json={'url':'https://github.com/o/r'}).json()
    assert client.get('/api/conversations').json()[0]['id']==c['id']
    r=client.post('/api/ask',json={'url':'https://github.com/o/r','question':'what?','conversation_id':c['id'],'version':0})
    assert r.status_code==200 and len(r.json()['messages'])==2
    assert client.post('/api/ask',json={'url':'https://github.com/o/r','question':'what?','conversation_id':c['id'],'version':0}).status_code==409
    assert client.get('/api/conversations/'+c['id']+'/messages').json()['version']==2
    assert client.delete('/api/conversations/'+c['id']).status_code==200
    assert client.get('/api/conversations/'+c['id']+'/messages').status_code==404
    monkeypatch.setattr(pipeline,'resume_completed_index',lambda *a:None)
    assert client.post('/api/conversations',json={'url':'https://github.com/o/r'}).status_code==400

def test_expired_lease_cannot_overwrite_new_turn(store):
    from backend.database.conversations import chats
    c=store.create('alice','o/r','a'*40)
    _,old,_=store.begin('alice',c['id'],'o/r',0)
    with store.engine.begin() as conn: conn.execute(chats.update().values(lease_until=0))
    _,new,_=store.begin('alice',c['id'],'o/r',0)
    with pytest.raises(HTTPException): store.finish(c['id'],old,0,'old',ANSWER)
    store.release(c['id'],old)
    assert store.get('alice',c['id'])['pending']
    store.finish(c['id'],new,0,'new',ANSWER)
