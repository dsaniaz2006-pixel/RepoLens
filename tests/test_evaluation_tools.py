"""No live API calls. These tests verify the tools, not external answer quality."""
import json
from pathlib import Path
from tests.test_analyzer import TREE, valid_analysis
from scripts.evaluate_repositories import audit_result, main as repo_main
from scripts.evaluate_rag import evaluate_cases, main as rag_main


def test_report_audit_structural_pass():
    data = {'analysis': valid_analysis(), 'tree': TREE, 'metadata': {'full_name':'owner/sample'}}
    checks = audit_result(data)
    assert checks['passed']
    assert checks['reading_path_count'] == 3
    assert checks['human_review'].startswith('NOT VERIFIED')


def test_report_audit_rejects_invented_file():
    data = {'analysis': valid_analysis(), 'tree': TREE, 'metadata': {'full_name':'owner/sample'}}
    data['analysis']['reading_path'][0]['path'] = 'invented_file.py'
    import pytest
    from backend.ai.analyzer import AnalyzerError
    with pytest.raises(AnalyzerError):audit_result(data)


def test_rag_eval_skips_unlabeled_and_calculates_hits():
    cases = [
        {'repository':'o/r','question':'one','expected_paths':['src/a.py','src/b.py']},
        {'repository':'o/r','question':'two','expected_paths':['src/c.py']},
        {'repository':'o/r','question':'three','expected_paths':[]},
    ]
    def fake_retrieval(repo, question, top_k):
        return [{'path':'src/a.py'}] if question=='one' else [{'path':'README.md'}]
    outcome=evaluate_cases(cases,fake_retrieval)
    assert outcome['labeled']==2 and outcome['unlabeled']==1
    assert outcome['hit_rate_at_k']==0.5 and outcome['mean_recall_at_k']==0.25


def test_questions_cover_twelve_diverse_scenarios():
    path=Path(__file__).resolve().parents[1]/'evaluation'/'rag_questions.json'
    data=json.loads(path.read_text())
    assert len(data['cases']) == 12
    assert len({c['repository'] for c in data['cases']}) == 3
    assert all(c['expected_paths'] and len(c['revision'])==40 and c['evidence'] for c in data['cases'])


def test_evaluation_scripts_require_explicit_live_opt_in(capsys):
    assert repo_main([]) == 0
    assert 'NOT RUN' in capsys.readouterr().out
    assert rag_main([]) == 0
    assert 'Label expected_paths' in capsys.readouterr().out


def test_model_checker_with_mocked_sdk():
    from scripts.check_models import check_model_access
    from types import SimpleNamespace
    class Models:
        def get(self,model):return SimpleNamespace(name=model)
        def generate_content(self,**kwargs):return SimpleNamespace(text='OK')
        def embed_content(self,**kwargs):return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1,0.2]) for _ in kwargs['contents']])
    data=check_model_access(SimpleNamespace(models=Models()),probe=True)
    assert data['generation']['probe']=='PASS' and data['embedding']['probe']=='PASS'
