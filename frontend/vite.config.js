import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';
import { JOIN_PROXY_PATTERN } from './config/proxyRoutes.mjs';

const entry = path => fileURLToPath(new URL(path, import.meta.url));
const useHTTPS = process.env.REPOLENS_LOCAL_HTTPS === '1';
const certPath = fileURLToPath(new URL('../.certs/localhost.pem', import.meta.url));
const keyPath = fileURLToPath(new URL('../.certs/localhost-key.pem', import.meta.url));
// The public origin comes from the validated launcher. Never trust an arbitrary
// browser X-Forwarded-Proto or Host header for OAuth callbacks.
const browserOrigin = new URL(process.env.REPOLENS_PUBLIC_ORIGIN || (useHTTPS ? 'https://127.0.0.1:5173' : 'http://127.0.0.1:5173'));
const proxyTarget = process.env.REPOLENS_API_ORIGIN || 'http://127.0.0.1:8000';
const apiProxy = {
 target:proxyTarget,
 changeOrigin:false,
 xfwd:true,
 configure(proxy) {
  proxy.on('proxyReq',(upstreamRequest) => {
   upstreamRequest.setHeader('Host',browserOrigin.host);
   upstreamRequest.setHeader('X-Forwarded-Host',browserOrigin.host);
   upstreamRequest.setHeader('X-Forwarded-Proto',browserOrigin.protocol.slice(0,-1));
  });
 },
};
export default defineConfig({
 server: {
  https: useHTTPS ? {cert:readFileSync(certPath),key:readFileSync(keyPath)} : undefined,
  proxy: {'/api':apiProxy, [JOIN_PROXY_PATTERN]:apiProxy},
 },
 build: {rollupOptions:{input:{
  gallery:entry('./gallery/index.html'),
  docs:entry('./docs/index.html'),
  demo:entry('./demo/index.html'),
  examples:entry('./examples/index.html'),
  pricing:entry('./pricing/index.html'),
  blog:entry('./blog/index.html'),
  landing:entry('./index.html'),
  login:entry('./login/index.html'),
  signup:entry('./signup/index.html'),
  dashboard:entry('./dashboard/index.html'),
 }}},
});
