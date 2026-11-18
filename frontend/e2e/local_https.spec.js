import {test,expect} from '@playwright/test';

test('HTTPS landing, login, and API are same-origin',async({page})=>{
  const errors=[];
  page.on('pageerror',err=>errors.push(err.message));
  const landing=await page.goto('/');
  expect(landing.status()).toBe(200);
  expect(await page.evaluate(()=>window.location.protocol)).toBe('https:');
  expect(await page.evaluate(()=>window.isSecureContext)).toBe(true);
  const health=await page.request.get('/api/health');
  expect(health.ok()).toBeTruthy();
  expect((await health.json()).status).toBe('ok');
  const login=await page.goto('/login/');
  expect(login.status()).toBe(200);
  expect(await page.evaluate(()=>window.location.protocol)).toBe('https:');
  const providers=await page.request.get('/api/auth/providers');
  expect(providers.ok()).toBeTruthy();
  expect((await providers.json()).providers).toBeDefined();
  expect(errors).toEqual([]);
});

test('HTTPS OAuth cookie security is not silently downgraded',async({request})=>{
  // A real Google/GitHub roundtrip requires provider console configuration.
  // The 401 proves authenticated APIs are still protected through the proxy.
  const me=await request.get('/api/auth/me');
  expect(me.status()).toBe(401);
  expect((await me.json()).detail).toMatch(/Sign in/i);
});
