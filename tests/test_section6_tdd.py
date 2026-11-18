"""Section 6 RED-first invitation and membership security acceptance tests.
No production database or OAuth network dependencies.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, select
from backend.database.conversations import metadata
from backend.database import product_store as store

@pytest.fixture
def demo(tmp_path):
    db=create_engine('sqlite:///'+str(tmp_path/'teams.db'))
    metadata.create_all(db)
    wid=store.workspace(db,'owner','Example team')
    yield db,wid
    db.dispose()

def test_targeted_invite_only_matching_verified_identity_consumes_it(demo):
    db,wid=demo
    token=store.invite(db,wid,'owner',recipient_email='Developer@Example.com')
    with pytest.raises(HTTPException) as denied:
        store.join(db,'wrong',token,verified_email='wrong@example.com')
    assert denied.value.status_code==403
    assert store.preview_invite(db,token)['recipient_restricted'] is True
    assert store.join(db,'dev',token,verified_email='developer@example.com')==wid
    assert store.role(db,wid,'dev')=='member'
    with pytest.raises(HTTPException):store.join(db,'other',token,verified_email='developer@example.com')

def test_targeted_invite_rejects_unknown_email_and_does_not_leak_it(demo):
    db,wid=demo
    token=store.invite(db,wid,'owner',recipient_email='dev@example.com')
    with pytest.raises(HTTPException) as denied:store.join(db,'dev',token,verified_email=None)
    assert denied.value.status_code==403
    preview=store.preview_invite(db,token)
    assert 'dev@example.com' not in str(preview)
    assert token not in str(store.pending_invitations(db,wid,'owner'))

def test_owner_admin_list_revoke_invite_member_cannot(demo):
    db,wid=demo
    token=store.invite(db,wid,'owner',recipient_email='dev@example.com')
    pending=store.pending_invitations(db,wid,'owner')
    assert len(pending)==1 and pending[0]['recipient_restricted'] is True
    store.join(db,'admin',store.invite(db,wid,'owner'))
    from sqlalchemy import update
    with db.begin() as conn:
        conn.execute(update(store.members).where(store.members.c.workspace==wid,store.members.c.user=='admin').values(role='admin'))
    assert len(store.pending_invitations(db,wid,'admin'))==1
    store.join(db,'member',store.invite(db,wid,'owner'))
    with pytest.raises(HTTPException) as denied:store.pending_invitations(db,wid,'member')
    assert denied.value.status_code==403
    assert store.revoke_invitation(db,wid,'admin',pending[0]['id']) is True
    with pytest.raises(HTTPException):store.join(db,'dev',token,verified_email='dev@example.com')

def test_legacy_unrestricted_invites_continue_to_work(demo):
    db,wid=demo
    token=store.invite(db,wid,'owner')
    assert store.preview_invite(db,token)['recipient_restricted'] is False
    assert store.join(db,'bob',token)==wid

def test_section6_app_migration_preserves_old_invites(tmp_path):
    from backend.database.schema_migrations import _config, migration_status
    from alembic import command
    auth='sqlite:///'+str(tmp_path/'a.db'); app='sqlite:///'+str(tmp_path/'b.db')
    command.upgrade(_config('app',app),'app_0001')
    legacy=create_engine(app)
    with legacy.begin() as conn:
        conn.execute(store.invites.insert().values(hash='a'*64,workspace='w',expires=9999999999))
    legacy.dispose()
    command.upgrade(_config('app',app),'head')
    engine=create_engine(app)
    assert 'recipient_email_hash' in {c['name'] for c in inspect(engine).get_columns('workspace_invites')}
    with engine.connect() as c:
        row=c.execute(select(store.invites).where(store.invites.c.hash=='a'*64)).mappings().one()
        assert row['recipient_email_hash'] is None
    engine.dispose()
    assert migration_status(auth,app)['app']['current']=='app_0002'


def test_invitation_expiration_blocks_use_and_is_not_reissued(demo):
    db,wid=demo
    token=store.invite(db,wid,'owner',recipient_email='invitee@example.com')
    key=__import__('hashlib').sha256(token.encode()).hexdigest()
    with db.begin() as conn:
        conn.execute(__import__('sqlalchemy').update(store.invites).where(store.invites.c.hash==key).values(expires=1))
    with pytest.raises(HTTPException) as error:
        store.join(db,'invitee',token,verified_email='invitee@example.com')
    assert error.value.status_code==400 and 'expired' in error.value.detail.lower()
    assert store.pending_invitations(db,wid,'owner')==[]


def test_invitation_limit_and_bad_recipient_does_not_create_any_record(demo):
    db,wid=demo
    with pytest.raises(HTTPException) as invalid:
        store.invite(db,wid,'owner',recipient_email='bad email\n@example.com')
    assert invalid.value.status_code==422
    assert store.pending_invitations(db,wid,'owner')==[]
    for _ in range(10):store.invite(db,wid,'owner')
    with pytest.raises(HTTPException) as limit:store.invite(db,wid,'owner')
    assert limit.value.status_code==429
    assert len(store.pending_invitations(db,wid,'owner'))==10


def test_workspace_migration_status_detects_missing_recipient_column(tmp_path):
    from backend.database.schema_migrations import _config,migration_status
    from alembic import command
    from sqlalchemy import create_engine,text
    auth='sqlite:///'+str(tmp_path/'a.db');app='sqlite:///'+str(tmp_path/'b.db')
    command.upgrade(_config('app',app),'app_0001')
    status=migration_status(auth,app)['app']
    assert status['current']=='app_0001' and not status['schema_valid']
    command.upgrade(_config('app',app),'head')
    assert migration_status(auth,app)['app']['up_to_date'] is True
