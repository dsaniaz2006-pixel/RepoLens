#!/usr/bin/env node
/** Verify the active RepoLens site and API through the local trusted TLS proxy. */
import {spawnSync} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {dirname,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {get} from 'node:https';
import {readSettings,validateLocalCertificates} from '../launcher_utils.mjs';

const root=dirname(dirname(fileURLToPath(import.meta.url)));
validateLocalCertificates(root);
const config=readSettings(root,process.env,['--https']);
const caResult=spawnSync('mkcert',['-CAROOT'],{encoding:'utf8'});
if(caResult.status!==0||!caResult.stdout.trim())throw new Error('mkcert root CA not found. Run setup first.');
const ca=readFileSync(join(caResult.stdout.trim(),'rootCA.pem'));
function request(path){
 return new Promise((resolve,reject)=>{
  const req=get(config.origin+path,{ca,timeout:8000},res=>{
   let body='';res.setEncoding('utf8');res.on('data',chunk=>{body+=chunk.slice(0,10000)});
   res.on('end',()=>resolve({status:res.statusCode,body,encrypted:res.socket.encrypted,authorizationError:res.socket.authorizationError}));
  });
  req.on('timeout',()=>req.destroy(new Error('HTTPS request timed out')));
  req.on('error',reject);
 });
}
try {
 const health=await request('/api/health');
 if(!health.encrypted||health.authorizationError||health.status!==200||JSON.parse(health.body).status!=='ok')throw new Error('HTTPS API proxy health check failed');
 const providers=await request('/api/auth/providers');
 if(providers.status!==200||typeof JSON.parse(providers.body).providers!=='object')throw new Error('HTTPS OAuth provider API check failed');
 const landing=await request('/');
 if(landing.status!==200||!landing.body.includes('<html'))throw new Error('HTTPS landing page check failed');
 const login=await request('/login/');
 if(login.status!==200||!login.body.includes('<html'))throw new Error('HTTPS login page check failed');
 console.log('PASS: TLS certificate verified against mkcert root CA.');
 console.log('PASS: HTTPS landing page and login page.');
 console.log('PASS: HTTPS /api/health and /api/auth/providers through same-origin proxy.');
 console.log('Verified: '+config.origin);
} catch(error) {
 console.error('HTTPS verification failed:',error.message);
 console.error('Confirm node start.mjs --https is running and the mkcert root CA is installed.');
 process.exitCode=1;
}
