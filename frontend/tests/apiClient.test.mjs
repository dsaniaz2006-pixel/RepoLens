import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readJSON, postJSON, getJSON, setCSRFToken } from '../src/apiClient.js';

test('returns a valid success JSON response', async () => {
  assert.deepEqual(await readJSON(new Response('{"status":"ok"}',{status:200})),{status:'ok'});
});
test('reports an empty server response clearly', async () => {
  await assert.rejects(readJSON(new Response('',{status:500})),/HTTP 500.*empty response/);
});
test('uses server error detail when available', async () => {
  await assert.rejects(readJSON(new Response('{"detail":"No Gemini access"}',{status:400})),/No Gemini access/);
});
test('reports a success response with invalid JSON', async () => {
  await assert.rejects(readJSON(new Response('not json',{status:200})),/invalid JSON response/);
});
test('postJSON sends the expected request body', async () => {
  const previous=globalThis.fetch;
  globalThis.fetch=async (url,init) => {
    assert.equal(url,'/api/analyze');
    assert.equal(init.method,'POST');
    assert.equal(JSON.parse(init.body).url,'https://github.com/pallets/flask');
    return new Response('{"status":"ok"}');
  };
  try { assert.equal((await postJSON('/api/analyze',{url:'https://github.com/pallets/flask'})).status,'ok'); }
  finally { globalThis.fetch=previous; }
});
test('getJSON surfaces connection failures',async()=>{
  const previous=globalThis.fetch;
  globalThis.fetch=async()=>{throw new Error('connection refused');};
  try {await assert.rejects(getJSON('/api/history'),/connection refused/);}
  finally {globalThis.fetch=previous;}
});

test('authenticated mutations include CSRF token and same-origin cookies', async()=>{
 const previous=globalThis.fetch;
 setCSRFToken('server-issued-token');
 globalThis.fetch=async(url,init)=>{
  assert.equal(init.headers['X-CSRF-Token'],'server-issued-token');
  assert.equal(init.credentials,'same-origin');
  return new Response('{"ok":true}');
 };
 try{assert.deepEqual(await postJSON('/api/auth/logout',{}),{ok:true})}
 finally{globalThis.fetch=previous;setCSRFToken('')}
});
test('expired sessions send the user back to login',async()=>{
 const previous=globalThis.window;let destination;
 globalThis.window={location:{replace:value=>{destination=value}}};
 try{
  await assert.rejects(readJSON(new Response('{"detail":"Sign in to continue."}',{status:401})),/Sign in/);
  assert.equal(destination,'/login/?reason=expired');
 }finally{if(previous===undefined)delete globalThis.window;else globalThis.window=previous}
});

test('network timeout releases request with actionable message',async()=>{
 const previous=globalThis.fetch;
 globalThis.fetch=async(_,init)=>new Promise((_,reject)=>init.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))));
 try{await assert.rejects(getJSON('/api/history',{timeoutMs:5}),/timed out/)}finally{globalThis.fetch=previous}
});
test('index job polls progress and returns completed result',async()=>{
 const {runIndexJob}=await import('../src/apiClient.js');const previous=globalThis.fetch;let calls=0;const progress=[];
 globalThis.fetch=async()=>new Response(JSON.stringify(++calls===1?{id:'j',state:'running',message:'Fetching source'}:{id:'j',state:'completed',message:'Ready',result:{chunks:42}}));
 try{assert.deepEqual(await runIndexJob('https://github.com/a/b',{pollMs:0,onProgress:v=>progress.push(v)}),{chunks:42});assert.deepEqual(progress,['Fetching source','Ready'])}finally{globalThis.fetch=previous}
});
test('index failure is visible and polling stops',async()=>{
 const {runIndexJob}=await import('../src/apiClient.js');const previous=globalThis.fetch;
 globalThis.fetch=async()=>new Response(JSON.stringify({id:'j',state:'failed',error:'Gemini quota exceeded'}));
 try{await assert.rejects(runIndexJob('https://github.com/a/b'),/quota exceeded/)}finally{globalThis.fetch=previous}
});
test('index abort requests server cancellation',async()=>{
 const {runIndexJob}=await import('../src/apiClient.js');const previous=globalThis.fetch;const urls=[];const controller=new AbortController();controller.abort();
 globalThis.fetch=async(url)=>{urls.push(url);return new Response(JSON.stringify({id:'j',state:'running'}))};
 try{await assert.rejects(runIndexJob('https://github.com/a/b',{signal:controller.signal}),/cancellation requested/);assert.deepEqual(urls,['/api/index/jobs','/api/jobs/j/cancel'])}finally{globalThis.fetch=previous}
});
