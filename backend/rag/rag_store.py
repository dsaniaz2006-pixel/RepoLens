"""Revision-isolated Chroma persistence. No uploaded code is executed."""
import hashlib
from functools import lru_cache
import os
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
from backend.core.operation_progress import report_progress, OperationStopped
from backend.core.config import CHROMA_PATH, INDEX_FORMAT_VERSION, CHUNK_SIZE_CHARS, CHUNK_OVERLAP_CHARS, RAG_INDEX_PROFILE


class StoreError(Exception):
    pass


def collection_name(repo, revision, model, *, format_version=INDEX_FORMAT_VERSION):
    return 'repolens_' + hashlib.sha256(f'{repo}\0{revision}\0{model}\0{format_version}\0{CHUNK_SIZE_CHARS}\0{CHUNK_OVERLAP_CHARS}\0{RAG_INDEX_PROFILE}'.encode()).hexdigest()[:35]


def get_collection(repo, revision, model, *, client=None, path=CHROMA_PATH, create=False):
    if client is None:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=path)
        except Exception as exc:
            raise StoreError('Unable to open ChromaDB; check installation and storage permissions') from exc
    name = collection_name(repo, revision, model)
    try:
        return client.get_or_create_collection(name=name) if create else client.get_collection(name=name)
    except Exception as exc:
        # Saved conversations remain pinned to their old SHA. After the
        # version-4 upgrade, those chats may still have only a version-3
        # collection. Read it without modifying it; a new build creates v4.
        if not create and str(INDEX_FORMAT_VERSION) == '4':
            old_name = collection_name(repo, revision, model, format_version='3')
            try:
                return client.get_collection(name=old_name)
            except Exception:
                pass
        message = ('Unable to create repository index; check storage permissions' if create else
                   'Unable to open repository index; run --index first and check storage permissions')
        raise StoreError(message) from exc


def store_chunks(repo, revision, model, chunks, vectors, *, client=None, path=CHROMA_PATH):
    if len(chunks) != len(vectors):
        raise StoreError('Embedding and chunk count differ')
    if not chunks:
        raise StoreError('No safe source chunks available to index')
    if any(x.get('repo') != repo or x.get('revision') != revision for x in chunks):
        raise StoreError('Chunk repository/revision does not match the target index')
    clear_index_cache()
    col = get_collection(repo, revision, model, client=client, path=path, create=True)
    try:
        # A cancelled or failed batch must never look like a complete index.
        # This marker persists across process restarts and is cleared only after
        # every batch has been saved successfully.
        col.modify(metadata={'repolens_complete': False})
        # Rebuilding the *same* collection with fewer/different chunks must
        # evict obsolete IDs. Upsert alone leaves old source passages in the
        # evidence pool, allowing answers grounded in stale code. Read IDs
        # only (not documents/embeddings), keeping this inexpensive and private.
        existing = col.get(include=[])
        existing_ids = existing.get('ids', []) if isinstance(existing, dict) else []
        incoming_ids = {chunk['id'] for chunk in chunks}
        stale_ids = [identity for identity in existing_ids if identity not in incoming_ids]
        for offset in range(0, len(stale_ids), 100):
            report_progress(f'Removing obsolete indexed chunks {offset + 1}–{min(offset + 100, len(stale_ids))} of {len(stale_ids)}…')
            col.delete(ids=stale_ids[offset:offset + 100])
        for offset in range(0, len(chunks), 100):
            report_progress(f'Saving indexed chunks {offset+1}–{min(offset+100,len(chunks))} of {len(chunks)}…')
            group, vec = chunks[offset:offset+100], vectors[offset:offset+100]
            col.upsert(ids=[x['id'] for x in group], embeddings=vec,
                       documents=[x['text'] for x in group],
                       metadatas=[{k: x[k] for k in ('repo','revision','path','start_line','end_line')} for x in group])
        report_progress('Finishing vector storage…')
        col.modify(metadata={'repolens_complete': True})
        clear_index_cache()
    except OperationStopped:
        raise
    except Exception as exc:
        raise StoreError('Unable to write repository index; check storage permissions and vector dimensions, then rerun --index') from exc
    return len(chunks)


def query_chunks(repo, revision, model, vector, top_k=5, *, client=None, path=CHROMA_PATH):
    if type(top_k) is not int or top_k < 1:
        raise StoreError('top_k must be a positive integer')
    col = get_collection(repo, revision, model, client=client, path=path)
    try:
        if isinstance(col.metadata, dict) and col.metadata.get('repolens_complete') is False:
            raise StoreError('Repository index is incomplete or still being built; finish or retry Build / refresh RAG index before asking questions')
        count = col.count()
        if count == 0:
            return []
        r = col.query(query_embeddings=[vector], n_results=min(top_k, count),
                      include=['documents','metadatas','distances'])
        results = [dict(text=t, **m, distance=d) for t,m,d in
                   zip(r['documents'][0],r['metadatas'][0],r['distances'][0])]
        if any(x['repo'] != repo or x['revision'] != revision for x in results):
            raise StoreError('Repository index contains mismatched repository/revision metadata; rebuild it')
        return results
    except StoreError:
        raise
    except Exception as exc:
        raise StoreError('Unable to query repository index; check storage and embedding settings, or rebuild with --index') from exc


@lru_cache(maxsize=8)
def read_index_chunks(repo, revision, model):
    """Read bounded index evidence for lexical retrieval; retain revision isolation."""
    col = get_collection(repo, revision, model)
    if (col.metadata or {}).get('repolens_complete') is False:
        raise StoreError('Repository index is incomplete; finish indexing first')
    if col.count() > 20000:
        raise StoreError('Index exceeds lexical retrieval limit; use a smaller repository index')
    result = col.get(include=['documents', 'metadatas'])
    chunks = [dict(text=t, **m) for t,m in zip(result['documents'],result['metadatas'])]
    if any(c['repo'] != repo or c['revision'] != revision for c in chunks):
        raise StoreError('Repository index contains mismatched revision metadata; rebuild it')
    return chunks


def clear_index_cache():
    """Invalidate cached evidence when a revision index is modified."""
    read_index_chunks.cache_clear()
