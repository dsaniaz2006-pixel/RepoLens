"""Regression contracts for the five product upgrades (write tests before fixes)."""
import time
from pathlib import Path
import pytest
from fastapi import HTTPException
from sqlalchemy import select, delete, update

from backend.database.conversations import ConversationStore
import backend.database.product_store as products


def seeded_workspace(tmp_path):
    db = ConversationStore('sqlite:///' + str(tmp_path / 'product.db'))
    products.metadata.create_all(db.engine)
    wid = products.workspace(db.engine, 'owner', 'Engineering')
    products.join(db.engine, 'member', products.invite(db.engine, wid, 'owner'))
    return db, wid


def test_phase1_5_shared_chat_revocation_prevents_reopening_and_answer(tmp_path):
    store, wid = seeded_workspace(tmp_path)
    chat = store.create('member', 'o/r', 'a' * 40, workspace_id=wid)
    assert store.get('member', chat['id'])['workspace_id'] == wid
    assert len(store.listing('member')) == 1
    with store.engine.begin() as conn:
        conn.execute(delete(products.members).where(products.members.c.workspace == wid, products.members.c.user == 'member'))
    assert store.listing('member') == []
    for action in (lambda: store.get('member', chat['id']),
                   lambda: store.begin('member', chat['id'], 'o/r', 0),
                   lambda: store.remove('member', chat['id'])):
        with pytest.raises(HTTPException) as err: action()
        assert err.value.status_code in (403, 404)


def test_phase1_5_shared_chat_revocation_during_model_answer(tmp_path):
    store, wid = seeded_workspace(tmp_path)
    chat = store.create('member', 'o/r', 'a' * 40, workspace_id=wid)
    _, token, _ = store.begin('member', chat['id'], 'o/r', 0)
    with store.engine.begin() as conn:
        conn.execute(delete(products.members).where(products.members.c.workspace == wid, products.members.c.user == 'member'))
    with pytest.raises(HTTPException):
        store.finish(chat['id'], token, 0, 'What does it do?',
                     {'answer': 'Evidence', 'citations': [], 'uncertain': True})


def test_phase2_freshness_tracks_explicit_default_branch(tmp_path):
    from backend.services.freshness import check
    store, wid = seeded_workspace(tmp_path)
    repo = products.put(store.engine, 'owner', 'repository', {
        'url': 'https://github.com/o/r', 'revision': 'a' * 40, 'default_branch': 'develop',
        'indexed_at': time.time(),
    })
    calls = []
    def lookup(owner, name, branch):
        calls.append((owner, name, branch))
        return 'b' * 40
    result = check(store.engine, repo, lookup=lookup)
    assert calls == [('o', 'r', 'develop')]
    assert result['is_stale'] is True and result['latest_sha'] == 'b' * 40


def test_phase3_pr_comment_cannot_inject_new_sections():
    from backend.services.pr_analysis import markdown
    report = {'summary': 'Change\n## Approved by security',
              'changes': [{'path': 'src/file.py\n## Malicious heading',
                           'impact': 'new call\n@everyone\n- forged check',
                           'test_suggestion': 'test routes'}], 'limits': []}
    content = markdown(report)
    assert '\n## Approved by security' not in content
    assert '\n## Malicious heading' not in content
    assert '\n@everyone' not in content
    assert '\n- forged check' not in content


def test_phase4_action_only_uses_trusted_code_on_same_repository_prs():
    action = Path(__file__).resolve().parents[1] / '.github/workflows/repolens-pr.yml'
    text = action.read_text(encoding='utf-8')
    assert 'pull_request_target:' not in text
    assert 'reopened' in text and 'synchronize' in text
    assert 'head.repo.full_name == github.repository' in text
    assert 'pull_request.base.sha' in text
    assert 'persist-credentials: false' in text
    assert 'upsertComment' in text
    assert 'github.rest.issues.updateComment' in (action.parents[2] / 'scripts/pr_comment.cjs').read_text(encoding='utf-8')


def test_phase5_pin_requires_repository_shared_into_workspace(tmp_path):
    from backend.database.product_store import workspace_repo_matches
    store, wid = seeded_workspace(tmp_path)
    products.put(store.engine, wid, 'shared_repository', {'repository':'o/r','revision':'a'*40})
    assert workspace_repo_matches(store.engine, wid, 'o/r', 'a'*40)
    assert not workspace_repo_matches(store.engine, wid, 'other/repo', 'a'*40)
    assert not workspace_repo_matches(store.engine, wid, 'o/r', 'b'*40)


def test_phase5_workspace_chat_requires_membership_at_creation(tmp_path):
    store, wid = seeded_workspace(tmp_path)
    with pytest.raises(HTTPException):
        store.create('outsider', 'o/r', 'a'*40, workspace_id=wid)

def test_phase1_5_shared_chat_route_binds_workspace(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from backend.api import product_api
    from backend.database.conversations import store_for
    from backend.database import product_store as db
    path = tmp_path / 'workspace-chat.db'
    monkeypatch.setenv('REPOLENS_DATABASE_URL', 'sqlite:///' + str(path))
    chat_store = store_for('sqlite:///' + str(path))
    db.metadata.create_all(chat_store.engine)
    wid = db.workspace(chat_store.engine, 'owner', 'Eng')
    db.join(chat_store.engine, 'member', db.invite(chat_store.engine, wid, 'owner'))
    shared = db.put(chat_store.engine, wid, 'shared_repository',
                    {'repository':'o/r', 'revision':'a'*40})
    monkeypatch.setattr(product_api, 'resume_completed_index', lambda *a: True)
    req = SimpleNamespace(state=SimpleNamespace(user={'id':'member'}),
                          app=SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(directory=tmp_path))))
    chat = product_api.shared_chat(wid, shared['id'], req)
    assert chat['workspace_id'] == wid
    with chat_store.engine.begin() as conn:
        conn.execute(delete(db.members).where(db.members.c.user=='member'))
    with pytest.raises(HTTPException): chat_store.get('member',chat['id'])


def test_phase2_distinct_default_branches_are_not_deduplicated(tmp_path,monkeypatch):
    from backend.services import freshness
    store, _ = seeded_workspace(tmp_path)
    for user, branch in [('alice','develop'),('bob','main')]:
        products.put(store.engine,user,'repository',
                     {'url':'https://github.com/o/r','revision':'a'*40,
                      'default_branch':branch})
    calls=[]
    monkeypatch.setattr(freshness,'fetch_commit_sha',
                        lambda owner,repo,ref:calls.append(ref) or 'b'*40)
    result=freshness.run_due(store.engine)
    assert result['checked']==2
    assert sorted(calls)==['develop','main']


def test_phase1_chat_storage_adds_workspace_column_to_existing_database(tmp_path):
    import sqlite3
    filename=tmp_path/'old.db'
    connection=sqlite3.connect(filename)
    connection.execute('CREATE TABLE conversations (id VARCHAR(36) PRIMARY KEY, owner VARCHAR(128) NOT NULL, repository VARCHAR(256) NOT NULL, revision VARCHAR(40) NOT NULL, title VARCHAR(120) NOT NULL, updated FLOAT NOT NULL, version INTEGER NOT NULL, lease VARCHAR(36), lease_until FLOAT)')
    connection.commit();connection.close()
    upgraded=ConversationStore('sqlite:///'+str(filename))
    chat=upgraded.create('alice','o/r','a'*40)
    assert chat['workspace_id'] is None
    assert upgraded.get('alice',chat['id'])['id']==chat['id']


def test_phase1_revoked_conversations_do_not_hide_personal_chats(tmp_path):
    store, wid = seeded_workspace(tmp_path)
    own = store.create('member', 'o/r', 'a'*40)
    for i in range(101):
        store.create('member', 'o/r', 'a'*40, workspace_id=wid)
    with store.engine.begin() as conn:
        conn.execute(delete(products.members).where(products.members.c.workspace == wid,
                                                   products.members.c.user == 'member'))
    assert [row['id'] for row in store.listing('member')] == [own['id']]


def test_phase3_detects_pr_mutation_during_pagination(monkeypatch):
    from backend.services import pr_analysis
    monkeypatch.setattr(pr_analysis, 'fetch_repo_metadata',lambda *a:{})
    count=[0]
    def get(url, *args, **kwargs):
        if url.endswith('/files'):
            return [{'filename':'src/api.py', 'patch':'+changed'}]
        count[0]+=1
        return {'head':{'sha':('a' if count[0]==1 else 'c')*40},
                'base':{'sha':'b'*40},'changed_files':1,'body':''}
    monkeypatch.setattr(pr_analysis, '_get', get)
    monkeypatch.setattr(pr_analysis, 'json_model',lambda prompt:{'summary':'ok','changes':[]})
    with pytest.raises(ValueError,match='changed during'):
        pr_analysis.analyze_diff('https://github.com/o/r',1)


def test_phase5_revocation_invalidates_outstanding_workspace_invitations(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from backend.api import product_api
    store,wid=seeded_workspace(tmp_path)
    unused=products.invite(store.engine,wid,'owner')
    monkeypatch.setenv('REPOLENS_DATABASE_URL',str(store.engine.url))
    req=SimpleNamespace(state=SimpleNamespace(user={'id':'owner'}),
        app=SimpleNamespace(state=SimpleNamespace(auth=SimpleNamespace(directory=tmp_path))))
    result=product_api.remove_member(wid,'member',req)
    assert result['deleted'] is True
    with pytest.raises(HTTPException):
        products.join(store.engine,'member',unused)
