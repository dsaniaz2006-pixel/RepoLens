import pytest,json
from pathlib import Path
from backend.services.onboarding import generate

DATA={'repo_id':'o/r','revision':'a'*40,'records':[{'path':'app.py','content':'# startup\ndef main():\n    run()\n'}]}
def payload():return {'day_1':[{'task':'Inspect startup','file':'app.py','line':2,'why':'Locate entry point','snippet':'def main():'}],'week_1':[{'task':'Trace delegated work','file':'app.py','line':3,'why':'Review the next call','snippet':'    run()'}],'first_contribution':{'task':'Investigate tests for startup','files':['app.py'],'assumptions':['Confirm coverage before changing code']}}

def test_onboarding_uses_verified_task_specific_lines():
    result=generate(DATA,model=lambda prompt:payload())
    assert [t['line'] for t in result['tasks']]==[2,3]
    assert result['generation']=='ai_with_verified_quotes'

@pytest.mark.parametrize('bad',['line','file','snippet'])
def test_onboarding_rejects_fabricated_evidence(bad):
    p=payload();p['day_1'][0][bad]={'line':1,'file':'fake.py','snippet':'def invented():'}[bad]
    with pytest.raises(ValueError):generate(DATA,model=lambda prompt:p)

def test_pr_uses_existing_file_selector_and_filters_secrets(monkeypatch):
    import backend.services.pr_analysis as pr
    from backend.services.file_selector import score_path
    monkeypatch.setattr(pr,'fetch_repo_metadata',lambda *a:{})
    files=[{'filename':'docs/huge.md','patch':'x','changes':99999},{'filename':'src/app.py','patch':'x','changes':1},{'filename':'.env','patch':'secret','changes':999999}]
    monkeypatch.setattr(pr,'_get',lambda path,*a,**k:files if path.endswith('/files') else {'head':{'sha':'a'*40},'base':{'sha':'b'*40},'body':'','changed_files':3})
    monkeypatch.setattr(pr,'json_model',lambda prompt:{'summary':'Review','changes':[]})
    result=pr.analyze_diff('https://github.com/o/r',1)
    assert [x['path'] for x in result['files']]==['src/app.py','docs/huge.md']
    assert result['files'][0]['selection_score']==score_path('src/app.py')

def test_auth_sqlalchemy_backend_preserves_identity_and_revocation(tmp_path):
    from backend.auth.auth import AuthManager
    auth=AuthManager(directory=tmp_path/'keys',environ={'REPOLENS_AUTH_DATABASE_URL':'sqlite:///'+str(tmp_path/'sql.db')})
    user=auth.upsert_user('github','123','A');updated=auth.upsert_user('github','123','B')
    assert updated['id']==user['id'] and updated['name']=='B'
    token=auth.new_session(user['id']);assert auth.authenticate(token)['id']==user['id']
    auth.revoke(token);assert auth.authenticate(token) is None

def test_migration_preserves_user_ids_chats_and_product_records(tmp_path):
    from backend.auth.auth import AuthManager
    from backend.database.conversations import ConversationStore
    import backend.database.product_store as product_store
    from backend.database.migrate_database import migrate
    folder=tmp_path/'source';auth=AuthManager(directory=folder,environ={});user=auth.upsert_user('github','1','A');token=auth.new_session(user['id'])
    chatstore=ConversationStore('sqlite:///'+str(folder/'conversations.sqlite3'))
    chat=chatstore.create(user['id'],'o/r','a'*40);row,lease,_=chatstore.begin(user['id'],chat['id'],'o/r',0)
    chatstore.finish(chat['id'],lease,0,'question',{'answer':'answer','citations':[],'uncertain':True})
    wid=product_store.workspace(chatstore.engine,user['id'],'Team')
    checklist=product_store.put(chatstore.engine,user['id'],'checklist',{'repository':'o/r','revision':'a'*40,'tasks':[],'first_contribution':{'task':'Investigate tests','files':['tests/test_app.py'],'assumptions':['Maintainer review required']}})
    share_token=product_store.create_checklist_share(chatstore.engine,user['id'],checklist['id'])
    target='sqlite:///'+str(tmp_path/'destination.db')
    preview=migrate(folder,target);assert not preview['applied'] and not (tmp_path/'destination.db').exists()
    result=migrate(folder,target,apply=True)
    assert result['counts']['users']==1 and result['counts']['checklist_shares']==1
    newauth=AuthManager(directory=tmp_path/'newkeys',environ={'REPOLENS_AUTH_DATABASE_URL':target})
    assert newauth.authenticate(token)['id']==user['id']
    target_store=ConversationStore(target)
    assert target_store.get(user['id'],chat['id'])['version']==2
    assert product_store.role(target_store.engine,wid,user['id'])=='owner'
    assert product_store.public_checklist(target_store.engine,share_token)['repository']=='o/r'
    with pytest.raises(ValueError):migrate(folder,target,apply=True)
    assert auth.authenticate(token)['id']==user['id']

def test_python_import_alias_and_method_flow():
    from backend.services.code_flow import trace
    records=[{'path':'main.py','content':'from service import work as execute\ndef main():\n    execute()\n'}, {'path':'service.py','content':'def work():\n    return 1\n'}]
    flow=trace(records);assert flow['edges'][0]['to']=='service.py:work'
    assert flow['edges'][0]['link_type']=='CONFIRMED'
    method=trace([{'path':'x.py','content':'class App:\n    def start(self):\n        self.run()\n    def run(self):\n        return 1\n'}])
    assert method['edges'][0]['to']=='x.py:App.run'

@pytest.mark.parametrize('path,source',[('main.js','function main() { helper(); }\nfunction helper() { return 1; }'),('main.ts','function main(): void { helper(); }\nfunction helper(): number { return 1; }'),('main.go','package main\nfunc main() { helper() }\nfunc helper() int { return 1 }')])
def test_non_python_flow_is_explicitly_inferred(path,source):
    from backend.services.code_flow import trace
    flow=trace([{'path':path,'content':source}]);assert flow['edges']
    assert flow['edges'][0]['link_type']=='INFERRED' and flow['edges'][0]['target_line']>0

def test_python_and_go_transitive_graphs_from_resolved_artifacts():
    from backend.services.dependency_graphs import graphs
    inspect={'installed':[{'metadata':{'name':'A','version':'1.0','requires_dist':['B>=2']}},{'metadata':{'name':'B','version':'2.0'}}]}
    result=graphs([{'path':'repolens-pip-inspect.json','content':json.dumps(inspect)},{'path':'repolens-go-graph.txt','content':'example.org/app example.org/a@v1.0.0\nexample.org/a@v1.0.0 example.org/b@v2.0.0\n'}])
    assert any(e['from'].endswith(':a') and e['to'].endswith(':b') for e in result['edges'])
    assert any(e['from'].endswith('a@v1.0.0') and e['to'].endswith('b@v2.0.0') for e in result['edges'])

def test_uv_lock_graph_contains_transitive_links():
    from backend.services.dependency_graphs import graphs
    content='[[package]]\nname="a"\nversion="1.0"\ndependencies=[{name="b"}]\n[[package]]\nname="b"\nversion="2.0"\n'
    result=graphs([{'path':'uv.lock','content':content}]);assert result['edges'][0]['to']=='uv.lock:b@2.0'

def test_twenty_gallery_receipts_match_source_hashes_and_pages():
    import hashlib
    root=Path(__file__).resolve().parents[1]
    receipts=list((root/'evaluation/gallery-evidence').glob('*.json'))
    assert len(receipts)==20
    manifest_path=root/'frontend/public/reports/gallery-manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for path in receipts:
        evidence=json.loads(path.read_text());assert len(evidence['revision'])==40
        assert hashlib.sha256(evidence['source'].encode()).hexdigest()==evidence['source_sha256']
        page=root/'frontend/public/gallery'/evidence['repository'].replace('/','-')/'index.html'
        published=manifest.get(evidence['repository'],{})
        if published.get('type')=='reviewed_ai_report':
            report=root/'frontend/public/reports'/(evidence['repository'].replace('/','-')+'-report.md')
            assert hashlib.sha256(report.read_bytes()).hexdigest()==published['report_sha256']
            assert published['revision'] in page.read_text() and 'Reviewed AI architecture report' in page.read_text()
        else:
            assert page.exists() and evidence['revision'] in page.read_text()
            assert 'not an AI architecture analysis' in page.read_text()
