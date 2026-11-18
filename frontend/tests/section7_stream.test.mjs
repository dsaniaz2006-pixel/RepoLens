import test from 'node:test';
import assert from 'node:assert/strict';
import {streamAnalyze,setCSRFToken} from '../src/apiClient.js';

const chunk=(text)=>new TextEncoder().encode(text);
function fakeResponse(parts,{status=200}={}){
  return {ok:status===200,status,body:new ReadableStream({start(controller){for(const part of parts)controller.enqueue(chunk(part));controller.close()}}),
    async text(){return parts.join('')}};
}
test('SSE parser handles split JSON and emits progress before final report',async()=>{
  let seen=[];let init;
  setCSRFToken('csrf-test');
  const orig=globalThis.fetch;
  globalThis.fetch=async(_url,request)=>{
    init=request;
    return fakeResponse(['data: {"status":"progress","message":"Fetching repos','itory"}\n\n:data heartbeat\n\n',
      'data: {"status":"done","result":{"analysis":{"project_summary":"yes"}}}\n\n']);
  };
  try{
    const result=await streamAnalyze('https://github.com/pallets/flask',{onProgress:s=>seen.push(s)});
    assert.equal(result.analysis.project_summary,'yes');
    assert.deepEqual(seen,['Fetching repository']);
    assert.equal(init.method,'POST');
    assert.equal(init.headers['X-CSRF-Token'],'csrf-test');
  }finally{globalThis.fetch=orig}
});

test('missing terminal event fails closed and secret-safe backend errors surface',async()=>{
  const orig=globalThis.fetch;
  try{
    globalThis.fetch=async()=>fakeResponse(['data: {"status":"progress","message":"Working"}\n\n']);
    await assert.rejects(streamAnalyze('https://github.com/a/b'),/disconnected/);
    globalThis.fetch=async()=>fakeResponse(['data: {"status":"error","message":"Unexpected processing error"}\n\n']);
    await assert.rejects(streamAnalyze('https://github.com/a/b'),/Unexpected processing error/);
  }finally{globalThis.fetch=orig}
});

test('rate limit returns normal JSON error before a stream starts',async()=>{
  const orig=globalThis.fetch;
  globalThis.fetch=async()=>({ok:false,status:429,text:async()=>JSON.stringify({detail:'Daily AI usage limit reached'})});
  try{await assert.rejects(streamAnalyze('https://github.com/a/b'),/Daily AI usage limit reached/)}
  finally{globalThis.fetch=orig}
});

test('CRLF delimiter split between transport chunks still parses completed event',async()=>{
 const orig=globalThis.fetch;
 globalThis.fetch=async()=>fakeResponse(['data: {"status":"done","result":{"ok":true}}\r','\n\r','\n']);
 try{assert.deepEqual(await streamAnalyze('https://github.com/pallets/flask'),{ok:true})}
 finally{globalThis.fetch=orig}
});
