"""Persistent repository freshness state with a cross-process worker lease."""
import time,uuid
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from backend.database.product_store import items,task_leases
from backend.github.github_client import fetch_commit_sha,parse_github_url

def check(db,item,*,lookup=None):
    lookup=lookup or fetch_commit_sha
    data=dict(item['data']);owner,repo=parse_github_url(data['url'])
    try:
        latest=lookup(owner,repo,data.get('default_branch') or 'HEAD')
        changed=latest!=data['revision']
        if changed and latest!=data.get('latest_sha'):data['changed_at']=time.time()
        data.update(latest_sha=latest,is_stale=changed,checked_at=time.time(),error=None)
    except Exception:
        data.update(checked_at=time.time(),error='Freshness check failed; check GitHub access or rate limits')
    with db.begin() as c:
        result=c.execute(update(items).where(items.c.id==item['id'],items.c.updated==item['updated']).values(data=data,updated=time.time()))
    if result.rowcount!=1:return {'superseded':True}  # A re-index won the race; its new SHA stays authoritative.
    return data

def check_due(db,*,heartbeat=None):
    with db.connect() as c:rows=[dict(r) for r in c.execute(select(items).where(items.c.kind.in_(['repository','shared_repository']))).mappings()]
    stats={'checked':0,'changed':0,'failed':0};cache={}
    def lookup(owner,repo,branch):
        key=(owner.lower(),repo.lower(),branch)
        if key not in cache:
            try:cache[key]=fetch_commit_sha(owner,repo,branch)
            except Exception as exc:cache[key]=exc
        if isinstance(cache[key],Exception):raise cache[key]
        return cache[key]
    for row in rows:
        data=row['data'];retry=900 if data.get('error') else 21600
        if time.time()-data.get('checked_at',0)<retry:continue
        if heartbeat:heartbeat()
        result=check(db,row,lookup=lookup)
        if result.get('superseded'):continue
        stats['checked']+=1;stats['failed']+=bool(result.get('error'))
        stats['changed']+=bool(result.get('is_stale') and result.get('latest_sha')!=data.get('latest_sha'))
    return stats

def run_due(db):
    token=str(uuid.uuid4());now=time.time();name='repository-freshness'
    with db.begin() as c:
        if not c.execute(select(task_leases).where(task_leases.c.name==name)).first():
            try:
                with c.begin_nested():c.execute(task_leases.insert().values(name=name,token=None,lease_until=0))
            except IntegrityError:pass  # Another worker initialized the same lease.
        claimed=c.execute(update(task_leases).where(task_leases.c.name==name,task_leases.c.lease_until<=now).values(token=token,lease_until=now+300))
        if claimed.rowcount!=1:return {'status':'already_running','checked':0,'changed':0,'failed':0}
    def heartbeat():
        with db.begin() as c:
            result=c.execute(update(task_leases).where(task_leases.c.name==name,task_leases.c.token==token).values(lease_until=time.time()+300))
        if result.rowcount!=1:raise ValueError('Freshness worker lease expired; another worker took over')
    try:return {'status':'completed',**check_due(db,heartbeat=heartbeat)}
    finally:
        with db.begin() as c:c.execute(update(task_leases).where(task_leases.c.name==name,task_leases.c.token==token).values(token=None,lease_until=0))
