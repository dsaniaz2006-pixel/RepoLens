"""Regression scenarios for source-grounded answers and faster Quick indexing."""
from __future__ import annotations

from backend.rag.chunker import chunk_files
from backend.rag.retriever import retrieve, contextual_query


def test_index_excerpts_capture_late_route_and_dispatch_functions_with_real_lines():
    from backend.rag.index_excerpts import source_excerpts
    lines=['# intro\n']+['# filler text describing another component\n']*220
    lines+=['    def route(self, rule):\n','        self.add_url_rule(rule, f)\n']
    lines+=['# unrelated\n']*180
    lines+=['    def dispatch_request(self):\n', '        return self.view_functions[rule.endpoint]()\n']
    original=''.join(lines)
    slices=source_excerpts(original,'src/framework/app.py',limit=3200)
    snippets=''.join(x['text'] for x in slices)
    assert 'def route(' in snippets
    assert 'def dispatch_request(' in snippets
    assert sum(len(x['text']) for x in slices)<=3200
    rec={'path':'src/framework/app.py','content':snippets,'segments':slices}
    chunks=chunk_files([rec],'owner/repo','a'*40)
    for c in chunks:
        actual=''.join(lines[c['start_line']-1:c['end_line']])
        assert c['text'] == actual, (c['start_line'],c['end_line'],c['text'])
    assert any('dispatch_request' in c['text'] and c['start_line']>300 for c in chunks)


def test_lexical_expands_route_and_request_vocabulary_without_inventing_evidence():
    from backend.rag.retriever import lexical_rank
    src=[
        dict(path='src/flask/sansio/scaffold.py',text='def route(self, rule):\n    self.add_url_rule(rule, f)\n',start_line=100,end_line=101),
        dict(path='src/flask/sansio/app.py',text='def add_url_rule(self, rule):\n    self.url_map.add(rule)\n',start_line=200,end_line=201),
        dict(path='src/flask/app.py',text='def dispatch_request(self):\n    return self.view_functions[rule.endpoint]()\n',start_line=300,end_line=301),
        dict(path='README.md',text='Flask routing routes and requests documentation. '*20,start_line=1,end_line=10),
    ]
    found=lexical_rank('Where does Flask register routes and handle incoming requests?',src)
    assert {c['path'] for c in found[:3]}=={c['path'] for c in src[:3]}


def test_contextual_followup_keeps_antecedent_of_second_question():
    history=[{'role':'user','content':'Where does Flask register routes?'},
             {'role':'assistant','content':'Insufficient evidence'},
             {'role':'user','content':'How do those functions connect to request handling?'},
             {'role':'assistant','content':'Insufficient evidence'}]
    got=contextual_query('Explain the second question in more detail.',history)
    assert 'Where does Flask register routes?' in got
    assert 'How do those functions connect' in got


def test_reading_immutable_revision_reuses_cached_index(monkeypatch):
    from backend.rag import rag_store
    class Col:
        metadata={'repolens_complete':True}
        def __init__(self):self.loads=0
        def count(self):return 1
        def get(self,**kwargs):
            self.loads+=1
            return {'documents':['def route(): pass\n'], 'metadatas':[{
                'repo':'o/r','revision':'a'*40,'path':'route.py','start_line':1,'end_line':1}]}
    c=Col()
    monkeypatch.setattr(rag_store,'get_collection',lambda *a,**kw:c)
    rag_store.clear_index_cache()
    try:
        assert rag_store.read_index_chunks('o/r','a'*40,'model')==rag_store.read_index_chunks('o/r','a'*40,'model')
        assert c.loads==1
    finally:rag_store.clear_index_cache()


def test_grounded_flow_fallback_cites_actual_calls_only():
    from backend.rag.source_symbols import grounded_source_answer
    evidence=[
        dict(path='scaffold.py',start_line=7,end_line=9,text='def route(self, rule):\n    self.add_url_rule(rule, f)\n'),
        dict(path='app.py',start_line=30,end_line=32,text='def add_url_rule(self, rule):\n    self.url_map.add(rule)\n'),
        dict(path='app.py',start_line=100,end_line=102,text='def dispatch_request(self):\n    return self.view_functions[rule.endpoint]()\n')]
    answer=grounded_source_answer('How do route registration and request dispatch connect?',evidence)
    assert answer and len(answer['citations'])>=2
    assert 'route' in answer['answer'] and 'dispatch_request' in answer['answer']
    assert answer['uncertain']  # No verified direct call from registration to dispatch.


def test_quick_index_cap_preserves_more_source_in_same_character_budget(monkeypatch):
    import backend.services.pipeline as pipeline
    from backend.github import github_client
    source='# comment\n'*1500+'def dispatch_request(self):\n    return self.view_functions[rule.endpoint]()\n'
    tree=[{'path':'src/framework/app.py','size':len(source),'type':'blob'}]
    monkeypatch.setattr(pipeline,'fetch_repo_metadata',lambda *a:{'default_branch':'main','private':False})
    monkeypatch.setattr(pipeline,'fetch_tree',lambda *a:(tree,False))
    monkeypatch.setattr(github_client,'fetch_file_content',lambda *a:source)
    data=pipeline.collect_repo('https://github.com/o/r',revision='a'*40,for_index=True)
    chunks=chunk_files(data['records'],'o/r','a'*40)
    assert any('dispatch_request' in c['text'] and c['start_line']>1000 for c in chunks)
    assert sum(len(c['text']) for c in chunks)<6000


def test_quick_index_prioritizes_route_registration_and_request_dispatch_source():
    from backend.services.file_selector import rank_for_rag_index
    tree=[{'path':'README.md','type':'blob'}]+[{'path':f'src/flask/alpha{i}.py','type':'blob'} for i in range(50)]
    tree += [{'path':p,'type':'blob'} for p in
             ['src/flask/app.py','src/flask/sansio/scaffold.py','src/flask/request.py']]
    selected=dict(rank_for_rag_index(tree,limit=12))
    assert 'src/flask/sansio/scaffold.py' in selected
    assert 'src/flask/app.py' in selected
    assert 'src/flask/request.py' in selected
    assert 'README.md' in selected


def test_quick_excerpts_keep_important_calls_after_long_docstrings():
    from backend.rag.index_excerpts import source_excerpts
    src=('"""Module overview"""\n'+'# helper\n'*60 +
         '    def route(self, rule):\n'+'        """\n'+('        Descriptive route documentation.\n'*90)+'        """\n'+
         '        self.add_url_rule(rule, f)\n'+'# footer\n'*80)
    snippets=''.join(s['text'] for s in source_excerpts(src,'src/flask/sansio/scaffold.py',limit=3500))
    assert 'def route' in snippets
    assert 'self.add_url_rule(rule, f)' in snippets


def test_three_flask_style_questions_return_conservative_cited_answers_when_model_omits_citations():
    """The screenshot's exact conversation pattern must not turn into three uncited refusals."""
    from backend.ai.qa import answer_question
    from types import SimpleNamespace
    evidence=[
        dict(path='src/flask/sansio/scaffold.py',start_line=100,end_line=102,
             text='def route(self, rule):\n    self.add_url_rule(rule, f)\n'),
        dict(path='src/flask/sansio/app.py',start_line=600,end_line=602,
             text='def add_url_rule(self, rule):\n    self.url_map.add(rule)\n'),
        dict(path='src/flask/app.py',start_line=800,end_line=802,
             text='def dispatch_request(self):\n    return self.view_functions[rule.endpoint]()\n'),
    ]
    class Uncited:
        def __init__(self):self.models=self;self.calls=0
        def generate_content(self,**kwargs):
            self.calls+=1
            return SimpleNamespace(text='{"answer":"Insufficient evidence","uncertain":true,"citations":[]}')
    model=Uncited()
    questions=[
        'Where does Flask register routes, and which functions are involved?',
        "How do those functions connect to Flask's request handling?",
        'Explain the second question in more detail and cite the relevant files.',
    ]
    for question in questions:
        answer=answer_question(question,evidence,client=model)
        assert answer['citations'] and answer['uncertain']
        assert 'insufficient evidence' not in answer['answer'].lower()
        assert all(c['path'] in {x['path'] for x in evidence} for c in answer['citations'])
    assert model.calls==3  # Avoid duplicate Gemini citation-repair calls.


def test_cache_is_invalidated_when_index_is_replaced(monkeypatch):
    from backend.rag import rag_store
    from unittest.mock import Mock
    class Collection:
        metadata={'repolens_complete':True}
        def __init__(self):self.reads=0
        def count(self):return 1
        def get(self,**kwargs):
            self.reads+=1
            return {'documents':['def example(): pass\n'], 'metadatas':[dict(repo='o/r',revision='b'*40,path='x.py',start_line=1,end_line=1)]}
        def modify(self,**kwargs):self.metadata=kwargs['metadata']
        def upsert(self,**kwargs):pass
    col=Collection()
    monkeypatch.setattr(rag_store,'get_collection',lambda *a,**kw:col)
    rag_store.clear_index_cache()
    try:
        for _ in range(3): rag_store.read_index_chunks('o/r','b'*40,'model')
        assert col.reads==1
        doc=dict(repo='o/r',revision='b'*40,id='x',path='x.py',text='def example(): pass\n',start_line=1,end_line=1)
        assert rag_store.store_chunks('o/r','b'*40,'model',[doc],[[1.,2.]])==1
        rag_store.read_index_chunks('o/r','b'*40,'model')
        # The replacement checks IDs once before upsert to remove obsolete
        # passages, then the invalidated lexical cache performs a fresh read.
        assert col.reads==3
    finally:rag_store.clear_index_cache()


def test_existing_saved_chats_can_read_legacy_v3_index_until_new_build():
    from backend.rag.rag_store import collection_name, get_collection
    current=collection_name('o/r','a'*40,'model')
    legacy=collection_name('o/r','a'*40,'model',format_version='3')
    assert current!=legacy
    class Client:
        def __init__(self):self.names=[]
        def get_collection(self,*,name):
            self.names.append(name)
            if name==legacy:return {'legacy':True}
            raise RuntimeError('Collection not found')
    client=Client()
    assert get_collection('o/r','a'*40,'model',client=client)=={'legacy':True}
    assert client.names==[current,legacy]
    # A new index must always write the new version and never touch legacy.
    class Writer(Client):
        def get_or_create_collection(self,*,name):
            self.names.append(name)
            return {'created':name}
    writer=Writer()
    assert get_collection('o/r','a'*40,'model',client=writer,create=True)=={'created':current}
    assert writer.names==[current]
