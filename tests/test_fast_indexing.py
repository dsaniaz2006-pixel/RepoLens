"""Regression checks for fast RAG: scope, quota math, cache batching and reuse."""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from backend.rag import embedding_cache as cache
from backend.services import pipeline


@pytest.mark.parametrize('profile,expected', [
    ('quick', [24, 35000, 90000]),
    ('balanced', [40, 80000, 250000]),
    ('full', [60, 120000, 600000]),
])
def test_profile_controls_index_coverage(profile, expected):
    env = dict(os.environ, REPOLENS_RAG_INDEX_PROFILE=profile)
    command = ('import json; from backend.core.config import '
               'RAG_MAX_FILES,RAG_MAX_FILE_CHARS,RAG_CONTEXT_BUDGET; '
               'print(json.dumps([RAG_MAX_FILES,RAG_MAX_FILE_CHARS,RAG_CONTEXT_BUDGET]))')
    process = subprocess.run([sys.executable, '-c', command], env=env,
                             capture_output=True, text=True, check=True)
    assert json.loads(process.stdout.strip()) == expected


def test_quick_profile_is_default():
    env = dict(os.environ)
    env.pop('REPOLENS_RAG_INDEX_PROFILE', None)
    process = subprocess.run([sys.executable, '-c',
        'from backend.core.config import RAG_INDEX_PROFILE; print(RAG_INDEX_PROFILE)'],
        env=env, capture_output=True, text=True, check=True)
    assert process.stdout.strip() == 'quick'


def test_token_estimation_no_longer_treats_bytes_as_tokens(monkeypatch):
    monkeypatch.setenv('REPOLENS_EMBED_CHARS_PER_TOKEN', '2.0')
    text = 'a' * 2000
    assert cache.estimate_tokens(text) == 1048
    monkeypatch.setenv('REPOLENS_EMBED_CHARS_PER_TOKEN', '1.0')
    assert cache.estimate_tokens(text) == 2048
    monkeypatch.setenv('REPOLENS_EMBED_CHARS_PER_TOKEN', '0.1')
    with pytest.raises(ValueError, match='between 1 and 4'):
        cache.estimate_tokens(text)


def test_cache_get_many_and_atomic_put(tmp_path, monkeypatch):
    monkeypatch.setenv('REPOLENS_EMBED_CACHE_DIR', str(tmp_path))
    cache.put_many('model', 'doc', [('a', [1., 2.]), ('b', [3., 4.])])
    assert cache.get_many('model', 'doc', ['a', 'b', 'missing']) == {
        'a': [1., 2.], 'b': [3., 4.]}
    with pytest.raises(ValueError, match='invalid'):
        cache.put_many('model', 'doc', [('c', [5.]), ('d', [float('nan')])])
    assert cache.get('model', 'doc', 'c') is None


def test_fast_batching_reduces_provider_calls_and_preserves_duplicate_positions(tmp_path, monkeypatch):
    monkeypatch.setenv('REPOLENS_EMBED_CACHE_DIR', str(tmp_path))
    monkeypatch.setenv('REPOLENS_EMBED_TPM', '20000')
    monkeypatch.setenv('REPOLENS_EMBED_CHARS_PER_TOKEN', '2.0')
    texts = [f'function_{i}_' + 'x' * 200 for i in range(20)]
    texts.append(texts[2])
    calls = []
    def generate(batch):
        calls.append(batch)
        return [[float(texts.index(t)), 2.0] for t in batch]
    got = cache.cached_embeddings(texts, 'doc', 'm', generate)
    assert len(calls) == 1 and len(calls[0]) == 20
    assert got[2] == got[-1]
    assert cache.cached_embeddings(texts, 'doc', 'm',
                                   lambda _: pytest.fail('should reuse cached vectors')) == got


def test_existing_current_index_returns_without_fetching_files(monkeypatch):
    sha = 'a' * 40
    monkeypatch.setattr(pipeline, 'fetch_repo_metadata',
                        lambda *_: {'default_branch': 'main', 'private': False})
    monkeypatch.setattr(pipeline, 'fetch_commit_sha', lambda *_: sha)
    monkeypatch.setattr(pipeline, 'resume_completed_index',
                        lambda repo, rev: {'repository': repo, 'revision': rev,
                                           'chunks': 8, 'indexed_files': 2})
    monkeypatch.setattr(pipeline, 'collect_repo',
                        lambda *a, **k: pytest.fail('current index must not fetch source'))
    result = pipeline.index_repo('https://github.com/o/r')
    assert result['reused'] and result['resumed'] and result['revision'] == sha
    assert result['reuse_lookup_seconds'] >= 0


def test_new_sha_indexes_once_and_keeps_pinned_revision(monkeypatch):
    sha = 'a' * 40
    monkeypatch.setattr(pipeline, 'fetch_repo_metadata',
                        lambda *_: {'default_branch': 'main', 'private': False})
    monkeypatch.setattr(pipeline, 'fetch_commit_sha', lambda *_: sha)
    monkeypatch.setattr(pipeline, 'resume_completed_index', lambda *a: None)
    calls = []
    def collect(url, **kwargs):
        calls.append(kwargs)
        return {'records': [{'path': 'src/a.py', 'content': 'def f(): pass\n'}],
                'repo_id': 'o/r', 'revision': sha, 'truncated': False,
                'metadata': {'default_branch': 'main'}}
    monkeypatch.setattr(pipeline, 'collect_repo', collect)
    monkeypatch.setattr(pipeline, 'embed_texts', lambda texts, **_: [[1., 2.]] * len(texts))
    monkeypatch.setattr(pipeline, 'store_chunks', lambda repo, rev, model, chunks, vectors: len(chunks))
    monkeypatch.setattr(pipeline, 'record_completed_index', lambda r: None)
    result = pipeline.index_repo('https://github.com/o/r')
    assert calls[0]['revision'] == sha and calls[0]['for_index'] is True
    assert result['indexed_files'] == 1 and result['chunks'] > 0
    assert result['index_profile'] == pipeline.RAG_INDEX_PROFILE and result['build_seconds'] >= 0


def test_current_private_repo_never_reuses_old_index(monkeypatch):
    monkeypatch.setattr(pipeline, 'fetch_repo_metadata',
                        lambda *_: {'default_branch': 'main', 'private': True})
    monkeypatch.setattr(pipeline, 'resume_completed_index',
                        lambda *_: pytest.fail('private index cannot be reused'))
    with pytest.raises(ValueError, match='Only public'):
        pipeline.index_repo('https://github.com/o/r')


def test_rate_budget_counts_estimated_not_raw_payload_bytes(monkeypatch):
    from backend.rag import embeddings
    expected=[]
    monkeypatch.setattr(cache, 'reserve', expected.append)
    class Client:
        def __init__(self):
            self.models = self
        def embed_content(self, **kwargs):
            return SimpleNamespace(embeddings=[])
    Client.__module__ = 'google.fake'
    result = embeddings._request_with_retry(Client(), model='test', contents=['a' * 2000])
    assert result.embeddings == []
    assert len(expected) == 1
    assert 1000 <= expected[0] < 2000


def test_quick_and_full_collections_cannot_mix(monkeypatch):
    from backend.rag import rag_store
    monkeypatch.setattr(rag_store, 'RAG_INDEX_PROFILE', 'quick')
    quick = rag_store.collection_name('o/r', 'a' * 40, 'model')
    monkeypatch.setattr(rag_store, 'RAG_INDEX_PROFILE', 'full')
    full = rag_store.collection_name('o/r', 'a' * 40, 'model')
    assert quick != full
