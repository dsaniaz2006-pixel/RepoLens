import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {JOIN_PROXY_PATTERN} from '../config/proxyRoutes.mjs';
import {analysisSSE} from '../e2e/helpers/analysisSSE.mjs';

const source = name => readFileSync(fileURLToPath(new URL(name, import.meta.url)), 'utf8');

test('TDD: invite landing file remains static while token exchange uses backend', () => {
 const matches = new RegExp(JOIN_PROXY_PATTERN);
 assert.ok(matches.test('/join'));
 assert.ok(matches.test('/join?token=abcdefghijklmnopqrstuvwxyz0123456789'));
 for (const path of ['/join.html', '/join.html?token=abcd', '/join.js', '/join-anything']) {
   assert.equal(matches.test(path), false, `${path} must not be intercepted by the API proxy`);
 }
 assert.match(source('../vite.config.js'), /JOIN_PROXY_PATTERN/);
});

test('TDD: SSE browser fixture matches the real stream contract', () => {
 const report = {metadata:{full_name:'a/one'},analysis:{project_summary:'Report for a/one'}};
 const chunks=analysisSSE(report).trim().split(/\n\n/);
 assert.equal(chunks.length,2);
 assert.equal(JSON.parse(chunks[0].slice(6)).status,'progress');
 const terminal = JSON.parse(chunks[1].slice(6));
 assert.equal(terminal.status,'done');
 assert.equal(terminal.result.analysis.project_summary,'Report for a/one');
 const dashboard=source('../e2e/dashboard.spec.js');
 assert.match(dashboard, /\/api\/analyze\/stream/);
 assert.doesNotMatch(dashboard, /route\('\*\*\/api\/analyze'/);
 assert.match(dashboard, /mockAuthenticatedWorkspace/);
});

test('TDD: offline browser suite does not run TLS tests through HTTP', () => {
 const offline=source('../playwright.config.js');
 const https=source('../playwright.https.config.js');
 const release=source('../../scripts/verify_predeploy.sh');
 assert.match(offline, /testIgnore:\s*\/local_https/);
 assert.match(https, /https:\/\/127\.0\.0\.1/);
 assert.match(https, /reuseExistingServer:\s*false/);
 const launcher = source('../../scripts/verify_local_https_browser.mjs');
 assert.match(release, /verify_local_https_browser\.mjs/);
 assert.match(launcher, /playwright\.https\.config\.js/);
 assert.match(launcher, /NODE_EXTRA_CA_CERTS/);
 assert.match(launcher, /NODE_USE_SYSTEM_CA/);
 assert.doesNotMatch(launcher, /ignoreHTTPSErrors:\s*true/);
});

test('TDD: authenticated browser suites use a closed default API boundary', () => {
  const suites = [
    'phase1_5.spec.js',
    'phase6_10.spec.js',
    'section2_security.spec.js',
    'section3_security.spec.js',
    'section6_workspaces.spec.js',
    'task1_white_edge.spec.js',
  ];

  for (const name of suites) {
    const code = source('../e2e/' + name);
    assert.match(
      code,
      /mockAuthenticatedWorkspace\(page\)/,
      name
    );
  }

  // Never remove real session-expiry protection.
  assert.match(
    source('../src/services/apiClient.js'),
    /reason=expired/
  );
});
