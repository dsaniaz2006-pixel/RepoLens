import { test } from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync,mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {readSettings,validateLocalCertificates} from '../../launcher_utils.mjs';

test('TDD: HTTPS launch upgrades an existing HTTP OAuth origin safely',()=>{
  const root=mkdtempSync(join(tmpdir(),'repolens-https-'));
  try {
    writeFileSync(join(root,'.env'),'REPOLENS_BASE_URL=http://127.0.0.1:5173\nREPOLENS_FRONTEND_PORT=5173\nGEMINI_API_KEY=secret-do-not-log\n');
    const settings=readSettings(root,{},['--https','--backend-port','8001']);
    assert.equal(settings.origin,'https://127.0.0.1:5173');
    assert.equal(settings.https,true);
    assert.equal(settings.backendPort,8001);
    assert.equal(settings.frontendPort,5173);
    assert.equal(JSON.stringify(settings).includes('secret-do-not-log'),false);
  } finally {rmSync(root,{recursive:true,force:true})}
});

test('TDD: HTTPS .env is auto-detected and can be explicitly switched back to HTTP',()=>{
  const root=mkdtempSync(join(tmpdir(),'repolens-https-env-'));
  try {
    writeFileSync(join(root,'.env'),'REPOLENS_BASE_URL=https://localhost:5173\n');
    assert.equal(readSettings(root,{},[]).https,true);
    assert.equal(readSettings(root,{},['--http']).origin,'http://localhost:5173');
  } finally {rmSync(root,{recursive:true,force:true})}
});

test('TDD: reject public HTTP/HTTPS origins, URL paths and HTTPS without certs',()=>{
  assert.throws(()=>readSettings('/missing',{REPOLENS_BASE_URL:'https://example.com:5173'},[]),/local/i);
  assert.throws(()=>readSettings('/missing',{REPOLENS_BASE_URL:'https://127.0.0.1:5173/evil'},[]),/origin|local/i);
  assert.throws(()=>validateLocalCertificates('/missing'),/mkcert|certificate|HTTPS/i);
});

test('TDD: certificate and private key must match and include both loopback names',t=>{
  const root=mkdtempSync(join(tmpdir(),'repolens-cert-'));
  try {
    mkdirSync(join(root,'.certs'),{recursive:true});
    const args=['req','-x509','-newkey','rsa:2048','-nodes','-keyout',join(root,'.certs','localhost-key.pem'),'-out',join(root,'.certs','localhost.pem'),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1,IP:::1'];
    const result=spawnSync('openssl',args,{encoding:'utf8'});
    if(result.status!==0){t.skip('OpenSSL with SAN generation unavailable on this machine');return}
    assert.doesNotThrow(()=>validateLocalCertificates(root));
    writeFileSync(join(root,'.certs','localhost-key.pem'),'not a PEM key');
    assert.throws(()=>validateLocalCertificates(root),/Invalid local HTTPS certificate/);
  } finally {rmSync(root,{recursive:true,force:true})}
});
