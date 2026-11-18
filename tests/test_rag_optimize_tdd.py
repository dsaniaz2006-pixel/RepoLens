"""Offline regression tests for actionable, bounded, source-grounded RAG."""
import json
from types import SimpleNamespace
from backend.core.config import RAG_TOP_K
import os
import subprocess
import sys
from backend.rag.retriever import retrieve
from backend.ai.qa import answer_question


class UncitedProvider:
    def __init__(self):
        self.models = self
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(text=json.dumps({
            'answer': 'This claim is not supported', 'uncertain': True,
            'citations': []}))


def test_default_evidence_window_includes_more_than_five_sources():
    chunks = [{'path': f'src/module_{i}.py', 'start_line': 1,
               'end_line': 2, 'text': f'def function_{i}():\n    return {i}'}
              for i in range(10)]
    observed = []
    def query(*args, **kwargs):
        observed.append(kwargs.get('top_k'))
        return chunks
    result = retrieve('owner/repo', 'a'*40, 'What modules exist?', top_k=8,
                      embedder=lambda *args, **kwargs: [[0.1, 0.9]],
                      query_fn=query)
    assert len(result) == 8
    assert len({chunk['path'] for chunk in result}) == 8
    assert observed == [40]


def test_insufficient_evidence_does_not_turn_into_uncited_answer():
    model = UncitedProvider()
    question = 'Fetches the current repository commit from GitHub.'
    chunks = [{'path': 'src/flask/app.py', 'start_line': 10,
               'end_line': 10, 'text': 'x = 1'}]
    result = answer_question(question, chunks, client=model)
    assert result['uncertain'] is True and result['citations'] == []
    assert question in result['answer']
    assert 'selected repository' in result['answer']
    assert 'index RepoLens instead' in result['answer']
    assert 'src/flask/app.py' in result['answer']
    assert 'This claim is not supported' not in result['answer']
    assert model.calls == 2


def test_valid_source_citation_remains_accepted():
    class CitedProvider:
        models = None
        def __init__(self):self.models=self
        def generate_content(self, **kwargs):
            return SimpleNamespace(text=json.dumps({
                'answer':'The function is defined here.', 'uncertain':False,
                'citations':[{'path':'src/a.py','start_line':1,'end_line':1}]}))
    result=answer_question('Where is the method?', [
        {'path':'src/a.py','start_line':1,'end_line':2,
         'text':'def method():\n    pass'}], client=CitedProvider())
    assert result['citations']==[{'path':'src/a.py','start_line':1,'end_line':2}]


def test_default_retrieval_depth_is_eight_without_override():
    from pathlib import Path
    env = dict(os.environ)
    env.pop('REPOLENS_RAG_TOP_K', None)
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-c', 'from backend.core.config import RAG_TOP_K; print(RAG_TOP_K)'],
        cwd=root, env=env, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == '8'


def test_retrieval_depth_rejects_unbounded_values():
    from pathlib import Path
    env = dict(os.environ, REPOLENS_RAG_TOP_K='500')
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-c', 'from backend.core.config import RAG_TOP_K'],
        cwd=root, env=env, text=True, capture_output=True)
    assert result.returncode != 0
    assert 'integer from 1 to 12' in result.stderr
