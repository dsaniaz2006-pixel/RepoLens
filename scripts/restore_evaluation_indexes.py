"""Restore packaged, completed evaluation indexes without embedding requests."""
import gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.core.config import EMBEDDING_MODEL
from backend.rag.rag_store import store_chunks
from backend.services.pipeline import index_settings,record_completed_index,resume_completed_index


def main():
    restored=[]
    for path in sorted((ROOT/'evaluation/checkpoints').glob('*.json.gz')):
        with gzip.open(path,'rt') as f:data=json.load(f)
        if data['settings']!=index_settings():raise ValueError('Checkpoint settings differ; rebuild rather than mixing embedding formats')
        result=data['result'];repo=result['repository'];revision=result['revision']
        count=store_chunks(repo,revision,EMBEDDING_MODEL,data['chunks'],data['vectors'])
        if count!=result['chunks']:raise ValueError('Checkpoint record count differs')
        record_completed_index(result)
        verified=resume_completed_index(repo,revision)
        if verified is None:raise ValueError('Restored checkpoint failed validation')
        restored.append(verified)
        print(repo,'restored',count,'chunks; no model requests')
    return 0 if restored else 1

if __name__=='__main__':raise SystemExit(main())
