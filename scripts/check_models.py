"""Opt-in live Gemini model access check; no repository source is transmitted.

--live uses models.get for both model IDs; --probe additionally calls the
smallest possible generation and embedding requests, consuming API quota.
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from backend.core.config import GEMINI_MODEL, EMBEDDING_MODEL


def check_model_access(client, probe=False):
    results={}
    for model, kind in ((GEMINI_MODEL,'generation'), (EMBEDDING_MODEL,'embedding')):
        try:
            info=client.models.get(model=model)
            results[kind]={'model':model,'metadata_access':'PASS' if info else 'FAIL', 'probe':'NOT_RUN'}
        except Exception as exc:
            results[kind]={'model':model,'metadata_access':'FAIL', 'probe':'NOT_RUN', 'error_type':type(exc).__name__}
            continue
        if probe:
            try:
                if kind=='generation':
                    response=client.models.generate_content(model=model,contents='Reply with OK.')
                    ok=bool(getattr(response,'text',''))
                else:
                    from backend.rag.embeddings import embed_texts
                    vectors=embed_texts(['RepoLens probe one', 'RepoLens probe two'],client=client,model=model)
                    ok=len(vectors)==2 and all(vectors)
                results[kind]['probe']='PASS' if ok else 'FAIL'
            except Exception as exc:
                results[kind]['probe']='FAIL'
                results[kind]['error_type']=type(exc).__name__
    return results


def main(argv=None):
    p=argparse.ArgumentParser(description='Check Gemini generation and embedding access without exposing keys.')
    p.add_argument('--live',action='store_true',help='Allow live Gemini models.get calls.')
    p.add_argument('--probe',action='store_true',help='Call both models with harmless test text (uses API quota).')
    args=p.parse_args(argv)
    if not args.live:
        print('NOT VERIFIED. Run with --live to check key-specific model access.')
        return 0
    load_dotenv(ROOT/'.env')
    key=os.environ.get('GEMINI_API_KEY')
    if not key:
        print('Missing GEMINI_API_KEY in local .env (never commit it).')
        return 2
    try:
        from google import genai
        client=genai.Client(api_key=key)
        results=check_model_access(client,args.probe)
        for kind,data in results.items():
            print(f"{kind}: {data['model']} metadata={data['metadata_access']} probe={data['probe']}")
        return 0 if all(d['metadata_access']=='PASS' and (not args.probe or d['probe']=='PASS') for d in results.values()) else 1
    except Exception as exc:
        print('SDK setup error:',type(exc).__name__)
        return 1

if __name__=='__main__':raise SystemExit(main())
