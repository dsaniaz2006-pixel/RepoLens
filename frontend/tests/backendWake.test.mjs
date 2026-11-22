import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  ensureBackendReady,
  waitForBackend,
  resetBackendReadinessForTests,
} from '../src/services/backendWake.mjs';

test('healthy API returns without retrying', async () => {
  resetBackendReadinessForTests();
  const urls = [];
  const fetchImpl = async (url, options) => {
    urls.push(url);
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.method, 'GET');
    return new Response('{"status":"ok"}', { status: 200 });
  };

  assert.equal(await waitForBackend({ maxWaitMs: 500, fetchImpl }), true);
  assert.deepEqual(urls, ['/api/health']);
});

test('transient gateway and HTML page are retried until FastAPI is ready', async () => {
  resetBackendReadinessForTests();
  let count = 0;
  const fetchImpl = async () => {
    count++;
    if (count === 1) return new Response('Bad Gateway', { status: 502 });
    if (count === 2) return new Response('<html>Loading</html>', { status: 200 });
    return new Response('{"status":"ok"}', { status: 200 });
  };

  assert.equal(await waitForBackend({ maxWaitMs: 500, retryDelayMs: 1, fetchImpl }), true);
  assert.equal(count, 3);
});

test('successful readiness is cached for the configured interval', async () => {
  resetBackendReadinessForTests();
  let count = 0;
  const fetchImpl = async () => {
    count++;
    return new Response('{"status":"ok"}', { status: 200 });
  };

  await ensureBackendReady({ fetchImpl, cacheMs: 1000 });
  await ensureBackendReady({ fetchImpl, cacheMs: 1000 });
  assert.equal(count, 1);
});

test('expired readiness cache triggers a new health check', async () => {
  resetBackendReadinessForTests();
  let count = 0;
  const fetchImpl = async () => {
    count++;
    return new Response('{"status":"ok"}', { status: 200 });
  };

  await ensureBackendReady({ fetchImpl, cacheMs: 0 });
  await ensureBackendReady({ fetchImpl, cacheMs: 0 });
  assert.equal(count, 2);
});

test('concurrent callers share one health-check operation', async () => {
  resetBackendReadinessForTests();
  let count = 0;
  const fetchImpl = async () => {
    count++;
    await new Promise(resolve => setTimeout(resolve, 15));
    return new Response('{"status":"ok"}', { status: 200 });
  };

  const results = await Promise.all([
    ensureBackendReady({ fetchImpl }),
    ensureBackendReady({ fetchImpl }),
    ensureBackendReady({ fetchImpl }),
  ]);
  assert.deepEqual(results, [true, true, true]);
  assert.equal(count, 1);
});

test('an already-aborted caller stops immediately', async () => {
  resetBackendReadinessForTests();
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    ensureBackendReady({ signal: controller.signal }),
    { name: 'AbortError' }
  );
});

test('one caller can cancel its wait without cancelling another caller', async () => {
  resetBackendReadinessForTests();
  let count = 0;
  const fetchImpl = async () => {
    count++;
    await new Promise(resolve => setTimeout(resolve, 20));
    return new Response('{"status":"ok"}', { status: 200 });
  };
  const controller = new AbortController();
  const cancelledWait = ensureBackendReady({ fetchImpl, signal: controller.signal });
  const otherWait = ensureBackendReady({ fetchImpl });
  controller.abort();

  await assert.rejects(cancelledWait, { name: 'AbortError' });
  assert.equal(await otherWait, true);
  assert.equal(count, 1);
});

test('unresponsive service fails with a bounded, useful error', async () => {
  resetBackendReadinessForTests();
  const fetchImpl = async () => new Response('unavailable', { status: 503 });
  await assert.rejects(
    ensureBackendReady({ maxWaitMs: 30, retryDelayMs: 2, fetchImpl }),
    /did not become ready/
  );
});

test('permanent client errors fail immediately instead of retrying', async () => {
  resetBackendReadinessForTests();
  let count = 0;
  const fetchImpl = async () => {
    count++;
    return new Response('Not found', { status: 404 });
  };
  await assert.rejects(
    ensureBackendReady({ maxWaitMs: 500, fetchImpl }),
    /HTTP 404/
  );
  assert.equal(count, 1);
});
