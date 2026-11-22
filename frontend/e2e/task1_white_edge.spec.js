import { test, expect } from '@playwright/test';
import {mockAuthenticatedWorkspace} from './helpers/mockAuthenticatedWorkspace.mjs';
// Intercept initial offline API requests before React mounts.
// Test-specific API mocks registered later take priority.
test.beforeEach(async ({page}) => {
  await mockAuthenticatedWorkspace(page);
});

// Task 1: the document itself must match the workspace background, not just .app.
// Mac trackpad rubber-band scrolling can reveal html/body behind a dark React app.
test('dashboard has no white document edge in dark and light modes', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('repolens-theme','dark'));
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me', route => route.fulfill({json:{user:{id:'edge-test',name:'Theme Tester'},csrf_token:'test-csrf'}}));
  await page.route('**/api/history', route => route.fulfill({json:[]}));
  await page.goto('/dashboard/');
  await expect(page.getByRole('heading',{name:'Welcome back, Theme.'})).toBeVisible();

  const canvasColors = () => page.evaluate(() => ({
    html: getComputedStyle(document.documentElement).backgroundColor,
    body: getComputedStyle(document.body).backgroundColor,
    root: getComputedStyle(document.getElementById('root')).backgroundColor,
    overscroll: getComputedStyle(document.documentElement).overscrollBehaviorY,
  }));
  await expect.poll(canvasColors).toEqual({
    html:'rgb(18, 20, 22)', body:'rgb(18, 20, 22)', root:'rgb(18, 20, 22)', overscroll:'none',
  });
  await page.getByRole('switch',{name:'Toggle theme'}).click();
  await expect.poll(canvasColors).toEqual({
    html:'rgb(238, 242, 244)',body:'rgb(238, 242, 244)',root:'rgb(238, 242, 244)',overscroll:'none',
  });
});
