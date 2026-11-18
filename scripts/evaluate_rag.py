"""Run a labeled, repeatable retrieval@k evaluation against existing indexes.

Requires actual index built for each repository; no generated answers are used as
reference labels. Unlabeled questions are skipped and never counted as passing.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.rag.retriever import retrieve


def evaluate_cases(cases, retrieval, top_k=5):
    entries=[]
    for case in cases:
        gold = case.get('expected_paths') or []
        if not gold:
            entries.append({'repository':case['repository'], 'question':case['question'], 'status':'UNLABELED'})
            continue
        chunks = retrieval(case['repository'], case['question'], top_k)
        found = {chunk['path'] for chunk in chunks}
        matches = sorted(set(gold) & found)
        ranges = case.get('evidence') or []
        covered = [e for e in ranges if any(c['path']==e['path'] and
            c.get('start_line',0)<=e['end_line'] and c.get('end_line',0)>=e['start_line'] for c in chunks)]
        entries.append({'repository':case['repository'], 'revision':case.get('revision'), 'question':case['question'], 'status':'EVALUATED',
                        'expected_paths':gold, 'retrieved_paths':sorted(found),
                        'matches':matches, 'hit_at_k':bool(matches),
                        'recall_at_k':len(matches)/len(set(gold)),
                        'retrieved_chunks':chunks,
                        'evidence_range_overlap':bool(covered) if ranges else None})
    judged=[x for x in entries if x['status']=='EVALUATED']
    return {'labeled':len(judged),'unlabeled':len(entries)-len(judged),
            'hit_rate_at_k':(sum(x['hit_at_k'] for x in judged)/len(judged)) if judged else None,
            'mean_recall_at_k':(sum(x['recall_at_k'] for x in judged)/len(judged)) if judged else None,
            'cases':entries}


def main(argv=None):
    p=argparse.ArgumentParser(description='Evaluate source retrieval using human-verified expected paths.')
    p.add_argument('--questions',type=Path,default=ROOT/'evaluation/rag_questions.json')
    p.add_argument('--top-k',type=int,default=5)
    p.add_argument('--live',action='store_true',help='Opt in to live GitHub and Gemini embedding requests.')
    p.add_argument('--build-indexes',action='store_true',help='Build indexes at labeled commit revisions before evaluation (uses embedding quota).')
    p.add_argument('--resume',action='store_true',help='Reuse completed indexes only when revision, settings, count and metadata match.')
    p.add_argument('--batch-queries',action='store_true',help='Embed evaluation questions together and checkpoint their vectors for repeatable reruns.')
    p.add_argument('--output',type=Path,default=ROOT/'reports'/'rag-evaluation.json')
    args=p.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ROOT / '.env', override=False)
    cases=json.loads(args.questions.read_text(encoding='utf-8'))['cases']
    if not args.live:
        print(f'{len(cases)} retrieval questions prepared; {sum(bool(c.get("expected_paths")) for c in cases)} labeled. Label expected_paths against exact source revisions; run --live --build-indexes to measure retrieval.')
        return 0
    if args.top_k < 1:
        p.error('--top-k must be >= 1')
    revisions={}
    for case in cases:
        if not case.get('expected_paths'):
            continue
        rev=case.get('revision','')
        if len(rev)!=40 or any(c not in '0123456789abcdefABCDEF' for c in rev):
            p.error('Every labeled question requires a full revision SHA; labels must match indexed source')
        repo=case['repository'].lower()
        if repo in revisions and revisions[repo]!=rev:
            p.error('Use a separate evaluation file for each revision of a repository')
        revisions[repo]=rev
    indexes=[]
    if args.build_indexes:
        from backend.services.pipeline import index_repo
        for repo,revision in revisions.items():
            print('Building labeled-revision index for',repo,revision)
            kwargs={'revision':revision}
            if args.resume:kwargs['resume']=True
            try:
                index=index_repo(f'https://github.com/{repo}',**kwargs)
            except Exception as exc:
                failure={'status':'INDEX_BUILD_FAILED','repository':repo,'revision':revision,
                    'error_type':type(exc).__name__,'indexes':indexes,
                    'instruction':'Preserve checkpoints; retry with --live --build-indexes --resume after checking provider quota.'}
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(failure,indent=2))
                print('Index build stopped:',type(exc).__name__,'; completed checkpoints retained.')
                return 1
            indexes.append(index)
            print('Indexed',index['indexed_files'],'files;',index['chunks'],'chunks')
    query_vectors={}
    if args.batch_queries:
        from backend.rag.embeddings import embed_texts
        from backend.core.config import CHROMA_PATH
        questions=list(dict.fromkeys(c['question'] for c in cases if c.get('expected_paths')))
        vectors=embed_texts(questions,task_type='RETRIEVAL_QUERY',
            checkpoint_path=Path(CHROMA_PATH)/'evaluation-query-vectors.json')
        query_vectors=dict(zip(questions,vectors))
    def run(repo,question,k):
        kwargs={'top_k':k}
        if args.batch_queries:
            kwargs['embedder']=lambda texts,**kw:[query_vectors[q] for q in texts]
        return retrieve(repo.lower(),revisions[repo.lower()],question,**kwargs)
    report=evaluate_cases(cases,run,args.top_k)
    report['revisions']=revisions
    report['top_k']=args.top_k
    report['indexes']=indexes
    from backend.core.config import INDEX_FORMAT_VERSION
    report['index_format_version']=INDEX_FORMAT_VERSION
    report['retrieval_policy']='semantic_candidates_5x_file_diversity_2'
    report['query_embedding_mode']='provider_batch_checkpoint' if args.batch_queries else 'provider_per_question'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f"Labeled: {report['labeled']}, unlabeled: {report['unlabeled']}, hit@k: {report['hit_rate_at_k']}, recall@k: {report['mean_recall_at_k']}")
    print('Saved to',args.output)
    return 0 if report['labeled'] else 2

if __name__=='__main__': raise SystemExit(main())
