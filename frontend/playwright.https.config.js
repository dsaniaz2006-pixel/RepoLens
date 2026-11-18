import { defineConfig } from '@playwright/test';
export default defineConfig({
 testDir: './e2e',
 testMatch: /local_https\.spec\.js/,
 fullyParallel: false,
 use: {baseURL:'https://127.0.0.1:5173',ignoreHTTPSErrors:false,headless:true},
 webServer: {
  command:'node ../start.mjs --https',
  url:'https://127.0.0.1:5173/api/health',
  ignoreHTTPSErrors:true, // Node's process does not use the macOS Keychain CA.
  reuseExistingServer:false,
  gracefulShutdown: { signal: 'SIGTERM', timeout: 10000 },
  timeout:90000,
 },
});
