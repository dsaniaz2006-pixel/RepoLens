/** Wake the public FastAPI health endpoint through the existing same-origin /api proxy.
 * All retries are GETs; never replay a mutation or an OAuth request.
 * This handles Render Free cold starts; it does not prevent Render from sleeping.
 */
const cancelled = () => new DOMException('Connection check cancelled.', 'AbortError');

function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(cancelled());
    let timer;
    const cleanup = () => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', stop);
    };
    const stop = () => { cleanup(); reject(cancelled()); };
    timer = setTimeout(() => { cleanup(); resolve(); }, ms);
    signal?.addEventListener('abort', stop, {once: true});
  });
}

export async function waitForBackend({
  signal,
  onProgress = () => {},
  maxWaitMs = 110000,
  attemptTimeoutMs = 20000,
  retryDelayMs = 2500,
} = {}) {
  const deadline = Date.now() + maxWaitMs;
  let attempt = 0;
  while (Date.now() < deadline) {
    if (signal?.aborted) throw cancelled();
    onProgress({attempt: ++attempt});
    const controller = new AbortController();
    const forwardAbort = () => controller.abort();
    signal?.addEventListener('abort', forwardAbort, {once: true});
    if (signal?.aborted) controller.abort();
    const perAttempt = Math.min(attemptTimeoutMs, Math.max(1, deadline - Date.now()));
    const timer = setTimeout(() => controller.abort(), perAttempt);
    try {
      const response = await fetch('/api/health', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: {Accept: 'application/json'},
        signal: controller.signal,
      });
      if (response.ok) {
        // Reject a 200 HTML proxy/loading page; require the actual FastAPI payload.
        const payload = await response.json().catch(() => null);
        if (payload?.status === 'ok') return true;
      }
    } catch (error) {
      if (signal?.aborted) throw cancelled();
      // A timeout, transient network failure, or gateway 5xx is retried below.
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', forwardAbort);
    }
    const remaining = deadline - Date.now();
    if (remaining > 0) await delay(Math.min(retryDelayMs, remaining), signal);
  }
  throw new Error('RepoLens server did not become ready. Try again or check your Render service logs.');
}
