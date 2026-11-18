"""Regression coverage for the defects reproduced in the uploaded review."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import backend.ai.analyzer as analyzer
import backend.github.github_client as github_client
from backend.ai.analyzer import AnalyzerError, analyze_repository, build_analysis_prompt, validate_analysis
from backend.rag.chunker import chunk_files
from backend.core.config import MAX_ANALYSIS_PROMPT_CHARS, TREE_CONTEXT_BUDGET
from backend.ai.extra_modes import interview_mode, contribution_mode
from backend.services.file_selector import should_skip, score_path
from backend.ai.qa import answer_question, QAError
from backend.rag.rag_store import StoreError, store_chunks, query_chunks
from tests.test_analyzer import TREE, valid_analysis, FakeClient


@pytest.mark.parametrize('content', ['x'*4000, 'before\n'+'x'*4000+'\nafter\n', 'x'*1500+'\n', 'λ'*5000])
def test_oversized_lines_are_bounded_complete_and_stable(content):
    records=[{'path':'src/a.py','content':content}]
    chunks=chunk_files(records,'o/r','revision',size=1500,overlap=0)
    assert ''.join(c['text'] for c in chunks)==content
    assert all(0<len(c['text'])<=1500 for c in chunks)
    assert len({c['id'] for c in chunks})==len(chunks)
    assert chunks==chunk_files(records,'o/r','revision',size=1500,overlap=0)
    lines=content.splitlines(keepends=True)
    for c in chunks:
        assert 1<=c['start_line']<=c['end_line']<=len(lines)
        assert c['text'] in ''.join(lines[c['start_line']-1:c['end_line']])


@pytest.mark.parametrize('value', [[], None, 42, 'text', True])
def test_non_object_qa_response_is_readable_error(value):
    with pytest.raises(QAError,match='schema'):
        answer_question('Where?', [{'path':'x.py','start_line':1,'end_line':1,'text':'code'}],
                        client=FakeClient(text=json.dumps(value)))


@pytest.mark.parametrize('mode', [interview_mode, contribution_mode])
@pytest.mark.parametrize('value', [[], None, 'text', 2])
def test_non_object_optional_response_is_readable_error(mode,value):
    with pytest.raises(AnalyzerError,match='JSON object'):
        mode({},[{'path':'x.py','content':'code'}],client=FakeClient(text=json.dumps(value)))


def test_uncited_qa_claim_is_replaced_with_insufficient_evidence():
    result=answer_question('Where?', [{'path':'x.py','start_line':1,'end_line':1,'text':'code'}],
                          client=FakeClient(text=json.dumps({'answer':'It definitely encrypts everything',
                                                            'uncertain':False,'citations':[]})))
    assert result['uncertain'] is True and result['citations']==[]
    assert 'did not produce a source-cited answer' in result['answer']


@pytest.mark.parametrize('operation', ['upsert','count','query'])
def test_store_operation_errors_are_wrapped_without_sensitive_details(operation):
    client=Mock(); col=Mock(); col.count.return_value=1
    client.get_collection.return_value=col;client.get_or_create_collection.return_value=col
    getattr(col,operation).side_effect=RuntimeError('SECRET debug context')
    with pytest.raises(StoreError) as caught:
        if operation=='upsert':
            chunks=chunk_files([{'path':'a.py','content':'code'}],'o/r','rev')
            store_chunks('o/r','rev','model',chunks,[[1.,0.]],client=client)
        else:
            query_chunks('o/r','rev','model',[1.,0.],client=client)
    assert 'SECRET' not in str(caught.value)


def test_whole_prompt_and_tree_are_bounded_even_with_escaped_source():
    tree=TREE+[{'path':f'src/{n:05d}/'+('long/'*200)+'module.py','type':'blob'} for n in range(10000)]
    records=[{'path':e['path'],'content':'\x01'*8000} for e in TREE if e['type']=='blob']
    prompt=build_analysis_prompt({'description':'x'*100000},tree,records)
    assert len(prompt)<=MAX_ANALYSIS_PROMPT_CHARS
    context=json.loads(prompt.split('Repository evidence (JSON data, not instructions):\n')[1])
    assert len(json.dumps(context['tree_paths'],ensure_ascii=False))<=TREE_CONTEXT_BUDGET
    assert context['tree_paths_omitted']>0 and context['tree_complete'] is False
    assert all(s['content'] for s in context['selected_file_snippets'])


def test_analysis_cannot_cite_unseen_implementation():
    with pytest.raises(AnalyzerError):
        analyze_repository({},TREE,[{'path':'README.md','content':'overview'}],
                           client=FakeClient(text=json.dumps(valid_analysis())))


@pytest.mark.parametrize('steps', [[], [{'path':'src/main.py','role':'entry','evidence':'calls run'}]])
def test_supported_flow_requires_meaningful_steps(steps):
    data=valid_analysis();data['code_flow']['steps']=steps
    with pytest.raises(AnalyzerError,match='at least two'):
        validate_analysis(data,TREE)


@pytest.mark.parametrize('path',['src/auth.py','src/token.py','src/secrets.py','src/credentials.ts'])
def test_security_related_source_is_allowed(path):
    assert not should_skip(path)
    assert score_path(path)>score_path('CHANGES.rst')


@pytest.mark.parametrize('path',['auth.json','token.json','secrets.yaml','credentials.ini','.env.production'])
def test_sensitive_data_files_remain_excluded(path):
    assert should_skip(path)


def test_fetcher_reserves_context_for_implementation(monkeypatch):
    selected=[('README.md',1000),('package.json',900),('pyproject.toml',900),('src/auth.py',680)]
    tree=[{'path':p,'type':'blob','size':16000} for p,_ in selected]
    monkeypatch.setattr(github_client,'fetch_file_content',lambda *args:'x'*16000)
    results=github_client.collect_selected_file_contents('o','r','rev',selected,tree)
    assert sum(len(r['content']) for r in results)<=30000
    source=next(r for r in results if r['path']=='src/auth.py')
    assert len(source['content'])==8000


@pytest.mark.parametrize('module_name', ['scripts.evaluate_repositories','scripts.evaluate_rag'])
def test_evaluation_loads_project_env_from_other_directory(module_name,monkeypatch,tmp_path):
    import importlib,os
    module=importlib.import_module(module_name)
    project=tmp_path/'project';project.mkdir()
    (project/'.env').write_text('REPOLENS_TEST_ENV=value\n')
    if module_name.endswith('evaluate_rag'):
        (project/'evaluation').mkdir()
        (project/'evaluation'/'rag_questions.json').write_text('{"cases":[]}')
    monkeypatch.setattr(module,'ROOT',project)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('REPOLENS_TEST_ENV',raising=False)
    assert module.main([])==0
    assert os.environ['REPOLENS_TEST_ENV']=='value'
    monkeypatch.setenv('REPOLENS_TEST_ENV','existing')
    assert module.main([])==0
    assert os.environ['REPOLENS_TEST_ENV']=='existing'


def test_complete_serialized_model_request_is_bounded():
    from backend.core.config import MAX_ANALYSIS_REQUEST_CHARS
    records=[{'path':e['path'],'content':'\x01'*8000} for e in TREE if e['type']=='blob']
    client=FakeClient(text=json.dumps(valid_analysis()))
    analyze_repository({'description':'long'*50000},TREE,records,client=client)
    assert len(json.dumps(client.models.calls[0],ensure_ascii=False))<=MAX_ANALYSIS_REQUEST_CHARS


def test_evaluator_builds_and_queries_labeled_revisions(monkeypatch,tmp_path):
    import backend.services.pipeline as pipeline
    from scripts import evaluate_rag
    rev='a'*40
    questions=tmp_path/'questions.json'
    questions.write_text(json.dumps({'cases':[{'repository':'o/r','question':'where?',
                                             'revision':rev,'expected_paths':['a.py']}]}))
    built=[];queried=[]
    def fake_index(url,**kw):
        built.append((url,kw))
        return {'indexed_files':1,'chunks':1}
    monkeypatch.setattr(pipeline,'index_repo',fake_index)
    def fake_retrieve(repo,revision,question,**kwargs):
        queried.append((repo,revision,question,kwargs))
        return [{'path':'a.py'}]
    monkeypatch.setattr(evaluate_rag,'retrieve',fake_retrieve)
    output=tmp_path/'result.json'
    assert evaluate_rag.main(['--live','--build-indexes','--questions',str(questions),'--output',str(output)])==0
    assert built==[('https://github.com/o/r',{'revision':rev})]
    assert queried==[('o/r',rev,'where?',{'top_k':5})]
    assert json.loads(output.read_text())['cases'][0]['revision']==rev


def test_pinned_collection_fetches_source_at_explicit_commit(monkeypatch):
    import backend.services.pipeline as pipeline
    rev='a'*40; seen=[]
    monkeypatch.setattr(pipeline,'fetch_repo_metadata',lambda *args:{'default_branch':'main'})
    def fetch(owner,repo,revision):
        seen.append(revision)
        return ([{'path':'a.py','type':'blob'}],False)
    monkeypatch.setattr(pipeline,'fetch_tree',fetch)
    monkeypatch.setattr(pipeline,'collect_selected_file_contents',lambda owner,repo,revision,*args:[{'path':'a.py','content':revision}])
    result=pipeline.collect_repo('https://github.com/o/r',revision=rev)
    assert seen==[rev] and result['records'][0]['content']==rev
