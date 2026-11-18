"""Opt-in integration test against a dedicated configured PostgreSQL database."""
import os,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'.env')
from backend.database.conversations import ConversationStore
from backend.database.product_store import workspace,invite,join,role,items,members,invites
from sqlalchemy import delete
url=os.getenv('REPOLENS_DATABASE_URL','')
if not url.startswith('postgresql+psycopg://'):raise SystemExit('Configure REPOLENS_DATABASE_URL for a dedicated PostgreSQL test database')
store=ConversationStore(url);user='check-'+uuid.uuid4().hex;cid=None;wid=None
try:
    chat=store.create(user,'pallets/flask','a'*40);cid=chat['id']
    _,token,_=store.begin(user,cid,'pallets/flask',0)
    store.finish(cid,token,0,'test',{'answer':'test','citations':[],'uncertain':True})
    assert store.get(user,cid)['version']==2
    wid=workspace(store.engine,user,'Integration test')
    assert join(store.engine,user+'-member',invite(store.engine,wid,user))==wid
    assert role(store.engine,wid,user+'-member')=='member'
    print('PostgreSQL conversation persistence and workspace invite checks passed')
finally:
    if cid:store.remove(user,cid)
    if wid:
        with store.engine.begin() as c:
            c.execute(delete(invites).where(invites.c.workspace==wid));c.execute(delete(members).where(members.c.workspace==wid));c.execute(delete(items).where(items.c.id==wid))
