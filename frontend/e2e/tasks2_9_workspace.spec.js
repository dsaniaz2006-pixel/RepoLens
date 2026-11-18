import {test,expect} from '@playwright/test';
import {mockAuthenticatedWorkspace} from './helpers/mockAuthenticatedWorkspace.mjs';

let unexpectedRequests = [];
test.beforeEach(async({page})=>{
 unexpectedRequests = await mockAuthenticatedWorkspace(page);
 await page.goto('/dashboard/');
 await expect(page.getByRole('button',{name:'Home',exact:true})).toBeVisible();
});

test.afterEach(()=>{
 // A new background request must be mocked explicitly, not sent to the
 // user's real backend where a 401 can masquerade as a UI failure.
 expect(unexpectedRequests).toEqual([]);
});

test('Task 2: Knowledge Hub shows pill tabs and real action buttons',async({page})=>{
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Repository knowledge'})).toBeVisible();
 const tab=page.getByRole('button',{name:'Freshness',exact:true});
 await expect(tab).toHaveClass(/selected/);
 await expect(page.getByRole('button',{name:'Build / Refresh index'})).toBeVisible();
 const radius=await tab.evaluate(e=>getComputedStyle(e).borderRadius);
 expect(parseFloat(radius)).toBeGreaterThan(10);
});

test('Task 3: settings overview shows structured provider and privacy cards',async({page})=>{
 await page.getByRole('button',{name:'Settings',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Settings & security'})).toBeVisible();
 await expect(page.locator('.settings-status-card')).toHaveCount(3);
 await expect(page.getByText('Configured on server')).toBeVisible();
 await expect(page.getByRole('heading',{name:'Account security'})).toBeVisible();
});

test('Task 4: Public Gallery stays inside dashboard shell with source snapshots',async({page})=>{
 await page.getByRole('button',{name:'Public Gallery'}).click();
 await expect(page).toHaveURL(/\/dashboard\/$/);
 await expect(page.getByRole('navigation',{name:'Workspace navigation'})).toBeVisible();
 await expect(page.locator('.gallery-tile')).toHaveCount(20);
 await page.getByRole('button',{name:/pallets\/flask/}).click();
 await expect(page.locator('iframe.gallery-report-frame')).toHaveAttribute('src','/gallery/pallets-flask/index.html');
 await page.getByRole('button',{name:'All repositories'}).click();
 await expect(page.locator('.gallery-tile')).toHaveCount(20);
});

test('Task 5 revised: wheel scroll stays within current page and sidebar clicks change views',async({page})=>{
 await expect(page.getByRole('heading',{name:'Welcome back, Test.'})).toBeVisible();
 await page.mouse.move(1050,480);
 await page.mouse.wheel(0,1500);
 await page.waitForTimeout(250);
 await expect(page.locator('.side nav .nav.active')).toHaveText('Home');
 await expect(page.locator('.rl-workspace-content')).toHaveAttribute('aria-label','Home content');
 await page.mouse.wheel(0,1800);
 await page.waitForTimeout(150);
 await expect(page.locator('.side nav .nav.active')).toHaveText('Home');
 await page.getByRole('button',{name:'Analyze Repo',exact:true}).click();
 await expect(page.locator('.rl-workspace-content')).toHaveAttribute('aria-label','Analyze Repo content');
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Repository knowledge'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Welcome back, Test.'})).toHaveCount(0);
});

test('welcome and text reveal have calm timing while preserving reduced-motion',async({page})=>{
 const welcome=page.locator('.rl-welcome-scene');
 await expect(welcome).toHaveCount(1);
 const welcomeSeconds=await welcome.evaluate(el=>parseFloat(getComputedStyle(el).animationDuration));
 expect(welcomeSeconds).toBeGreaterThanOrEqual(4.1);
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 const title=page.getByRole('heading',{name:'Repository knowledge'});
 await expect(title).toBeVisible();
 await expect(title).toHaveClass(/rl-text-reveal/);
 const duration=await title.evaluate(el=>parseFloat(getComputedStyle(el).animationDuration));
 expect(duration).toBeGreaterThanOrEqual(.9);
});

test('reduced-motion mode keeps all text visible without reveal animation',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.getByRole('button',{name:'Settings',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Settings & security'})).toBeVisible();
 const heading=page.getByRole('heading',{name:'Settings & security'});
 const animation=await heading.evaluate(el=>getComputedStyle(el).animationName);
 expect(animation).toBe('none');
 await page.getByRole('button',{name:'Home',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Welcome back, Test.'})).toBeVisible();
});

test('Tasks 6-9: moving liquid nav, matching logo, one-session welcome and reveal',async({page})=>{
 await expect(page.locator('.rl-nav-water')).toBeVisible();
 const svg=await page.request.get('/favicon-v2.svg?v=20');
 expect(await svg.text()).toMatch(/#28547a/i);
 await expect(page.locator('.rl-welcome-scene')).toHaveCount(1);
 await page.reload();
 await expect(page.locator('.rl-welcome-scene')).toHaveCount(0);
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await expect(page.locator('.hub-tabs .selected')).toBeVisible();
 await page.getByRole('button',{name:'Security',exact:true}).click();
 await expect(page.getByRole('button',{name:'Scan dependencies and patterns'})).toBeVisible();
});
