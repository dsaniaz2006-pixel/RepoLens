import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
const runner = resolve('scripts/verify_local_https_browser.mjs');
const run=(env)=>spawnSync(process.execPath,[runner],{cwd:process.cwd(),env,encoding:'utf8'});
test('HTTPS runner rejects missing certificate authority without launching Playwright',()=>{
 const dir=mkdtempSync(join(tmpdir(),'rl-ca-fail-'));
 try {
  const bin=join(dir,'bin'); mkdirSync(bin);
  writeFileSync(join(bin,'mkcert'), '#!/bin/sh\nprintf "%s\\n" "$TEST_CAROOT"\n', {mode:0o755});
  const result=run({...process.env,PATH:bin+':'+process.env.PATH,TEST_CAROOT:join(dir,'absent')});
  assert.equal(result.status,1);
  assert.match(result.stderr,/rootCA.pem is missing/);
 } finally {rmSync(dir,{recursive:true,force:true});}
});
test('HTTPS runner provides the mkcert CA to Node TLS without disabling checks',()=>{
 const dir=mkdtempSync(join(tmpdir(),'rl-ca-ok-'));
 try {
  const bin=join(dir,'bin'); mkdirSync(bin); const ca=join(dir,'rootCA.pem');
  writeFileSync(ca,'-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n');
  writeFileSync(join(bin,'mkcert'), '#!/bin/sh\nprintf "%s\\n" "$TEST_CAROOT"\n', {mode:0o755});
  writeFileSync(join(bin,'npx'), '#!/bin/sh\nprintf "%s\\n" "$NODE_EXTRA_CA_CERTS" "$NODE_USE_SYSTEM_CA" "$NODE_TLS_REJECT_UNAUTHORIZED" "$@" > "$TEST_OUT"\n', {mode:0o755});
  const output=join(dir,'out.txt');
  const result=run({...process.env,PATH:bin+':'+process.env.PATH,TEST_CAROOT:dir,TEST_OUT:output,NODE_TLS_REJECT_UNAUTHORIZED:'0'});
  assert.equal(result.status,0,result.stderr);
  const lines=readFileSync(output,'utf8').trim().split('\n');
  assert.equal(lines[0],ca);
  assert.equal(lines[1],'1');
  assert.equal(lines[2],'');
  assert.equal(lines[3],'playwright');
  assert.ok(lines.includes('--config=playwright.https.config.js'));
 } finally {rmSync(dir,{recursive:true,force:true});}
});
