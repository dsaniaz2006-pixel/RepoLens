import {test,expect} from '@playwright/test';
import {mockAuthenticatedWorkspace} from './helpers/mockAuthenticatedWorkspace.mjs';
// Intercept initial offline API requests before React mounts.
// Test-specific API mocks registered later take priority.
test.beforeEach(async ({page}) => {
  await mockAuthenticatedWorkspace(page);
});

// Browser contract checks use fake provider data. Real Ollama, GitHub Advisories
// and the 20 manually reviewed AI reports are separate live acceptance gates.
test.beforeEach(async ({page})=>{
 await page.route('**/api/auth/me',r=>r.fulfill({json:{user:{id:'alice',name:'Alice'},csrf_token:'csrf'}}));
 await page.route('**/api/history',r=>r.fulfill({json:[]}));
 await page.route('**/api/repositories',r=>r.fulfill({json:[]}));
 await page.route('**/api/workspaces',r=>r.fulfill({json:[]}));
});

// Register every test-specific API route before mounting React. Otherwise the
// initial background fetch may hit an unmocked live server and redirect on 401.
async function openWorkspace(page) {
 await page.goto('/dashboard/');
 await expect(page.getByRole('button',{name:'Knowledge Hub',exact:true})).toBeVisible();
}


test('Phase 7 security scan exposes verified and unverified advisory status',async ({page})=>{
 const result={id:'scan-1',kind:'security',updated:1,data:{repository:'pallets/flask',revision:'a'.repeat(40),
   dependencies:[{name:'example',constraint:'==1.2.3',version:'1.2.3',check_status:'checked',
     advisories:[{id:'GHSA-test',cve:'CVE-TEST',severity:'moderate',status:'version_unverified',
                  affected_range:'unsupported-range',fixed_version:'1.3.0',summary:'Manual review required'}],possible_imports:[]}],
   patterns:[],warnings:[],limits:[],coverage:{packages_checked:1,packages_discovered:1,
    advisory_complete:true,unverified_advisories:1},dependency_graph:{nodes:[],edges:[],limits:[]}}};
 await page.route('**/api/insights/security',r=>r.fulfill({json:[result]}));
 await page.route('**/api/security-scan',r=>r.fulfill({json:result}));
 await openWorkspace(page);
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await page.getByRole('button',{name:'Security',exact:true}).click();
 await page.getByRole('button',{name:'Scan dependencies and patterns'}).click();
 await expect(page.getByText('GHSA-test',{exact:false})).toBeVisible();
 await expect(page.getByText('version_unverified',{exact:false})).toBeVisible();
 await expect(page.getByText('not a clean-security certification',{exact:false})).toBeVisible();
});

test('Phase 8 code flow displays source-confirmed route edge and diagram',async ({page})=>{
 const result={id:'flow-1',kind:'flow',updated:1,data:{repository:'pallets/flask',revision:'a'.repeat(40),
   mermaid:'flowchart TD\n a[route] --> b[handler]',limits:[],edges:[{
     from:'route[GET /items]',to:'src/flask/app.py:items',link_type:'CONFIRMED',
     path:'src/flask/app.py',line:42,snippet:'@app.get("/items")'}]}};
 await page.route('**/api/insights/flow',r=>r.fulfill({json:[result]}));
 await page.route('**/api/flow',r=>r.fulfill({json:result}));
 await openWorkspace(page);
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await page.getByRole('button',{name:'Code Flow',exact:true}).click();
 await page.getByRole('button',{name:'Trace source flow'}).click();
 await expect(page.getByRole('img',{name:'Source call-flow diagram'})).toBeVisible();
 // The SVG also contains an accessible <title> that is intentionally not
 // visible. Assert the actual evidence row rather than that hidden title.
 await expect(page.locator('table tbody tr').filter({hasText:'route[GET /items]'})).toBeVisible();
 await expect(page.getByRole('link',{name:'src/flask/app.py:42'})).toHaveAttribute('href',
  'https://github.com/pallets/flask/blob/'+ 'a'.repeat(40) +'/src/flask/app.py#L42');
});

test('Phase 6 assigned onboarding progress persists after a delayed server save',async ({page})=>{
 const wid='test-workspace';
 const row={id:'assignment-1',data:{active:true,assignee:'alice',checklist_version:'a'.repeat(64),
    snapshot:{repository:'o/r',revision:'a'.repeat(40),tasks:[{
      id:'task-1',phase:'Day 1',task:'Read source',path:'app.py',line:1,done:false}]}}};
 await page.route('**/api/workspaces',r=>r.fulfill({json:[{id:wid,role:'member',data:{name:'Test team'}}]}));
 await page.route(`**/api/workspaces/${wid}`,r=>r.fulfill({json:{role:'member',members:[{user:'alice',role:'member'}],repositories:[],pins:[]}}));
 await page.route(`**/api/workspaces/${wid}/assignments`,async route=>{
   if(route.request().method()==='POST'){
     const body=route.request().postDataJSON();
     row.data.snapshot.tasks[0].done=body.done;
     await new Promise(resolve=>setTimeout(resolve,400));
     return route.fulfill({json:row});
   }
   return route.fulfill({json:[row]});
 });
 await page.route(`**/api/workspaces/${wid}/assignments/assignment-1/complete`,async route=>{
   const body=route.request().postDataJSON();
   row.data.snapshot.tasks[0].done=body.done;
   await new Promise(resolve=>setTimeout(resolve,400));
   return route.fulfill({json:row});
 });
 await page.route('**/api/insights/checklist',r=>r.fulfill({json:[]}));
 await page.route('**/api/conversations',r=>r.fulfill({json:[]}));
 await openWorkspace(page);
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await page.getByRole('button',{name:'Teams',exact:true}).click();
 await expect(page.getByLabel('Your workspaces')).toBeVisible();
 await page.getByLabel('Your workspaces').selectOption(wid);
 await expect(page.getByText('0/1 complete')).toBeVisible();
 const saved=page.waitForResponse(r=>r.url().endsWith('/assignments/assignment-1/complete')&&r.request().method()==='POST');
 await page.getByRole('checkbox').check();
 // Optimistic checkbox update must be visible while the response is delayed.
 await expect(page.getByRole('checkbox')).toBeChecked();
 await expect(page.getByText('1/1 complete')).toBeVisible();
 await saved;
 await page.reload();
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await page.getByRole('button',{name:'Teams',exact:true}).click();
 await page.getByLabel('Your workspaces').selectOption(wid);
 await expect(page.getByText('1/1 complete')).toBeVisible();
 await expect(page.getByRole('checkbox')).toBeChecked();
});

test('Phase 9 approved local snapshot uses the local API, not public ask',async ({page})=>{
 const publicAskRequests=[];
 await page.route('**/api/ask',route=>{
   publicAskRequests.push(route.request().url());
   return route.fulfill({status:500,json:{detail:'Public API must not be used for local questions'}});
 });
 const snapshot={id:'local-1',data:{alias:'demo',repository:'local/abc',revision:'b'.repeat(64),limits:[]}};
 await page.route('**/api/local/repositories',r=>r.fulfill({json:{approved:['demo'],indexes:[snapshot]}}));
 await page.route('**/api/local/repositories/local-1/ask',r=>{
   expect(r.request().postDataJSON().question).toBe('Where is main?');
   return r.fulfill({json:{answer:'main() is in main.py',uncertain:false,citations:[
     {path:'main.py',start_line:1,end_line:2}]}});
 });
 await openWorkspace(page);
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await page.getByRole('button',{name:'Local Repositories',exact:true}).click();
 await expect(page.getByRole('button',{name:'Local Repositories',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(page.getByRole('heading',{name:'Private local repository'})).toBeVisible();
 await expect(page.getByLabel('Saved snapshot')).toBeVisible();
 await page.getByLabel('Saved snapshot').selectOption('local-1');
 await page.getByLabel('Question').fill('Where is main?');
 await page.getByRole('button',{name:'Ask local repository'}).click();
 await expect(page.getByText('main() is in main.py')).toBeVisible();
 await expect(page.getByText('main.py:1–2')).toBeVisible();
 expect(publicAskRequests).toHaveLength(0);
});


test('Knowledge Hub tabs stay responsive while a background refresh is pending',async ({page})=>{
 await page.route('**/api/repositories',async r=>{
   await new Promise(resolve=>setTimeout(resolve,1200));
   return r.fulfill({json:[]});
 });
 await page.route('**/api/local/repositories',r=>r.fulfill({json:{approved:['demo'],indexes:[]}}));
 await openWorkspace(page);
 await page.getByRole('button',{name:'Knowledge Hub',exact:true}).click();
 await page.getByRole('button',{name:'Local Repositories',exact:true}).click();
 await expect(page.getByRole('button',{name:'Local Repositories',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(page.getByLabel('Saved snapshot')).toBeVisible();
});
