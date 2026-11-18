"""Regression checks for scheduler concurrency, bounded diffs and reviewed publication."""
import json,time
from pathlib import Path
import pytest
from sqlalchemy import create_engine,select,update
import backend.database.product_store as store

@pytest.fixture
def db(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'state.db'))
    store.metadata.create_all(engine)
    return engine

def test_freshness_lease_blocks_overlap_and_recovers_expiry(db,monkeypatch):
    import backend.services.freshness as freshness
    with db.begin() as c:c.execute(store.task_leases.insert().values(name='repository-freshness',token='other',lease_until=time.time()+100))
    assert freshness.run_due(db)['status']=='already_running'
    with db.begin() as c:c.execute(update(store.task_leases).values(lease_until=0))
    monkeypatch.setattr(freshness,'check_due',lambda *a,**k: {'checked':2,'changed':1,'failed':0})
    assert freshness.run_due(db)=={'status':'completed','checked':2,'changed':1,'failed':0}
    with db.connect() as c:assert c.execute(select(store.task_leases.c.token)).scalar_one() is None

def test_freshness_due_state_survives_worker_restart_and_deduplicates(db,monkeypatch):
    import backend.services.freshness as freshness
    for owner,kind in [('alice','repository'),('bob','shared_repository')]:
        store.put(db,owner,kind,{'url':'https://github.com/o/r','revision':'a'*40})
    calls=[]
    monkeypatch.setattr(freshness,'fetch_commit_sha',lambda *a: calls.append(a) or 'b'*40)
    assert freshness.run_due(db)['changed']==2
    assert len(calls)==1
    assert freshness.run_due(db)['checked']==0

def test_freshness_does_not_overwrite_concurrent_reindex(db):
    import backend.services.freshness as freshness
    row=store.put(db,'alice','repository',{'url':'https://github.com/o/r','revision':'a'*40})
    def lookup(*a):
        with db.begin() as c:c.execute(update(store.items).where(store.items.c.id==row['id']).values(data={'url':'https://github.com/o/r','revision':'c'*40},updated=time.time()+1))
        return 'b'*40
    assert freshness.check(db,row,lookup=lookup)=={'superseded':True}
    assert store.own(db,'alice',row['id'])['data']['revision']=='c'*40

def diff_setup(monkeypatch,files):
    import backend.services.pr_analysis as pr
    monkeypatch.setattr(pr,'fetch_repo_metadata',lambda *a:{})
    monkeypatch.setattr(pr,'_get',lambda path,*a,**k:files if path.endswith('/files') else {'head':{'sha':'a'*40},'base':{'sha':'b'*40},'changed_files':len(files)})
    monkeypatch.setattr(pr,'json_model',lambda p:{'summary':'Scoped review','changes':[]})
    return pr

def test_diff_budget_reports_omitted_files_and_sections(monkeypatch):
    files=[{'filename':f'src/file{i}.py','patch':'+'+'x'*10000} for i in range(10)]
    pr=diff_setup(monkeypatch,files);monkeypatch.setenv('REPOLENS_DIFF_MAX_BATCHES','1')
    result=pr.analyze_diff('https://github.com/o/r',1)
    assert result['coverage']['model_batches']==1
    assert result['coverage']['evidence_sections']<result['coverage']['total_sections']
    assert result['omitted_paths'] and any('incomplete' in x for x in result['limits'])

def test_diff_citations_must_belong_to_the_current_batch(monkeypatch):
    files=[{'filename':f'src/file{i}.py','patch':'x'*3500} for i in range(10)]
    pr=diff_setup(monkeypatch,files)
    def model(prompt):
        batch=json.loads(prompt.split('\n',1)[1])['files']
        outside=next(f['filename'] for f in files if f['filename'] not in {x['path'] for x in batch})
        return {'summary':'Review','changes':[{'path':outside,'impact':'Unsupported','test_suggestion':'Review'}]}
    monkeypatch.setattr(pr,'json_model',model)
    with pytest.raises(ValueError,match='unsupported evidence'):pr.analyze_diff('https://github.com/o/r',1)

def test_compare_resolves_both_refs_before_request(monkeypatch):
    import backend.services.pr_analysis as pr
    monkeypatch.setattr(pr,'fetch_repo_metadata',lambda *a:{})
    monkeypatch.setattr(pr,'fetch_commit_sha',lambda o,r,ref: ('a' if ref=='main' else 'b')*40)
    paths=[]
    monkeypatch.setattr(pr,'_get',lambda path,*a,**k:paths.append(path) or {'files':[]})
    result=pr.analyze_diff('https://github.com/o/r',base='main',head='feature')
    assert paths==['/repos/o/r/compare/'+'a'*40+'...'+'b'*40]
    assert result['revision']=='b'*40

def test_gallery_resume_isolation_and_reviewed_publication(tmp_path,monkeypatch):
    import backend.services.gallery_pipeline as gallery
    from tests.test_analyzer import TREE,valid_analysis
    from backend.services.report import render_report
    monkeypatch.setenv('REPOLENS_MODEL_PROVIDER','gemini')
    calls=[]
    def generate(url,output_dir,**kwargs):
        calls.append(url)
        if url.endswith('/bad'):raise RuntimeError('private provider message')
        folder=Path(output_dir);folder.mkdir(parents=True,exist_ok=True)
        metadata={'full_name':'o/good','html_url':url}
        analysis=valid_analysis();target=folder/'original.md'
        target.write_text(render_report(analysis,metadata,TREE))
        return {'analysis':analysis,'metadata':metadata,'tree':TREE,'report_path':str(target),'revision':'a'*40,'evidence_paths':[r['path'] for r in TREE if r['type']=='blob']}
    result=gallery.generate_ai_reports(tmp_path,['o/bad','o/good'],generator=generate)
    assert [r['status'] for r in result]==['failed','generated']
    assert 'private provider' not in gallery.state_path(tmp_path,'o/bad').read_text()
    assert gallery.publish(tmp_path,['o/good'])==[]
    assert gallery.generate_ai_reports(tmp_path,['o/good'],generator=generate)[0]['resumed']
    assert len(calls)==2
    gallery.approve(tmp_path,'o/good','Source reviewer')
    assert gallery.publish(tmp_path,['o/good'])==['o/good']
    manifest=json.loads((tmp_path/'frontend/public/reports/gallery-manifest.json').read_text())
    assert manifest['o/good']['type']=='reviewed_ai_report'
    report=gallery.state_path(tmp_path,'o/good').parent/'report.md'
    report.write_text(report.read_text()+'Changed after review')
    with pytest.raises(ValueError,match='changed'):gallery.publish(tmp_path,['o/good'])

@pytest.mark.parametrize('vectors', [[[1.0]],[[1.0],[float('nan')]],[[1.0],[1.0,2.0]]])
def test_invalid_embedding_batch_is_not_partially_cached(tmp_path,monkeypatch,vectors):
    import backend.rag.embedding_cache as cache
    monkeypatch.setenv('REPOLENS_EMBED_CACHE_DIR',str(tmp_path))
    with pytest.raises(ValueError):cache.cached_embeddings(['a','b'],'document','model',lambda _:vectors)
    assert cache.get('model','document','a') is None
    assert cache.get('model','document','b') is None

def test_release_excludes_private_runtime_and_preserves_public_assets(tmp_path):
    from scripts.package_release import package
    import zipfile
    root=tmp_path/'source';root.mkdir()
    for name in ['.env','.env.local','.env.example','.repolens_backups/old/.env','.repolens_gallery/o-r/state.json','reports/private.md','frontend/public/reports/o-r-report.md','frontend/dist/index.html','api.py','node_modules/a.js','.repolens_auth/secret.key','__MACOSX/._file']:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('example')
    (root/'outside-link').symlink_to(tmp_path,target_is_directory=True)
    target=tmp_path/'release.zip';package(root,target)
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist())=={'RepoLens/.env.example','RepoLens/api.py','RepoLens/frontend/public/reports/o-r-report.md','RepoLens/frontend/dist/index.html'}

def test_migration_releases_runtime_leases(tmp_path):
    from backend.auth.auth import AuthManager
    from backend.database.conversations import ConversationStore
    from backend.database.migrate_database import migrate
    source=tmp_path/'source';AuthManager(directory=source,environ={})
    engine=ConversationStore('sqlite:///'+str(source/'conversations.sqlite3')).engine
    store.metadata.create_all(engine)
    with engine.begin() as c:c.execute(store.task_leases.insert().values(name='repository-freshness',token='old-worker',lease_until=time.time()+100))
    target='sqlite:///'+str(tmp_path/'destination.db');migrate(source,target,apply=True)
    with create_engine(target).connect() as c:
        row=c.execute(select(store.task_leases)).mappings().one()
        assert row['token'] is None and row['lease_until']==0
