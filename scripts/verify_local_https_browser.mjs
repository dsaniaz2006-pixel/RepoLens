#!/usr/bin/env node
/** Run real HTTPS Playwright tests against the verified local mkcert CA.
 * Never disable TLS validation or expose rootCA-key.pem. */
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const carootResult = spawnSync('mkcert', ['-CAROOT'], { encoding: 'utf8', timeout: 10000 });
if (carootResult.error || carootResult.status !== 0) {
  console.error('HTTPS TEST BLOCKED: mkcert is unavailable. Install with brew install mkcert, then run mkcert -install.');
  process.exit(1);
}
const caroot = carootResult.stdout.trim();
const certificate = isAbsolute(caroot) ? join(caroot, 'rootCA.pem') : '';
if (!certificate || !existsSync(certificate)) {
  console.error('HTTPS TEST BLOCKED: mkcert rootCA.pem is missing. Run mkcert -install and node scripts/setup_local_https.mjs.');
  process.exit(1);
}
let pem = '';
try { pem = readFileSync(certificate, 'utf8'); } catch {
  console.error('HTTPS TEST BLOCKED: Cannot read the local mkcert CA certificate.');
  process.exit(1);
}
if (!pem.includes('-----BEGIN CERTIFICATE-----')) {
  console.error('HTTPS TEST BLOCKED: mkcert CA file is not a PEM certificate.');
  process.exit(1);
}
const env = {
  ...process.env,
  NODE_EXTRA_CA_CERTS: certificate,
  NODE_USE_SYSTEM_CA: '1',
};
// Deliberately do NOT set NODE_TLS_REJECT_UNAUTHORIZED=0 or ignoreHTTPSErrors.
delete env.NODE_TLS_REJECT_UNAUTHORIZED;
console.log('HTTPS tests: validating TLS with the local mkcert CA (verification enabled).');
const result = spawnSync(process.platform === 'win32' ? 'npx.cmd' : 'npx',
  ['playwright', 'test', '--config=playwright.https.config.js', ...process.argv.slice(2)],
  { cwd: join(root, 'frontend'), stdio: 'inherit', env });
if (result.error) {
  console.error('HTTPS TEST BLOCKED: Could not launch Playwright:', result.error.message);
  process.exit(1);
}
process.exit(result.status === null ? 1 : result.status);
