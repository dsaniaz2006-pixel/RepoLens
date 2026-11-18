"""Opt-in live Q&A smoke test at the source-reviewed evaluation revisions."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--repos',nargs='+',help='Optionally run only selected evaluation repositories')
    parser.add_argument('--output',type=Path,default=ROOT/'reports'/'qa-evaluation.json')
    args=parser.parse_args(argv)
    if not args.live:
        print('NOT RUN: --live uses Gemini embedding and generation quota; build labeled indexes first.')
        return 0
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env',override=False)
    from backend.rag.retriever import retrieve
    from backend.ai.qa import answer_question
    cases=json.loads((ROOT/'evaluation'/'rag_questions.json').read_text())['cases']
    selected=[dict(cases[i],expected_insufficient=False) for i in (3,4,8)]
    selected.append(dict(repository=cases[8]['repository'],revision=cases[8]['revision'],
        question='What is the verified internal production deployment hostname used by the maintainers?',
        expected_insufficient=True))
    if args.repos:
        selected=[c for c in selected if c['repository'] in args.repos]
        if not selected:parser.error('No evaluation questions match --repos')
    results=[]
    for case in selected:
        base={k:case[k] for k in ('repository','revision','question','expected_insufficient')}
        try:
            chunks=retrieve(case['repository'],case['revision'],case['question'])
            answer=answer_question(case['question'],chunks)
            passed=(answer['uncertain'] and not answer['citations']) if case['expected_insufficient'] else bool(answer['citations'])
            results.append(dict(base,answer=answer,retrieved_chunks=chunks,structural_pass=passed,
                semantic_review='Requires source review; citation validity alone is insufficient'))
            label='insufficient' if not answer['citations'] else ('partial' if answer['uncertain'] else 'answered')
            print(case['repository'],label,'structural_pass=',passed,flush=True)
        except Exception as exc:
            results.append(dict(base,structural_pass=False,error_type=type(exc).__name__))
            print(case['repository'],'FAILED',type(exc).__name__,flush=True)
    from backend.core.config import INDEX_FORMAT_VERSION
    payload=dict(live_executed=True,index_format_version=INDEX_FORMAT_VERSION,cases=results)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    return 0 if all(c['structural_pass'] for c in results) else 1

if __name__=='__main__':raise SystemExit(main())
