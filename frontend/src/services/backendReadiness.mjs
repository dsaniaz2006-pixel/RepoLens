/**
 * Detect a sleeping API before login/session requests start.
 * Uses the existing same-origin /api/health Vercel rewrite (no CORS or secrets).
 * Render Free can still spin down; this merely handles its cold start gracefully.
 */
export class BackendUnavailableError extends Error {
  constructor(message, {permanent=false}={}) {
    super(message);
    this.name='BackendUnavailableError';
    this.permanent=permanent;
  }
}

function aborted() {
  const error=new Error('Connection check cancelled.');
  error.name='AbortError';
  return error;
}

function sleep(ms,signal) {
  if(signal?.aborted)return Promise.reject(aborted());
  return new Promise((resolve,reject)=>{
    let timer;
    const cancel=()=>{
      clearTimeout(timer);
      signal?.removeEventListener('abort',cancel);
      reject(aborted());
    };
    timer=setTimeout(()=>{
      signal?.removeEventListener('abort',cancel);
      resolve();
    },ms);
    signal?.addEventListener('abort',cancel,{once:true});
  });
}

async function probe(endpoint,timeoutMs,signal,fetchImpl) {
  const controller=new AbortController();
  const onAbort=()=>controller.abort();
  signal?.addEventListener('abort',onAbort,{once:true});
  if(signal?.aborted)controller.abort();
  const timer=setTimeout(()=>controller.abort(),timeoutMs);
  try {
    const response=await fetchImpl(endpoint,{
      method:'GET',
      credentials:'same-origin',
      cache:'no-store',
      signal:controller.signal,
      headers:{Accept:'application/json'},
    });
    if(!response.ok){
      const permanent=response.status>=400&&response.status<500
        &&response.status!==408&&response.status!==429;
      throw new BackendUnavailableError(
        `Health check returned HTTP ${response.status}.`,
        {permanent}
      );
    }
    // A 200 from a fallback HTML page is not evidence the Python API is running.
    let body;
    try {body=await response.json();}
    catch {
      throw new BackendUnavailableError('Health check did not return JSON.',{permanent:true});
    }
    if(body?.status!=='ok'){
      throw new BackendUnavailableError('Unexpected health check response.',{permanent:true});
    }
    return true;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort',onAbort);
  }
}

/**
 * Try for at most maxWaitMs including network and pauses.
 * onStatus receives "checking", "waking", or "ready".
 * Deliberately never retries a POST or authenticated mutation.
 */
export async function waitForBackendReady({
  endpoint='/api/health',
  signal,
  onStatus=()=>{},
  fetchImpl=globalThis.fetch,
  maxWaitMs=120000,
  requestTimeoutMs=12000,
  retryDelayMs=3500,
}={}){
  if(typeof fetchImpl!=='function')throw new Error('Fetch is unavailable.');
  if(signal?.aborted)throw aborted();
  const deadline=Date.now()+maxWaitMs;
  let lastError;
  onStatus('checking');
  while(Date.now()<deadline){
    if(signal?.aborted)throw aborted();
    const remaining=deadline-Date.now();
    try {
      await probe(endpoint,Math.max(1,Math.min(requestTimeoutMs,remaining)),signal,fetchImpl);
      if(signal?.aborted)throw aborted();
      onStatus('ready');
      return true;
    }catch(error){
      if(signal?.aborted)throw aborted();
      if(error instanceof BackendUnavailableError&&error.permanent){
        throw error;
      }
      lastError=error;
      onStatus('waking');
    }
    const rest=deadline-Date.now();
    if(rest<=0)break;
    await sleep(Math.min(retryDelayMs,rest),signal);
  }
  throw new BackendUnavailableError(
    'RepoLens could not connect to its backend. The server may still be starting, or the service may be unavailable. Select Retry connection.',
    {cause:lastError}
  );
}
