"""Phase 6 incident regressions: bounded evidence and safe provider failures."""
import json
from types import SimpleNamespace

import pytest

from backend.ai import model_provider
from backend.services import onboarding


def dataset(n=1):
    return {'repo_id': 'pallets/flask', 'revision': 'a' * 40,
            'records': [{'path': f'src/app{i}.py',
                         'content': 'def main():\n    return True\n' + '\n'.join(f'def test_{j}(): pass' for j in range(2000))}
                        for i in range(n)]}


def valid():
    return {
        'day_1': [{'task': 'Inspect entry point', 'file': 'src/app0.py', 'line': 1,
                   'why': 'Trace startup', 'snippet': 'def main():'}],
        'week_1': [{'task': 'Trace return value', 'file': 'src/app0.py', 'line': 2,
                    'why': 'Inspect state', 'snippet': '    return True'}],
        'first_contribution': {'task': 'Investigate tests', 'files': ['src/app0.py'],
                               'assumptions': ['Tests may be incomplete']},
    }


def test_compact_prompt_uses_real_line_numbers_and_stays_bounded():
    seen = []
    result = onboarding.generate(dataset(30), model=lambda prompt: (seen.append(prompt), valid())[1])
    assert len(seen[0]) <= onboarding.MAX_ONBOARDING_PROMPT_CHARS
    assert len(json.dumps(dataset(30))) > len(seen[0]) * 10
    assert '"line": 1, "text": "def main():"' in seen[0]
    assert result['tasks'][0]['line'] == 1
    assert result['generation'] == 'ai_with_verified_quotes'


def test_invalid_source_quote_may_be_repaired_once(monkeypatch):
    attempts = []
    bad = valid()
    bad['day_1'][0]['snippet'] = 'def imaginary():'

    def fake(prompt):
        attempts.append(prompt)
        return bad if len(attempts) == 1 else valid()

    monkeypatch.setattr(onboarding, 'json_model', fake)
    result = onboarding.generate(dataset())
    assert len(attempts) == 2
    assert 'REPAIR REQUIRED' in attempts[1]
    assert result['tasks'][0]['snippet'] == 'def main():'


def test_provider_malformed_json_retry_once(monkeypatch):
    tries = []

    def fake(prompt):
        tries.append(prompt)
        if len(tries) == 1:
            raise model_provider.ModelResponseError('bad JSON', kind='invalid_json')
        return valid()

    monkeypatch.setattr(onboarding, 'json_model', fake)
    assert onboarding.generate(dataset())['tasks']
    assert len(tries) == 2


def test_quota_does_not_trigger_second_request(monkeypatch):
    tries = []

    def fake(prompt):
        tries.append(prompt)
        raise model_provider.ModelResponseError('Gemini quota or rate limit reached (HTTP 429)',
                                                kind='quota', status=429)

    monkeypatch.setattr(onboarding, 'json_model', fake)
    with pytest.raises(model_provider.ModelResponseError, match='429'):
        onboarding.generate(dataset())
    assert len(tries) == 1


def test_model_provider_classifies_sdk_quota_without_leaking_secret(monkeypatch):
    monkeypatch.setenv('REPOLENS_MODEL_PROVIDER', 'ollama')

    class FailingClient:
        models = None
        def __init__(self): self.models = self
        def generate_content(self, **kwargs):
            error = RuntimeError('raw sdk error contains secret-key-123')
            error.status_code = 429
            raise error

    monkeypatch.setattr(model_provider, 'local_client', lambda: FailingClient())
    with pytest.raises(model_provider.ModelResponseError) as err:
        model_provider.json_model('test')
    assert err.value.status == 429 and err.value.kind == 'quota'
    assert 'secret-key-123' not in str(err.value)


def test_model_provider_rejects_empty_and_non_object_output(monkeypatch):
    monkeypatch.setenv('REPOLENS_MODEL_PROVIDER', 'ollama')
    for value, kind in [('', 'empty_json'), ('{} garbage', 'invalid_json'), ('[1, 2]', 'invalid_json')]:
        fake = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_: SimpleNamespace(text=value)))
        monkeypatch.setattr(model_provider, 'local_client', lambda: fake)
        with pytest.raises(model_provider.ModelResponseError) as err:
            model_provider.json_model('test')
        assert err.value.kind == kind


def test_invalid_model_schema_never_saved_after_repair(monkeypatch):
    monkeypatch.setattr(onboarding, 'json_model', lambda prompt: {'day_1': [], 'week_1': [],
                                                                  'first_contribution': {}})
    with pytest.raises(ValueError, match='failed source validation after one repair'):
        onboarding.generate(dataset())


def test_explicit_injected_model_rejects_fabrication_without_retry():
    bad = valid()
    bad['week_1'][0]['line'] = 300000
    calls = []
    with pytest.raises(ValueError, match='does not match'):
        onboarding.generate(dataset(), model=lambda prompt: (calls.append(prompt), bad)[1])
    assert len(calls) == 1

@pytest.mark.parametrize('kind,expected', [
    ('quota', 429), ('auth', 503), ('invalid_json', 502),
    ('empty_json', 502), ('timeout', 504), ('model', 503),
])
def test_checklist_api_surface_preserves_provider_error_category(kind, expected):
    from fastapi import HTTPException
    from backend.api.product_api import safe

    def fail():
        raise model_provider.ModelResponseError('Safe error detail', kind=kind)

    with pytest.raises(HTTPException) as raised:
        safe(fail)
    assert raised.value.status_code == expected
    assert raised.value.detail == 'Safe error detail'


class _TransientError(RuntimeError):
    status_code = 503


class _QuotaError(RuntimeError):
    status_code = 429


def test_gemini_retries_transient_503_then_uses_valid_response(monkeypatch):
    calls, delays = [], []

    def call(**kwargs):
        calls.append(kwargs)
        if len(calls) < 3:
            raise _TransientError('provider overloaded: internal details')
        return SimpleNamespace(text=json.dumps(valid()))

    monkeypatch.setattr(model_provider.time, 'sleep', delays.append)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=call))
    response = model_provider._generate_structured_response(client, model='example', prompt='hello', kind='gemini')
    assert json.loads(response.text) == valid()
    assert len(calls) == 3
    assert delays == [1, 2]


def test_gemini_503_stops_after_three_attempts_without_leaking_details(monkeypatch):
    count, delays = [], []
    monkeypatch.setattr(model_provider.time, 'sleep', delays.append)

    def fail(**kwargs):
        count.append(1)
        raise _TransientError('secret: provider token 123')

    client = SimpleNamespace(models=SimpleNamespace(generate_content=fail))
    with pytest.raises(model_provider.ModelResponseError) as error:
        model_provider._generate_structured_response(client, model='example', prompt='hello', kind='gemini')
    assert error.value.status == 503 and error.value.kind == 'unavailable'
    assert len(count) == 3 and delays == [1, 2]
    assert 'secret: provider token 123' not in str(error.value)


def test_gemini_does_not_retry_quota_or_ollama_errors(monkeypatch):
    calls, delays = [], []
    monkeypatch.setattr(model_provider.time, 'sleep', delays.append)

    def quota(**kwargs):
        calls.append(1)
        raise _QuotaError('sensitive')

    client = SimpleNamespace(models=SimpleNamespace(generate_content=quota))
    with pytest.raises(model_provider.ModelResponseError) as error:
        model_provider._generate_structured_response(client, model='example', prompt='hello', kind='gemini')
    assert error.value.kind == 'quota' and len(calls) == 1 and not delays

    calls.clear()
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: (calls.append(1), (_ for _ in ()).throw(_TransientError('Ollama down')))[1]))
    with pytest.raises(model_provider.ModelResponseError):
        model_provider._generate_structured_response(client, model='local', prompt='hello', kind='ollama')
    assert len(calls) == 1 and not delays
