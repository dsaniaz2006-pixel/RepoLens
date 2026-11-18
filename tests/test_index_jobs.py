import time
from threading import Event
import pytest
from backend.rag.index_jobs import IndexJobs
from backend.core.operation_progress import report_progress, pause


def wait_for(manager, owner, job_id):
    for _ in range(200):
        job=manager.get(owner, job_id)
        if job['state']!='running': return job
        time.sleep(.005)
    pytest.fail('job did not finish')


def test_progress_completion_and_owner_isolation():
    manager=IndexJobs();release=Event();started=Event()
    def work(url):
        report_progress('Embedding 1 of 2');started.set();release.wait(1)
        return {'chunks':2}
    job=manager.start('alice','https://github.com/a/b',work,str);started.wait(1)
    assert manager.get('alice',job['id'])['message']=='Embedding 1 of 2'
    assert manager.get('bob',job['id']) is None
    assert manager.get('bob',job['id'],cancel=True) is None
    assert manager.start('alice','https://github.com/A/B.git',work,str)['id']==job['id']
    with pytest.raises(ValueError,match='currently being indexed'):
        manager.start('bob','https://github.com/a/b/',work,str)
    release.set()
    assert wait_for(manager,'alice',job['id'])['result']=={'chunks':2}
    manager.pool.shutdown()


def test_cancel_stops_work_before_final_write():
    manager=IndexJobs();started=Event();writes=[]
    def work(url):
        started.set();pause(10);writes.append('saved')
    job=manager.start('alice','https://github.com/a/b',work,str);started.wait(1)
    manager.get('alice',job['id'],cancel=True)
    assert wait_for(manager,'alice',job['id'])['state']=='cancelled'
    assert writes==[]
    manager.pool.shutdown()


def test_deadline_and_failure_message():
    manager=IndexJobs(timeout=0)
    job=manager.start('alice','https://github.com/a/b',lambda _:None,str)
    assert wait_for(manager,'alice',job['id'])['state']=='failed'
    manager.pool.shutdown()
    manager=IndexJobs()
    def fail(_): raise RuntimeError('secret provider error')
    job=manager.start('alice','https://github.com/a/b',fail,lambda _: 'Safe error')
    assert wait_for(manager,'alice',job['id'])['error']=='Safe error'
    manager.pool.shutdown()


def test_index_job_api_auth_csrf_and_completion(signed_in_client,monkeypatch):
    import backend.api.api as api
    from fastapi.testclient import TestClient
    manager=IndexJobs();monkeypatch.setattr(api,'jobs',manager)
    monkeypatch.setenv('GEMINI_API_KEY','offline-test-key')
    monkeypatch.setattr(api,'index_repo',lambda url:{'chunks':3,'revision':'a'*40})
    assert TestClient(api.app).post('/api/index/jobs',json={'url':'https://github.com/a/b'}).status_code==401
    response=signed_in_client.post('/api/index/jobs',json={'url':'https://github.com/a/b'})
    assert response.status_code==202
    job=response.json();finished=wait_for(manager, signed_in_client.get('/api/auth/me').json()['user']['id'],job['id'])
    assert finished['result']['chunks']==3
    assert signed_in_client.get('/api/jobs/'+job['id']).json()['state']=='completed'
    signed_in_client.headers.pop('X-CSRF-Token')
    assert signed_in_client.post('/api/jobs/'+job['id']+'/cancel').status_code==403
    manager.pool.shutdown()


def test_index_job_missing_gemini_fails_immediately(signed_in_client,monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    r=signed_in_client.post('/api/index/jobs',json={'url':'https://github.com/a/b'})
    assert r.status_code==400 and 'Google sign-in' in r.json()['detail']


def test_pipeline_rejects_overlapping_writes_even_outside_job_api(monkeypatch):
    import backend.services.pipeline as pipeline
    from concurrent.futures import ThreadPoolExecutor
    started, release = Event(), Event()
    def work(*args, **kwargs):
        started.set()
        assert release.wait(2)
        return {'chunks': 1}
    monkeypatch.setattr(pipeline, '_index_repo', work)
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(pipeline.index_repo, 'https://github.com/A/B')
        assert started.wait(1)
        try:
            with pytest.raises(ValueError, match='currently being indexed'):
                pipeline.index_repo('https://github.com/a/b.git')
        finally:
            release.set()
        assert running.result() == {'chunks': 1}
    assert pipeline.index_repo('https://github.com/a/b') == {'chunks': 1}
