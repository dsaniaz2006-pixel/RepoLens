"""Export completed evaluation indexes as portable source/vector checkpoints."""
import gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.core.config import EMBEDDING_MODEL,INDEX_FORMAT_VERSION
from backend.services.pipeline import index_settings,resume_completed_index
from backend.rag.rag_store import get_collection


def main():
    evaluation=json.loads((ROOT/'reports/rag-retest.json').read_text())
    output=ROOT/'evaluation/checkpoints';output.mkdir(parents=True,exist_ok=True)
    for index in evaluation['indexes']:
        repo,revision=index['repository'],index['revision']
        verified=resume_completed_index(repo,revision)
        if not verified:raise ValueError('Only verified completed indexes can be exported')
        data=get_collection(repo,revision,EMBEDDING_MODEL).get(include=['metadatas','documents','embeddings'])
        chunks=[dict(m,id=i,text=t) for i,t,m in zip(data['ids'],data['documents'],data['metadatas'])]
        payload=dict(result=verified,settings=index_settings(),chunks=chunks,vectors=data['embeddings'].tolist())
        path=output/f'{repo.replace("/","-")}-v{INDEX_FORMAT_VERSION}.json.gz'
        temporary=path.with_suffix('.tmp')
        with gzip.open(temporary,'wt',encoding='utf-8') as f:json.dump(payload,f)
        temporary.replace(path)
        print(repo,len(chunks),'chunks exported;',path.stat().st_size,'bytes',flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
