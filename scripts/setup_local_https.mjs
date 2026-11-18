#!/usr/bin/env node
/** macOS/Windows/Linux local HTTPS setup. Never bundles a private key in a ZIP. */
import {spawnSync} from 'node:child_process';
import {chmodSync,existsSync,mkdirSync,readFileSync,renameSync,statSync,writeFileSync} from 'node:fs';
import {dirname,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {localCertPaths,validateLocalCertificates} from '../launcher_utils.mjs';

const root=dirname(dirname(fileURLToPath(import.meta.url)));
const result=spawnSync('mkcert',['-version'],{stdio:'pipe',encoding:'utf8'});
if(result.error||result.status!==0){
 console.error('mkcert is required. On macOS: brew install mkcert  (then rerun this command).');
 process.exit(1);
}
const install=spawnSync('mkcert',['-install'],{stdio:'inherit'});
if(install.status!==0){console.error('Unable to install the local CA. Do not bypass browser certificate warnings.');process.exit(1)}
const paths=localCertPaths(root);
mkdirSync(dirname(paths.cert),{recursive:true,mode:0o700});
const create=spawnSync('mkcert',['-cert-file',paths.cert,'-key-file',paths.key,'localhost','127.0.0.1','::1'],{stdio:'inherit'});
if(create.status!==0){console.error('mkcert could not create local HTTPS certificates.');process.exit(1)}
chmodSync(paths.key,0o600);
validateLocalCertificates(root);

// Update only the public scheme in the local, gitignored .env. Preserve
// the user's API keys, database connections, and OAuth provider credentials.
const envPath=join(root,'.env');
if(existsSync(envPath)){
 const content=readFileSync(envPath,'utf8');
 let changed=false;
 const next=content.replace(/^(\s*(?:export\s+)?REPOLENS_BASE_URL\s*=\s*)([^\r\n]*)(\r?)$/gm,(_line,prefix,value,cr)=>{
  let url;
  try {url=new URL(value.trim().replace(/\s+#.*$/,'').replace(/^['"]|['"]$/g,''))}
  catch {throw new Error('Invalid REPOLENS_BASE_URL in .env. Use http://127.0.0.1:5173');}
  if(!['127.0.0.1','localhost'].includes(url.hostname)||!['http:','https:'].includes(url.protocol)||url.pathname!=='/'||url.search||url.hash||url.username||url.password)throw new Error('Local HTTPS must use a local origin with no path or credentials');
  url.protocol='https:';
  changed=true;
  return prefix+url.origin+cr;
 });
 const updated=changed?next:content.replace(/\s*$/,'\n')+'REPOLENS_BASE_URL=https://127.0.0.1:5173\n';
 // Avoid a second copy of user secrets; write only a temporary file, then rename.
 const tmp=envPath+'.https.tmp';
 const mode=statSync(envPath).mode&0o777;
 try{writeFileSync(tmp,updated,{mode:mode&0o600});chmodSync(tmp,mode&0o600);renameSync(tmp,envPath)}
 catch(error){console.error('Could not update .env. Review REPOLENS_BASE_URL manually.');process.exit(1)}
 console.log('Updated only REPOLENS_BASE_URL in your private .env. No credentials were printed.');
}else{
 console.log('No .env yet: copy your existing private .env into RepoLens before starting.');
 console.log('Then set REPOLENS_BASE_URL=https://127.0.0.1:5173 or use node start.mjs --https.');
}
console.log('Trusted local HTTPS certificates created in .certs (not distributed or committed).');
console.log('Start: node start.mjs --https');
console.log('Open:  https://127.0.0.1:5173/');
console.log('OAuth callback paths: /api/auth/callback/google and /api/auth/callback/github');
