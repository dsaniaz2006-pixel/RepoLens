import {test, expect} from '@playwright/test';
import {mockAuthenticatedWorkspace} from './helpers/mockAuthenticatedWorkspace.mjs';
// Intercept initial offline API requests before React mounts.
// Test-specific API mocks registered later take priority.
test.beforeEach(async ({page}) => {
  await mockAuthenticatedWorkspace(page);
});

const wid='section6-workspace';
const inviteId='a'.repeat(64);

async function setup(page,role='owner') {
  let invitations=[];
  const createRequests=[];
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me',r=>r.fulfill({json:{user:{id:'alice',name:'Alice'},csrf_token:'csrf'}}));
  await page.route('**/api/history',r=>r.fulfill({json:[]}));
  await page.route('**/api/repositories',r=>r.fulfill({json:[]}));
  await page.route('**/api/conversations',r=>r.fulfill({json:[]}));
  await page.route('**/api/insights/checklist',r=>r.fulfill({json:[]}));
  await page.route('**/api/workspaces',r=>r.fulfill({json:[{id:wid,role,data:{name:'Engineering'}}]}));
  await page.route(`**/api/workspaces/${wid}`,r=>r.fulfill({json:{role,members:[{user:'alice',role}],pins:[],repositories:[]}}));
  await page.route(`**/api/workspaces/${wid}/assignments`,r=>r.fulfill({json:[]}));
  await page.route(`**/api/workspaces/${wid}/invitations`,r=>r.fulfill({json:invitations}));
  await page.route(`**/api/workspaces/${wid}/invite`,r=>{
    const payload=r.request().postDataJSON();
    createRequests.push(payload);
    invitations=[{id:inviteId,expires:1893456000,recipient_restricted:!!payload.recipient_email}];
    return r.fulfill({json:{url:'http://127.0.0.1:5175/join?token=SAFE_NONSECRET_TEST_PLACEHOLDER',expires_in:86400,
      recipient_restricted:!!payload.recipient_email}});
  });
  await page.route(`**/api/workspaces/${wid}/invitations/${inviteId}`,r=>{
    invitations=[];
    return r.fulfill({json:{revoked:true}});
  });
  await page.goto('/dashboard/');
  await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
  await page.getByRole('button',{name:'Teams',exact:true}).click();
  await page.getByLabel('Your workspaces').selectOption(wid);
  return {createRequests};
}

test('owner creates recipient-verified invite, sees it once and revokes it',async({page})=>{
  const {createRequests}=await setup(page,'owner');
  await expect(page.getByRole('heading',{name:'Team invitations'})).toBeVisible();
  await page.getByLabel('Invitee email').fill('developer@example.com');
  await page.getByRole('button',{name:'Create invitation link'}).click();
  await expect(page.getByLabel('New invitation link')).toBeVisible();
  expect(createRequests).toEqual([{recipient_email:'developer@example.com'}]);
  await expect(page.getByText('Restricted to a verified email')).toBeVisible();
  await page.getByRole('button',{name:'Revoke invitation'}).click();
  await expect(page.getByText('No pending invitations.')).toBeVisible();
  await expect(page.getByLabel('New invitation link')).toHaveCount(0);
});

test('ordinary member cannot issue or inspect invitations',async({page})=>{
  await setup(page,'member');
  await expect(page.getByText('Your role: member.',{exact:false})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Team invitations'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Create invitation link'})).toHaveCount(0);
});
