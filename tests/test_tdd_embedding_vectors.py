"""New audit regression tests (TDD): reject invalid vectors before they reach RAG."""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from backend.rag.embeddings import embed_texts, EmbeddingError


def fake_client(vectors):
    client = Mock()
    client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=v) for v in vectors]
    )
    return client


def test_embedding_rejects_nonfinite_vector():
    with pytest.raises(EmbeddingError):
        embed_texts(['auth code'], client=fake_client([[float('nan'), 1.0]]), model='test-model')


def test_embedding_rejects_mixed_dimensions():
    with pytest.raises(EmbeddingError):
        embed_texts(['a', 'b'], client=fake_client([[0.1, 0.2], [0.3]]), model='test-model')


def test_corrupted_checkpoint_is_recomputed(tmp_path):
    texts = ['a']
    model = 'test-model'
    task = 'RETRIEVAL_DOCUMENT'
    signature = hashlib.sha256(json.dumps([model, task,
        'explicit-content-code-retrieval-v1', texts]).encode()).hexdigest()
    checkpoint = tmp_path/'checkpoint.json'
    checkpoint.write_text(json.dumps({'signature':signature, 'vectors':[[float('nan'),1.0]]}))
    client=fake_client([[0.2,0.3]])
    result=embed_texts(texts, client=client, model=model, checkpoint_path=checkpoint)
    assert result == [[0.2,0.3]]
    assert client.models.embed_content.call_count == 1


def test_embedding_rejects_dimension_change_across_batches(tmp_path):
    """Never persist a dimension-mismatched second batch; keep valid progress."""
    client = Mock()
    client.models.embed_content.side_effect = [
        SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2])] * 50),
        SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3])]),
    ]
    checkpoint = tmp_path / 'progress.json'
    with pytest.raises(EmbeddingError):
        embed_texts([f'chunk-{i}' for i in range(51)], client=client,
                    model='test-model', checkpoint_path=checkpoint)
    saved = json.loads(checkpoint.read_text())
    assert len(saved['vectors']) == 50  # only the valid first batch was stored
    assert client.models.embed_content.call_count == 2


def test_valid_checkpoint_is_reused_without_new_provider_calls(tmp_path):
    texts = ['a', 'b']
    model, task = 'test-model', 'RETRIEVAL_DOCUMENT'
    signature = hashlib.sha256(json.dumps([
        model, task, 'explicit-content-code-retrieval-v1', texts
    ]).encode()).hexdigest()
    checkpoint = tmp_path / 'progress.json'
    vectors = [[0.1, 0.2], [0.3, 0.4]]
    checkpoint.write_text(json.dumps({'signature': signature, 'vectors': vectors}))
    client = fake_client([])
    assert embed_texts(texts, client=client, model=model,
                       checkpoint_path=checkpoint) == vectors
    client.models.embed_content.assert_not_called()
