"""Failure-first contract for Section 4 rate/usage policy."""
from backend.security.usage_limits import action_for_request, PLAN_LIMITS, HOURLY_LIMITS

def test_expensive_request_route_mapping():
    assert action_for_request('POST','/api/analyze')=='analyze'
    assert action_for_request('POST','/api/ask')=='ask'
    assert action_for_request('POST','/api/index/jobs')=='index'
    assert action_for_request('GET','/api/usage') is None
    assert action_for_request('POST','/api/auth/keys') is None

def test_daily_limits():
    assert PLAN_LIMITS['free']=={'analyze':5,'ask':20,'index':2}
    assert HOURLY_LIMITS['analyze']==10
