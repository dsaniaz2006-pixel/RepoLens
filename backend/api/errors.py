"""Shared API error boundary.

Do not return provider traces, secrets, source text, or raw request payloads.
Public HTTP statuses and messages match the original endpoint contracts.
"""
from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from backend.security.controls import public_error_detail


async def validation_error_response(_request, exc):
    """Provide bounded field names, not request input or user secrets."""
    fields = []
    for item in exc.errors()[:8]:
        loc = [str(segment) for segment in item.get('loc', ())
               if isinstance(segment, (str, int))]
        fields.append({'field': '.'.join(loc)[:120], 'msg': 'Invalid request data.'})
    return JSONResponse(status_code=422, content={'detail': fields},
                        headers={'Cache-Control': 'no-store'})


def raise_report_api_error(exc):
    """Map report/RAG errors to the same safe HTTP contract as before."""
    if isinstance(exc, HTTPException):
        raise exc
    # Lazy imports avoid importing expensive AI/RAG code while building the app.
    from backend.github.github_client import GitHubError
    from backend.ai.analyzer import AnalyzerError
    from backend.rag.embeddings import EmbeddingError
    from backend.rag.rag_store import StoreError
    from backend.ai.qa import QAError
    if isinstance(exc, (ValueError, GitHubError, AnalyzerError, EmbeddingError, StoreError, QAError)):
        raise HTTPException(status_code=400, detail=public_error_detail(exc)) from exc
    raise HTTPException(status_code=500,
                        detail='Unexpected processing error; inspect local server logs') from exc


def safe_product_call(call):
    """Wrap roadmap endpoint operations while retaining provider-specific statuses."""
    try:
        return call()
    except HTTPException:
        raise
    except Exception as exc:
        from backend.github.github_client import GitHubError
        from backend.ai.model_provider import ModelResponseError
        if isinstance(exc, ModelResponseError):
            status = {'quota': 429, 'auth': 503, 'model': 503, 'request': 502,
                      'connection': 503, 'timeout': 504, 'unavailable': 503,
                      'invalid_json': 502, 'empty_json': 502,
                      'provider': 502}.get(exc.kind, 502)
            raise HTTPException(status, public_error_detail(exc)) from exc
        if isinstance(exc, (ValueError, GitHubError)):
            raise HTTPException(400, public_error_detail(exc)) from exc
        raise HTTPException(500,
                            'Operation failed; check server configuration and service access') from exc
