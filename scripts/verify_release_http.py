"""Real production HTTP smoke test with synthetic accounts; not OAuth/browser acceptance."""
import json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx

def main():
    from backend.auth.auth import AuthManager,COOKIE
    from backend.database.conversations import ConversationStore
    import backend.database.product_store as store
    with tempfile.TemporaryDirectory() as temp:
        directory=Path(temp)/'auth';manager=AuthManager(directory=directory,environ={})
        users=[manager.upsert_user('github',str(i),'Synthetic '+str(i)) for i in (9001,9002)]
        tokens=[manager.new_session(u['id']) for u in users]
        db=ConversationStore('sqlite:///'+str(directory/'conversations.sqlite3')).engine;store.metadata.create_all(db)
        source=store.put(db,users[0]['id'],'checklist',{'repository':'o/r','revision':'a'*40,'tasks':[{'id':'read','done':False,'task':'Read source','phase':'Day 1','path':'main.py','line':1,'end_line':1,'snippet':'pass','why':'Entry'}],'first_contribution':{'task':'Investigate','files':['main.py'],'assumptions':['Review first']}})
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        env={**os.environ,'REPOLENS_AUTH_DIR':str(directory),'REPOLENS_FRESHNESS_SCHEDULER':'external','REPOLENS_BASE_URL':base}
        def start():
            proc=subprocess.Popen([sys.executable,'-m','uvicorn','backend.api.api:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(100):
                try:
                    if httpx.get(base+'/api/health',trust_env=False).status_code==200:return proc
                except httpx.HTTPError:pass
                if proc.poll() is not None:raise RuntimeError('Server failed to start')
                time.sleep(.1)
            proc.terminate();raise RuntimeError('Server startup timed out')
        clients=[httpx.Client(base_url=base,trust_env=False,cookies={COOKIE:t},headers={'X-CSRF-Token':manager.authenticate(t)['csrf']}) for t in tokens]
        anon=httpx.Client(base_url=base,trust_env=False);proc=start()
        try:
            assert anon.get('/').status_code==200
            assert anon.get('/dashboard/').status_code==303
            assert anon.get('/api/workspaces').status_code==401
            assert anon.get('/gallery/pallets-flask/').status_code==200
            page=anon.get('/gallery/pallets-flask/').text;assert 'copy-link' in page and 'Try on your repo' in page
            owner,hire=clients
            wid=owner.post('/api/workspaces',json={'name':'HTTP acceptance'}).json()['id']
            invite=owner.post(f'/api/workspaces/{wid}/invite').json()
            assert anon.get('/join?token='+invite['token']).status_code==200
            assert hire.get('/api/invitations/'+invite['token']).json()['name']=='HTTP acceptance'
            assert hire.get(f'/api/workspaces/{wid}').status_code==403
            assert hire.post('/api/workspaces/join',json={'token':invite['token']}).status_code==200
            assert hire.post('/api/workspaces/join',json={'token':invite['token']}).status_code==400
            assert hire.post(f'/api/workspaces/{wid}/invite').status_code==403
            assignment=owner.post(f'/api/workspaces/{wid}/assignments',json={'checklist_id':source['id'],'assignee':users[1]['id']}).json()
            endpoint=f"/api/workspaces/{wid}/assignments/{assignment['id']}/complete"
            assert owner.post(endpoint,json={'task_id':'read','done':True}).status_code==403
            assert hire.post(endpoint,json={'task_id':'read','done':True}).status_code==200
            share=owner.post(f"/api/checklists/{source['id']}/share").json()['token']
            assert anon.get('/api/public/checklists/'+share).status_code==200
            owner.delete(f"/api/checklists/{source['id']}/share")
            assert anon.get('/api/public/checklists/'+share).status_code==404
            proc.terminate();proc.wait(timeout=10);proc=start()
            rows=hire.get(f'/api/workspaces/{wid}/assignments').json()
            assert rows[0]['data']['snapshot']['tasks'][0]['done'] is True
            assert owner.get('/api/workspaces').json()[0]['id']==wid
            payload={'passed':True,'production_build_http':True,'restart_persistence':True,'synthetic_accounts':2,'oauth_tested':False,'browser_tested':False,'checks':['anonymous gallery and CTA','dashboard login gating','invitation preview nonmutating','join and replay','member invitation denied','assignment owner/assignee restrictions','progress persisted after restart','public share revoke']}
            path=ROOT/'evaluation/HTTP_ACCEPTANCE_2026_10_25.json';path.write_text(json.dumps(payload,indent=2));print(json.dumps(payload))
        finally:
            proc.terminate();proc.wait(timeout=10)
            for client in clients+[anon]:client.close()
            db.dispose()
if __name__=='__main__':main()
