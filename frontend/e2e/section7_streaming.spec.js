import {test, expect} from '@playwright/test';

const RESPONSE={
  analysis:{project_summary:'Streamed analysis completed.',repository_map:[],tech_stack:[],reading_path:[],entry_points:[],
    code_flow:{summary:'Test flow',supported:true,steps:[]},limitations:[]},
  metadata:{full_name:'pallets/flask',html_url:'https://github.com/pallets/flask',default_branch:'main',language:'Python'},
  tree:[],truncated:false,revision:'a'.repeat(40),evidence_paths:[]
};
test('authenticated analysis uses SSE progress and renders final report',async({page})=>{
  let streams=0,legacy=0;
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me',route=>route.fulfill({json:{user:{id:'test-user',name:'Test User'},csrf_token:'validcsrf'}}));
  await page.route('**/api/history',route=>route.fulfill({json:[]}));
  await page.route('**/api/usage',route=>route.fulfill({json:{plan:'free',reset_at:1900000000,
    usage:{analyze:{used:0,limit:5},ask:{used:0,limit:20},index:{used:0,limit:2}}}}));
  await page.route('**/api/analyze/stream',route=>{
    streams++;
    expect(route.request().method()).toBe('POST');
    expect(route.request().headers()['x-csrf-token']).toBe('validcsrf');
    return route.fulfill({status:200,headers:{'Content-Type':'text/event-stream'},
      body:'data: '+JSON.stringify({status:'progress',message:'Fetching repository tree…'})+'\n\n'
         +'data: '+JSON.stringify({status:'done',result:RESPONSE})+'\n\n'});
  });
  await page.route('**/api/analyze',route=>{legacy++;return route.abort()});
  await page.goto('/dashboard/');
  await page.getByRole('button',{name:'Analyze Repo'}).first().click();
  await page.getByRole('button',{name:'Analyze Repository'}).click();
  await expect(page.getByText('Streamed analysis completed.')).toBeVisible();
  expect(streams).toBe(1);
  expect(legacy).toBe(0);
});

test('analyze shows a safe 429 quota message without confusing it for a stream',async({page})=>{
  await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
  await page.route('**/api/auth/me',route=>route.fulfill({json:{user:{id:'user',name:'User'},csrf_token:'csrf'}}));
  await page.route('**/api/history',route=>route.fulfill({json:[]}));
  await page.route('**/api/usage',route=>route.fulfill({json:{plan:'free',usage:{analyze:{used:5,limit:5},ask:{used:0,limit:20},index:{used:0,limit:2}}}}));
  await page.route('**/api/analyze/stream',route=>route.fulfill({status:429,contentType:'application/json',body:JSON.stringify({detail:'Daily AI usage limit reached'})}));
  await page.goto('/dashboard/');
  await page.getByRole('button',{name:'Analyze Repo'}).first().click();
  await page.getByRole('button',{name:'Analyze Repository'}).click();
  await expect(page.getByRole('alert')).toContainText('Daily AI usage limit reached');
});
