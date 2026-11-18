import test from 'node:test';
import assert from 'node:assert/strict';
import {workspaceMockResponse, mockAuthenticatedWorkspace, DEFAULT_WORKSPACE_USAGE} from '../e2e/helpers/mockAuthenticatedWorkspace.mjs';

test('workspace E2E mocks every authenticated initial page fetch', () => {
  for (const endpoint of ['/api/auth/me', '/api/history', '/api/usage', '/api/config-status',
      '/api/repositories', '/api/workspaces', '/api/insights/security', '/api/auth/keys', '/api/auth/sessions', '/api/auth/audit']) {
    const result=workspaceMockResponse(endpoint);
    assert.ok(result, `missing ${endpoint}`);
    assert.equal(result.status, 200);
  }
  assert.equal(DEFAULT_WORKSPACE_USAGE.usage.index.limit, 2);
});

test('workspace mocks do not fabricate untested APIs or weaken auth', () => {
  assert.equal(workspaceMockResponse('/api/ask'), null);
  assert.equal(workspaceMockResponse('/api/any-sensitive-endpoint'), null);
  assert.equal(workspaceMockResponse('/api/auth/me', {user:{id:'bob'},csrfToken:'csrf2'}).json.user.id, 'bob');
});

test('workspace E2E fallback prevents accidental real-server 401 redirects', async () => {
  let handler;
  const page={route: async (_pattern, callback) => {handler=callback;}};
  const unexpected=await mockAuthenticatedWorkspace(page);
  const call=async(path, method='GET')=>{
    let result;
    await handler({request:()=>({url:()=>`http://127.0.0.1:5175${path}`,method:()=>method}),
      fulfill:async options=>{result=options;}});
    return result;
  };
  const me=await call('/api/auth/me');
  assert.equal(me.status,200);
  assert.ok(me.json.csrf_token);
  assert.equal((await call('/api/usage')).status,200);
  const unknown=await call('/api/unknown');
  assert.equal(unknown.status,501);
  assert.match(unknown.json.detail,/Unmocked workspace test request/);
  assert.deepEqual(unexpected,['GET /api/unknown']);
});
