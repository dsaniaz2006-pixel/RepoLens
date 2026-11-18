"""Disposable HTTP lifecycle: memberships, restricted invitations and private chats.
Remote OAuth/Gemini/GitHub are never invoked, and no production Neon data is touched.
"""
import sys
from types import ModuleType
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

@pytest.fixture
def browsers(tmp_path, monkeypatch):
    try:
        from authlib.integrations.starlette_client import OAuth  # noqa:F401
    except ImportError:
        for name in ('authlib','authlib.integrations','authlib.integrations.starlette_client'):
            module=ModuleType(name)
            if name.endswith('starlette_client'):
                module.OAuth=type('DisabledOAuthForOfflineTest', (), {'register':lambda *args,**kwargs:None})
            monkeypatch.setitem(sys.modules,name,module)
    from backend.database.conversations import store_for
    store_for.cache_clear()
    app_url='sqlite:///'+str(tmp_path/'application.db')
    monkeypatch.setenv('REPOLENS_DATABASE_URL',app_url)
    monkeypatch.setenv('REPOLENS_AUTH_DATABASE_URL','sqlite:///'+str(tmp_path/'startup_auth.db'))
    monkeypatch.setenv('REPOLENS_ENV','development')
    monkeypatch.setenv('REPOLENS_BASE_URL','http://127.0.0.1:5173')
    from backend.api.api import app
    from backend.auth.auth import AuthManager,COOKIE
    from backend.database import product_store as store
    import backend.api.product_api as endpoints
    monkeypatch.setattr(endpoints,'resume_completed_index',lambda repo,sha:True)
    mgr=AuthManager(directory=tmp_path/'auth',environ={})
    monkeypatch.setattr(app.state,'auth',mgr)
    people=[mgr.upsert_user('github',name,name,email=email)
            for name,email in [('alice','owner@example.com'),('bob','invitee@example.com'),('charlie','other@example.com')]]
    clients=[]
    for person in people:
        session=mgr.new_session(person['id'])
        client=TestClient(app)
        client.cookies.set(COOKIE,session)
        client.headers['X-CSRF-Token']=mgr.authenticate(session)['csrf']
        clients.append(client)
    yield app_url,people,clients,store
    store_for.cache_clear()


def test_targeted_invitation_requires_matching_verified_oauth_identity(browsers):
    url,people,(alice,bob,charlie),store=browsers
    ws=alice.post('/api/workspaces',json={'name':'Private Team'}).json()['id']
    invite=alice.post(f'/api/workspaces/{ws}/invite',json={'recipient_email':'Invitee@Example.com'})
    assert invite.status_code==200,invite.text
    token=invite.json()['token']
    # No email or unredacted token appears in the public invitation preview.
    preview=charlie.get('/api/invitations/'+token)
    assert preview.status_code==200 and preview.json()['recipient_restricted'] is True
    assert 'invitee@example.com' not in preview.text
    declined=charlie.post('/api/workspaces/join',json={'token':token})
    assert declined.status_code==403
    joined=bob.post('/api/workspaces/join',json={'token':token})
    assert joined.status_code==200 and joined.json()['id']==ws
    assert len(alice.get(f'/api/workspaces/{ws}').json()['members'])==2
    assert charlie.get(f'/api/workspaces/{ws}').status_code==403
    assert alice.get(f'/api/workspaces/{ws}/invitations').json()==[]
    assert charlie.post('/api/workspaces/join',json={'token':token}).status_code==400


def test_invitation_admin_permissions_revoke_and_removed_members(browsers):
    url,people,(alice,bob,charlie),store=browsers
    ws=alice.post('/api/workspaces',json={'name':'Workspace'}).json()['id']
    open_token=alice.post(f'/api/workspaces/{ws}/invite').json()['token']
    assert bob.post('/api/workspaces/join',json={'token':open_token}).status_code==200
    assert bob.post(f'/api/workspaces/{ws}/invite').status_code==403
    assert bob.get(f'/api/workspaces/{ws}/invitations').status_code==403
    assert alice.post(f'/api/workspaces/{ws}/members/{people[1]["id"]}',json={'role':'admin'}).status_code==200
    pending=bob.post(f'/api/workspaces/{ws}/invite',json={'recipient_email':'other@example.com'}).json()['token']
    candidates=bob.get(f'/api/workspaces/{ws}/invitations').json()
    assert len(candidates)==1 and candidates[0]['recipient_restricted']
    assert bob.delete(f'/api/workspaces/{ws}/invitations/{candidates[0]["id"]}').json()['revoked'] is True
    assert charlie.post('/api/workspaces/join',json={'token':pending}).status_code==400
    pending=alice.post(f'/api/workspaces/{ws}/invite',json={'recipient_email':'other@example.com'}).json()['token']
    assert alice.delete(f'/api/workspaces/{ws}/members/{people[1]["id"]}').status_code==200
    assert bob.get(f'/api/workspaces/{ws}').status_code==403
    assert bob.post(f'/api/workspaces/{ws}/invite').status_code==403
    # Member removal invalidates outstanding invitations, even one from owner.
    assert charlie.post('/api/workspaces/join',json={'token':pending}).status_code==400


def test_private_workspace_chats_inaccessible_to_other_member(browsers):
    url,people,(alice,bob,charlie),store=browsers
    ws=alice.post('/api/workspaces',json={'name':'Team'}).json()['id']
    token=alice.post(f'/api/workspaces/{ws}/invite').json()['token']
    assert bob.post('/api/workspaces/join',json={'token':token}).status_code==200
    db=store.configured_engine()  # Same disposable app URL.
    repo=store.put(db,people[0]['id'],'repository',{
        'url':'https://github.com/pallets/flask','repository':'pallets/flask','revision':'a'*40})
    shared=alice.post(f'/api/workspaces/{ws}/repositories',json={'repository_id':repo['id']})
    assert shared.status_code==200,shared.text
    cid=bob.post(f'/api/workspaces/{ws}/repositories/{shared.json()["id"]}/chat').json()['id']
    assert alice.get(f'/api/conversations/{cid}/messages').status_code==404
    assert charlie.get(f'/api/conversations/{cid}/messages').status_code==404
    assert bob.get(f'/api/conversations/{cid}/messages').status_code==200
    assert alice.delete(f'/api/workspaces/{ws}/members/{people[1]["id"]}').status_code==200
    assert bob.get(f'/api/conversations/{cid}/messages').status_code==404
