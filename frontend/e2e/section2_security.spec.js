import {test, expect} from '@playwright/test';
import {mockAuthenticatedWorkspace} from './helpers/mockAuthenticatedWorkspace.mjs';
// Intercept initial offline API requests before React mounts.
// Test-specific API mocks registered later take priority.
test.beforeEach(async ({page}) => {
  await mockAuthenticatedWorkspace(page);
});

// Browser E2E with intercepted API responses: exercises the real React Settings UI.
// Provider consent and live Neon are covered by separate manual acceptance gates.
test('Settings: issue one-time developer key, copy and revoke it', async ({page}) => {
  let keys=[];
  const secret='rl_live_example_token_only_display_once';
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me',r=>r.fulfill({json:{user:{id:'alice',name:'Alice Tester'},csrf_token:'csrf'}}));
  await page.route('**/api/history',r=>r.fulfill({json:[]}));
  await page.route('**/api/config-status',r=>r.fulfill({json:{model_provider:'gemini',gemini_key_configured:false,github_token_configured:false}}));
  await page.route('**/api/auth/sessions',r=>r.fulfill({json:{sessions:[{id:'one',current:true,expires_at:2000000000,user_agent:'Chrome',ip_address:'127.0.0.1'}]}}));
  await page.route(/\/api\/auth\/keys(?:\/[^?]*)?(?:\?.*)?$/,r=>{
    const request=r.request();
    if(request.method()==='POST'){
      keys=[{id:'key1',name:request.postDataJSON().name,key_prefix:'rl_live_exam',created_at:2000000000}];
      return r.fulfill({status:201,json:{...keys[0],key:secret}});
    }
    if(request.method()==='DELETE'){keys=[];return r.fulfill({json:{revoked:true}});}
    return r.fulfill({json:{keys}});
  });
  await page.goto('/dashboard/');
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Account security'})).toBeVisible();
  await page.getByLabel('Key name').fill('Terminal Key');
  await page.getByRole('button',{name:'Create API key'}).click();
  await expect(page.getByTestId('section2-secret')).toHaveText(secret);
  await expect(page.getByText('Terminal Key',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:"I've saved this key"}).click();
  await expect(page.getByTestId('section2-secret')).toHaveCount(0);
  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'Revoke key Terminal Key'}).click();
  await expect(page.getByText('No active developer API keys.')).toBeVisible();
  await expect(page.getByTestId('section2-secret')).toHaveCount(0);
});

test('Settings: shows active device and sends revoke-all request',async ({page})=>{
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me',r=>r.fulfill({json:{user:{id:'alice',name:'Alice'},csrf_token:'csrf'}}));
  await page.route('**/api/history',r=>r.fulfill({json:[]}));
  await page.route('**/api/config-status',r=>r.fulfill({json:{}}));
  await page.route('**/api/auth/keys',r=>r.fulfill({json:{keys:[]}}));
  await page.route('**/api/auth/sessions',r=>r.fulfill({json:{sessions:[{id:'one',current:true,expires_at:2000000000,user_agent:'Safari',ip_address:'127.0.0.1'}]}}));
  let revoked=false;
  await page.route('**/api/auth/sessions/all',r=>{revoked=r.request().method()==='DELETE' && r.request().headers()['x-csrf-token']==='csrf';return r.fulfill({json:{revoked:true}});});
  await page.goto('/dashboard/');
  await page.getByRole('button',{name:'Settings',exact:true}).click();
  await expect(page.getByText('This device')).toBeVisible();
  await expect(page.getByText('Safari · 127.0.0.1')).toBeVisible();
  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'Sign out all devices'}).click();
  await expect.poll(()=>revoked).toBeTruthy();
});
