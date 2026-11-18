/** Cross-platform development launcher (macOS, Windows, Linux).
 * Requires a local Python virtual environment and installed frontend packages.
 * No .env contents or API tokens are printed.
 */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import {readSettings,preflight} from './launcher_utils.mjs';

const root = dirname(fileURLToPath(import.meta.url));
const onWindows = process.platform === 'win32';
const python = join(root, '.venv', onWindows ? 'Scripts/python.exe' : 'bin/python');
const npm = onWindows ? 'npm.cmd' : 'npm';
let settings;
let healthURL;
let backend;
let frontend;
let stopping = false;

function terminateTree(child) {
  if (!child?.pid) return;
  if (onWindows) {
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
  } else {
    try { process.kill(-child.pid, 'SIGTERM'); }
    catch { try { child.kill('SIGTERM'); } catch {} }
  }
}

function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  console.log('\nStopping RepoLens...');
  terminateTree(frontend);
  terminateTree(backend);
  process.exit(exitCode);
}
process.on('SIGINT', () => stop(130));
process.on('SIGTERM', () => stop(143));

async function healthy() {
  try {
    const response = await fetch(healthURL, { signal: AbortSignal.timeout(1200) });
    return response.ok && (await response.json()).status === 'ok';
  } catch { return false; }
}

async function run() {
  if (!existsSync(python)) {
    throw new Error('Missing .venv: create it using python3 -m venv .venv (macOS) or py -m venv .venv (Windows).');
  }
  if (!existsSync(join(root, 'frontend', 'node_modules'))) {
    throw new Error('Missing frontend/node_modules: run npm install inside frontend first.');
  }
  settings=readSettings(root,process.env,process.argv.slice(2));
  await preflight(settings,root);
  // FastAPI is bound to 127.0.0.1. Vite is the TLS termination point: all
  // browser traffic (including /api and OAuth redirects) stays on HTTPS.
  healthURL='http://127.0.0.1:'+settings.backendPort+'/api/health';
  if(settings.check){console.log('Configuration and ports are ready. Website: '+settings.origin);return;}

  console.log('Starting RepoLens backend...');
  backend = spawn(python, ['-m', 'uvicorn', 'backend.api.api:app', '--host', '127.0.0.1', '--port', String(settings.backendPort), '--proxy-headers', '--forwarded-allow-ips', '127.0.0.1', '--no-access-log'], {
    cwd: root, env:{...process.env,REPOLENS_BASE_URL:settings.origin}, stdio: 'inherit', detached: !onWindows
  });
  backend.on('error', error => { console.error('Backend startup error:', error.message); stop(1); });

  let ready = false;
  for (let attempt = 0; attempt < 40; attempt++) {
    if (stopping) return;
    if (backend.exitCode !== null || backend.signalCode !== null) {
      throw new Error('Backend exited before /api/health responded. Read the Python traceback above.');
    }
    if (await healthy()) { ready = true; break; }
    await delay(1000);
  }
  if (!ready) throw new Error('Backend did not start within 40 seconds; inspect FastAPI output above.');

  console.log('Starting RepoLens frontend...');
  frontend = spawn(npm, ['run', 'dev', '--', '--host', new URL(settings.origin).hostname, '--port', String(settings.frontendPort), '--strictPort'], {
    cwd: join(root, 'frontend'), env:{...process.env,REPOLENS_LOCAL_HTTPS:settings.https?'1':'0',REPOLENS_PUBLIC_ORIGIN:settings.origin,REPOLENS_API_ORIGIN:'http://127.0.0.1:'+settings.backendPort}, stdio: 'inherit', detached: !onWindows, shell: onWindows
  });
  frontend.on('error', error => { console.error('Frontend startup error:', error.message); stop(1); });
  backend.on('exit', code => { if (!stopping) { console.error('Backend exited unexpectedly.'); stop(code || 1); } });
  frontend.on('exit', code => { if (!stopping) stop(code || 1); });
  console.log('\nWebsite:   '+settings.origin);
  console.log('Dashboard: '+settings.origin+'/dashboard/');
  console.log('API:       '+settings.origin+'/api/health (encrypted through Vite proxy)');
  console.log('Public docs: '+settings.origin+'/docs/');
  if(settings.https)console.log('TLS:       trusted local mkcert certificate; backend is loopback-only\n');
}
run().catch(error => { console.error(error.message); stop(1); });
