"""Phase 0 regression tests: restart recovery, durable receipts and quota failures."""
import sqlite3
import time
from types import SimpleNamespace

import pytest

from backend.rag.index_jobs import IndexJobs
from backend.rag import embedding_cache
from backend.rag import embeddings


def wait_for(manager, owner, job_id):
    for _ in range(300):
        current = manager.get(owner, job_id)
        if current and current['state'] not in ('running', 'interrupted'):
            return current
        time.sleep(0.01)
    pytest.fail('Index job did not finish')


def test_persistent_completed_job_receipt_and_account_boundary(tmp_path):
    path = tmp_path / 'private' / 'jobs.sqlite3'
    a = IndexJobs(storage_path=path)
    receipt = a.start('alice', 'https://github.com/owner/repo',
                      lambda url: {'chunks': 3}, lambda exc: 'safe error')
    assert wait_for(a, 'alice', receipt['id'])['state'] == 'completed'
    a.pool.shutdown()
    b = IndexJobs(storage_path=path)
    assert b.get('bob', receipt['id']) is None
    assert b.get('alice', receipt['id'])['result'] == {'chunks': 3}
    b.pool.shutdown()


def test_interrupted_job_auto_recovers_same_id(tmp_path):
    path = tmp_path / 'jobs.sqlite3'
    a = IndexJobs(storage_path=path)
    receipt = a.start('alice', 'https://github.com/o/r',
                      lambda url: {'chunks': 1}, str)
    assert wait_for(a, 'alice', receipt['id'])['state'] == 'completed'
    a.pool.shutdown()
    # Simulate the abrupt process exit after the job was recorded as running.
    with sqlite3.connect(path) as c:
        c.execute('UPDATE index_jobs SET state=?, cancel_requested=0 WHERE id=?',
                  ('running', receipt['id']))
    b = IndexJobs(storage_path=path)
    assert b.get('alice', receipt['id'])['state'] == 'interrupted'
    seen = []
    assert b.recover(lambda owner, url: (seen.append((owner, url)) or {'chunks': 2}), str) == 1
    result = wait_for(b, 'alice', receipt['id'])
    assert result['result'] == {'chunks': 2}
    assert seen == [('alice', 'https://github.com/o/r')]
    b.pool.shutdown()


def test_cancel_requested_during_restart_is_never_auto_restarted(tmp_path):
    path = tmp_path / 'jobs.sqlite3'
    a = IndexJobs(storage_path=path)
    receipt = a.start('alice', 'https://github.com/o/r', lambda url: {'chunks': 1}, str)
    assert wait_for(a, 'alice', receipt['id'])['state'] == 'completed'
    a.pool.shutdown()
    with sqlite3.connect(path) as c:
        c.execute('UPDATE index_jobs SET state=?, cancel_requested=1 WHERE id=?',
                  ('running', receipt['id']))
    b = IndexJobs(storage_path=path)
    assert b.get('alice', receipt['id'])['state'] == 'cancelled'
    assert b.recover(lambda owner, url: pytest.fail('must not restart'), str) == 0
    b.pool.shutdown()


def test_corrupt_cached_dimensions_are_not_returned(tmp_path, monkeypatch):
    monkeypatch.setenv('REPOLENS_EMBED_CACHE_DIR', str(tmp_path))
    embedding_cache.put('model', 'doc', 'a', [0.1, 0.2])
    embedding_cache.put('model', 'doc', 'b', [0.3])
    with pytest.raises(ValueError, match='dimensions'):
        embedding_cache.cached_embeddings(['a', 'b'], 'doc', 'model', lambda _: pytest.fail('all cached'))


def test_daily_quota_429_fails_fast_with_actionable_error(monkeypatch):
    class DailyQuota(Exception):
        code = 429
        details = {'error': {'message': 'Quota exceeded: requests per day (RPD) limit'}}
    class Client:
        class Models:
            def embed_content(self, **kwargs):
                raise DailyQuota('429 exhausted daily quota')
        models = Models()
    monkeypatch.setattr(embeddings, 'pause', lambda _: pytest.fail('Must not wait for daily quota'))
    with pytest.raises(embeddings.EmbeddingError, match='daily quota'):
        embeddings.embed_texts(['source'], client=Client(), model='test-model')
