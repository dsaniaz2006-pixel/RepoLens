"""API-integration acceptance tests; run in the normal Mac/CI requirements environment.

These tests require Authlib and exercise actual FastAPI endpoints and SQLite,
while isolating only remote GitHub/Gemini/Chroma calls with explicit mocks.
"""
from types import SimpleNamespace


def second_user(auth_manager):
    from fastapi.testclient import TestClient
    from backend.api.api import app
    from backend.auth.auth import COOKIE
    user=auth_manager.upsert_user('github','phase-1-5-bob','Bob','bob@example.com')
    token=auth_manager.new_session(user['id'])
    client=TestClient(app)
    client.cookies.set(COOKIE,token)
    client.headers['X-CSRF-Token']=auth_manager.authenticate(token)['csrf']
    return client,user['id']


def test_shared_chats_are_revoked_through_real_api(signed_in_client,auth_manager,monkeypatch):
    from backend.api import product_api
    from backend.database import product_store
    import backend.services.pipeline as pipeline
    from backend.api.api import app
    from backend.database.conversations import request_store

    alice=signed_in_client
    bob,bob_id=second_user(auth_manager)
    owner_id=alice.get('/api/auth/me').json()['user']['id']
    wid=alice.post('/api/workspaces',json={'name':'Research'}).json()['id']
    token=alice.post(f'/api/workspaces/{wid}/invite').json()['token']
    assert bob.post('/api/workspaces/join',json={'token':token}).status_code==200

    db=product_store.engine(SimpleNamespace(app=app))
    source=product_store.put(db,owner_id,'repository',{
        'url':'https://github.com/o/r','repository':'o/r','revision':'a'*40})
    shared=alice.post(f'/api/workspaces/{wid}/repositories',
                     json={'repository_id':source['id']})
    assert shared.status_code==200
    monkeypatch.setattr(product_api,'resume_completed_index',lambda *a:True)
    thread=bob.post(f'/api/workspaces/{wid}/repositories/{shared.json()["id"]}/chat')
    assert thread.status_code==200
    chat=thread.json()
    assert chat['workspace_id']==wid

    monkeypatch.setattr(pipeline,'retrieve',lambda *a:[{'path':'app.py'}])
    monkeypatch.setattr(pipeline,'answer_question',lambda *a,**k:{
        'answer':'Function is in app.py','citations':[{'path':'app.py','start_line':1,'end_line':4}],
        'uncertain':False})
    response=bob.post('/api/ask',json={'url':'https://github.com/o/r',
        'question':'Where is the handler?','conversation_id':chat['id'],'version':0})
    assert response.status_code==200
    assert len(response.json()['messages'])==2
    assert bob.get(f'/api/conversations/{chat["id"]}/messages').status_code==200
    assert alice.delete(f'/api/workspaces/{wid}/members/{bob_id}').status_code==200
    assert all(c['id']!=chat['id'] for c in bob.get('/api/conversations').json())
    assert bob.get(f'/api/conversations/{chat["id"]}/messages').status_code==404
    assert bob.post('/api/ask',json={'url':'https://github.com/o/r',
        'question':'Follow-up','conversation_id':chat['id'],'version':2}).status_code==404
    assert bob.delete(f'/api/conversations/{chat["id"]}').status_code==404


def test_pins_cannot_cross_unshared_repository(signed_in_client,auth_manager):
    from backend.database import product_store
    from backend.database.conversations import request_store
    from backend.api.api import app
    alice=signed_in_client
    bob,bob_id=second_user(auth_manager)
    wid=alice.post('/api/workspaces',json={'name':'Only repo A'}).json()['id']
    token=alice.post(f'/api/workspaces/{wid}/invite').json()['token']
    assert bob.post('/api/workspaces/join',json={'token':token}).status_code==200
    db=product_store.engine(SimpleNamespace(app=app))
    product_store.put(db,wid,'shared_repository',{'repository':'o/r','revision':'a'*40})
    store=request_store(SimpleNamespace(app=app))
    outsider_chat=store.create(bob_id,'other/repo','b'*40)
    _,lease,_=store.begin(bob_id,outsider_chat['id'],'other/repo',0)
    store.finish(outsider_chat['id'],lease,0,'question',{
        'answer':'Evidence','citations':[{'path':'README.md','start_line':1,'end_line':1}],
        'uncertain':False})
    assistant=store.get(bob_id,outsider_chat['id'])['messages'][1]
    response=bob.post(f'/api/workspaces/{wid}/pins',json={
        'conversation_id':outsider_chat['id'],'message_id':assistant['id']})
    assert response.status_code==403
    own_chat=store.create(bob_id,'o/r','a'*40,workspace_id=wid)
    _,lease,_=store.begin(bob_id,own_chat['id'],'o/r',0)
    store.finish(own_chat['id'],lease,0,'question',{
        'answer':'Verified','citations':[{'path':'app.py','start_line':1,'end_line':2}],
        'uncertain':False})
    assistant=store.get(bob_id,own_chat['id'])['messages'][1]
    response=bob.post(f'/api/workspaces/{wid}/pins',json={
        'conversation_id':own_chat['id'],'message_id':assistant['id']})
    assert response.status_code==200
    assert response.json()['data']['revision']=='a'*40


def test_freshness_and_diff_routes_persist_results(signed_in_client,monkeypatch):
    from backend.api.api import app
    from backend.database import product_store
    from backend.services import freshness,pr_analysis
    from backend.api.product_api import track_index
    owner=signed_in_client.get('/api/auth/me').json()['user']['id']
    db=product_store.engine(SimpleNamespace(app=app))
    entry=track_index(db,owner,'https://github.com/o/r',{
        'revision':'a'*40, 'default_branch':'develop'})
    checked=[]
    monkeypatch.setattr(freshness,'fetch_commit_sha',lambda o,r,branch:checked.append(branch) or 'b'*40)
    response=signed_in_client.post(f'/api/repositories/{entry["id"]}/check')
    assert response.status_code==200 and response.json()['is_stale']
    assert checked==['develop']
    monkeypatch.setattr(pr_analysis,'analyze_diff',lambda *a:{
        'repository':'o/r','revision':'b'*40,'summary':'Auth routes changed',
        'changes':[{'path':'app.py','impact':'New route','test_suggestion':'Run endpoint tests'}],
        'coverage':{'analyzed_files':1,'eligible_files':1,'model_batches':1},
        'limits':[]})
    report=signed_in_client.post('/api/diff',json={
        'url':'https://github.com/o/r','base':'main','head':'develop'})
    assert report.status_code==200
    assert signed_in_client.get('/api/insights/diff').json()[0]['id']==report.json()['id']
