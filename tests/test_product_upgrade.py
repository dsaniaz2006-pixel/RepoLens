import pytest
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import create_engine
import backend.database.product_store as store

@pytest.fixture
def db(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'products.db'))
    store.metadata.create_all(engine)
    return engine

def test_workspace_invite_single_use_and_access(db):
    wid=store.workspace(db,'alice','Team')
    with pytest.raises(HTTPException):store.role(db,wid,'bob')
    token=store.invite(db,wid,'alice');assert store.join(db,'bob',token)==wid
    assert store.role(db,wid,'bob')=='member'
    with pytest.raises(HTTPException):store.invite(db,wid,'bob')
    with pytest.raises(HTTPException):store.join(db,'carol',token)
    assert store.role(db,wid,'alice')=='owner'

def test_private_results_cannot_be_read_by_team_member(db):
    wid=store.workspace(db,'alice','Team');store.join(db,'bob',store.invite(db,wid,'alice'))
    item=store.put(db,'alice','checklist',{'tasks':[]})
    with pytest.raises(HTTPException):store.own(db,'bob',item['id'])
    assert store.listing(db,'bob','checklist')==[]

def test_freshness_changes_and_network_error(db,monkeypatch):
    import backend.services.freshness as freshness
    row=store.put(db,'alice','repository',{'url':'https://github.com/o/r','revision':'a'*40})
    monkeypatch.setattr(freshness,'fetch_commit_sha',lambda *a:'b'*40)
    assert freshness.check(db,row)['is_stale'] is True
    def fail(*a):raise ValueError('secret provider error')
    monkeypatch.setattr(freshness,'fetch_commit_sha',fail)
    nextrow=store.own(db,'alice',row['id'])
    status=freshness.check(db,nextrow)
    assert status['is_stale'] is True and 'secret' not in status['error']

def test_scanner_exact_versions_ranges_and_unavailable():
    from backend.services.security_scanner import scan
    records=[{'path':'requirements.txt','content':'requests==2.0.0\nflask>=2\n-r other.txt'}, {'path':'a.py','content':'import requests\neval(value)\nsubprocess.run(args, shell=False)\nsubprocess.run(args, shell=True)'}]
    def get(path,context,params):
        if params['affects']=='flask':raise ValueError('offline')
        assert params['affects']=='requests@2.0.0'
        return [{'ghsa_id':'GHSA-test','severity':'high','vulnerabilities':[{'package':{'name':'requests'},'vulnerable_version_range':'<3','first_patched_version':'3'}]}]
    result=scan(records,advisory_get=get)
    assert result['dependencies'][0]['advisories'][0]['status']=='affected'
    assert result['dependencies'][1]['check_status']=='unavailable'
    assert len(result['patterns'])==2 and result['warnings']

def test_flow_marks_cross_file_calls_inferred_and_does_not_execute():
    from backend.services.code_flow import trace
    result=trace([{'path':'main.py','content':'def main():\n    helper()\ndef helper():\n    remote()\n'}, {'path':'lib.py','content':'def remote():\n    return 1\n'}])
    assert [e['link_type'] for e in result['edges']]==['CONFIRMED','INFERRED']
    assert 'flowchart TD' in result['mermaid'] and result['edges'][0]['line']==2

def test_pr_validation_and_citation_paths(monkeypatch):
    import backend.services.pr_analysis as pr
    monkeypatch.setattr(pr,'fetch_repo_metadata',lambda *a:{'private':False})
    def get(path,*a,**k):
        if path.endswith('/files'):return [{'filename':'app.py','patch':'+ def main(): pass','status':'modified'}]
        return {'head':{'sha':'a'*40},'base':{'sha':'b'*40},'body':'Update','changed_files':1}
    monkeypatch.setattr(pr,'_get',get)
    monkeypatch.setattr(pr,'json_model',lambda p:{'summary':'Change','changes':[{'path':'fake.py','impact':'x','test_suggestion':'y'}]})
    with pytest.raises(ValueError):pr.analyze_diff('https://github.com/o/r',1)
    monkeypatch.setattr(pr,'json_model',lambda p:{'summary':'Change','changes':[{'path':'app.py','impact':'x','test_suggestion':'y'}]})
    assert pr.analyze_diff('https://github.com/o/r',1)['unmentioned_paths']==['app.py']

def test_ollama_never_uses_gemini(monkeypatch):
    import backend.ai.model_provider as provider
    import backend.rag.embeddings as embeddings
    monkeypatch.setenv('REPOLENS_MODEL_PROVIDER','ollama')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    calls=[]
    def local(route,payload):
        calls.append(route)
        return {'response':'{"answer":"local"}'} if route=='/api/generate' else {'embeddings':[[1.0,2.0]]}
    monkeypatch.setattr(provider,'local_request',local)
    assert provider.json_model('test')['answer']=='local'
    assert embeddings.embed_texts(['a'])==[[1.0,2.0]]
    assert calls==['/api/generate','/api/embed']

def test_embedding_cache_reuses_completed_batches(tmp_path,monkeypatch):
    import backend.rag.embedding_cache as cache
    monkeypatch.setenv('REPOLENS_EMBED_CACHE_DIR',str(tmp_path))
    calls=[]
    def generate(texts):calls.append(texts);return [[float(len(t))] for t in texts]
    assert cache.cached_embeddings(['a','b','a'],'doc','model',generate)==[[1.0],[1.0],[1.0]]
    assert cache.cached_embeddings(['a'],'doc','model',generate)==[[1.0]]
    assert calls==[['a','b']]
    cache.cached_embeddings(['a'],'query','model',generate)
    assert len(calls)==2

def test_checklist_api_persistence_pdf_and_access(signed_in_client,monkeypatch):
    import backend.api.product_api as product_api
    monkeypatch.setattr(product_api,'collect_repo',lambda *a,**k:{'repo_id':'o/r','revision':'a'*40,'records':[{'path':'app.py','content':'print(1)'}]})
    import backend.services.onboarding as onboarding
    monkeypatch.setattr(onboarding,'json_model',lambda prompt:{'day_1':[{'task':'Inspect output','file':'app.py','line':1,'why':'Trace the output','snippet':'print(1)'}],'week_1':[{'task':'Investigate output testing','file':'app.py','line':1,'why':'Find expected behavior','snippet':'print(1)'}],'first_contribution':{'task':'Investigate test coverage','files':['app.py'],'assumptions':['Maintainer review required']}})
    client=signed_in_client
    result=client.post('/api/checklists',json={'url':'https://github.com/o/r'})
    assert result.status_code==200
    item=result.json()
    assert client.post('/api/checklists/'+item['id']+'/complete',json={'task_id':item['data']['tasks'][0]['id'],'done':True}).json()['tasks'][0]['done']
    assert client.get('/api/checklists/'+item['id']+'/pdf').content.startswith(b'%PDF')
    assert client.get('/api/insights/checklist').json()[0]['data']['tasks'][0]['done']

def _create_checklist(client,monkeypatch):
    import backend.services.onboarding as onboarding
    import backend.api.product_api as product_api
    monkeypatch.setattr(product_api,'collect_repo',lambda *a,**k:{'repo_id':'o/r','revision':'a'*40,'records':[{'path':'app.py','content':'print(1)'}]})
    monkeypatch.setattr(onboarding,'json_model',lambda prompt:{'day_1':[{'task':'Inspect output','file':'app.py','line':1,'why':'Trace the output','snippet':'print(1)'}],'week_1':[{'task':'Investigate output testing','file':'app.py','line':1,'why':'Find expected behavior','snippet':'print(1)'}],'first_contribution':{'task':'Investigate test coverage','files':['app.py'],'assumptions':['Maintainer review required']}})
    response=client.post('/api/checklists',json={'url':'https://github.com/o/r'})
    assert response.status_code==200
    return response.json()

def test_public_checklist_share_is_read_only_and_exposes_only_checklist_content(signed_in_client,auth_manager,monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import select,update
    import backend.api.api as api
    import backend.database.product_store as store
    from backend.database.conversations import request_store
    item=_create_checklist(signed_in_client,monkeypatch)
    db=request_store(SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(auth=auth_manager)))).engine
    private={'account_id':'private-account','conversation_id':'private-conversation','session_data':'private-session','api_key':'private-api-key','internal_record':'private-db-record'}
    data=item['data']|private
    data['tasks'][0].update(private)
    data['first_contribution'].update(private)
    with db.begin() as connection:
        connection.execute(update(store.items).where(store.items.c.id==item['id']).values(data=data))
    link=signed_in_client.post('/api/checklists/'+item['id']+'/share')
    assert link.status_code==200
    token=link.json()['token']
    share=signed_in_client.get('/api/checklists/'+item['id']+'/share')
    assert share.json()=={'active':True}
    with db.connect() as connection:
        stored_hash=connection.execute(select(store.checklist_shares.c.token_hash).where(store.checklist_shares.c.checklist_id==item['id'])).scalar_one()
    assert stored_hash!=token and len(stored_hash)==64
    anonymous=TestClient(api.app)
    response=anonymous.get('/api/public/checklists/'+token)
    assert response.status_code==200
    public=response.json()
    assert set(public)=={'repository','revision','tasks','first_contribution'}
    assert set(public['tasks'][0])=={'phase','task','path','line','end_line','why','snippet','done'}
    assert set(public['first_contribution'])=={'task','files','assumptions'}
    serialized=response.text
    assert all(value not in serialized for value in private.values())
    assert anonymous.get('/api/workspaces?token='+token).status_code==401

def test_public_checklist_share_rejects_invalid_token(signed_in_client):
    from fastapi.testclient import TestClient
    import backend.api.api as api
    response=TestClient(api.app).get('/api/public/checklists/not-a-valid-share-token')
    assert response.status_code==404

def test_revoking_checklist_share_immediately_invalidates_link(signed_in_client,monkeypatch):
    from fastapi.testclient import TestClient
    import backend.api.api as api
    item=_create_checklist(signed_in_client,monkeypatch)
    token=signed_in_client.post('/api/checklists/'+item['id']+'/share').json()['token']
    anonymous=TestClient(api.app)
    assert anonymous.get('/api/public/checklists/'+token).status_code==200
    assert signed_in_client.delete('/api/checklists/'+item['id']+'/share').json()=={'revoked':True}
    assert anonymous.get('/api/public/checklists/'+token).status_code==404
    assert signed_in_client.get('/api/checklists/'+item['id']+'/share').json()=={'active':False}

def test_replacing_checklist_share_invalidates_previous_link(signed_in_client,monkeypatch):
    from fastapi.testclient import TestClient
    import backend.api.api as api
    item=_create_checklist(signed_in_client,monkeypatch)
    first=signed_in_client.post('/api/checklists/'+item['id']+'/share').json()['token']
    second=signed_in_client.post('/api/checklists/'+item['id']+'/share').json()['token']
    anonymous=TestClient(api.app)
    assert first!=second
    assert anonymous.get('/api/public/checklists/'+first).status_code==404
    assert anonymous.get('/api/public/checklists/'+second).status_code==200

def test_only_checklist_owner_can_create_or_revoke_share(signed_in_client,auth_manager,monkeypatch):
    from fastapi.testclient import TestClient
    import backend.api.api as api
    from backend.auth.auth import COOKIE
    item=_create_checklist(signed_in_client,monkeypatch)
    bob=auth_manager.upsert_user('github','456','Other user','other@example.com')
    session=auth_manager.new_session(bob['id'])
    other=TestClient(api.app)
    other.cookies.set(COOKIE,session)
    other.headers['X-CSRF-Token']=auth_manager.authenticate(session)['csrf']
    assert other.post('/api/checklists/'+item['id']+'/share').status_code==404
    token=signed_in_client.post('/api/checklists/'+item['id']+'/share').json()['token']
    assert other.delete('/api/checklists/'+item['id']+'/share').status_code==404
    anonymous=TestClient(api.app)
    assert anonymous.post('/api/checklists/'+item['id']+'/share').status_code==401
    assert anonymous.delete('/api/checklists/'+item['id']+'/share').status_code==401
    assert anonymous.get('/api/public/checklists/'+token).status_code==200

def test_team_routes_and_member_role_guard(signed_in_client):
    client=signed_in_client
    wid=client.post('/api/workspaces',json={'name':'Team'}).json()['id']
    assert client.get('/api/workspaces/'+wid).json()['role']=='owner'
    assert len(client.post('/api/workspaces/'+wid+'/invite').json()['token'])>20
    assert client.get('/api/workspaces/nonexistent').status_code==403

def test_dependency_graph_resolves_transitive_npm_packages():
    import json
    from backend.services.security_scanner import dependency_graph
    lock={'name':'demo','packages':{'':{'dependencies':{'a':'^1'}},'node_modules/a':{'version':'1.0.0','dependencies':{'b':'^2'}},'node_modules/b':{'version':'2.0.0'}}}
    result=dependency_graph([{'path':'package-lock.json','content':json.dumps(lock)}])
    assert len(result['nodes'])==3
    assert result['edges'][1]['to']=='package-lock.json:node_modules/b'

def test_embedding_cache_partial_failure_resumes(tmp_path,monkeypatch):
    import backend.rag.embedding_cache as cache
    monkeypatch.setenv('REPOLENS_EMBED_CACHE_DIR',str(tmp_path))
    # Faster batching now packs more chunks per request; use a lower test-only
    # TPM to exercise a two-batch partial failure and resume explicitly.
    monkeypatch.setenv('REPOLENS_EMBED_TPM','6000');calls=[]
    def generate(texts):
        calls.append(texts)
        if len(calls)==2:raise ValueError('offline')
        return [[1.0] for _ in texts]
    texts=['a'*4100,'b'*4100]
    with pytest.raises(ValueError):cache.cached_embeddings(texts,'doc','model',generate)
    result=cache.cached_embeddings(texts,'doc','model',generate)
    assert result==[[1.0],[1.0]] and calls[-1]==[texts[1]]

def test_quota_budget_waits_without_exceeding_rpm(tmp_path,monkeypatch):
    import backend.rag.embedding_cache as cache
    monkeypatch.setenv('REPOLENS_EMBED_CACHE_DIR',str(tmp_path));monkeypatch.setenv('REPOLENS_EMBED_RPM','1')
    clock=[100.0];wait=[]
    monkeypatch.setattr(cache.time,'time',lambda:clock[0])
    def pause(seconds):wait.append(seconds);clock[0]+=seconds
    monkeypatch.setattr(cache,'pause',pause)
    cache.reserve(10);cache.reserve(10)
    assert sum(wait)>=60

def test_local_provider_rejects_remote_endpoint(monkeypatch):
    import backend.ai.model_provider as provider
    monkeypatch.setenv('OLLAMA_URL','https://example.com')
    with pytest.raises(ValueError,match='loopback'):provider.local_request('/api/generate',{})

def test_new_routes_require_authentication_and_csrf(signed_in_client):
    from fastapi.testclient import TestClient
    import backend.api.api as api
    anonymous=TestClient(api.app)
    for path in ('/api/workspaces','/api/repositories','/api/insights/checklist'):
        assert anonymous.get(path).status_code==401
    signed_in_client.headers.pop('X-CSRF-Token')
    assert signed_in_client.post('/api/workspaces',json={'name':'Team'}).status_code==403

def test_freshness_worker_lifecycle(auth_manager):
    from fastapi.testclient import TestClient
    import backend.api.api as api
    with TestClient(api.app) as client:
        assert client.get('/api/health').status_code==200
        task=api.app.state.freshness_worker
        assert not task.done()
    assert task.done()

def test_public_gallery_is_accessible_without_account(auth_manager):
    from fastapi.testclient import TestClient
    import backend.api.api as api
    client=TestClient(api.app)
    assert client.get('/gallery/').status_code==200
    page=client.get('/gallery/pallets-flask/')
    assert page.status_code==200 and 'Source snapshot — AI review pending' in page.text
    assert 'not an AI architecture analysis' in page.text

def test_team_member_cannot_read_owners_conversation(signed_in_client,auth_manager):
    from backend.database.conversations import request_store
    from types import SimpleNamespace
    import backend.api.api as api
    from backend.auth.auth import COOKIE
    from fastapi.testclient import TestClient
    owner=signed_in_client.get('/api/auth/me').json()['user']['id']
    chat=request_store(SimpleNamespace(app=api.app)).create(owner,'o/r','a'*40)
    wid=signed_in_client.post('/api/workspaces',json={'name':'Team'}).json()['id']
    token=signed_in_client.post('/api/workspaces/'+wid+'/invite').json()['token']
    user=auth_manager.upsert_user('github','456','Member','member@example.com');session=auth_manager.new_session(user['id'])
    member=TestClient(api.app);member.cookies.set(COOKIE,session);member.headers['X-CSRF-Token']=auth_manager.authenticate(session)['csrf']
    assert member.post('/api/workspaces/join',json={'token':token}).status_code==200
    assert member.get('/api/conversations/'+chat['id']+'/messages').status_code==404
    assert member.post('/api/workspaces/'+wid+'/invite').status_code==403
    assert member.post('/api/workspaces/'+wid+'/members/'+owner,json={'role':'member'}).status_code==403

def test_scanner_flags_dynamic_open_paths_but_not_literals():
    from backend.services.security_scanner import patterns

    records = [{
        "path": "files.py",
        "content": (
            'open("safe.txt")\n'
            'open(path)\n'
            'open(file=provided_path)\n'
            'other(path)\n'
        ),
    }]

    findings = patterns(records)

    dynamic_findings = [
        finding for finding in findings
        if finding["issue"].startswith("Dynamic file path:")
    ]

    assert len(dynamic_findings) == 2
    assert [finding["line"] for finding in dynamic_findings] == [2, 3]
    assert all(
        finding["status"] == "review_required"
        for finding in dynamic_findings
    )
