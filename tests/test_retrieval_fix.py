from backend.rag.retriever import contextual_query, lexical_rank, retrieve

def test_standalone_question_drops_unrelated_history():
    history=[{'role':'user','content':'Does imaginary_secret_engine.py exist?'}]
    q='How does Flask implement URL routing in src/flask/sansio/app.py?'
    assert contextual_query(q,history)==q
    assert 'Previous question' in contextual_query('What calls it?',history)

def test_exact_path_recovers_semantic_miss():
    target=dict(path='src/flask/sansio/app.py',start_line=597,end_line=630,text='def add_url_rule(self, rule): self.url_map.add(rule)')
    unrelated=dict(path='README.md',start_line=1,end_line=5,text='Flask is a web framework')
    q='How does URL routing work in src/flask/sansio/app.py?'
    result=retrieve('pallets/flask','a'*40,q,embedder=lambda *a,**k:[[1.0]],query_fn=lambda *a,**k:[unrelated],lexical_fn=lambda *a:[unrelated,target])
    assert result[0]==target

def test_lexical_symbols_beat_unrelated_text():
    chunks=[dict(path='a.py',text='def add_url_rule(rule): pass'),dict(path='b.py',text='def send_email(): pass')]
    assert lexical_rank('What does add_url_rule do?',chunks)[0]['path']=='a.py'

def test_empty_retrieval_has_distinct_message():
    from backend.ai.qa import answer_question
    result=answer_question('Where is routing?',[])
    assert 'No source passages were retrieved' in result['answer']
    assert result['uncertain'] and not result['citations']
