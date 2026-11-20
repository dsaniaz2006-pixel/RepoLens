import {test} from 'node:test';
import assert from 'node:assert/strict';
import {waitForBackend} from '../src/services/backendWake.mjs';

test('healthy API returns without retrying', async () => {
  const oldFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url, options) => {
    urls.push(url);
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.method, 'GET');
    return new Response('{"status":"ok"}', {status: 200});
  };
  try {
    assert.equal(await waitForBackend({maxWaitMs: 500}), true);
    assert.deepEqual(urls, ['/api/health']);
  } finally {globalThis.fetch = oldFetch;}
});

test('transient gateway and HTML page are retried until FastAPI is ready', async () => {
  const oldFetch = globalThis.fetch;
  let count = 0;
  globalThis.fetch = async () => {
    count++;
    if (count === 1) return new Response('Bad Gateway', {status: 502});
    if (count === 2) return new Response('<html>Loading</html>', {status: 200});
    return new Response('{"status":"ok"}', {status: 200});
  };
  try {
    assert.equal(await waitForBackend({maxWaitMs: 500, retryDelayMs: 1}), true);
    assert.equal(count, 3);
  } finally {globalThis.fetch = oldFetch;}
});

test('an aborted wake-up check stops immediately', async () => {
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(waitForBackend({signal: controller.signal}), {name: 'AbortError'});
});

test('unresponsive service fails with a bounded, useful error', async () => {
  const oldFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response('unavailable', {status: 503});
  try {
    await assert.rejects(
      waitForBackend({maxWaitMs: 30, retryDelayMs: 2}),
      /did not become ready/
    );
  } finally {globalThis.fetch = oldFetch;}
});
