"""Gemini embeddings with injectable client for offline tests."""
import os
import time
from backend.core.operation_progress import report_progress, pause, OperationStopped
import logging
import json
import hashlib
from pathlib import Path
from backend.core.config import EMBEDDING_MODEL
from backend.rag.embedding_cache import QuotaBudgetError, valid_vector, estimate_tokens

class EmbeddingError(Exception):
    pass

def _request_with_retry(client, **kwargs):
    for attempt in range(4):
        try:
            report_progress(None)
            from backend.rag.embedding_cache import reserve
            # Injected mocks do not consume network quota.
            if type(client).__module__.startswith('google.'):
                reserve(estimate_tokens(json.dumps(kwargs.get('contents', []), ensure_ascii=False), overhead=200))
            report_progress('Sending embedding batch to Gemini; network timeout is 60 seconds…')
            return client.models.embed_content(**kwargs)
        except Exception as exc:
            status = getattr(exc, 'code', getattr(exc, 'status_code', None))
            try:
                status = int(status)
            except (TypeError, ValueError):
                status = None
            if status not in (429, 500, 502, 503, 504):
                raise
            details = getattr(exc, 'details', {})
            diagnostic = (str(details) + ' ' + str(exc)).lower()
            if status == 429 and any(marker in diagnostic for marker in
                                     ('perday', 'per_day', 'per day', 'daily', 'rpd', 'requests_per_day')):
                raise EmbeddingError('Gemini embedding daily quota is exhausted. Check your AI Studio quota and retry after the daily reset, or select a local Ollama model. Saved embedding batches are retained.') from exc
            if attempt == 3:
                raise EmbeddingError('Gemini embedding API is still rate-limited or unavailable after four attempts. Check model availability and quota; saved batches can be resumed.') from exc
            delay = 60.0 if status == 429 else min(8.0, 2.0 ** attempt)
            if isinstance(details,dict):
                error = details.get('error',details)
                for detail in error.get('details',[]) if isinstance(error,dict) else []:
                    value=detail.get('retryDelay') if isinstance(detail,dict) else None
                    if isinstance(value,str) and value.endswith('s'):
                        try: delay=max(1.0,float(value[:-1])+1)
                        except ValueError: pass
            # Long/daily quota exhaustion needs user action, not rapid retries.
            if delay > 60:
                raise EmbeddingError('Gemini requested a long retry delay. Stop indexing and retry later; saved embedding batches remain cached.') from exc
            logging.getLogger(__name__).warning('Embedding API returned HTTP %s; retry in %.0f seconds', status, delay)
            report_progress(f'Gemini embedding API HTTP {status}: retrying in {delay:.0f} seconds…')
            pause(delay)

def embed_texts(texts, *, task_type='RETRIEVAL_DOCUMENT', client=None, model=EMBEDDING_MODEL, checkpoint_path=None):
    from backend.ai.model_provider import provider, local_embeddings
    if client is None and provider()=='ollama':
        try: return local_embeddings(texts)
        except ValueError as exc: raise EmbeddingError(str(exc)) from exc
    if not texts:
        return []
    if client is None:
        key = os.environ.get('GEMINI_API_KEY')
        if not key:
            raise EmbeddingError('GEMINI_API_KEY is missing; configure .env first')
        try:
            from google import genai
            client = genai.Client(api_key=key, http_options={'timeout': 60000, 'retry_options': {'attempts': 1}})
        except Exception as exc:
            raise EmbeddingError('Unable to initialize Google GenAI embedding client') from exc
    try:
        vectors = []
        checkpoint = Path(checkpoint_path) if checkpoint_path else None
        signature=hashlib.sha256(json.dumps([model,task_type,'explicit-content-code-retrieval-v1',list(texts)]).encode()).hexdigest()
        if checkpoint and checkpoint.exists():
            try:
                cached=json.loads(checkpoint.read_text())
                saved=cached.get('vectors',[])
                if (cached.get('signature') == signature and isinstance(saved, list) and len(saved) <= len(texts)
                        and all(valid_vector(v) for v in saved)
                        and len({len(v) for v in saved}) <= 1):
                    vectors=saved
            except (OSError,ValueError,AttributeError):
                pass
        # Embedding 2 aggregates a list of strings into one Content. Explicit
        # Content objects preserve one vector per chunk; task instructions are
        # text prefixes for this model, rather than the legacy task_type field.
        is_v2 = 'gemini-embedding-2' in model
        for offset in range(len(vectors), len(texts), 50):
            report_progress(f'Embedding chunks {offset + 1}–{min(offset + 50, len(texts))} of {len(texts)}…')
            group = texts[offset:offset + 50]
            if is_v2:
                contents = [{'parts': [{'text':
                    ('task: code retrieval | query: ' + text) if task_type == 'RETRIEVAL_QUERY'
                    else ('title: none | text: ' + text)}]} for text in group]
                response = _request_with_retry(client,model=model, contents=contents)
            else:
                response = _request_with_retry(client,model=model, contents=list(group),
                          config={'task_type': task_type})
            batch = [list(x.values) for x in response.embeddings]
            if len(batch) != len(group):
                raise ValueError('Embedding batch count differs from input count')
            if not all(valid_vector(v) for v in batch):
                raise ValueError('Embedding batch contains non-finite or invalid vectors')
            if len({len(v) for v in vectors + batch}) != 1:
                raise ValueError('Embedding batch has inconsistent vector dimensions')
            vectors.extend(batch)
            if checkpoint:
                checkpoint.parent.mkdir(parents=True,exist_ok=True)
                pending=checkpoint.with_suffix('.tmp')
                pending.write_text(json.dumps({'signature':signature,'vectors':vectors}))
                pending.replace(checkpoint)
        if (len(vectors) != len(texts) or not all(valid_vector(v) for v in vectors)
                or len({len(v) for v in vectors}) != 1):
            raise ValueError('Embedding count, values, or dimensions invalid')
        return vectors
    except (OperationStopped, QuotaBudgetError, EmbeddingError):
        raise
    except Exception as exc:
        raise EmbeddingError('Embedding request failed; check model access, quota and network') from exc

# Injectable clients retain deterministic test behavior. Real Gemini calls use the
# persistent cache; checkpoints remain available in the underlying implementation.
_uncached_embed_texts = embed_texts

def embed_texts(texts, *, task_type='RETRIEVAL_DOCUMENT', client=None, model=EMBEDDING_MODEL, checkpoint_path=None):
    from backend.ai.model_provider import provider
    if client is not None or provider()=='ollama':
        return _uncached_embed_texts(texts,task_type=task_type,client=client,model=model,checkpoint_path=checkpoint_path)
    from backend.rag.embedding_cache import cached_embeddings
    try:
        return cached_embeddings(texts,task_type,model,lambda batch:_uncached_embed_texts(batch,task_type=task_type,model=model))
    except OperationStopped: raise
    except QuotaBudgetError as exc: raise EmbeddingError(str(exc)) from exc
    except EmbeddingError: raise
    except Exception as exc: raise EmbeddingError('Embedding failed; check model access, quota and the configured batch budget. Completed batches are cached for retry.') from exc
