"""Acceptance regressions for invitation URLs, independent assignments and private source."""
import json,time
from pathlib import Path
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,update,select
import backend.database.product_store as store

@pytest.fixture
def db(tmp_path):
    db=create_engine('sqlite:///'+str(tmp_path/'state.db'))
    store.metadata.create_all(db)
    return db

def seed(db):
    wid=store.workspace(db,'manager','Engineering')
    for user in ('alice','bob'):store.join(db,user,store.invite(db,wid,'manager'))
    row=store.put(db,'manager','checklist',{'repository':'o/r','revision':'a'*40,'tasks':[{'id':'read','done':True,'task':'Read source'}],'first_contribution':{'task':'Investigate'}})
    return wid,row

def test_invitation_preview_never_joins_and_distinguishes_errors(db):
    wid=store.workspace(db,'manager','Engineering');token=store.invite(db,wid,'manager')
    assert store.preview_invite(db,token)['name']=='Engineering'
    with pytest.raises(HTTPException):store.role(db,wid,'alice')
    store.join(db,'alice',token)
    with pytest.raises(HTTPException,match='already used'):store.preview_invite(db,token)
    token=store.invite(db,wid,'manager')
    with db.begin() as c:c.execute(update(store.invites).values(expires=0))
    with pytest.raises(HTTPException,match='expired'):store.preview_invite(db,token)
    with pytest.raises(HTTPException,match='Invalid'):store.preview_invite(db,'invalid')

def test_invitation_concurrent_redemption_one_winner(db):
    from concurrent.futures import ThreadPoolExecutor
    wid=store.workspace(db,'manager','Engineering');token=store.invite(db,wid,'manager')
    def redeem(user):
        try:store.join(db,user,token);return True
        except HTTPException:return False
    with ThreadPoolExecutor(2) as pool:assert sum(pool.map(redeem,['alice','bob']))==1

def test_invitation_http_url_and_csrf(signed_in_client):
    c=signed_in_client
    wid=c.post('/api/workspaces',json={'name':'Join test'}).json()['id']
    invite=c.post(f'/api/workspaces/{wid}/invite').json()
    assert '/join?token='+invite['token'] in invite['url']
    assert c.get('/join?token='+invite['token']).status_code==200
    assert c.get('/api/invitations/'+invite['token']).json()['name']=='Join test'
    assert c.post('/api/workspaces/join',json={'token':invite['token']},headers={'X-CSRF-Token':''}).status_code==403
    assert c.post('/api/workspaces/join',json={'token':invite['token']}).status_code==200
    assert c.post('/api/workspaces/join',json={'token':invite['token']}).status_code==400

def test_assignments_independent_versioned_persistent_and_authorized(db):
    wid,source=seed(db)
    a=store.assign_checklist(db,'manager',wid,source['id'],'alice')
    b=store.assign_checklist(db,'manager',wid,source['id'],'bob')
    store.complete_assignment(db,'alice',wid,a['id'],'read',True)
    assert store.own(db,wid,b['id'])['data']['snapshot']['tasks'][0]['done'] is False
    assert store.own(db,wid,a['id'])['data']['snapshot']['revision']=='a'*40
    source['data']['revision']='b'*40
    with db.begin() as c:c.execute(update(store.items).where(store.items.c.id==source['id']).values(data=source['data']))
    reopened=create_engine(str(db.url))
    assert store.own(reopened,wid,a['id'])['data']['snapshot']['revision']=='a'*40
    assert len(store.assignments(db,'alice',wid))==1
    assert len(store.assignments(db,'manager',wid))==2
    with pytest.raises(HTTPException):store.complete_assignment(db,'bob',wid,a['id'],'read',False)
    with pytest.raises(HTTPException):store.assign_checklist(db,'alice',wid,source['id'],'bob')
    with pytest.raises(HTTPException):store.assign_checklist(db,'manager',wid,source['id'],'outsider')
    with pytest.raises(HTTPException):store.assignments(db,'outsider',wid)

def test_member_removal_closes_assignment(signed_in_client,auth_manager):
    c=signed_in_client;wid=c.post('/api/workspaces',json={'name':'Team'}).json()['id']
    import backend.api.api as api
    from types import SimpleNamespace
    db=store.engine(SimpleNamespace(app=api.app));manager=c.get('/api/auth/me').json()['user']['id']
    store.join(db,'alice',store.invite(db,wid,manager))
    source=store.put(db,manager,'checklist',{'repository':'o/r','revision':'a'*40,'tasks':[{'id':'read','done':False}]})
    assignment=store.assign_checklist(db,manager,wid,source['id'],'alice')
    assert c.delete(f'/api/workspaces/{wid}/members/alice').status_code==200
    store.join(db,'alice',store.invite(db,wid,manager))
    with pytest.raises(HTTPException,match='closed'):store.complete_assignment(db,'alice',wid,assignment['id'],'read',True)

@pytest.fixture
def local(tmp_path,monkeypatch):
    import backend.core.config as config
    monkeypatch.setenv('REPOLENS_MODEL_PROVIDER','ollama');monkeypatch.setattr(config,'EMBEDDING_MODEL','ollama:test')
    folder=tmp_path/'repo';folder.mkdir();(folder/'main.py').write_text('def main():\n    return 42\n')
    monkeypatch.setenv('REPOLENS_LOCAL_REPOSITORIES',json.dumps({'demo':{'path':str(folder),'users':['alice']}}))
    return folder

def test_local_stable_snapshots_and_account_allowlist(local):
    from backend.github.local_repositories import collect
    a=collect('demo','alice');b=collect('demo','alice')
    assert a['revision']==b['revision'] and a['repo_id']==b['repo_id']
    (local/'main.py').write_text('def main():\n    return 43\n')
    c=collect('demo','alice');assert c['repo_id']==a['repo_id'] and c['revision']!=a['revision']
    for alias,user in [('demo','bob'),('../repo','alice'),('/etc','alice')]:
        with pytest.raises(ValueError,match='approved'):collect(alias,user)

def test_local_symlinks_hardlinks_secrets_and_builds_filtered(local,tmp_path):
    from backend.github.local_repositories import collect
    (local/'.env').write_text('SECRET=value');(local/'credentials.py').write_text('x=1')
    (local/'node_modules').mkdir();(local/'node_modules'/'lib.py').write_text('x=1')
    outside=tmp_path/'outside.py';outside.write_text('outside=1')
    (local/'link.py').symlink_to(outside);(local/'escape').symlink_to(tmp_path,target_is_directory=True)
    import os
    os.link(outside,local/'hard.py')
    assert [r['path'] for r in collect('demo','alice')['records']]==['main.py']

def test_local_cloud_rejected_before_source_or_provider(local,monkeypatch):
    from backend.github.local_repositories import collect
    monkeypatch.setenv('REPOLENS_MODEL_PROVIDER','gemini')
    with pytest.raises(ValueError,match='require'):collect('demo','alice')

def test_local_question_uses_snapshot_paths_not_github(local,monkeypatch):
    import backend.github.local_repositories as lr, backend.rag.retriever as retriever, backend.ai.qa as qa
    data=lr.collect('demo','alice');data['repository']=data['repo_id']
    calls=[]
    monkeypatch.setattr(retriever,'retrieve',lambda repo,rev,q:calls.append((repo,rev,q)) or [])
    monkeypatch.setattr(qa,'answer_question',lambda q,c:{'answer':'Evidence unavailable','citations':[],'uncertain':True})
    assert lr.ask(data,'alice','question')['citation_type']=='local_path'
    assert calls==[(data['repository'],data['revision'],'question')]
    with pytest.raises(ValueError):lr.ask(data,'bob','question')

def test_scanner_preserves_markers_and_discloses_package_cap():
    from backend.services.security_scanner import scan
    result=scan([{'path':'requirements.txt','content':'\n'.join(f'p{i}==1; python_version < "3.12"' for i in range(62))}],advisory_get=lambda *a,**k:[])
    assert result['dependencies'][0]['marker']=='python_version < "3.12"'
    assert result['coverage']['packages_discovered']==62
    assert result['coverage']['packages_checked']==60
    assert not result['coverage']['complete'] and not result['coverage']['advisory_complete']

def test_scanner_full_advisory_page_is_partial():
    from backend.services.security_scanner import scan
    result=scan([{'path':'requirements.txt','content':'requests==1'}],advisory_get=lambda *a,**k:[{}]*100)
    assert result['dependencies'][0]['check_status']=='partial'
    assert not result['coverage']['advisory_complete']

def test_freshness_index_change_reindex_cycle(db,monkeypatch):
    from backend.api.product_api import track_index
    from backend.services.freshness import check
    first=track_index(db,'alice','https://github.com/o/r',{'revision':'a'*40})
    assert check(db,first,lookup=lambda *a:'a'*40)['is_stale'] is False
    current=store.own(db,'alice',first['id'])
    assert check(db,current,lookup=lambda *a:'b'*40)['is_stale'] is True
    refreshed=track_index(db,'alice','https://github.com/o/r',{'revision':'b'*40})
    assert refreshed['data']['previous_revision']=='a'*40
    assert check(db,refreshed,lookup=lambda *a:'b'*40)['is_stale'] is False

def test_lockfile_same_version_platform_variants_are_distinct():
    from backend.services.dependency_graphs import graphs
    content='[[package]]\nname="a"\nversion="1.0"\nsource={registry="one"}\n[[package]]\nname="a"\nversion="1.0"\nsource={registry="two"}\n'
    graph=graphs([{'path':'uv.lock','content':content}])
    assert len({n['id'] for n in graph['nodes']})==2

def test_environment_export_without_platform_does_not_guess_marker():
    from backend.services.dependency_graphs import graphs
    payload={'installed':[{'metadata':{'name':'a','version':'1','requires_dist':['b; sys_platform == "win32"']}}]}
    result=graphs([{'path':'repolens-pip-inspect.json','content':json.dumps(payload)}])
    assert result['edges'][0]['active'] is None
    assert any('missing' in x for x in result['limits'])
