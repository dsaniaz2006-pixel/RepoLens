"""Regressions for repeated uncited answers despite retrievable source code."""
from types import SimpleNamespace
from backend.ai.qa import answer_question
from backend.rag.retriever import retrieve, contextual_query


def chunk(path, text, start=20):
    return dict(path=path, text=text, start_line=start, end_line=start+len(text.splitlines())-1)


class StubModel:
    def __init__(self, *responses):
        self.responses=responses
        self.calls=[]
        self.models=self
    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        i=min(len(self.calls)-1, len(self.responses)-1)
        return SimpleNamespace(text=self.responses[i])


def test_uncited_model_answer_recovers_only_verifiable_function_definition():
    c=chunk('src/flask/sansio/app.py','    def add_url_rule(self, rule, endpoint=None):\n        self.url_map.add(rule)\n',600)
    model=StubModel('{"answer":"The function is add_url_rule.","uncertain":false,"citations":[]}')
    out=answer_question('Which function registers a URL rule?', [c], client=model)
    assert out['citations'] == [{'path':'src/flask/sansio/app.py','start_line':600,'end_line':601}]
    assert 'add_url_rule' in out['answer']
    assert not out['uncertain']


def test_uncited_answer_never_invents_symbol_without_definition():
    c=chunk('README.md','This repository offers a web framework.\n')
    model=StubModel('{"answer":"Flask has some function.","uncertain":false,"citations":[]}')
    out=answer_question('Which function registers a URL rule?', [c], client=model)
    assert out['uncertain'] and out['citations']==[]
    assert 'add_url_rule' not in out['answer']


def test_routing_decorator_symbol_uses_source_not_readme_claim():
    src=chunk('src/flask/sansio/scaffold.py','    def route(self, rule: str, **options):\n        """Register a view function for a given URL rule."""\n        def decorator(f):\n            self.add_url_rule(rule, endpoint, f, **options)\n',400)
    readme=chunk('README.md','The word route decorator appears several times.\n',1)
    model=StubModel('{"answer":"I cannot establish citation.","uncertain":true,"citations":[]}')
    out=answer_question('Where does Flask define its route decorator?', [readme,src], client=model)
    assert 'src/flask/sansio/scaffold.py' in str(out['citations'])
    assert 'route' in out['answer']


def test_symbol_retrieval_prioritizes_code_over_docs_and_remains_revision_scoped():
    source=chunk('src/flask/sansio/scaffold.py','def route(self, rule):\n    return decorator\n')
    doc=chunk('README.md','route decorator route decorator route decorator route decorator\n',1)
    other=chunk('src/flask/sansio/app.py','def add_url_rule(self, rule):\n    return self.url_map.add(rule)\n')
    calls=[]
    def lexical(repo,revision,model):
        calls.append((repo,revision))
        return [doc,source,other]
    retrieved=retrieve('pallets/flask','a'*40,'Where is the route decorator?',
                       top_k=2,embedder=lambda *args,**kwargs:[[0.2,0.1]],
                       query_fn=lambda *args,**kwargs:[doc],lexical_fn=lexical)
    assert retrieved[0]['path']=='src/flask/sansio/scaffold.py'
    assert calls[0][:2]==('pallets/flask','a'*40)


def test_question_two_follow_up_context_includes_prior_user_question():
    history=[{'role':'user','content':'Where is the route decorator?'},
             {'role':'assistant','content':'Defined in scaffold.py'},
             {'role':'user','content':'Which function registers a URL rule?'},
             {'role':'assistant','content':'The add_url_rule function registers the rule.'}]
    q=contextual_query('How does the function from question 2 connect to request dispatch?',history)
    assert 'Which function registers a URL rule?' in q
    assert 'add_url_rule' in q


def test_chat_turn_persists_grounded_recovery_citation_after_reload(tmp_path,monkeypatch):
    from backend.database.conversations import ConversationStore, answer_turn
    from backend.services import pipeline
    store=ConversationStore('sqlite:///'+str(tmp_path/'source_chat.sqlite'))
    row=store.create('alice','pallets/flask','a'*40)
    model=StubModel('{"answer":"The function is add_url_rule.","uncertain":false,"citations":[]}')
    evidence=[chunk('src/flask/sansio/app.py','    def add_url_rule(self, rule):\n        self.url_map.add(rule)\n',600)]
    monkeypatch.setattr(pipeline,'retrieve',lambda repo,revision,question:evidence)
    monkeypatch.setattr(pipeline,'answer_question',lambda q,docs,history:answer_question(q,docs,history=history,client=model))
    result=answer_turn(store,'alice',row['id'],'https://github.com/pallets/flask','Which function registers a URL rule?',0)
    assert result['messages'][1]['citations'][0]['path']=='src/flask/sansio/app.py'
    restored=ConversationStore(str(store.engine.url)).get('alice',row['id'])
    assert restored['messages'][1]['citations']==result['messages'][1]['citations']
    assert 'add_url_rule' in restored['messages'][1]['content']


def test_uncited_model_gets_one_evidence_only_retry_and_accepts_valid_citation():
    c=chunk('src/core/auth.py','def verify_session(token):\n    return bool(token)\n',30)
    model=StubModel(
        '{"answer":"Session validation exists","uncertain":false,"citations":[]}',
        '{"answer":"verify_session checks a token","uncertain":false,"citations":'
        '[{"path":"src/core/auth.py","start_line":30,"end_line":31}]}'
    )
    out=answer_question('Where does token verification happen?', [c], client=model)
    assert len(model.calls)==2
    assert out['answer']=='verify_session checks a token'
    assert out['citations'][0]['path']=='src/core/auth.py'


def test_model_is_not_retried_when_citations_are_already_valid():
    c=chunk('src/core/auth.py','def verify_session(token):\n    return bool(token)\n',30)
    model=StubModel('{"answer":"In auth.py","uncertain":false,"citations":'
                    '[{"path":"src/core/auth.py","start_line":30,"end_line":30}]}')
    out=answer_question('Where does token verification happen?', [c], client=model)
    assert len(model.calls)==1
    assert out['citations']


def test_fresh_conversation_db_lists_without_uninitialized_membership_table(tmp_path):
    from backend.database.conversations import ConversationStore
    store=ConversationStore('sqlite:///'+str(tmp_path/'fresh.sqlite3'))
    store.create('alice','pallets/flask','a'*40)
    assert store.listing('alice')
    assert store.listing('bob')==[]
