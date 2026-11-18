"""Section 4 failure-first tests, no external services."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from backend.auth.auth import AuthManager
from backend.database.schema_migrations import upgrade_databases, migration_status

@pytest.fixture(params=['local','sqlalchemy'])
def manager(tmp_path,request):
    if request.param == 'local':
        return AuthManager(directory=tmp_path/'auth',environ={})
    url='sqlite:///'+str(tmp_path/'auth.db')
    upgrade_databases(url,'sqlite:///'+str(tmp_path/'app.db'))
    return AuthManager(directory=tmp_path/'local',environ={'REPOLENS_AUTH_DATABASE_URL':url})

def test_quota_atomic_and_utc_reset(manager):
    user=manager.upsert_user('github','one','One')['id']
    for i in range(2):
        result=manager.reserve_usage(user,'ask','127.0.0.1',now=1763000000,limits={'free':{'ask':2}},hourly={'ask':10})
        assert result['used']==i+1
    with pytest.raises(Exception) as exc:
        manager.reserve_usage(user,'ask','127.0.0.1',now=1763000000,limits={'free':{'ask':2}},hourly={'ask':10})
    assert getattr(exc.value,'status_code',None)==429
    assert manager.usage_snapshot(user,now=1763000000,limits={'free':{'ask':2}})['usage']['ask']['used']==2
    assert manager.reserve_usage(user,'ask','127.0.0.1',now=1763086400,limits={'free':{'ask':2}},hourly={'ask':10})['used']==1

def test_quota_parallel_not_exceeded(manager):
    user=manager.upsert_user('github','parallel','Parallel')['id']
    def attempt(_):
        try:
            manager.reserve_usage(user,'analyze','127.0.0.4',now=1763000000,
                                  limits={'free':{'analyze':3}},hourly={'analyze':20})
            return True
        except Exception as exc:
            if getattr(exc,'status_code',None)==429: return False
            raise
    with ThreadPoolExecutor(max_workers=8) as pool:
        result=list(pool.map(attempt,range(20)))
    assert sum(result)==3
    assert manager.usage_snapshot(user,now=1763000000,limits={'free':{'analyze':3}})['usage']['analyze']['used']==3

def test_ip_limit_rollback_and_isolation(manager):
    a=manager.upsert_user('github','a','A')['id']
    b=manager.upsert_user('github','b','B')['id']
    manager.reserve_usage(a,'index','1.2.3.4',now=1763000000,limits={'free':{'index':5}},hourly={'index':1})
    with pytest.raises(Exception) as exc:
        manager.reserve_usage(b,'index','1.2.3.4',now=1763000000,limits={'free':{'index':5}},hourly={'index':1})
    assert getattr(exc.value,'status_code',None)==429
    # A rate-limit denial must not consume B's daily usage.
    assert manager.usage_snapshot(b,now=1763000000,limits={'free':{'index':5}})['usage']['index']['used']==0
    assert manager.reserve_usage(b,'index','5.6.7.8',now=1763000000,limits={'free':{'index':5}},hourly={'index':1})['used']==1

def test_schema_additive(tmp_path):
    a='sqlite:///'+str(tmp_path/'auth.db'); b='sqlite:///'+str(tmp_path/'app.db')
    upgrade_databases(a,b)
    assert migration_status(a,b)['auth']['current']=='auth_0005'
    manager=AuthManager(directory=tmp_path/'private',environ={'REPOLENS_AUTH_DATABASE_URL':a})
    account=manager.upsert_user('github','historic','Historic')
    manager.reserve_usage(account['id'],'ask','127.0.0.1',limits={'free':{'ask':5}},hourly={'ask':10})
    upgrade_databases(a,b)
    assert manager.authenticate(manager.new_session(account['id']))['id']==account['id']

def test_hourly_reset_and_no_raw_ip_in_database(manager):
    user=manager.upsert_user('github','iptest','IP')['id']
    now=1763000000
    manager.reserve_usage(user,'ask','192.0.2.44',now=now,
                          limits={'free':{'ask':4}},hourly={'ask':1})
    with pytest.raises(Exception) as exc:
        manager.reserve_usage(user,'ask','192.0.2.44',now=now,
                              limits={'free':{'ask':4}},hourly={'ask':1})
    assert getattr(exc.value,'status_code',None)==429
    assert manager.reserve_usage(user,'ask','192.0.2.44',now=(now//3600+1)*3600,
                                 limits={'free':{'ask':4}},hourly={'ask':1})['used']==2
    with manager.connect() as conn:
        buckets=conn.execute('SELECT identity_hash,count FROM request_buckets').fetchall()
        events=conn.execute('SELECT action,user_id FROM usage_events').fetchall()
    assert all(len(r['identity_hash'])==64 and '192.0.2.44' not in r['identity_hash'] for r in buckets)
    assert len(events)==2 and all(r['user_id']==user for r in events)


def test_unknown_plan_cannot_increase_free_quota(manager):
    user=manager.upsert_user('github','plan-test','Plan')['id']
    with manager.connect() as db:
        db.execute('INSERT INTO user_plans(user_id,plan) VALUES(?,?)',(user,'enterprise_unverified'))
    assert manager.usage_snapshot(user)['plan']=='free'

def test_legacy_to_sqlalchemy_migration_retains_section4_counters(tmp_path):
    from backend.database.migrate_database import migrate
    folder=tmp_path/'legacy'
    old=AuthManager(directory=folder,environ={})
    user=old.upsert_user('github','migrate-usage','Usage')['id']
    old.reserve_usage(user,'ask','203.0.113.3',now=1763000000,
                      limits={'free':{'ask':5}},hourly={'ask':10})
    destination='sqlite:///'+str(tmp_path/'destination.sqlite3')
    preview=migrate(folder,destination)
    assert preview['counts']['usage_events']==1 and not preview['applied']
    assert migrate(folder,destination,apply=True)['applied']
    new=AuthManager(directory=tmp_path/'new',environ={'REPOLENS_AUTH_DATABASE_URL':destination})
    assert new.usage_snapshot(user,now=1763000000,limits={'free':{'ask':5}})['usage']['ask']['used']==1
