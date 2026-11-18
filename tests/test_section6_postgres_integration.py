"""Opt-in *real PostgreSQL* acceptance test using ONLY a disposable test DB.

Required: REPOLENS_TEST_POSTGRES_URL points to a Neon branch database named
repolens_section6_test. This test never uses REPOLENS_DATABASE_URL.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func, text
import pytest
from backend.database.conversations import metadata
from backend.database import product_store as store


def test_neon_two_simultaneous_redeemers_cannot_join_with_one_invitation():
    url=os.environ.get('REPOLENS_TEST_POSTGRES_URL','')
    if not url:
        pytest.skip('Set REPOLENS_TEST_POSTGRES_URL for disposable Neon test database')
    from sqlalchemy.engine import make_url
    parsed=make_url(url)
    if parsed.drivername != 'postgresql+psycopg' or parsed.database!='repolens_section6_test':
        pytest.fail('Refusing to run: URL must be psycopg PostgreSQL and database repolens_section6_test')
    prod=os.environ.get('REPOLENS_DATABASE_URL','')
    if prod:
        production=make_url(prod)
        if production.host==parsed.host and production.database==parsed.database:
            pytest.fail('Refusing to test against the production database')
    engine=create_engine(url,pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            assert conn.scalar(text('SELECT current_database()'))=='repolens_section6_test'
        metadata.create_all(engine)
        wid=store.workspace(engine,'section6-owner','Concurrent acceptance')
        token=store.invite(engine,wid,'section6-owner')
        def redeem(user):
            try:
                return ('success',store.join(engine,user,token))
            except HTTPException as err:
                return ('denied',err.status_code)
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(redeem,['section6-user-a','section6-user-b']))
        assert sum(result[0]=='success' for result in outcomes)==1,outcomes
        assert sum(result[0]=='denied' for result in outcomes)==1,outcomes
        with engine.connect() as c:
            member_count=c.scalar(select(func.count()).select_from(store.members).where(store.members.c.workspace==wid))
            assert member_count==2  # owner + exactly one invitee
    finally:
        engine.dispose()
