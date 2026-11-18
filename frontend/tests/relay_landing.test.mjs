import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {fileURLToPath} from 'node:url';
const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const read = file => readFileSync(join(root,file),'utf8');

test('Relay-inspired landing preserves sign-in, workbench, and gallery routes', () => {
  const html=read('index.html');
  assert.match(html, /<body class="relay-landing">/);
  for (const route of ['/login/','/signup/','/dashboard/','/gallery/','/reports/pallets-flask-report.md'])
    assert.ok(html.includes(`href="${route}"`),`missing ${route}`);
  assert.match(html, /<main id="main">/);
  assert.match(html, /aria-label="Main navigation"/);
  assert.match(html, /aria-label="Product resources"/);
  assert.match(html, /Example \/ Not a live scan/i);
});

test('landing palette and animation styles are scoped off authenticated pages', () => {
  const html=read('index.html');
  const css=read('public/relay-landing.css');
  const dashboard=read('dashboard/index.html');
  assert.match(html, /href="\/relay-landing.css"/);
  assert.doesNotMatch(dashboard, /relay-landing\.css/);
  assert.match(css,/--rl-bg:#121416/);
  assert.match(css,/--rl-blue:#3177ac/);
  assert.match(css,/--rl-card:#1c2024/);
  assert.match(css, /prefers-reduced-motion:reduce/);
  assert.doesNotMatch(css, /#(?:d6f08d|a3dc3a|a8e433)\b/i);
});

test('the illustrated workflow never invokes or pretends to perform authenticated analysis', () => {
  const js=read('site/landing.js');
  assert.doesNotMatch(js,/fetch\s*\(/);
  assert.doesNotMatch(js,/location\.assign|window\.open/);
  assert.match(js,/aria-pressed/);
  assert.match(js,/IntersectionObserver/);
  assert.match(js,/mountDepthRibbons/);
});

test('original perspective light sculpture has depth cues without a new dependency or API access', () => {
  const js=read('site/depth-ribbons.js');
  const landing=read('site/landing.js');
  const html=read('index.html');
  const css=read('public/relay-landing.css');
  assert.match(js,/perspective/);
  assert.match(js,/Math\.sin\(theta\)/);
  assert.match(js,/requestAnimationFrame/);
  assert.match(js,/document\.hidden/);
  assert.match(js,/reducedMotion\.matches/);
  assert.doesNotMatch(js, /fetch\s*\(|XMLHttpRequest|WebSocket/);
  assert.match(landing, /mountDepthRibbons/);
  assert.match(html, /hero-depth-field/);
  assert.match(html, /glass-backplane-near/);
  assert.match(css, /rotateY\(calc\(-12deg/);
  assert.match(css, /@media\(max-width:760px\)/);
});
