/**
 * Single source of truth for waking the RepoLens API.
 * A health GET may be retried; application requests are never replayed.
 */
const READY_CACHE_MS = 15000;
let readyUntil = 0;
let readinessPromise = null;

const cancelled = () => {
  const error = new Error('Connection check cancelled.');
  error.name = 'AbortError';
  return error;
};

function waitWithSignal(promise, signal) {
  if (!signal) return promise;
  if (signal.aborted) return Promise.reject(cancelled());
  return new Promise((resolve, reject) => {
    const onAbort = () => {
      signal.removeEventListener('abort', onAbort);
      reject(cancelled());
    };
    signal.addEventListener('abort', onAbort, { once: true });
    promise.then(
      value => {
        signal.removeEventListener('abort', onAbort);
        resolve(value);
      },
      error => {
        signal.removeEventListener('abort', onAbort);
        reject(error);
      }
    );
  });
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function probeUntilReady({
  endpoint,
  onProgress,
  maxWaitMs,
  attemptTimeoutMs,
  retryDelayMs,
  fetchImpl,
}) {
  const deadline = Date.now() + maxWaitMs;
  let attempt = 0;
  let lastStatus = null;

  while (Date.now() < deadline) {
    onProgress({ attempt: ++attempt });
    const remaining = deadline - Date.now();
    const controller = new AbortController();
    const timeout = setTimeout(
      () => controller.abort(),
      Math.max(1, Math.min(attemptTimeoutMs, remaining))
    );

    try {
      const response = await fetchImpl(endpoint, {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
      lastStatus = response.status;

      if (response.ok) {
        const payload = await response.json().catch(() => null);
        if (payload?.status === 'ok') {
          onProgress({ attempt, ready: true });
          return true;
        }
      } else if (
        response.status >= 400 &&
        response.status < 500 &&
        response.status !== 408 &&
        response.status !== 429
      ) {
        throw new Error(`Backend health check returned HTTP ${response.status}.`);
      }
    } catch (error) {
      if (error?.message?.startsWith('Backend health check returned')) throw error;
      // Timeouts, network errors, gateway errors, 429 and non-JSON pages
      // are transient during a cold start and are retried below.
    } finally {
      clearTimeout(timeout);
    }

    const rest = deadline - Date.now();
    if (rest > 0) await delay(Math.min(retryDelayMs, rest));
  }

  const suffix = lastStatus ? ` Last health-check status: HTTP ${lastStatus}.` : '';
  throw new Error(
    `RepoLens server did not become ready within ${maxWaitMs} ms.${suffix} Check the Render service logs and try again.`
  );
}

/**
 * Shared readiness coordinator:
 * - coalesces simultaneous health checks into one request sequence;
 * - caches a successful result briefly to avoid pinging on every poll;
 * - each caller can cancel its own wait without cancelling other callers;
 * - only the safe GET /api/health is retried.
 */
export async function ensureBackendReady({
  endpoint = '/api/health',
  signal,
  onProgress = () => {},
  maxWaitMs = 30000,
  attemptTimeoutMs = 20000,
  retryDelayMs = 2500,
  cacheMs = READY_CACHE_MS,
  fetchImpl = globalThis.fetch,
} = {}) {
  if (signal?.aborted) throw cancelled();
  if (typeof fetchImpl !== 'function') throw new Error('Fetch is unavailable.');

  if (Date.now() < readyUntil) {
    onProgress({ attempt: 0, ready: true, cached: true });
    return true;
  }

  if (!readinessPromise) {
    const operation = probeUntilReady({
      endpoint, onProgress, maxWaitMs, attemptTimeoutMs, retryDelayMs, fetchImpl,
    }).then(result => {
      readyUntil = Date.now() + cacheMs;
      return result;
    });

    readinessPromise = operation.finally(() => {
      if (readinessPromise === wrapped) readinessPromise = null;
    });
    const wrapped = readinessPromise;
  }

  return waitWithSignal(readinessPromise, signal);
}

/** Backwards-compatible name used by the app's startup and sign-up screens. */
export function waitForBackend(options = {}) {
  return ensureBackendReady({
    ...options,
    onProgress: options.onProgress || (() => {}),
  });
}

/** Isolated test hook; does not affect production behaviour. */
export function resetBackendReadinessForTests() {
  readyUntil = 0;
  readinessPromise = null;
}
