import {test, expect} from '@playwright/test';
import {mockAuthenticatedWorkspace} from './helpers/mockAuthenticatedWorkspace.mjs';
// Intercept initial offline API requests before React mounts.
// Test-specific API mocks registered later take priority.
test.beforeEach(async ({page}) => {
  await mockAuthenticatedWorkspace(page);
});

// UI E2E uses the real built React app with intercepted API responses.
// This intentionally does not simulate Google/GitHub consent or production Neon.
test('Account Security lists only safe audit metadata and refreshes after an API-key action', async ({page}) => {
  let events=[];
  let keys=[];
  const rawSecret='rl_live_test_one_time_value_do_not_log';
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me',r=>r.fulfill({json:{user:{id:'alice',name:'Alice'},csrf_token:'csrf'}}));
  await page.route('**/api/history',r=>r.fulfill({json:[]}));
  await page.route('**/api/config-status',r=>r.fulfill({json:{model_provider:'gemini',gemini_key_configured:true,github_token_configured:true}}));
  await page.route('**/api/auth/sessions',r=>r.fulfill({json:{sessions:[{id:'session1',current:true,expires_at:2000000000,user_agent:'Chrome'}]}}));
  await page.route('**/api/auth/audit',r=>r.fulfill({json:{events}}));
  await page.route(/\/api\/auth\/keys(?:\/[^?]*)?(?:\?.*)?$/,r=>{
    if(r.request().method()==='POST'){
      keys=[{id:'key1',name:'Security test',created_at:1900000000,key_prefix:'rl_live_test'}];
      events=[{id:'event1',action:'api_key:created',created_at:1900000000}];
      return r.fulfill({status:201,json:{...keys[0],key:rawSecret}});
    }
    return r.fulfill({json:{keys}});
  });
  await page.goto('/dashboard/');
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Recent security activity'})).toBeVisible();
  await page.getByLabel('Key name').fill('Security test');
  await page.getByRole('button',{name:'Create API key'}).click();
  await expect(page.getByTestId('section2-secret')).toHaveText(rawSecret);
  await expect(page.getByText('api key — created')).toBeVisible();
  await page.getByRole('button',{name:"I've saved this key"}).click();
  await expect(page.getByTestId('section2-secret')).toHaveCount(0);
  await expect(page.locator('.security-audit-card')).not.toContainText(rawSecret);
});

// This page previously had an inline script. The strict CSP now requires
// a same-origin module so invite tokens aren't sent through unsafe script injection.
test('Invitation page uses same-origin JS and never embeds an inline script', async ({page})=>{
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me',r=>r.fulfill({status:401,json:{detail:'Sign in to continue.'}}));
  await page.goto('/join.html?token=abcdefghijklmnopqrstuvwxyz0123456789');
  await expect(page.getByText('Sign in, then review and confirm this invitation.')).toBeVisible();
  expect(await page.locator('script:not([src])').count()).toBe(0);
});
