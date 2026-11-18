"""Section 4 browser-free HTTP E2E through real FastAPI middleware.
The external Gemini/GitHub call is replaced by deterministic local function.
"""
from fastapi.testclient import TestClient
import pytest
from backend.api.api import app
from backend.auth.auth import AuthManager, COOKIE
from backend.database.schema_migrations import upgrade_databases

@pytest.fixture(params=['sqlite','sqlalchemy'])
def demo(request,tmp_path,monkeypatch):
    if request.param=='sqlalchemy':
        auth='sqlite:///'+str(tmp_path/'auth.sqlite3')
        upgrade_databases(auth,'sqlite:///'+str(tmp_path/'app.sqlite3'))
        mgr=AuthManager(directory=tmp_path/'userdir',environ={'REPOLENS_AUTH_DATABASE_URL':auth})
    else:
        mgr=AuthManager(directory=tmp_path/'userdir',environ={})
    monkeypatch.setattr(app.state,'auth',mgr)
    alice=mgr.upsert_user('github','alice','Alice')
    bob=mgr.upsert_user('github','bob','Bob')
    token=mgr.new_session(alice['id'])
    browser=TestClient(app)
    browser.cookies.set(COOKIE,token)
    browser.headers['X-CSRF-Token']=mgr.authenticate(token)['csrf']
    return mgr,alice,bob,browser


def test_usage_route_authenticated_scoped(demo):
    mgr,alice,bob,browser=demo
    assert browser.get('/api/usage').json()['usage']['ask']=={'used':0,'limit':20,'remaining':20}
    assert TestClient(app).get('/api/usage').status_code==401
    mgr.reserve_usage(alice['id'],'ask','127.0.0.1')
    assert browser.get('/api/usage').json()['usage']['ask']['used']==1
    bob_token=mgr.new_session(bob['id'])
    separate=TestClient(app);separate.cookies.set(COOKIE,bob_token)
    assert separate.get('/api/usage').json()['usage']['ask']['used']==0


def test_http_budget_exhaustion_returns_429_before_external_work(demo,monkeypatch):
    mgr,alice,bob,browser=demo
    import backend.api.api as api
    calls=[]
    def fake_optional(url,mode):
        calls.append((url,mode))
        return {'questions':[]}
    monkeypatch.setattr(api,'_optional_mode',fake_optional)
    for index in range(5):
        response=browser.post('/api/interview',json={'url':'https://github.com/pallets/flask'})
        assert response.status_code==200,response.text
        assert response.headers.get('X-RateLimit-Remaining')==str(4-index)
    response=browser.post('/api/interview',json={'url':'https://github.com/pallets/flask'})
    assert response.status_code==429
    assert 'Retry-After' in response.headers
    assert len(calls)==5
    assert browser.get('/api/usage').json()['usage']['analyze']['used']==5
    # Refreshing, or using another browser session of same user, doesn't bypass.
    token=mgr.new_session(alice['id']); other=TestClient(app)
    other.cookies.set(COOKIE,token);other.headers['X-CSRF-Token']=mgr.authenticate(token)['csrf']
    assert other.post('/api/interview',json={'url':'https://github.com/pallets/flask'}).status_code==429


def test_csrf_and_unauthenticated_attempts_do_not_spend_quota(demo):
    mgr,alice,bob,browser=demo
    raw=TestClient(app)
    assert raw.post('/api/analyze',json={'url':'https://github.com/pallets/flask'}).status_code==401
    other=TestClient(app)
    other.cookies.set(COOKIE,browser.cookies.get(COOKIE))
    assert other.post('/api/analyze',json={'url':'https://github.com/pallets/flask'}).status_code==403
    assert browser.get('/api/usage').json()['usage']['analyze']['used']==0


def test_bearer_request_spends_same_user_quota(demo,monkeypatch):
    mgr,alice,bob,browser=demo
    import backend.api.api as api
    monkeypatch.setattr(api,'_optional_mode',lambda url,mode:{'questions':[]})
    key=mgr.create_api_key(alice['id'],'Integration')['key']
    response=TestClient(app).post('/api/interview',json={'url':'https://github.com/pallets/flask'},headers={'Authorization':'Bearer '+key})
    assert response.status_code==200
    assert browser.get('/api/usage').json()['usage']['analyze']['used']==1

def test_fail_closed_if_quota_database_is_unavailable(demo,monkeypatch):
    mgr,alice,bob,browser=demo
    import backend.api.api as api
    executed=[]
    monkeypatch.setattr(api,'_optional_mode',lambda url,mode:executed.append(1))
    def offline(*args,**kwargs):raise RuntimeError('database host unavailable; private URL omitted')
    monkeypatch.setattr(mgr,'reserve_usage',offline)
    response=browser.post('/api/interview',json={'url':'https://github.com/pallets/flask'})
    assert response.status_code==503
    assert 'private URL' not in response.text
    assert executed==[]

def test_usage_endpoint_fails_safely_when_storage_is_unavailable(demo,monkeypatch):
    mgr,alice,bob,browser=demo
    def offline(*args,**kwargs): raise RuntimeError('private database password error')
    monkeypatch.setattr(mgr,'usage_snapshot',offline)
    response=browser.get('/api/usage')
    assert response.status_code==503
    assert 'password' not in response.text
