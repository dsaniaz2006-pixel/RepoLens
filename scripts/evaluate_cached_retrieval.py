"""Replay saved query vectors; no fresh embedding or answer-quality claims."""
import gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.evaluate_rag import evaluate_cases
from backend.rag.retriever import retrieve

def main():
    with gzip.open(ROOT/'evaluation/query-embeddings.json.gz','rt') as f:saved=json.load(f)
    vectors=dict(zip(saved['questions'],saved['cache']['vectors']))
    cases=json.loads((ROOT/'evaluation/rag_questions.json').read_text())['cases']
    revisions={c['repository']:c['revision'] for c in cases if c.get('expected_paths')}
    def run(repo,question,k):
        return retrieve(repo,revisions[repo],question,top_k=k,embedder=lambda texts,**kw:[vectors[t] for t in texts])
    report=evaluate_cases(cases,run,5)
    report.update(mode='cached_vectors_only',fresh_provider_calls=False,answer_correctness_evaluated=False,revisions=revisions)
    # Retrieval provenance is enough; do not duplicate source passages in the public evidence file.
    for case in report['cases']:case.pop('retrieved_chunks',None)
    path=ROOT/'evaluation/CACHED_RETRIEVAL_2026_10_25.json';path.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:report[k] for k in ('labeled','hit_rate_at_k','mean_recall_at_k','mode')}))
if __name__=='__main__':main()
