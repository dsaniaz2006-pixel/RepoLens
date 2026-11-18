import {serverErrorMessage} from './errors.mjs';
let csrfToken = '';
export function setCSRFToken(value) { csrfToken = value || ''; }
// One place for API response handling: Vite proxies /api to the Python server.
export async function readJSON(response) {
  const raw = await response.text();
  let data;
  try { data = raw.trim() ? JSON.parse(raw) : null; }
  catch { data = null; }

  if (!response.ok) {
    if (response.status === 401 && typeof window !== 'undefined') {
      window.location.replace('/login/?reason=expired');
    }
    throw new Error(serverErrorMessage(response.status, raw, data?.detail));
  }
  if (data === null) {
    throw new Error('API returned an empty or invalid JSON response. Check the FastAPI terminal and ' +
      'Chrome DevTools → Network for the failed request (especially proxy failures or server restarts).');
  }
  return data;
}
// Bound the complete request, including reading the response body.
async function request(url, init={}, {signal, timeoutMs=30000, blob=false}={}) {
  const controller = new AbortController();
  const abort = ()=>controller.abort();
  if(signal?.aborted) controller.abort();
  signal?.addEventListener('abort',abort,{once:true});
  let timedOut=false;
  const timer=setTimeout(()=>{timedOut=true;controller.abort()},timeoutMs);
  try {
    const response=await fetch(url,{credentials:'same-origin',cache:'no-store',...init,signal:controller.signal});
    if(blob && response.ok) return await response.blob();
    return await readJSON(response);
  } catch(err) {
    if(timedOut) throw new Error('The request timed out. Check server connectivity and provider quota, then retry. A running server operation may still finish.');
    if(signal?.aborted) throw new Error('Request cancelled.');
    if(err instanceof TypeError) throw new Error('Cannot contact RepoLens API. Ensure FastAPI is running. '+err.message);
    throw err;
  } finally {clearTimeout(timer);signal?.removeEventListener('abort',abort)}
}
export async function postJSON(url, payload, options={}) {
  return request(url,{method:'POST',headers:{'Content-Type':'application/json',...(csrfToken?{'X-CSRF-Token':csrfToken}:{})},body:JSON.stringify(payload)}, {timeoutMs:300000,...options});
}
export async function getJSON(url, options={}) { return request(url,{},options); }
export async function downloadReport(url, filename, options={}) {
  const data=await request(url,{}, {...options,blob:true});
  const link=document.createElement('a'), objectURL=URL.createObjectURL(data);
  link.href=objectURL;link.download=filename;document.body.append(link);link.click();link.remove();
  setTimeout(()=>URL.revokeObjectURL(objectURL),1000);
}
export async function runIndexJob(url, {signal,onProgress=()=>{},pollMs=1000}={}) {
  // Always obtain the job ID before honouring cancellation so the server job
  // cannot be orphaned by an abort during the initial POST.
  let job=await postJSON('/api/index/jobs',{url},{timeoutMs:30000});
  const end=Date.now()+16*60*1000;
  try {
    while(true) {
      if(signal?.aborted) throw new Error('Index cancellation requested. Completed batches are saved for retry.');
      onProgress(job.message);
      if(job.state==='completed') return job.result;
      if(job.state==='failed'||job.state==='cancelled') throw new Error(job.error||job.message);
      if(Date.now()>end) throw new Error('Index exceeded the waiting limit. Check provider quota and retry to resume saved batches.');
      await new Promise(resolve=>setTimeout(resolve,pollMs));
      job=await getJSON('/api/jobs/'+job.id,{signal});
    }
  } catch(error) {
    if(signal?.aborted||Date.now()>end) {
      try {await postJSON('/api/jobs/'+job.id+'/cancel',{}, {timeoutMs:10000})}
      catch {throw new Error('Unable to confirm cancellation. The index may still be running. Reconnect and click Build / Refresh to check it.');}
      throw new Error('Index cancellation requested. The current network request may take up to 60 seconds to finish; completed batches are saved for retry.');
    }
    throw error;
  }
}

export async function deleteJSON(url) { return request(url,{method:"DELETE",headers:{"X-CSRF-Token":csrfToken}}); }

// Read POST SSE streams incrementally; events may be split across TCP chunks.
// A new analysis counts against the same daily quota as legacy /api/analyze.
export async function streamAnalyze(url, {signal, onProgress=()=>{}}={}) {
  let response;
  try {
    response = await fetch('/api/analyze/stream', {
      method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: {'Content-Type':'application/json',...(csrfToken?{'X-CSRF-Token':csrfToken}:{})},
      body: JSON.stringify({url}), signal,
    });
  } catch (error) {
    if (signal?.aborted) throw new Error('Analysis stream cancelled.');
    if (error instanceof TypeError) throw new Error('Cannot contact RepoLens API. Ensure FastAPI is running. '+error.message);
    throw error;
  }
  if (!response.ok) return readJSON(response); // parses 401, 429, 422, 503
  if (!response.body) throw new Error('Analysis streaming is unavailable in this browser.');
  const reader=response.body.getReader();
  const decoder=new TextDecoder();
  let pending='', result=null, terminal=false;
  const handle = (block) => {
    const line=block.split('\n').find(line=>line.startsWith('data:'));
    if(!line)return;
    let event;
    try {event=JSON.parse(line.slice(5).trim())}
    catch {throw new Error('Malformed analysis progress event. Inspect the API server.')}
    if(event.status==='progress')onProgress(event.message||'Processing repository…');
    if(event.status==='error')throw new Error(event.message||'Analysis failed.');
    if(event.status==='done') {result=event.result;terminal=true;}
  };
  try {
    while(!terminal){
      const {value,done}=await reader.read();
      if(done)break;
      pending=(pending+decoder.decode(value,{stream:true})).replace(/\r\n/g,'\n');
      if(pending.length>8*1024*1024)throw new Error('Unexpectedly large progress event.');
      let end;
      while((end=pending.indexOf('\n\n'))!==-1){
        const block=pending.slice(0,end);pending=pending.slice(end+2);
        handle(block);
        if(terminal)break;
      }
    }
    if(!terminal)throw new Error('Analysis stream disconnected before a complete report was returned. Retry to analyze again.');
    return result;
  } catch(error){
    if(signal?.aborted)throw new Error('Analysis stream cancelled. An in-flight provider call may finish before server work stops.');
    throw error;
  } finally {await reader.cancel().catch(()=>{});reader.releaseLock();}
}
