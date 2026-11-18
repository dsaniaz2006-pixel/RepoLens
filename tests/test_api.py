from fastapi.testclient import TestClient
from backend.api.api import app

def test_health():
    client = TestClient(app)
    assert client.get('/api/health').json() == {'status':'ok'}

def test_bad_report_name(signed_in_client):
    client = signed_in_client
    assert client.get('/api/report/bad!owner/repo').status_code == 400

def test_bad_question_payload(signed_in_client):
    client = signed_in_client
    assert client.post('/api/ask', json={'url':'https://github.com/a/b','question':''}).status_code == 422


def test_config_status_does_not_expose_secrets(monkeypatch, signed_in_client):
    monkeypatch.setenv('GEMINI_API_KEY', 'DO_NOT_SHOW_GEMINI')
    monkeypatch.setenv('GITHUB_TOKEN', 'DO_NOT_SHOW_GITHUB')
    client=signed_in_client
    response=client.get('/api/config-status')
    assert response.status_code==200
    data=response.json()
    assert data['gemini_key_configured'] is True
    assert data['github_token_configured'] is True
    assert 'DO_NOT_SHOW' not in response.text
