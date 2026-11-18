import net from 'node:net';
import {readFileSync,existsSync} from 'node:fs';
import {join} from 'node:path';
import {X509Certificate,createPrivateKey,createPublicKey} from 'node:crypto';

const CERT_NAME = 'localhost.pem';
const KEY_NAME = 'localhost-key.pem';

export function localCertPaths(root) {
 return {cert:join(root,'.certs',CERT_NAME),key:join(root,'.certs',KEY_NAME)};
}

/** Ensure TLS never silently falls back to HTTP or ships with an invalid key. */
export function validateLocalCertificates(root) {
 const paths=localCertPaths(root);
 if(!existsSync(paths.cert)||!existsSync(paths.key)) {
  throw new Error('Local HTTPS certificate missing. Install mkcert and run: node scripts/setup_local_https.mjs. Certificates are private and are not included in the ZIP.');
 }
 try {
  const cert=new X509Certificate(readFileSync(paths.cert));
  const key=createPrivateKey(readFileSync(paths.key));
  const keyPublic=createPublicKey(key).export({type:'spki',format:'der'});
  const certPublic=cert.publicKey.export({type:'spki',format:'der'});
  if(!keyPublic.equals(certPublic))throw new Error('Certificate and private key do not match');
  if(Date.now()<new Date(cert.validFrom).getTime()||Date.now()>new Date(cert.validTo).getTime())throw new Error('Certificate is not currently valid');
  if(!cert.checkHost('localhost')||!cert.checkIP('127.0.0.1'))throw new Error('Certificate must include localhost and 127.0.0.1');
 } catch (error) {
  throw new Error('Invalid local HTTPS certificate: '+error.message+'. Re-run: node scripts/setup_local_https.mjs');
 }
 return paths;
}

export function readSettings(root, environment=process.env, args=[]) {
 const values={};
 if(existsSync(join(root,'.env'))) {
  for(const line of readFileSync(join(root,'.env'),'utf8').split(/\r?\n/)) {
   const match=line.match(/^\s*(?:export\s+)?(REPOLENS_BACKEND_PORT|REPOLENS_FRONTEND_PORT|REPOLENS_BASE_URL)\s*=\s*(.*?)\s*$/);
   if(match) values[match[1]]=match[2].replace(/\s+#.*$/,'').replace(/^(['"])(.*)\1$/,'$2');
  }
 }
 for(const key of ['REPOLENS_BACKEND_PORT','REPOLENS_FRONTEND_PORT','REPOLENS_BASE_URL']) if(environment[key]!==undefined)values[key]=environment[key];
 let backend=values.REPOLENS_BACKEND_PORT||'8000',front=values.REPOLENS_FRONTEND_PORT;
 let protocolOverride=null;
 for(let i=0;i<args.length;i++) {
  if(args[i]==='--backend-port')backend=args[++i];
  else if(args[i]==='--https')protocolOverride='https:';
  else if(args[i]==='--http')protocolOverride='http:';
  else if(args[i]!=='--check')throw new Error('Usage: node start.mjs [--check] [--https|--http] [--backend-port NUMBER]');
 }
 const port=(value)=>{if(!/^\d+$/.test(String(value))||Number(value)<1||Number(value)>65535)throw new Error('Ports must be integers from 1 to 65535');return Number(value)};
 const origin=values.REPOLENS_BASE_URL?new URL(values.REPOLENS_BASE_URL):new URL('http://127.0.0.1:'+(front||5173));
 if(protocolOverride)origin.protocol=protocolOverride;
 if(!['http:','https:'].includes(origin.protocol)||!['127.0.0.1','localhost'].includes(origin.hostname)||origin.username||origin.password||origin.pathname!=='/'||origin.search||origin.hash)throw new Error('The development launcher requires a local HTTP or HTTPS REPOLENS_BASE_URL origin with no path or credentials. Public HTTPS belongs behind the production reverse proxy.');
 front=port(front||origin.port||(origin.protocol==='https:'?443:80));
 if(Number(origin.port||(origin.protocol==='https:'?443:80))!==front)throw new Error('REPOLENS_FRONTEND_PORT must match REPOLENS_BASE_URL. Keep your OAuth callback origin consistent.');
 return {backendPort:port(backend),frontendPort:front,origin:origin.origin,https:origin.protocol==='https:',check:args.includes('--check')};
}
export function portAvailable(port) {
 return new Promise((resolve,reject)=>{const server=net.createServer();server.once('error',e=>['EADDRINUSE','EACCES'].includes(e.code)?resolve(false):reject(e));server.listen(port,'127.0.0.1',()=>server.close(()=>resolve(true)))});
}
export async function preflight(settings,root=null) {
 const ports=[settings.backendPort,settings.frontendPort];
 if(ports[0]===ports[1])throw new Error('Backend and frontend must use different ports');
 if(settings.https&&root)validateLocalCertificates(root);
 const free=await Promise.all(ports.map(portAvailable));
 const occupied=ports.filter((_,i)=>!free[i]);
 if(occupied.length)throw new Error('Port '+occupied.join(', ')+' is already in use. No process was stopped. In the terminal running the old server press Ctrl+C. On macOS inspect the owner with: lsof -nP -iTCP:'+occupied[0]+' -sTCP:LISTEN. For a backend conflict you can use: node start.mjs --backend-port 8001.');
}
