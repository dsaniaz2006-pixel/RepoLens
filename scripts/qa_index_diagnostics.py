#!/usr/bin/env python3
"""Inspect repository QA coverage without sending questions to Gemini.

Run from project root after indexing, e.g.
  python scripts/qa_index_diagnostics.py https://github.com/pallets/flask --question 'Where is the route decorator?'

The output contains file paths and line ranges only (no source content, keys,
or private tokens). It checks the exact current revision and current index
profile, which prevents accidentally inspecting an unrelated old collection.
"""
import argparse
from pathlib import Path
import sys
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
load_dotenv(ROOT/'.env')


def main():
    parser=argparse.ArgumentParser(description='Diagnose local Chroma RAG QA coverage')
    parser.add_argument('url',help='Public GitHub repository URL')
    parser.add_argument('--question',default='Where does the repository define its main route?')
    parser.add_argument('--revision',help='Optional 40-character pinned commit SHA')
    parser.add_argument('--probe-retrieval',action='store_true',
        help='Run one REAL embedding query and show hybrid retrieval paths; consumes provider quota')
    args=parser.parse_args()
    from backend.github.github_client import parse_github_url,fetch_repo_metadata,fetch_commit_sha
    from backend.rag.rag_store import read_index_chunks
    from backend.rag.source_symbols import ranked_definitions
    from backend.rag.retriever import lexical_rank
    from backend.core.config import EMBEDDING_MODEL,RAG_INDEX_PROFILE,RAG_TOP_K
    owner,repo=parse_github_url(args.url)
    revision=args.revision
    if not revision:
        metadata=fetch_repo_metadata(owner,repo)
        revision=fetch_commit_sha(owner,repo,metadata['default_branch'])
    print('Repository:',f'{owner}/{repo}', '\nRevision:',revision, '\nProfile:',RAG_INDEX_PROFILE)
    try:
        chunks=read_index_chunks(f'{owner}/{repo}'.lower(),revision,EMBEDDING_MODEL)
    except Exception as exc:
        print('Index unavailable for this revision/profile:',exc)
        return 1
    print('Indexed chunks:',len(chunks),'\nIndexed paths:',len({c['path'] for c in chunks}))
    matches=ranked_definitions(args.question,chunks)
    print('Matching source function declarations:',len(matches))
    for score,symbol,c in matches[:8]:
        print(f'  {symbol}() — {c["path"]}:L{c["start_line"]}–L{c["end_line"]}')
    if not matches:
        print('No matching function declaration is present in this indexed coverage. '
              'Try Balanced/Full indexing before expecting definitive source answers.')
    print('Top lexical source matches:')
    for c in lexical_rank(args.question,chunks)[:5]:
        print(f'  {c["path"]}:L{c["start_line"]}–L{c["end_line"]}')
    if args.probe_retrieval:
        # This is deliberately opt-in: one query embedding may cost provider
        # quota; diagnostics otherwise need only local Chroma reads.
        from backend.rag.retriever import retrieve
        print('Hybrid retrieval probe (one live query embedding; no answer generation):')
        try:
            evidence = retrieve(f'{owner}/{repo}'.lower(),revision,args.question,top_k=RAG_TOP_K)
        except Exception as exc:
            # Avoid printing raw provider exception text, which may include
            # credential-bearing URLs or internal paths.
            print('Retrieval probe failed: verify model access, quota and index profile.')
            return 2
        for i,c in enumerate(evidence,1):
            print(f'  {i}. {c["path"]}:L{c["start_line"]}–L{c["end_line"]}')
        if not evidence:
            print('No passages found for the pinned revision. Rebuild its RAG index.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
