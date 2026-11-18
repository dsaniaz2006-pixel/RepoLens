import pytest
from backend.rag import embedding_cache as cache
from backend.core.operation_progress import OperationStopped

@pytest.fixture
def limiter(tmp_path, monkeypatch):
    monkeypatch.setenv('REPOLENS_EMBED_CACHE_DIR', str(tmp_path))
    monkeypatch.setenv('REPOLENS_EMBED_TPM', '15000')
    monkeypatch.setenv('REPOLENS_EMBED_RPM', '30')
    clock=[100.0]
    monkeypatch.setattr(cache.time,'time',lambda:clock[0])
    monkeypatch.setattr(cache.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(cache,'pause',lambda seconds:clock.__setitem__(0,clock[0]+seconds))
    return clock

def test_two_batches_resume_after_window(limiter,monkeypatch):
    messages=[];monkeypatch.setattr(cache,'report_progress',messages.append)
    cache.reserve(8094);cache.reserve(6457);cache.reserve(7000)
    assert 160 <= limiter[0] < 161
    assert any('14,551/15,000' in (m or '') for m in messages)
    with cache.connect() as c:assert c.execute('SELECT count(*) FROM usage').fetchone()[0]==1

def test_future_clock_does_not_wait_forever(limiter):
    with cache.connect() as c:c.execute('INSERT INTO usage VALUES (?,?)',(1000,14551))
    with pytest.raises(cache.QuotaBudgetError,match='system clock'):cache.reserve(7000)

def test_contended_limiter_stops_after_90_seconds(limiter,monkeypatch):
    cache.reserve(14551)
    def pause(seconds):
        limiter[0]+=seconds
        with cache.connect() as c:c.execute('UPDATE usage SET stamp=?',(limiter[0],))
    monkeypatch.setattr(cache,'pause',pause)
    with pytest.raises(cache.QuotaBudgetError,match='90 seconds'):cache.reserve(7000)
    assert limiter[0]==190

def test_wait_can_be_cancelled(limiter,monkeypatch):
    cache.reserve(14551)
    def stop(message):raise OperationStopped('cancelled')
    monkeypatch.setattr(cache,'report_progress',stop)
    with pytest.raises(OperationStopped):cache.reserve(7000)

def test_quota_error_reaches_user(monkeypatch):
    from backend.rag import embeddings
    monkeypatch.setenv('REPOLENS_MODEL_PROVIDER','gemini')
    def fail(*args):raise cache.QuotaBudgetError('Local quota stayed busy')
    monkeypatch.setattr(cache,'cached_embeddings',fail)
    with pytest.raises(embeddings.EmbeddingError,match='Local quota stayed busy'):embeddings.embed_texts(['x'])


def test_cached_vectors_survive_a_quota_stop(limiter):
    cache.put('model','doc','saved',[1.0,2.0])
    def fail(texts):raise cache.QuotaBudgetError('busy')
    with pytest.raises(cache.QuotaBudgetError):
        cache.cached_embeddings(['saved','new'],'doc','model',fail)
    assert cache.get('model','doc','saved')==[1.0,2.0]
    assert cache.get('model','doc','new') is None
