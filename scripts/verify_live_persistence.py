"""Reopen evaluated live indexes in a fresh process, without model calls."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evaluation',type=Path,default=ROOT/'reports/rag-retest.json')
    p.add_argument('--output',type=Path,default=ROOT/'reports/live-chroma-check.json')
    args=p.parse_args(argv)
    from backend.rag.rag_store import get_collection,query_chunks,store_chunks,collection_name
    from backend.core.config import EMBEDDING_MODEL,INDEX_FORMAT_VERSION
    data=json.loads(args.evaluation.read_text())
    results=[]
    for index in data['indexes']:
        repo,rev=index['repository'],index['revision']
        col=get_collection(repo,rev,EMBEDDING_MODEL)
        stored=col.get(include=['metadatas','documents','embeddings'])
        before=col.count()
        matches=all(m['repo']==repo and m['revision']==rev for m in stored['metadatas'])
        chunk=dict(stored['metadatas'][0],id=stored['ids'][0],text=stored['documents'][0])
        vector=stored['embeddings'][0].tolist()
        store_chunks(repo,rev,EMBEDDING_MODEL,[chunk],[vector])
        retrieved=query_chunks(repo,rev,EMBEDDING_MODEL,vector)
        passed=before==index['chunks']==col.count() and matches and bool(retrieved)
        results.append(dict(repository=repo,revision=rev,chunks=before,
            collection=collection_name(repo,rev,EMBEDDING_MODEL),passed=passed,
            persisted_vectors_requeried=True,repeat_upsert_preserved_count=before==col.count(),metadata_isolated=matches))
    unique=len({r['collection'] for r in results})==len(results)
    payload=dict(index_format_version=INDEX_FORMAT_VERSION,no_model_calls=True,fresh_process=True,
        distinct_repository_collections=unique,passed=unique and all(r['passed'] for r in results),results=results)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,indent=2))
    return 0 if payload['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
