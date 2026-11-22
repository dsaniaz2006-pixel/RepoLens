import {test,expect} from '@playwright/test';

// All provider checks are intercepted; this does not exercise real OAuth consent.
async function mockAnonymous(page,providers={google:true,github:true}){
  await page.route('**/api/auth/providers',route=>route.fulfill({status:200,json:{providers}}));
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me',route=>route.fulfill({status:401,json:{detail:'not authenticated'}}));
}

test('glass sign-up theme uses RepoLens palette and real configured OAuth choices',async({page})=>{
  await mockAnonymous(page);
  await page.goto('/signup/');
  await expect(page.getByRole('heading',{name:'Get started with RepoLens.'})).toBeVisible();
  await expect(page.locator('[data-provider="google"]')).toBeEnabled();
  await expect(page.locator('[data-provider="github"]')).toBeEnabled();
  await expect(page.getByRole('link',{name:/Log in/})).toHaveAttribute('href','/login/');
  expect(await page.locator('.rl-auth').evaluate(node=>getComputedStyle(node).backgroundColor)).toBe('rgb(18, 20, 22)');
});

test('unconfigured OAuth provider remains disabled and server message is visible',async({page})=>{
  await mockAnonymous(page,{google:false,github:true});
  await page.goto('/login/');
  await expect(page.getByRole('heading',{name:'Welcome back.'})).toBeVisible();
  await expect(page.locator('[data-provider="google"]')).toBeDisabled();
  await expect(page.locator('[data-provider="github"]')).toBeEnabled();
  await expect(page.getByRole('status')).toContainText('One sign-in provider is available');
});

test('provider outage fails closed and retry can restore provider availability',async({page})=>{
  let online=false;
  await page.route('**/api/auth/providers',route=>online
    ?route.fulfill({status:200,json:{providers:{google:true,github:false}}})
    :route.fulfill({status:503,json:{detail:'offline'}}));
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me',route=>route.fulfill({status:401,json:{detail:'not authenticated'}}));
  await page.goto('/signup/');
  await expect(page.getByRole('status')).toContainText('sign-in service is unavailable');
  await expect(page.locator('[data-provider="google"]')).toBeDisabled();
  online=true;
  await page.getByRole('button',{name:/Check again/}).click();
  await expect(page.locator('[data-provider="google"]')).toBeEnabled();
});

test('mobile auth remains readable with no horizontal overflow and reduced-motion support',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.emulateMedia({reducedMotion:'reduce'});
  await mockAnonymous(page);
  await page.goto('/signup/');
  await expect(page.getByRole('heading',{name:'Get started with RepoLens.'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2)).toBe(false);
  await expect(page.getByRole('link',{name:'RepoLens home'})).toHaveAttribute('href','/');
  const anim=await page.locator('.rl-auth-story').evaluate(node=>getComputedStyle(node).animationDuration);
  expect(Number.parseFloat(anim)).toBeLessThan(.01);
});
