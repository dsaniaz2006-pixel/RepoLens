"""Section 5 RED/GREEN tests: durable, accurately referenced conversations."""
import pytest
from fastapi import HTTPException
from backend.database.conversations import ConversationStore, answer_turn
from backend.rag.retriever import contextual_query

REPO = 'pallets/flask'
SHA = 'a' * 40
EVIDENCE = [{'path':'src/flask/app.py','start_line':7,'end_line':9,'text':'def route(self): pass'}]
ANSWER = {'answer':'The source-backed route is defined here.','citations':[{'path':'src/flask/app.py','start_line':7,'end_line':9}], 'uncertain':False}


def test_old_numbered_question_uses_correct_absolute_turn_after_history_window(tmp_path,monkeypatch):
    """Question 2 must not accidentally resolve to question 8 after 8 turns."""
    from backend.services import pipeline
    store=ConversationStore('sqlite:///'+str(tmp_path/'saved.sqlite3'))
    chat=store.create('alice',REPO,SHA)
    retrieved=[]; prompted=[]
    monkeypatch.setattr(pipeline,'retrieve',lambda repo,rev,q: retrieved.append((repo,rev,q)) or EVIDENCE)
    monkeypatch.setattr(pipeline,'answer_question',lambda q,chunks,history: prompted.append(history) or ANSWER)
    for i in range(8):
        question=('Which function validates sessions?' if i==1 else f'Unique unrelated topic {i}')
        chat=answer_turn(store,'alice',chat['id'],f'https://github.com/{REPO}',question,chat['version'])
    assert len(chat['messages'])==16
    chat=answer_turn(store,'alice',chat['id'],f'https://github.com/{REPO}',
        'How does the function from question 2 connect to the app?',chat['version'])
    query=retrieved[-1][2]
    assert 'Which function validates sessions?' in query
    assert 'Unique unrelated topic 3' not in query
    assert retrieved[-1][:2]==(REPO,SHA)
    assert any('Which function validates sessions?' in m['content'] for m in prompted[-1])
    assert len(prompted[-1])<=12
    reloaded=ConversationStore(str(store.engine.url)).get('alice',chat['id'])
    assert reloaded==chat
    assert len(reloaded['messages'])==18
    assert reloaded['messages'][-1]['citations']==ANSWER['citations']


def test_numbered_future_question_never_borrows_a_different_question(tmp_path,monkeypatch):
    from backend.services import pipeline
    store=ConversationStore('sqlite:///'+str(tmp_path/'saved.sqlite3'))
    chat=store.create('alice',REPO,SHA)
    queries=[]
    monkeypatch.setattr(pipeline,'retrieve',lambda repo,rev,q: queries.append(q) or EVIDENCE)
    monkeypatch.setattr(pipeline,'answer_question',lambda q,chunks,history: ANSWER)
    chat=answer_turn(store,'alice',chat['id'],f'https://github.com/{REPO}','Where is the router?',0)
    answer_turn(store,'alice',chat['id'],f'https://github.com/{REPO}','Explain the function from question 500',2)
    assert 'Where is the router?' not in queries[-1]


def test_cross_user_cannot_read_or_reference_another_users_history(tmp_path,monkeypatch):
    from backend.services import pipeline
    store=ConversationStore('sqlite:///'+str(tmp_path/'saved.sqlite3'))
    chat=store.create('alice',REPO,SHA)
    calls=[]
    monkeypatch.setattr(pipeline,'retrieve',lambda *args: calls.append(args) or EVIDENCE)
    with pytest.raises(HTTPException) as error:
        answer_turn(store,'bob',chat['id'],f'https://github.com/{REPO}',
                    'What is in question 1?',0)
    assert error.value.status_code==404
    assert calls==[]


def test_reference_without_explicit_source_does_not_guess_after_history_rollover():
    history=[{'role':'user','content':f'Question number {i}'} for i in range(7,12)]
    query=contextual_query('How does the function from question 2 work?',history,referenced_turn=None)
    assert query=='How does the function from question 2 work?'
