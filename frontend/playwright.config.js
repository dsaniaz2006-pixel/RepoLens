import { defineConfig } from '@playwright/test';
export default defineConfig({
 testDir: './e2e',
 // The offline UI suite intentionally uses HTTP and mocked APIs. Run the
 // real-backend TLS suite with playwright.https.config.js instead.
 testIgnore: /local_https\.spec\.js/,
 fullyParallel: true,
 use: { baseURL: 'http://127.0.0.1:5175', headless: true, launchOptions: {executablePath:process.env.REPOLENS_CHROMIUM_EXECUTABLE, args:['--no-sandbox','--disable-dev-shm-usage']} },
 webServer: {command:'npm run dev -- --port 5175 --strictPort',url:'http://127.0.0.1:5175',reuseExistingServer:false},
});
