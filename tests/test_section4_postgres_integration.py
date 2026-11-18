"""Real PostgreSQL atomic quota integration, opt-in disposable schema only.

Set REPOLENS_TEST_POSTGRES_URL to a disposable TEST database/Neon branch.
Never point this at your production Neon DB; this test creates and drops a schema.
"""
import os, uuid
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

@pytest.mark.skipif(not os.getenv('REPOLENS_TEST_POSTGRES_URL'),reason='Disposable PostgreSQL test database not configured')
def test_postgres_concurrent_quota_and_migrations(tmp_path):
    from backend.auth.auth import AuthManager
    from backend.database.schema_migrations import upgrade_databases,migration_status
    root=os.environ['REPOLENS_TEST_POSTGRES_URL']
    assert make_url(root).get_backend_name()=='postgresql'
    schema='usage4_'+uuid.uuid4().hex
    admin=create_engine(root)
    with admin.begin() as connection:
        connection.execute(text('CREATE SCHEMA '+schema))
    url=make_url(root).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    try:
        state=upgrade_databases(url,url)
        assert state['auth']['current']=='auth_0005'
        assert state['auth']['up_to_date'] and state['app']['up_to_date']
        mgr=AuthManager(directory=tmp_path/'auth',environ={'REPOLENS_AUTH_DATABASE_URL':url})
        uid=mgr.upsert_user('github','concurrent-user','Alice')['id']
        def reserve(_):
            try:
                mgr.reserve_usage(uid,'ask','198.51.100.11',now=1763000000,
                    limits={'free':{'ask':3}},hourly={'ask':50})
                return True
            except Exception as exc:
                if getattr(exc,'status_code',None)==429:return False
                raise
        with ThreadPoolExecutor(max_workers=12) as pool:
            outcome=list(pool.map(reserve,range(30)))
        assert sum(outcome)==3
        assert mgr.usage_snapshot(uid,now=1763000000,limits={'free':{'ask':3}})['usage']['ask']['used']==3
        with mgr.connect() as connection:
            assert connection.execute('SELECT COUNT(*) AS n FROM usage_events WHERE user_id=?',(uid,)).fetchone()['n']==3
        assert migration_status(url,url)['auth']['up_to_date']
        mgr.sql_database.engine.dispose()
    finally:
        with admin.begin() as connection:
            connection.execute(text('DROP SCHEMA '+schema+' CASCADE'))
        admin.dispose()
