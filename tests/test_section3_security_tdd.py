"""Section 3 security acceptance: failure-first tests for control boundaries."""
import pytest

from backend.security.controls import (
    validate_repository_url, validate_question, public_error_detail,
    audit_route, validate_production_settings,
)


def test_github_input_disallows_untrusted_hosts_and_url_tricks():
    for url in ['http://github.com/a/b', 'https://github.com.evil.net/a/b',
                'https://github.com@localhost/a/b', 'https://github.com/a/b?token=secret',
                'https://github.com/a/b/other', 'https://127.0.0.1/a/b']:
        with pytest.raises(ValueError): validate_repository_url(url)
    assert validate_repository_url(' https://github.com/pallets/flask/ ') == 'https://github.com/pallets/flask/'


def test_question_allows_legitimate_security_questions_but_rejects_control_bytes():
    assert validate_question('How can I ignore previous instructions in tests?') == 'How can I ignore previous instructions in tests?'
    for text in ['', '  ', 'hello\x00 world', 'test\x1b']:
        with pytest.raises(ValueError): validate_question(text)


def test_error_details_never_echo_environment_secrets_or_credentials(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','FAKEVERYSECRETVALUE123')
    monkeypatch.setenv('GITHUB_TOKEN','GITHUB_NOT_FOR_OUTPUT_123')
    detail=public_error_detail(ValueError('bad FAKEVERYSECRETVALUE123 and https://alice:secret@host/db?password=YES'))
    assert 'FAKEVERYSECRETVALUE123' not in detail
    assert 'secret@' not in detail
    assert 'password=YES' not in detail
    assert 'GITHUB_NOT_FOR_OUTPUT_123' not in detail


def test_audit_router_whitelists_actions_no_tokens_or_querystrings():
    assert audit_route('DELETE','/api/conversations/abc') == ('conversation:deleted','abc')
    assert audit_route('POST','/api/workspaces/abc/members/def') == ('workspace:role_changed','abc')
    assert audit_route('POST','/api/workspaces/abc/invite') == ('workspace:invited','abc')
    assert audit_route('POST','/api/workspaces/join') == ('workspace:joined',None)
    assert audit_route('GET','/api/invitations/secret-token') is None
    assert audit_route('POST','/api/ask') is None
    assert audit_route('POST','/api/analyze') == ('report:generated',None)


def test_production_settings_fail_closed_with_recoverable_message():
    baseline={
        'REPOLENS_ENV':'production',
        'REPOLENS_BASE_URL':'https://repolens.example',
        'REPOLENS_SESSION_SECRET':'r'*48,
        'REPOLENS_AUTH_DATABASE_URL':'postgresql+psycopg://user:secret@host/auth',
        'REPOLENS_DATABASE_URL':'postgresql+psycopg://user:secret@host/app',
        'GITHUB_CLIENT_ID':'my-id','GITHUB_CLIENT_SECRET':'provider-secret',
    }
    assert validate_production_settings(baseline) is None
    for variable in ['REPOLENS_DATABASE_URL','REPOLENS_AUTH_DATABASE_URL','GITHUB_CLIENT_SECRET']:
        broken=dict(baseline); broken.pop(variable)
        with pytest.raises(ValueError,match='Production'): validate_production_settings(broken)
    broken=dict(baseline);broken['REPOLENS_BASE_URL']='http://127.0.0.1:5173'
    with pytest.raises(ValueError,match='HTTPS'): validate_production_settings(broken)
