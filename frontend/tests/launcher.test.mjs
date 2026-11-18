import {test} from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {readSettings,preflight,portAvailable} from '../../launcher_utils.mjs';
test('backend override leaves the configured OAuth origin consistent',()=>{
 const root=mkdtempSync(join(tmpdir(),'repolens-launch-'));
 try{writeFileSync(join(root,'.env'),'REPOLENS_BASE_URL=http://localhost:5174\nGEMINI_API_KEY=ignored\n');const result=readSettings(root,{},['--backend-port','8010']);assert.equal(result.origin,'http://localhost:5174');assert.equal(result.frontendPort,5174);assert.equal(result.backendPort,8010);assert.equal(result.GEMINI_API_KEY,undefined)}finally{rmSync(root,{recursive:true})}
});
test('occupied port is detected and the existing listener survives',async()=>{
 const server=net.createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;
 try{assert.equal(await portAvailable(port),false);await assert.rejects(preflight({backendPort:port,frontendPort:port===5173?5174:5173}),/already in use/);assert.equal(server.listening,true)}finally{await new Promise(r=>server.close(r))}
});
test('invalid ports and mismatched callback origins fail before spawning',()=>{
 assert.throws(()=>readSettings('/missing',{},['--backend-port','0']),/Ports/);
 assert.throws(()=>readSettings('/missing',{REPOLENS_BASE_URL:'http://127.0.0.1:5173',REPOLENS_FRONTEND_PORT:'5174'}),/must match/)
});
