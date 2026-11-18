"""End-to-end *offline* pipeline tests: real selection, content budgets,
structured response validation, Markdown saving, chunking and Chroma adapter.
Only the remote GitHub/Gemini boundaries are simulated; no live claims.
"""
from __future__ import annotations
import base64
import json
from types import SimpleNamespace

import backend.github.github_client as github_client
import backend.services.pipeline as pipeline
from backend.ai.analyzer import analyze_repository
from backend.rag.chunker import chunk_files
from backend.rag.embeddings import embed_texts
from backend.ai.qa import answer_question
from backend.rag.rag_store import store_chunks, query_chunks, collection_name
from tests.test_analyzer import valid_analysis

CODE = {
    'README.md': '# Sample app\nStart with the README.\n',
    'pyproject.toml': '[project]\nname = "sample"\n',
    'src/main.py': 'from .service import run\n\ndef main():\n    return run()\n',
    'src/service.py': 'def run():\n    return 42\n',
    'tests/test_service.py': 'from src.service import run\n\ndef test_run():\n    assert run() == 42\n',
}


def fake_github_get(path, context, params=None, **kwargs):
    if path == '/repos/owner/sample':
        return {'name': 'sample', 'full_name': 'owner/sample', 'default_branch': 'main',
                'description': 'Synthetic source used for offline testing', 'language':'Python',
                'html_url':'https://github.com/owner/sample'}
    if path.startswith('/repos/owner/sample/commits/'):
        return {'sha':'a'*40}
    if path.startswith('/repos/owner/sample/git/trees/'):
        return {'truncated': False,
                'tree': [{'path':p, 'type':'blob','size':len(content.encode())} for p,content in CODE.items()]}
    if path.startswith('/repos/owner/sample/contents/'):
        name = path.removeprefix('/repos/owner/sample/contents/')
        return {'encoding':'base64','content':base64.b64encode(CODE[name].encode()).decode()}
    raise AssertionError(f'Unexpected fake endpoint: {path}')


class FakeGemini:
    class Models:
        def generate_content(self, **kwargs):
            return SimpleNamespace(text=json.dumps(valid_analysis()))
    models = Models()


def test_real_pipeline_with_faked_external_boundaries(monkeypatch,tmp_path):
    monkeypatch.setattr(github_client,'_get',fake_github_get)
    original = analyze_repository
    def fake_analyze(metadata,tree,records,tree_truncated=False):
        assert 0 < len(records) <= 20
        assert sum(len(r['content']) for r in records) <= 30000
        assert 'src/main.py' in {r['path'] for r in records}
        return original(metadata,tree,records,tree_truncated,client=FakeGemini())
    monkeypatch.setattr(pipeline,'analyze_repository',fake_analyze)
    result = pipeline.generate_report('https://github.com/owner/sample', output_dir=str(tmp_path))
    text=(tmp_path/'owner-sample-report.md').read_text()
    assert result['metadata']['full_name']=='owner/sample'
    assert '## 5. Recommended reading path' in text
    assert '`src/main.py`' in text
    assert result['report_path']==str(tmp_path/'owner-sample-report.md')
    assert 'src' in text  # Source directory inferred from tree paths


def test_report_infers_directory_when_recursive_tree_has_no_tree_node():
    from backend.services.report import render_report
    analysis=valid_analysis()
    tree=[{'type':'blob','path':p} for p in CODE]
    rendered=render_report(analysis,{'full_name':'owner/sample'},tree)
    assert '`src`: Application source.' in rendered


class MemoryCollection:
    def __init__(self): self.items={}; self.metadata=None
    def modify(self, *, metadata): self.metadata=metadata
    def upsert(self, ids, embeddings, documents, metadatas):
        for i,vector,text,meta in zip(ids,embeddings,documents,metadatas):
            self.items[i]=(vector,text,meta)
    def count(self): return len(self.items)
    def get(self, *, include): return {'ids': list(self.items)}
    def delete(self, *, ids):
        for identity in ids: self.items.pop(identity, None)
    def query(self, query_embeddings, n_results, include):
        vec=query_embeddings[0]
        ranked=sorted(self.items.items(),key=lambda item: sum((a-b)**2 for a,b in zip(vec,item[1][0])))[:n_results]
        return {'documents':[[data[1] for _,data in ranked]],
                'metadatas':[[data[2] for _,data in ranked]],
                'distances':[[sum((a-b)**2 for a,b in zip(vec,data[0])) for _,data in ranked]]}


class MemoryClient:
    def __init__(self): self.collections={}
    def get_or_create_collection(self,name):
        return self.collections.setdefault(name,MemoryCollection())
    def get_collection(self,name):
        if name not in self.collections: raise KeyError(name)
        return self.collections[name]


def test_full_local_rag_store_and_citation_without_network():
    chunks=chunk_files([{'path':'src/auth.py','content':'def validate_token(value):\n    return bool(value)\n'}],
                       'owner/sample','a'*40, size=120,overlap=15)
    store=MemoryClient()
    vectors=[[0.1,0.9] for _ in chunks]
    assert store_chunks('owner/sample','a'*40,'test-embed',chunks,vectors,client=store)==1
    assert store_chunks('owner/sample','a'*40,'test-embed',chunks,vectors,client=store)==1
    retrieved=query_chunks('owner/sample','a'*40,'test-embed',[0.1,0.9],client=store)
    assert retrieved[0]['path']=='src/auth.py'
    class FakeQA:
        class Models:
            def generate_content(self,**kwargs):
                return SimpleNamespace(text=json.dumps({'answer':'The validate_token function handles this.',
                   'uncertain':False,'citations':[{'path':'src/auth.py','start_line':1,'end_line':2}]}))
        models=Models()
    output=answer_question('Where is token validation?',retrieved,client=FakeQA())
    assert output['citations'][0]['start_line']==1
    # Same commit under another repository is a completely separate collection.
    assert collection_name('owner/sample','a'*40,'test-embed')!=collection_name('someone/else','a'*40,'test-embed')
