"""Exercise actual local Chroma persistence with synthetic vectors, no API calls."""
import pytest

from backend.rag.chunker import chunk_files
from backend.rag.rag_store import store_chunks, query_chunks, StoreError


def test_persisted_index_reopens_and_is_revision_isolated(tmp_path):
    pytest.importorskip('chromadb')
    repo, revision, model = 'local/storage-check', 'a' * 40, 'synthetic-test'
    chunks = chunk_files([
        {'path': 'src/auth.py', 'content': 'def validate_token(token):\n    return bool(token)\n'},
        {'path': 'src/math.py', 'content': 'def add(a, b):\n    return a + b\n'},
    ], repo, revision, size=200, overlap=20)
    assert len(chunks) == 2
    vectors = [[1., 0., 0.], [0., 1., 0.]]
    path = str(tmp_path / 'chroma')
    assert store_chunks(repo, revision, model, chunks, vectors, path=path) == 2
    # The adapter creates a new PersistentClient for each call. Repeat indexing
    # must upsert the same chunk IDs instead of duplicating the collection.
    assert store_chunks(repo, revision, model, chunks, vectors, path=path) == 2
    found = query_chunks(repo, revision, model, vectors[0], top_k=5, path=path)
    assert len(found) == 2
    assert found[0]['path'] == 'src/auth.py'
    assert found[0]['start_line'] == 1
    assert 'validate_token' in found[0]['text']
    with pytest.raises(StoreError):
        query_chunks(repo, 'b' * 40, model, vectors[0], path=path)
    with pytest.raises(StoreError):
        query_chunks('other/repo', revision, model, vectors[0], path=path)


def test_cancelled_partial_index_is_not_queryable_and_retry_completes(tmp_path, monkeypatch):
    pytest.importorskip('chromadb')
    import backend.rag.rag_store as rag_store
    from backend.core.operation_progress import OperationStopped
    repo, revision, model = 'local/cancellation', 'a' * 40, 'synthetic-test'
    chunks = chunk_files([
        {'path': f'src/file{i}.py', 'content': f'value = {i}\n'}
        for i in range(101)
    ], repo, revision)
    vectors = [[1., 0., 0.] for _ in chunks]
    path = str(tmp_path / 'chroma')
    def stop_second_batch(message):
        if '101' in message:
            # Let the first batch finish before cancellation is observed.
            if rag_store.get_collection(repo, revision, model, path=path).count() == 100:
                raise OperationStopped('cancelled')
    monkeypatch.setattr(rag_store, 'report_progress', stop_second_batch)
    with pytest.raises(OperationStopped):
        store_chunks(repo, revision, model, chunks, vectors, path=path)
    assert rag_store.get_collection(repo, revision, model, path=path).count() == 100
    with pytest.raises(StoreError, match='incomplete'):
        query_chunks(repo, revision, model, vectors[0], path=path)
    monkeypatch.setattr(rag_store, 'report_progress', lambda _: None)
    assert store_chunks(repo, revision, model, chunks, vectors, path=path) == 101
    assert len(query_chunks(repo, revision, model, vectors[0], path=path)) == 5
