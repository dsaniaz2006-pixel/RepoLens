import {test,expect} from '@playwright/test';
import {mockAuthenticatedWorkspace} from './helpers/mockAuthenticatedWorkspace.mjs';
import {analysisSSE} from './helpers/analysisSSE.mjs';
const report=(repo)=>({metadata:{full_name:repo,html_url:`https://github.com/${repo}`,default_branch:'main'},analysis:{project_summary:`Report for ${repo}`},tree:[]});
test.beforeEach(async({page})=>{
 // Start with a closed API boundary; overrides below model this test's requests.
 await mockAuthenticatedWorkspace(page,{user:{id:'test',name:'Test user'},csrfToken:'test-csrf'});
 await page.route('**/api/history',route=>route.fulfill({json:[{metadata:report('b/two').metadata,modified:1}]}));
 await page.route('**/api/history/b/two',route=>route.fulfill({json:report('b/two')}));
 await page.route('**/api/analyze/stream',route=>{
  expect(route.request().method()).toBe('POST');
  expect(route.request().headers()['x-csrf-token']).toBe('test-csrf');
  return route.fulfill({status:200,headers:{'Content-Type':'text/event-stream'},body:analysisSSE(report('a/one'))});
 });
 await page.goto('/dashboard/');
 await page.getByRole('button',{name:'Analyze Repo',exact:true}).click();
 await page.getByRole('button',{name:'Analyze Repository',exact:true}).click();
 await expect(page.getByText('Report for a/one')).toBeVisible();
});
test('chat uses displayed repository, saves follow-ups and opens pinned citations',async({page})=>{
 let chat={id:'chat-1',repository:'a/one',revision:'a'.repeat(40),version:0,title:'a/one',messages:[],pending:false};
 await page.route('**/api/conversations',route=>route.fulfill({json:route.request().method()==='POST'?chat:[chat]}));
 await page.route('**/api/conversations/chat-1/messages',route=>route.fulfill({json:chat}));
 await page.route('**/api/ask',route=>{
  const body=route.request().postDataJSON();
  expect(body.url).toBe('https://github.com/a/one');
  expect(body.version).toBe(chat.version);
  chat={...chat,version:chat.version+2,messages:[...chat.messages,{id:'u'+chat.version,role:'user',content:body.question,citations:[]},{id:'a'+chat.version,role:'assistant',content:'Saved answer '+chat.version,citations:[{path:'app.py',start_line:1,end_line:4}]}]};
  return route.fulfill({json:chat});
 });
 await page.getByLabel('GitHub URL').fill('https://github.com/b/two');
 await page.getByRole('button',{name:'Ask RepoLens',exact:true}).click();
 await page.getByRole('button',{name:'Open conversations',exact:true}).click();
 await expect(page.getByLabel('Chat repository URL')).toHaveValue('https://github.com/a/one');
 await page.getByRole('button',{name:'New chat',exact:true}).click();
 await page.getByLabel('Your question', {exact:true}).fill('Where?');
 await page.getByRole('button',{name:'Send question'}).click();
 await expect(page.getByText('Saved answer 0', {exact:true})).toBeVisible();
 await page.getByLabel('Your question', {exact:true}).fill('What calls it?');
 await page.getByRole('button',{name:'Send question'}).click();
 await expect(page.getByText('Saved answer 2', {exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'app.py:L1–L4'}).first()).toHaveAttribute('href',`https://github.com/a/one/blob/${'a'.repeat(40)}/app.py#L1-L4`);
 await page.getByRole('button',{name:'Reload messages'}).click();
 await expect(page.getByText('Saved answer 2', {exact:true})).toBeVisible();
});

test('Home is an overview and Analyze Repo keeps the workbench',async({page})=>{
 await page.getByRole('button',{name:'Home',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Welcome back, Test.'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Recent analyses'})).toBeVisible();
 await expect(page.getByLabel('GitHub URL')).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'Analysis Report',exact:true})).toHaveCount(0);
 await expect(page.getByRole('link',{name:'Landing page'})).toHaveCount(0);
 await expect(page.locator('.brand-logo')).toHaveAttribute('src','/favicon-v2.svg?v=20');
 await expect(page.locator('link[rel="icon"]')).toHaveAttribute('href','/favicon-v2.svg?v=20');
 await page.getByRole('button',{name:'Analyze Repo',exact:true}).click();
 await expect(page.getByLabel('GitHub URL')).toBeVisible();
 await expect(page.getByText('Report for a/one')).toBeVisible();
});
test('recent report on Home opens the analysis workbench',async({page})=>{
 await page.getByRole('button',{name:'Home',exact:true}).click();
 await page.getByRole('button',{name:/b\/two/}).click();
 await expect(page.getByText('Report for b/two')).toBeVisible();
 await expect(page.getByRole('button',{name:'Analyze Repo',exact:true})).toHaveClass('nav active');
});

test('Knowledge Hub saves evidence-based onboarding progress',async({page})=>{
 let item={id:'onboarding-1',kind:'checklist',updated:1,data:{repository:'a/one',revision:'a'.repeat(40),generation:'ai_with_verified_quotes',tasks:[{id:'task-1',phase:'Day 1',task:'Inspect request dispatch',path:'app.py',line:12,why:'Locate the dispatch entry point',snippet:'def dispatch():',done:false}],first_contribution:{task:'Investigate dispatch test coverage'}}};
 await page.route('**/api/repositories',route=>route.fulfill({json:[]}));
 await page.route('**/api/workspaces',route=>route.fulfill({json:[]}));
 await page.route('**/api/insights/checklist',route=>route.fulfill({json:[item]}));
 await page.route('**/api/checklists',route=>route.fulfill({json:item}));
 // The checklist screen queries share status after creation. Do not leak to a
 // real backend and mistake its unauthenticated 401 for an expired session.
 await page.route('**/api/checklists/onboarding-1/share',route=>route.fulfill({json:{active:false}}));
 await page.route('**/api/checklists/onboarding-1/complete',route=>{
  item={...item,data:{...item.data,tasks:item.data.tasks.map(t=>({...t,done:route.request().postDataJSON().done}))}};
  return route.fulfill({json:item.data});
 });
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await page.getByRole('button',{name:'Onboarding',exact:true}).click();
 await page.getByRole('button',{name:'Create onboarding checklist',exact:true}).click();
 await expect(page.getByText('def dispatch():',{exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'app.py:12',exact:true})).toHaveAttribute('href',`https://github.com/a/one/blob/${'a'.repeat(40)}/app.py#L12`);
 await page.getByRole('checkbox').check();
 await expect(page.getByText('1 of 1 tasks completed',{exact:true})).toBeVisible();
});

test('public gallery has twenty real report links',async({page})=>{
 await page.goto('/gallery/');
 await expect(page.locator('article a')).toHaveCount(20);
 await page.getByRole('link',{name:'pallets/flask',exact:true}).click();
 await expect(page).toHaveURL(/\/gallery\/pallets-flask\/index\.html$/);
 await expect(page.locator('main')).toContainText(/Generation method: deterministic public-source inspection|AI repository architecture report/);
});
