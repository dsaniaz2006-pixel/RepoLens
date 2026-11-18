import {test,expect} from '@playwright/test';

test('Docs and Public Gallery share a persistent cinematic colour theme',async({page})=>{
  await page.goto('/docs/');
  const toggle=page.getByRole('switch',{name:'Toggle theme'});
  await expect(toggle).toHaveAttribute('aria-checked','true');
  await expect(page.locator('html')).toHaveAttribute('data-repolens-theme','dark');
  await expect.poll(()=>page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor)).toBe('rgb(18, 20, 22)');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-checked','false');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-repolens-theme','light');
  await page.goto('/gallery/');
  await expect(page.getByRole('switch',{name:'Toggle theme'})).toHaveAttribute('aria-checked','false');
  await page.getByRole('switch',{name:'Toggle theme'}).click();
  await expect(page.locator('html')).toHaveAttribute('data-repolens-theme','dark');
  await expect(page.locator('.catalog article')).toHaveCount(20);
});

test('public pages remain readable without horizontal overflow on mobile',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/pricing/');
  await expect(page.getByRole('switch',{name:'Toggle theme'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.goto('/gallery/');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
