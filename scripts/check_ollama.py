"""Opt-in local generation and embedding probe; no repository source is sent."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Contact the configured local Ollama daemon')
    args=parser.parse_args(argv)
    if not args.live:
        print('NOT RUN. Set REPOLENS_MODEL_PROVIDER=ollama and add --live to test the local models.')
        return 0
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    from backend.ai.model_provider import provider,json_model
    from backend.rag.embeddings import embed_texts
    if provider()!='ollama':
        print('Set REPOLENS_MODEL_PROVIDER=ollama in .env and restart. No cloud probe was attempted.')
        return 2
    try:
        result=json_model('Return JSON exactly: {"status":"OK"}')
        if result.get('status')!='OK':raise ValueError('Invalid model output')
        vectors=embed_texts(['RepoLens local model check'])
        if len(vectors)!=1 or not vectors[0]:raise ValueError('Invalid embedding response')
        print('PASS: local JSON generation and embedding; rebuild an index and test source citations next.')
        return 0
    except Exception as exc:
        print('FAIL:',type(exc).__name__,'Check Ollama is running and both configured models are pulled.')
        return 1

if __name__=='__main__':raise SystemExit(main())
