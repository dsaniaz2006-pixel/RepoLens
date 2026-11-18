"""Test new optional API routes without GitHub or Gemini network calls."""
from fastapi.testclient import TestClient
import backend.api.api as api


def test_interview_api_reuses_source_context(monkeypatch, signed_in_client):
    example = {'metadata':{'full_name':'x/y'},'records':[{'path':'README.md','content':'help'}]}
    calls=[]
    monkeypatch.setattr(api,'collect_repo',lambda url: (calls.append(url),example)[1])
    monkeypatch.setattr(api,'interview_mode',lambda meta,records:{'questions':[{'question':'why?','answer':'yes'}]})
    res=signed_in_client.post('/api/interview',json={'url':'https://github.com/x/y'})
    assert res.status_code==200 and calls==['https://github.com/x/y']
    assert res.json()['questions'][0]['question']=='why?'


def test_contribution_api_uses_real_mode(monkeypatch, signed_in_client):
    monkeypatch.setattr(api,'collect_repo',lambda url:{'metadata':{},'records':[]})
    monkeypatch.setattr(api,'contribution_mode',lambda meta,records:{'task':'Review tests'})
    res=signed_in_client.post('/api/contribution',json={'url':'https://github.com/x/y'})
    assert res.status_code==200 and res.json()['task']=='Review tests'


def test_optional_api_input_validation(signed_in_client):
    res=signed_in_client.post('/api/interview',json={'url':''})
    assert res.status_code==422
