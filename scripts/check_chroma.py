"""Real Chroma persistence smoke test with separate writer/reader processes.

No GitHub, Gemini or keys. Uses deterministic vectors in a temporary directory.
"""
from __future__ import annotations
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.rag.rag_store import store_chunks, query_chunks, get_collection


def _check(phase,location):
    import chromadb
    from chromadb.config import Settings
    client=chromadb.PersistentClient(path=location,settings=Settings(anonymized_telemetry=False))
    if phase=='write':
        for repo,rev,path in [('test/example','a'*40,'src/auth.py'),
                              ('test/other','a'*40,'other.py'),
                              ('test/example','b'*40,'new.py')]:
            chunk={'id':'chunk-one','repo':repo,'revision':rev,'path':path,
                   'start_line':1,'end_line':2,'text':'def validate_token(token):\n    return bool(token)\n'}
            for _ in range(2):
                store_chunks(repo,rev,'test-vector-model',[chunk],[[0.2,0.8]],client=client)
    else:
        for repo,rev,path in [('test/example','a'*40,'src/auth.py'),
                              ('test/other','a'*40,'other.py'),
                              ('test/example','b'*40,'new.py')]:
            col=get_collection(repo,rev,'test-vector-model',client=client)
            assert col.count()==1
            results=query_chunks(repo,rev,'test-vector-model',[0.2,0.8],client=client)
            assert len(results)==1 and results[0]['path']==path and results[0]['start_line']==1


def run_smoke():
    with tempfile.TemporaryDirectory(prefix='repolens_chroma_check_') as location:
        for phase in ('write','read'):
            completed=subprocess.run([sys.executable,str(Path(__file__).resolve()),phase,location],
                                     capture_output=True,text=True,timeout=45)
            if completed.returncode:
                raise RuntimeError('Chroma subprocess persistence check failed')
    return True


if __name__=='__main__':
    try:
        if len(sys.argv)==3 and sys.argv[1] in ('write','read'):
            _check(sys.argv[1],sys.argv[2])
        else:
            print('Chroma cross-process persistence, idempotency and repo/revision isolation:',
                  'PASS' if run_smoke() else 'FAIL')
    except Exception as exc:
        print('Chroma storage smoke test failed:',type(exc).__name__)
        raise SystemExit(1)
