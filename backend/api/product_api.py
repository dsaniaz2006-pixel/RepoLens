"""Authenticated roadmap features. Existing middleware supplies user and CSRF checks."""
import time
import io
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import Response,JSONResponse
from pydantic import BaseModel,Field,field_validator
from backend.security.controls import validate_repository_url, validate_question
from sqlalchemy import select,update,delete
import backend.database.product_store as store
from backend.services.pipeline import collect_repo,resume_completed_index
from backend.github.github_client import parse_github_url

router=APIRouter(prefix='/api')
class Repo(BaseModel):
    url: str = Field(min_length=1,max_length=500)

    @field_validator('url')
    @classmethod
    def valid_repo(cls, value):
        return validate_repository_url(value)
class Diff(Repo):
    pr:int|None=Field(default=None,ge=1)
    base:str|None=Field(default=None,max_length=200)
    head:str|None=Field(default=None,max_length=200)
class Name(BaseModel):
    name: str = Field(min_length=1,max_length=100)

    @field_validator('name')
    @classmethod
    def safe_name(cls, value):
        from backend.security.controls import validate_question
        return validate_question(value)
class Token(BaseModel):token:str=Field(min_length=20,max_length=200)
class InviteOptions(BaseModel):recipient_email:str|None=Field(default=None,max_length=254)
class Role(BaseModel):role:str
class Task(BaseModel):task_id:str;done:bool
class Pin(BaseModel):conversation_id:str;message_id:str
class SharedRepo(BaseModel):repository_id:str

def uid(r):return r.state.user['id']
# All product endpoint error mapping is maintained in one API boundary.
from backend.api.errors import safe_product_call as safe

def track_index(db,user,url,result):
    owner,name=parse_github_url(url)
    repository=result.get('repository',f'{owner}/{name}'.lower())
    old=next((x for x in store.listing(db,user,'repository') if x['data']['repository']==repository),None)
    data={'url':url,'repository':repository,'revision':result['revision'],'indexed_at':time.time(),'checked_at':0,'is_stale':None,'latest_sha':None,'error':None}
    if result.get('default_branch') or (old and old['data'].get('default_branch')):
        data['default_branch']=result.get('default_branch') or old['data']['default_branch']
    if old:
        data['previous_revision']=old['data']['revision']
        updated=time.time()
        with db.begin() as c:c.execute(update(store.items).where(store.items.c.id==old['id'],store.items.c.owner==user).values(data=data,updated=updated))
        return dict(old,data=data,updated=updated)
    return store.put(db,user,'repository',data)

@router.get('/repositories')
def repositories(r:Request):return store.listing(store.engine(r),uid(r),'repository')
@router.post('/repositories/{iid}/check')
def freshness(iid:str,r:Request):
    from backend.services.freshness import check
    db=store.engine(r);item=store.own(db,uid(r),iid,'repository')
    return check(db,item)
@router.post('/repositories/register')
def register(body:Repo,r:Request):
    def work():
        from backend.github.github_client import fetch_repo_metadata,fetch_commit_sha
        owner,repo=parse_github_url(body.url);m=fetch_repo_metadata(owner,repo)
        if m.get('private'):raise ValueError('Only public repositories are supported')
        sha=fetch_commit_sha(owner,repo,m['default_branch']);result=resume_completed_index(f'{owner}/{repo}'.lower(),sha)
        if not result:raise ValueError('Build the current revision index first')
        return track_index(store.engine(r),uid(r),body.url,result)
    return safe(work)
@router.post('/diff')
def diff(body:Diff,r:Request):
    from backend.services.pr_analysis import analyze_diff
    return safe(lambda:store.put(store.engine(r),uid(r),'diff',analyze_diff(body.url,body.pr,body.base,body.head)))
@router.post('/security-scan')
def security(body:Repo,r:Request):
    from backend.services.security_scanner import scan_repository
    def work():
        data=collect_repo(body.url,pin_revision=True,for_index=True)
        result=scan_repository(data);result.update(repository=data['repo_id'],revision=data['revision'])
        return store.put(store.engine(r),uid(r),'security',result)
    return safe(work)
@router.post('/flow')
def flow(body:Repo,r:Request):
    from backend.services.code_flow import trace
    def work():
        data=collect_repo(body.url,pin_revision=True,for_index=True)
        return store.put(store.engine(r),uid(r),'flow',dict(trace(data['records']),repository=data['repo_id'],revision=data['revision']))
    return safe(work)
@router.get('/insights/{kind}')
def insights(kind:str,r:Request):
    if kind not in {'diff','security','flow','checklist'}:raise HTTPException(404,'Unknown insight')
    return store.listing(store.engine(r),uid(r),kind)
@router.post('/checklists')
def checklist(body:Repo,r:Request):
    def work():
        data=collect_repo(body.url,pin_revision=True,for_index=True)
        from backend.services.onboarding import generate
        return store.put(store.engine(r),uid(r),'checklist',generate(data))
    return safe(work)
@router.post('/checklists/{iid}/share')
def create_checklist_share(iid:str,r:Request):
    return {'token':store.create_checklist_share(store.engine(r),uid(r),iid)}
@router.get('/checklists/{iid}/share')
def checklist_share_status(iid:str,r:Request):
    return {'active':store.checklist_share_active(store.engine(r),uid(r),iid)}
@router.delete('/checklists/{iid}/share')
def revoke_checklist_share(iid:str,r:Request):
    return {'revoked':store.revoke_checklist_share(store.engine(r),uid(r),iid)}
@router.get('/public/checklists/{token}')
def public_checklist(token:str,r:Request):
    return JSONResponse(
        content=store.public_checklist(store.engine(r),token),
        headers={'Cache-Control':'no-store'},
    )
@router.post('/checklists/{iid}/complete')
def complete(iid:str,body:Task,r:Request):
    db=store.engine(r);row=store.own(db,uid(r),iid,'checklist');data=row['data']
    task=next((t for t in data['tasks'] if t['id']==body.task_id),None)
    if not task:raise HTTPException(404,'Task not found')
    task['done']=body.done
    with db.begin() as c:
        result=c.execute(update(store.items).where(store.items.c.id==iid,store.items.c.owner==uid(r),store.items.c.updated==row['updated']).values(data=data,updated=time.time()))
        if result.rowcount!=1:raise HTTPException(409,'Checklist changed; reload and retry')
    return data
@router.get('/checklists/{iid}/pdf')
def checklist_pdf(iid:str,r:Request):
    from reportlab.pdfgen import canvas
    from textwrap import wrap
    row=store.own(store.engine(r),uid(r),iid,'checklist');buf=io.BytesIO();pdf=canvas.Canvas(buf);y=800
    lines=['RepoLens onboarding: '+row['data']['repository'],'Revision: '+row['data']['revision']]
    for t in row['data']['tasks']:lines.extend(wrap(('[x] ' if t['done'] else '[ ] ')+t['phase']+': '+t['task'],90))
    lines+=wrap('First contribution: '+row['data']['first_contribution']['task'],90)
    for line in lines:
        if y<50:pdf.showPage();y=800
        pdf.drawString(40,y,line);y-=18
    pdf.save();return Response(buf.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="onboarding.pdf"'})

@router.get('/workspaces')
def workspaces(r:Request):
    db=store.engine(r)
    with db.connect() as c:return [dict(x) for x in c.execute(select(store.items,store.members.c.role).join(store.members,store.items.c.id==store.members.c.workspace).where(store.members.c.user==uid(r),store.items.c.kind=='workspace')).mappings()]
@router.post('/workspaces')
def workspace(body:Name,r:Request):
    if not body.name.strip():raise HTTPException(400,'Workspace name cannot be blank')
    return {'id':store.workspace(store.engine(r),uid(r),body.name.strip())}
@router.post('/workspaces/join')
def join(body:Token,r:Request):return {'id':store.join(store.engine(r),uid(r),body.token,verified_email=r.state.user.get('email'))}
@router.post('/workspaces/{wid}/invite')
def invite(wid:str,r:Request,body:InviteOptions=None):
    recipient = body.recipient_email if body else None
    token=store.invite(store.engine(r),wid,uid(r),recipient_email=recipient)
    return {'token':token,'url':r.app.state.auth.base_url+'/join?token='+token,'expires_in':86400,
            'recipient_restricted':bool(recipient)}

@router.get('/workspaces/{wid}/invitations')
def list_invitations(wid:str,r:Request):
    return store.pending_invitations(store.engine(r),wid,uid(r))

@router.delete('/workspaces/{wid}/invitations/{invitation_id}')
def revoke_invitation(wid:str,invitation_id:str,r:Request):
    return {'revoked':store.revoke_invitation(store.engine(r),wid,uid(r),invitation_id)}
@router.get('/workspaces/{wid}')
def team(wid:str,r:Request):
    db=store.engine(r);myrole=store.role(db,wid,uid(r))
    with db.connect() as c:people=[dict(x) for x in c.execute(select(store.members).where(store.members.c.workspace==wid)).mappings()]
    repos=store.listing(db,wid,'shared_repository')
    return {'role':myrole,'members':people,'pins':store.listing(db,wid,'pin'),'repositories':repos}
@router.post('/workspaces/{wid}/members/{user}')
def change_role(wid:str,user:str,body:Role,r:Request):
    db=store.engine(r)
    if store.role(db,wid,uid(r))!='owner':raise HTTPException(403,'Only the owner can change roles')
    if body.role not in {'admin','member'}:raise HTTPException(400,'Choose admin or member')
    if store.role(db,wid,user)=='owner':raise HTTPException(400,'Owner role cannot be changed')
    with db.begin() as c:c.execute(update(store.members).where(store.members.c.workspace==wid,store.members.c.user==user).values(role=body.role))
    return {'updated':True}
@router.delete('/workspaces/{wid}/members/{user}')
def remove_member(wid:str,user:str,r:Request):
    db=store.engine(r);mine=store.role(db,wid,uid(r));theirs=store.role(db,wid,user)
    if theirs=='owner' or (uid(r)!=user and mine!='owner'):raise HTTPException(403,'Only the owner can remove other members; owner cannot be removed')
    with db.begin() as c:
        c.execute(delete(store.members).where(store.members.c.workspace==wid,store.members.c.user==user))
        if uid(r)!=user:
            # Invite links are bearer credentials with no named recipient.
            # Removing a member must revoke any outstanding links they may
            # have copied; the owner can issue fresh invitations afterward.
            c.execute(delete(store.invites).where(store.invites.c.workspace==wid))
        rows=c.execute(select(store.items).where(store.items.c.owner==wid,store.items.c.kind=='assignment')).mappings().all()
        for row in rows:
            if row['data']['assignee']==user:
                data=dict(row['data'],active=False)
                c.execute(update(store.items).where(store.items.c.id==row['id']).values(data=data,updated=time.time()))
    return {'deleted':True}
@router.post('/workspaces/{wid}/repositories')
def share_repo(wid:str,body:SharedRepo,r:Request):
    db=store.engine(r);store.role(db,wid,uid(r),True);repo=store.own(db,uid(r),body.repository_id,'repository')
    existing=next((x for x in store.listing(db,wid,'shared_repository') if x['data']['repository']==repo['data']['repository']),None)
    if existing:
        with db.begin() as c:c.execute(update(store.items).where(store.items.c.id==existing['id']).values(data=repo['data'],updated=time.time()))
        return dict(existing,data=repo['data'])
    return store.put(db,wid,'shared_repository',repo['data'])
@router.post('/workspaces/{wid}/repositories/{iid}/chat')
def shared_chat(wid:str,iid:str,r:Request):
    from backend.database.conversations import request_store
    db=store.engine(r);store.role(db,wid,uid(r));repo=store.own(db,wid,iid,'shared_repository')['data']
    if not resume_completed_index(repo['repository'],repo['revision']):raise HTTPException(400,'Shared index is unavailable; ask the owner to rebuild it')
    return request_store(r).create(uid(r),repo['repository'],repo['revision'],workspace_id=wid)
@router.post('/workspaces/{wid}/pins')
def pin(wid:str,body:Pin,r:Request):
    from backend.database.conversations import request_store
    db=store.engine(r);store.role(db,wid,uid(r));chat=request_store(r).get(uid(r),body.conversation_id)
    message=next((m for m in chat['messages'] if m['id']==body.message_id and m['role']=='assistant' and m['citations']),None)
    if not message:raise HTTPException(400,'Choose an answer with citations from your own conversation')
    if not store.workspace_repo_matches(db,wid,chat['repository'],chat['revision']):
        raise HTTPException(403,'Only answers for a currently shared repository revision may be pinned')
    return store.put(db,wid,'pin',{'repository':chat['repository'],'revision':chat['revision'],'answer':message['content'],'citations':message['citations'],'author':uid(r)})
@router.delete('/workspaces/{wid}/pins/{iid}')
def delete_pin(wid:str,iid:str,r:Request):
    db=store.engine(r);role=store.role(db,wid,uid(r));pin=store.own(db,wid,iid,'pin')
    if pin['data']['author']!=uid(r) and role not in {'owner','admin'}:raise HTTPException(403,'Only author or admin can delete this pin')
    with db.begin() as c:c.execute(delete(store.items).where(store.items.c.id==iid))
    return {'deleted':True}


@router.get('/invitations/{token}')
def invitation_preview(token:str,r:Request):
    return store.preview_invite(store.engine(r),token)

class Assignment(BaseModel):
    checklist_id:str
    assignee:str

@router.post('/workspaces/{wid}/assignments')
def assign(wid:str,body:Assignment,r:Request):
    return store.assign_checklist(store.engine(r),uid(r),wid,body.checklist_id,body.assignee)

@router.get('/workspaces/{wid}/assignments')
def assigned(wid:str,r:Request):
    return store.assignments(store.engine(r),uid(r),wid)

@router.post('/workspaces/{wid}/assignments/{iid}/complete')
def assignment_progress(wid:str,iid:str,body:Task,r:Request):
    return store.complete_assignment(store.engine(r),uid(r),wid,iid,body.task_id,body.done)

class LocalRepo(BaseModel):alias:str=Field(min_length=1,max_length=64)
class LocalQuestion(BaseModel):
    question: str = Field(min_length=1,max_length=4000)

    @field_validator('question')
    @classmethod
    def safe_question(cls, value):
        return validate_question(value)

@router.get('/local/repositories')
def local_repositories(r:Request):
    from backend.github.local_repositories import approved
    return safe(lambda:{'approved':list(approved(uid(r))),'indexes':store.listing(store.engine(r),uid(r),'local_repository')})

@router.post('/local/index')
def local_index(body:LocalRepo,r:Request):
    from backend.github.local_repositories import index
    return safe(lambda:store.put(store.engine(r),uid(r),'local_repository',index(body.alias,uid(r))))

@router.post('/local/repositories/{iid}/ask')
def local_ask(iid:str,body:LocalQuestion,r:Request):
    from backend.github.local_repositories import ask
    return safe(lambda:ask(store.own(store.engine(r),uid(r),iid,'local_repository')['data'],uid(r),body.question))
