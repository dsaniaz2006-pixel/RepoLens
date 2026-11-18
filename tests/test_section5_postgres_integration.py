"""Opt-in live PostgreSQL conversation persistence/isolation test.

REPOLENS_TEST_POSTGRES_URL MUST be a disposable Neon branch/test database.
This test creates and drops one isolated schema; never use a production URL.
"""
import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.mark.skipif(not os.environ.get('REPOLENS_TEST_POSTGRES_URL'),
                    reason='No disposable PostgreSQL test database configured')
def test_postgres_pinned_conversation_survives_reopen_and_is_private():
    from backend.database.conversations import ConversationStore
    root=os.environ['REPOLENS_TEST_POSTGRES_URL']
    parsed=make_url(root)
    assert parsed.get_backend_name()=='postgresql', 'Requires a disposable PostgreSQL database'
    schema='section5_'+uuid.uuid4().hex
    admin=create_engine(root)
    with admin.begin() as connection:
        connection.execute(text('CREATE SCHEMA '+schema))
    url=parsed.update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    store=None; restarted=None
    try:
        store=ConversationStore(url)
        chat=store.create('alice','pallets/flask','a'*40)
        first=store.get('alice',chat['id'])
        assert first['messages']==[]
        row,lease,history=store.begin('alice',chat['id'],'pallets/flask',0)
        assert history==[]
        store.finish(chat['id'],lease,0,'Where is the route?',
            {'answer':'Route lives in app.py','citations':[{'path':'app.py','start_line':2,'end_line':4}], 'uncertain':False})
        store.release(chat['id'],lease)
        store.engine.dispose()
        restarted=ConversationStore(url)
        restored=restarted.get('alice',chat['id'])
        assert restored['version']==2
        assert restored['revision']=='a'*40
        assert [m['role'] for m in restored['messages']]==['user','assistant']
        assert restored['messages'][1]['citations'][0]['path']=='app.py'
        assert not restarted.listing('bob')
        with pytest.raises(Exception) as error:
            restarted.get('bob',chat['id'])
        assert getattr(error.value,'status_code',None)==404
    finally:
        if store: store.engine.dispose()
        if restarted: restarted.engine.dispose()
        with admin.begin() as connection:
            connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        admin.dispose()
