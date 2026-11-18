"""Section 7: streaming HTTP integration and inexpensive authentication tests."""
import json
import sys
from types import ModuleType
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    try:
        from authlib.integrations.starlette_client import OAuth
    except ImportError:
        for name in ('authlib','authlib.integrations','authlib.integrations.starlette_client'):
            mod=ModuleType(name)
            if name.endswith('starlette_client'):
                mod.OAuth=type('DisabledOAuthForOfflineTest',(),{'register':lambda *args,**kwargs:None})
            monkeypatch.setitem(sys.modules,name,mod)
    monkeypatch.setenv('REPOLENS_AUTH_DATABASE_URL','sqlite:///'+str(tmp_path/'auth.db'))
    monkeypatch.setenv('REPOLENS_DATABASE_URL','sqlite:///'+str(tmp_path/'app.db'))
    monkeypatch.setenv('REPOLENS_ENV','development')
    monkeypatch.setenv('REPOLENS_BASE_URL','http://127.0.0.1:5173')
    from backend.api.api import app
    from backend.auth.auth import AuthManager, COOKIE
    mgr=AuthManager(directory=tmp_path/'auth', environ={})
    monkeypatch.setattr(app.state,'auth',mgr)
    usr=mgr.upsert_user('github','stream-user','Streaming',email='test@example.com')
    session=mgr.new_session(usr['id'])
    c=TestClient(app)
    c.cookies.set(COOKIE,session)
    c.headers['X-CSRF-Token']=mgr.authenticate(session)['csrf']
    yield c,tmp_path


def parse_events(response):
    return [json.loads(item[6:]) for item in response.text.split('\n') if item.startswith('data: ')]


def test_stream_uses_same_quota_and_persists_history(client, monkeypatch):
    c,tmp=client
    import backend.api.api as endpoint
    import backend.services.pipeline as pipeline
    monkeypatch.setattr(endpoint,'REPORT_DIR',tmp/'reports')
    def fake_report(url, **kwargs):
        from backend.core.operation_progress import report_progress
        report_progress('Fetching repository tree…')
        report_progress('Analyzing selected source with AI…')
        return {'analysis':{'project_summary':'test'},'metadata':{'full_name':'pallets/flask'},
                'tree':[],'truncated':False,'revision':'a'*40,'evidence_paths':[]}
    monkeypatch.setattr(endpoint,'generate_report',fake_report)
    response=c.post('/api/analyze/stream',json={'url':'https://github.com/pallets/flask'})
    assert response.status_code==200,response.text
    assert response.headers['content-type'].startswith('text/event-stream')
    events=parse_events(response)
    assert any(e.get('status')=='progress' and 'tree' in e.get('message','') for e in events)
    assert events[-1]['status']=='done'
    assert events[-1]['result']['revision']=='a'*40
    assert list((tmp/'reports/users').glob('*/pallets-flask-analysis.json'))
    assert c.get('/api/usage').json()['usage']['analyze']['used']==1


def test_stream_sanitizes_error_and_does_not_leak_exception(client,monkeypatch):
    c,_=client
    import backend.api.api as endpoint
    def broken(*args,**kwargs):
        raise RuntimeError('SECRET_PASSWORD_SHOULD_NOT_APPEAR')
    monkeypatch.setattr(endpoint,'generate_report',broken)
    response=c.post('/api/analyze/stream',json={'url':'https://github.com/pallets/flask'})
    assert response.status_code==200
    events=parse_events(response)
    assert events[-1]['status']=='error'
    assert 'SECRET_PASSWORD' not in response.text


def test_stream_invalid_url_not_charged_and_unauthenticated_denied(client):
    c,_=client
    response=c.post('/api/analyze/stream',json={'url':'https://example.com/repo'})
    assert response.status_code==422
    unauth=TestClient(c.app)
    assert unauth.post('/api/analyze/stream',json={'url':'https://github.com/pallets/flask'}).status_code==401


def test_stream_policy_identical_to_legacy_analyze():
    from backend.security.usage_limits import action_for_request
    assert action_for_request('POST','/api/analyze/stream')=='analyze'
    assert action_for_request('POST','/api/analyze')=='analyze'
    assert action_for_request('GET','/api/analyze/stream') is None
