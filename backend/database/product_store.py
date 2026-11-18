"""Durable product records and team ACLs on the configured SQLAlchemy database."""
import secrets
import hashlib
import time
import uuid
import re
from sqlalchemy import Table,Column,String,JSON,Float,select,delete,update
from fastapi import HTTPException
from backend.database.conversations import metadata,request_store

items=Table('product_items',metadata,Column('id',String(36),primary_key=True),Column('owner',String(128),index=True,nullable=False),Column('kind',String(30),index=True,nullable=False),Column('data',JSON,nullable=False),Column('updated',Float,nullable=False))
members=Table('workspace_members',metadata,Column('workspace',String(36),primary_key=True),Column('user',String(128),primary_key=True),Column('role',String(12),nullable=False))
invites=Table('workspace_invites',metadata,Column('hash',String(64),primary_key=True),Column('workspace',String(36),nullable=False),Column('expires',Float,nullable=False),Column('recipient_email_hash',String(64),nullable=True))
checklist_shares=Table('checklist_shares',metadata,
    Column('checklist_id',String(36),primary_key=True),
    Column('token_hash',String(64),nullable=False,unique=True),
    Column('created',Float,nullable=False))

used_invites=Table('used_workspace_invites',metadata,Column('hash',String(64),primary_key=True),Column('used_at',Float,nullable=False))

task_leases=Table('task_leases',metadata,Column('name',String(80),primary_key=True),Column('token',String(36)),Column('lease_until',Float,nullable=False))

def engine(request):
    value=request_store(request).engine
    metadata.create_all(value)
    return value

def put(db,owner,kind,data):
    item=dict(id=str(uuid.uuid4()),owner=owner,kind=kind,data=data,updated=time.time())
    with db.begin() as c:c.execute(items.insert().values(**item))
    return item

def own(db,owner,iid,kind=None):
    with db.connect() as c:row=c.execute(select(items).where(items.c.id==iid,items.c.owner==owner)).mappings().first()
    if not row or (kind and row['kind']!=kind):raise HTTPException(404,'Record not found')
    return dict(row)

def listing(db,owner,kind):
    with db.connect() as c:return [dict(r) for r in c.execute(select(items).where(items.c.owner==owner,items.c.kind==kind).order_by(items.c.updated.desc()).limit(100)).mappings()]

def workspace_repo_matches(db, wid, repository, revision):
    """Require that a pinned answer corresponds to currently shared evidence."""
    with db.connect() as connection:
        rows=connection.execute(select(items.c.data).where(
            items.c.owner == wid, items.c.kind == 'shared_repository')).scalars()
        return any(isinstance(data, dict) and data.get('repository') == repository
                   and data.get('revision') == revision for data in rows)


def role(db,wid,user,admin=False):
    with db.connect() as c:value=c.execute(select(members.c.role).where(members.c.workspace==wid,members.c.user==user)).scalar()
    if not value or (admin and value not in {'owner','admin'}):raise HTTPException(403,'Workspace access denied')
    return value

def workspace(db,user,name):
    wid=str(uuid.uuid4())
    with db.begin() as c:
        c.execute(items.insert().values(id=wid,owner=user,kind='workspace',data={'name':name},updated=time.time()))
        c.execute(members.insert().values(workspace=wid,user=user,role='owner'))
    return wid

# The email value is verified by Google OIDC or GitHub's verified /user/emails
# endpoint during login. Never accept claimed identity from the invitee's body.
_INVITEE_EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})+")


def normalize_invitee_email(email):
    if email is None or email == '':
        return None
    if not isinstance(email, str) or len(email) > 254 or not _INVITEE_EMAIL.fullmatch(email):
        raise HTTPException(422, 'Enter a valid recipient email address')
    return email.casefold()


def _email_hash(email):
    normalized = normalize_invitee_email(email)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest() if normalized else None


def invite(db,wid,user,*,recipient_email=None):
    role(db,wid,user,True)
    recipient_hash = _email_hash(recipient_email)
    token=secrets.token_urlsafe(32)
    with db.begin() as c:
        # PostgreSQL serializes invite issuance per workspace. Expired invites
        # are ignored rather than counted against the outstanding limit.
        if db.dialect.name == 'postgresql':
            c.execute(select(items.c.id).where(items.c.id==wid).with_for_update())
        pending=c.execute(select(invites.c.hash).where(invites.c.workspace==wid,invites.c.expires>time.time())).fetchall()
        if len(pending)>=10:raise HTTPException(429,'Revoke an invitation before creating another (10 active maximum)')
        c.execute(invites.insert().values(hash=hashlib.sha256(token.encode()).hexdigest(),workspace=wid,
                                          expires=time.time()+86400,recipient_email_hash=recipient_hash))
    return token


def pending_invitations(db,wid,user):
    role(db,wid,user,True)
    with db.connect() as c:
        rows=c.execute(select(invites).where(invites.c.workspace==wid,invites.c.expires>time.time())
                       .order_by(invites.c.expires)).mappings().all()
    return [{'id':row['hash'], 'expires':row['expires'],
             'recipient_restricted':bool(row['recipient_email_hash'])} for row in rows]


def revoke_invitation(db,wid,user,invitation_id):
    role(db,wid,user,True)
    if not isinstance(invitation_id,str) or not re.fullmatch('[0-9a-f]{64}',invitation_id):
        raise HTTPException(404,'Invitation not found')
    with db.begin() as c:
        removed=c.execute(delete(invites).where(invites.c.workspace==wid,invites.c.hash==invitation_id))
    if removed.rowcount!=1:raise HTTPException(404,'Invitation not found')
    return True


def join(db,user,token,*,verified_email=None):
    key=hashlib.sha256(token.encode()).hexdigest()
    with db.begin() as c:
        row=c.execute(select(invites).where(invites.c.hash==key,invites.c.expires>time.time())).mappings().first()
        if not row:
            used=c.execute(select(used_invites).where(used_invites.c.hash==key)).first()
            expired=c.execute(select(invites).where(invites.c.hash==key)).first()
            raise HTTPException(400,'Invite already used' if used else 'Invite expired' if expired else 'Invalid invitation')
        if row['recipient_email_hash'] and _email_hash(verified_email) != row['recipient_email_hash']:
            raise HTTPException(403,'This invitation is restricted to a different verified account email')
        removed=c.execute(delete(invites).where(invites.c.hash==key))
        if removed.rowcount!=1:raise HTTPException(409,'Invite already used')
        c.execute(used_invites.insert().values(hash=key,used_at=time.time()))
        if not c.execute(select(members).where(members.c.workspace==row['workspace'],members.c.user==user)).first():
            c.execute(members.insert().values(workspace=row['workspace'],user=user,role='member'))
    return row['workspace']

def create_checklist_share(db,owner,iid):
    own(db,owner,iid,'checklist')
    token=secrets.token_urlsafe(32)
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    with db.begin() as c:
        c.execute(delete(checklist_shares).where(checklist_shares.c.checklist_id==iid))
        c.execute(checklist_shares.insert().values(checklist_id=iid,token_hash=token_hash,created=time.time()))
    return token

def checklist_share_active(db,owner,iid):
    own(db,owner,iid,'checklist')
    with db.connect() as c:
        return c.execute(select(checklist_shares.c.checklist_id).where(checklist_shares.c.checklist_id==iid)).first() is not None

def revoke_checklist_share(db,owner,iid):
    own(db,owner,iid,'checklist')
    with db.begin() as c:
        result=c.execute(delete(checklist_shares).where(checklist_shares.c.checklist_id==iid))
    return result.rowcount==1

def public_checklist(db,token):
    if not isinstance(token,str) or not 20<=len(token)<=200:
        raise HTTPException(404,'Shared checklist not found')
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    with db.connect() as c:
        share=c.execute(select(checklist_shares.c.checklist_id).where(checklist_shares.c.token_hash==token_hash)).first()
        if not share:
            raise HTTPException(404,'Shared checklist not found')
        row=c.execute(select(items.c.data).where(items.c.id==share.checklist_id,items.c.kind=='checklist')).mappings().first()
    if not row:
        raise HTTPException(404,'Shared checklist not found')
    data=row['data']
    if not isinstance(data,dict):
        raise HTTPException(500,'Shared checklist data is unavailable')
    tasks=data.get('tasks')
    contribution=data.get('first_contribution')
    if (not isinstance(data.get('repository'),str) or not isinstance(data.get('revision'),str)
            or not isinstance(tasks,list) or not isinstance(contribution,dict)):
        raise HTTPException(500,'Shared checklist data is unavailable')
    public_tasks=[]
    for task in tasks:
        if (not isinstance(task,dict) or not all(isinstance(task.get(key),str) for key in ('phase','task','path','why','snippet'))
                or type(task.get('line')) is not int or type(task.get('end_line')) is not int
                or type(task.get('done')) is not bool):
            raise HTTPException(500,'Shared checklist data is unavailable')
        public_tasks.append({key:task[key] for key in ('phase','task','path','line','end_line','why','snippet','done')})
    if (not isinstance(contribution.get('task'),str) or not isinstance(contribution.get('files'),list)
            or any(not isinstance(path,str) for path in contribution['files'])
            or not isinstance(contribution.get('assumptions'),list)
            or any(not isinstance(value,str) for value in contribution['assumptions'])):
        raise HTTPException(500,'Shared checklist data is unavailable')
    return {
        'repository':data['repository'],
        'revision':data['revision'],
        'tasks':public_tasks,
        'first_contribution':{
            'task':contribution['task'],
            'files':contribution['files'],
            'assumptions':contribution['assumptions'],
        },
    }


def configured_engine():
    """Background tools use the same database without initializing an OAuth session."""
    import os
    from pathlib import Path
    from backend.database.conversations import store_for
    folder=Path(os.getenv('REPOLENS_AUTH_DIR',str(Path(__file__).resolve().parents[2]/'.repolens_auth')))
    folder.mkdir(parents=True,exist_ok=True)
    value=store_for(os.getenv('REPOLENS_DATABASE_URL') or 'sqlite:///'+str(folder/'conversations.sqlite3')).engine
    metadata.create_all(value)
    return value


def preview_invite(db,token):
    key=hashlib.sha256(token.encode()).hexdigest()
    with db.connect() as c:
        if c.execute(select(used_invites).where(used_invites.c.hash==key)).first():
            raise HTTPException(400,'Invite already used')
        row=c.execute(select(invites).where(invites.c.hash==key)).mappings().first()
        if not row:raise HTTPException(404,'Invalid invitation')
        if row['expires']<=time.time():raise HTTPException(400,'Invite expired')
        workspace=c.execute(select(items.c.data).where(items.c.id==row['workspace'],items.c.kind=='workspace')).scalar()
        if not workspace:raise HTTPException(404,'Workspace no longer exists')
        return {'workspace':row['workspace'],'name':workspace['name'],'expires':row['expires'],
                'recipient_restricted':bool(row['recipient_email_hash'])}

def assign_checklist(db,manager,wid,iid,assignee):
    import copy,json
    role(db,wid,manager,True);role(db,wid,assignee)
    source=own(db,manager,iid,'checklist')
    snapshot=copy.deepcopy(source['data'])
    for task in snapshot['tasks']:task['done']=False
    version=hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()
    return put(db,wid,'assignment',{'assignee':assignee,'assigned_by':manager,'source_id':iid,
        'checklist_version':version,'snapshot':snapshot,'active':True})

def assignments(db,user,wid):
    access=role(db,wid,user)
    return [x for x in listing(db,wid,'assignment') if access in {'owner','admin'} or x['data']['assignee']==user]

def complete_assignment(db,user,wid,iid,task_id,done):
    role(db,wid,user)
    row=own(db,wid,iid,'assignment');data=row['data']
    if data['assignee']!=user:raise HTTPException(403,'Only the assignee can change progress')
    if not data.get('active'):raise HTTPException(403,'Assignment was closed when membership ended; request a new assignment')
    task=next((t for t in data['snapshot']['tasks'] if t['id']==task_id),None)
    if not task:raise HTTPException(404,'Task not found')
    task['done']=done
    with db.begin() as c:
        result=c.execute(update(items).where(items.c.id==iid,items.c.updated==row['updated']).values(data=data,updated=time.time()))
        if result.rowcount!=1:raise HTTPException(409,'Progress changed; reload and retry')
    return dict(row,data=data)
