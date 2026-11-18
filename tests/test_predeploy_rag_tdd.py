"""Pre-deployment bug reproductions: immutable RAG evidence and bounded API calls."""
from unittest.mock import Mock
import pytest

from backend.rag.rag_store import store_chunks, query_chunks, StoreError


class FakeCollection:
    """Minimal Chroma-compatible fake with IDs persisting between rebuilds."""
    def __init__(self):
        self.metadata = {}
        self.items = {}
        self.deleted = []

    def modify(self, *, metadata):
        self.metadata = metadata

    def count(self):
        return len(self.items)

    def get(self, *, include):
        return {'ids': list(self.items)}

    def upsert(self, *, ids, embeddings, documents, metadatas):
        for identity, vector, text, meta in zip(ids, embeddings, documents, metadatas):
            self.items[identity] = (vector, text, meta)

    def delete(self, *, ids):
        self.deleted.extend(ids)
        for identity in ids:
            self.items.pop(identity, None)


class FakeChroma:
    def __init__(self):
        self.collection = FakeCollection()

    def get_or_create_collection(self, *, name):
        return self.collection

    def get_collection(self, *, name):
        return self.collection


def chunk(identity):
    return {'id': identity, 'repo':'o/r', 'revision':'a'*40,
            'path':f'src/{identity}.py', 'start_line':1, 'end_line':1,
            'text':f'def {identity}(): pass'}


def test_rebuilding_same_revision_drops_obsolete_chunks():
    client = FakeChroma()
    assert store_chunks('o/r','a'*40,'model',[chunk('old'), chunk('keep')],[[1.,0.],[0.,1.]],client=client) == 2
    assert store_chunks('o/r','a'*40,'model',[chunk('keep')],[[0.,1.]],client=client) == 1
    assert list(client.collection.items) == ['keep']
    assert client.collection.deleted == ['old']
    assert client.collection.metadata == {'repolens_complete': True}


def test_rebuild_with_unchanged_ids_does_not_delete_vectors():
    client = FakeChroma()
    docs=[chunk('keep')]
    store_chunks('o/r','a'*40,'model',docs,[[1.,0.]],client=client)
    store_chunks('o/r','a'*40,'model',docs,[[0.,1.]],client=client)
    assert client.collection.deleted == []
    assert client.collection.items['keep'][0] == [0.,1.]


def test_invalid_question_does_not_fetch_github(monkeypatch):
    from backend.services import pipeline
    fetched = Mock(side_effect=AssertionError('GitHub must not be contacted'))
    monkeypatch.setattr(pipeline,'fetch_repo_metadata',fetched)
    with pytest.raises(ValueError,match='Question must not be empty'):
        pipeline.ask_repo('https://github.com/pallets/flask',' \t\n')
    fetched.assert_not_called()


def test_deletion_failure_leaves_index_unqueryable():
    client = FakeChroma()
    store_chunks('o/r','a'*40,'model',[chunk('old')],[[1.,0.]],client=client)

    def unavailable(*, ids):
        raise RuntimeError('private storage details')
    client.collection.delete = unavailable
    with pytest.raises(StoreError) as error:
        store_chunks('o/r','a'*40,'model',[chunk('new')],[[1.,0.]],client=client)
    assert 'private storage details' not in str(error.value)
    assert client.collection.metadata == {'repolens_complete': False}
    with pytest.raises(StoreError, match='incomplete'):
        query_chunks('o/r','a'*40,'model',[1.,0.],client=client)


@pytest.mark.parametrize('question', ['', '  ', None])
def test_invalid_questions_are_bounded_before_network(monkeypatch, question):
    from backend.services import pipeline
    fetched = Mock(side_effect=AssertionError('GitHub must not be contacted'))
    monkeypatch.setattr(pipeline,'fetch_repo_metadata',fetched)
    with pytest.raises(ValueError, match='Question must not be empty'):
        pipeline.ask_repo('https://github.com/pallets/flask',question)
    fetched.assert_not_called()
