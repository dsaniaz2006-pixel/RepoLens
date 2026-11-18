import {test, expect} from '@playwright/test';
import {mockAuthenticatedWorkspace} from './helpers/mockAuthenticatedWorkspace.mjs';
// Intercept initial offline API requests before React mounts.
// Test-specific API mocks registered later take priority.
test.beforeEach(async ({page}) => {
  await mockAuthenticatedWorkspace(page);
});

// User-visible upgrade journeys. External GitHub/Gemini requests are mocked;
// server authorization and SQL persistence are covered by Python HTTP tests.
test.beforeEach(async ({page}) => {
  await page.route('**/api/auth/me', route => route.fulfill({json:{user:{id:'alice',name:'Alice'},csrf_token:'csrf-test'}}));
  await page.route('**/api/history', route => route.fulfill({json:[]}));
  await page.route('**/api/repositories', route => route.fulfill({json:[]}));
  await page.route('**/api/workspaces', route => route.fulfill({json:[]}));
});

// Route fixtures must be in place *before* the page's initial API calls.
async function openDashboard(page) {
  await page.goto('/dashboard/');
  await expect(page.getByRole('button',{name:'Knowledge Hub',exact:true})).toBeVisible();
}

test('Phase 2 + 3: a stale repository can open a persisted PR/commit comparison',async({page}) => {
  const repository={id:'repo-1',kind:'repository',data:{
    url:'https://github.com/o/r',repository:'o/r',revision:'a'.repeat(40),
    latest_sha:'b'.repeat(40),checked_at:1700000000,is_stale:true}};
  const diff={id:'diff-1',kind:'diff',updated:1700000000,data:{
    repository:'o/r',revision:'b'.repeat(40),summary:'Auth flow changed',
    changes:[{path:'app.py',impact:'The auth handler changed',test_suggestion:'Test session validation'}],
    coverage:{analyzed_files:1,eligible_files:1,model_batches:1},
    omitted_paths:[],unmentioned_paths:[],limits:[]}};
  await page.route('**/api/repositories',route=>route.fulfill({json:[repository]}));
  await page.route('**/api/insights/diff',route=>route.fulfill({json:[diff]}));
  await page.route('**/api/diff',route=>{
    const data=route.request().postDataJSON();
    expect(data.base).toBe('a'.repeat(40));
    expect(data.head).toBe('b'.repeat(40));
    return route.fulfill({json:diff});
  });
  await openDashboard(page);
  await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
  await expect(page.getByText('Changed since indexing',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Explain changes',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Auth flow changed'})).toBeVisible();
  await expect(page.getByText('Evidence covers 1 of 1 eligible files',{exact:false})).toBeVisible();
});

test('Phase 5: a member opens a workspace-scoped private chat from a shared index',async({page}) => {
  const wid='workspace-1';
  const shared={id:'shared-1',data:{repository:'o/r',revision:'a'.repeat(40),is_stale:false}};
  const team={role:'member',members:[{user:'alice',role:'member'},{user:'owner',role:'owner'}],
    repositories:[shared],pins:[]};
  await page.route('**/api/workspaces',route=>route.fulfill({json:[{id:wid,data:{name:'Engineering'},role:'member'}]}));
  await page.route(`**/api/workspaces/${wid}`,route=>route.fulfill({json:team}));
  await page.route(`**/api/workspaces/${wid}/assignments`,route=>route.fulfill({json:[]}));
  await page.route('**/api/insights/checklist',route=>route.fulfill({json:[]}));
  await page.route('**/api/conversations',route=>route.fulfill({json:[]}));
  await page.route(`**/api/workspaces/${wid}/repositories/${shared.id}/chat`,route=>{
    expect(route.request().method()).toBe('POST');
    return route.fulfill({json:{id:'conversation-1',workspace_id:wid,repository:'o/r',revision:'a'.repeat(40),messages:[]}});
  });
  await openDashboard(page);
  await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
  await page.getByRole('button',{name:'Teams',exact:true}).click();
  await expect(page.getByRole('button',{name:'Teams',exact:true})).toHaveAttribute('aria-pressed','true');
  await expect(page.getByLabel('Your workspaces')).toBeVisible();
  await page.getByLabel('Your workspaces').selectOption(wid);
  await expect(page.getByText('Your role: member.',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Start private chat'}).click();
  await expect(page.getByText('Private chat created.',{exact:false})).toBeVisible();
});
