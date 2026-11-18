"""Provider selection shared by model generation and embedding paths.

Model errors have deliberately bounded, non-secret messages so users can
troubleshoot quota and invalid JSON without exposing provider responses.
"""
import json
import math
import os
import time
from types import SimpleNamespace
from urllib.parse import urlparse

import requests


class ModelResponseError(ValueError):
    """Safe model failure with a stable kind for bounded callers' retries."""

    def __init__(self, message, *, kind='provider', status=None):
        super().__init__(message)
        self.kind = kind
        self.status = status


def provider():
    value = os.getenv('REPOLENS_MODEL_PROVIDER', 'gemini').lower()
    if value not in {'gemini', 'ollama'}:
        raise ValueError('REPOLENS_MODEL_PROVIDER must be gemini or ollama')
    return value


def local_request(route, payload):
    base = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
    parsed = urlparse(base)
    if (parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('OLLAMA_URL must use HTTP on a loopback address')
    try:
        with requests.Session() as session:
            session.trust_env = False
            response = session.post(base + route, json=payload, timeout=120, allow_redirects=False)
            if response.status_code != 200:
                raise ModelResponseError('Ollama returned an error; verify installed model and local server',
                                         kind='provider', status=response.status_code)
            return response.json()
    except requests.RequestException as exc:
        raise ModelResponseError('Cannot reach local Ollama; start it and pull configured models',
                                 kind='connection') from exc


class OllamaClient:
    def __init__(self):
        self.models = self

    def generate_content(self, *, contents, model=None, config=None, **kwargs):
        result = local_request('/api/generate', {
            'model': os.getenv('OLLAMA_MODEL', 'llama3.2'),
            'prompt': contents, 'stream': False, 'format': 'json',
            'options': {'temperature': 0.1, 'num_ctx': 32768},
        })
        text = result.get('response')
        if not isinstance(text, str) or not text.strip():
            raise ModelResponseError('Ollama returned an empty response', kind='empty_json')
        return SimpleNamespace(text=text)


def local_client():
    return OllamaClient() if provider() == 'ollama' else None


def local_embeddings(texts):
    results = []
    for offset in range(0, len(texts), 16):
        from backend.core.operation_progress import report_progress
        report_progress('Creating local embeddings…')
        batch = local_request('/api/embed', {
            'model': os.getenv('OLLAMA_EMBED_MODEL', 'nomic-embed-text'),
            'input': texts[offset:offset+16], 'truncate': False,
        }).get('embeddings')
        if not isinstance(batch, list) or len(batch) != len(texts[offset:offset+16]):
            raise ValueError('Ollama embedding count mismatch')
        for vector in batch:
            if (not isinstance(vector, list) or not vector
                    or not all(type(n) in (float, int) and math.isfinite(n) for n in vector)):
                raise ValueError('Invalid Ollama embedding')
        results.extend(batch)
    if results and len({len(v) for v in results}) != 1:
        raise ValueError('Ollama embedding dimensions mismatch')
    return results


def _http_status(exc):
    """Read SDK status codes without including the exception text (may be sensitive)."""
    for obj in (exc, getattr(exc, 'response', None)):
        if obj is None:
            continue
        for name in ('status_code', 'code', 'status'):
            value = getattr(obj, name, None)
            if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
                return value
            if isinstance(value, str) and value.isdigit() and 100 <= int(value) <= 599:
                return int(value)
    return None


def _provider_failure(exc, model_kind):
    if isinstance(exc, ModelResponseError):
        return exc
    code = _http_status(exc)
    name = 'Ollama' if model_kind == 'ollama' else 'Gemini'
    if code == 429:
        return ModelResponseError(f'{name} quota or rate limit reached (HTTP 429). Check provider quota before retrying.',
                                  kind='quota', status=429)
    if code in (401, 403):
        return ModelResponseError(f'{name} API access denied (HTTP {code}). Check model access and credentials.',
                                  kind='auth', status=code)
    if code == 404:
        return ModelResponseError(f'{name} model not found (HTTP 404). Check the configured model name.',
                                  kind='model', status=404)
    if code == 400:
        return ModelResponseError(f'{name} rejected the generation request (HTTP 400). Check model support and input size.',
                                  kind='request', status=400)
    if code is not None and code >= 500:
        return ModelResponseError(f'{name} service unavailable (HTTP {code}). Retry later.',
                                  kind='unavailable', status=code)
    if isinstance(exc, (requests.Timeout, TimeoutError)) or 'timeout' in type(exc).__name__.lower():
        return ModelResponseError(f'{name} generation timed out. Try a smaller source prompt.',
                                  kind='timeout')
    return ModelResponseError(f'{name} generation request failed. Check server logs and provider access.',
                              kind='provider')


def _generate_structured_response(client, *, model, prompt, kind):
    """Retry a *transient* Gemini 5xx at most twice; never retry auth/quota/client errors.

    The result is still validated by json_model. This bounded retry is for
    provider unavailability only, not a replacement for model/source checks.
    """
    attempts = 3 if kind == 'gemini' else 1
    for index in range(attempts):
        try:
            return client.models.generate_content(
                model=model, contents=prompt,
                config={'response_mime_type': 'application/json', 'temperature': 0.1},
            )
        except Exception as exc:
            if kind != 'gemini' or _http_status(exc) not in (500, 502, 503, 504) or index == attempts - 1:
                raise _provider_failure(exc, kind) from exc
            # 1s, then 2s: modest backoff; leave quota (429) alone.
            time.sleep(2 ** index)
    raise AssertionError('Unreachable: retry loop always returns or raises')


def json_model(prompt):
    """Produce an object; never return misleading text or leak raw SDK errors."""
    from backend.core.config import GEMINI_MODEL

    kind = provider()
    client = local_client()
    if client is None:
        key = os.getenv('GEMINI_API_KEY')
        if not key:
            raise ModelResponseError('GEMINI_API_KEY is missing; configure it in your local .env',
                                     kind='auth')
        try:
            from google import genai
            client = genai.Client(api_key=key, http_options={
                'timeout': 60000, 'retry_options': {'attempts': 1},
            })
        except Exception as exc:
            raise _provider_failure(exc, kind) from exc
    response = _generate_structured_response(client, model=GEMINI_MODEL, prompt=prompt, kind=kind)
    try:
        text = getattr(response, 'text', None)
    except (ValueError, AttributeError) as exc:
        raise ModelResponseError('AI model response contained no usable JSON text.',
                                 kind='empty_json') from exc
    if not isinstance(text, str) or not text.strip():
        raise ModelResponseError('AI model returned an empty JSON response. Use a smaller prompt or check output limits.',
                                 kind='empty_json')
    try:
        result = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ModelResponseError('AI model returned malformed JSON. Regeneration with stricter instructions is needed.',
                                 kind='invalid_json') from exc
    if not isinstance(result, dict):
        raise ModelResponseError('AI model returned JSON but not a JSON object.', kind='invalid_json')
    return result
