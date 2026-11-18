import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../src/style.css', import.meta.url), 'utf8');
const html = readFileSync(new URL('../dashboard/index.html', import.meta.url), 'utf8');

test('dashboard covers the document canvas with charcoal so no white edge appears during trackpad overscroll', () => {
  assert.match(css, /html\s*,\s*body\s*,\s*#root\s*\{[^}]*background(?:-color)?\s*:\s*#121416\s*;/);
  assert.match(css, /html\s*,\s*body\s*\{[^}]*overscroll-behavior-y\s*:\s*none\s*;/);
  assert.match(css, /#root\s*\{[^}]*min-height\s*:\s*100(?:dvh|vh)\s*;/);
});

test('document canvas stays light when switching to the light theme', () => {
  assert.match(css, /html\[data-repolens-theme="light"\][\s\S]*?background(?:-color)?\s*:\s*#eef2f4\s*;/);
  assert.match(html, /<meta name="theme-color" content="#121416"\s*\/>/);
});
