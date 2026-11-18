import {test,expect} from '@playwright/test';

const REPO='pallets/flask', SHA='a'.repeat(40);
const citation={path:'src/flask/app.py',start_line:11,end_line:13};

test('saved chat restores after browser reload, follow-up and revision-pinned evidence survive',async({page})=>{
 let chat={id:'section5-1',repository:REPO,revision:SHA,version:0,title:REPO,messages:[],pending:false};
 await page.route('**/api/auth/me',r=>r.fulfill({json:{user:{id:'alice',name:'Alice'},csrf_token:'csrf'}}));
 await page.route('**/api/history',r=>r.fulfill({json:[]}));
 await page.route('**/api/usage',r=>r.fulfill({json:{plan:'free',reset_at:1900000000,usage:{analyze:{used:0,limit:5},ask:{used:0,limit:20},index:{used:0,limit:2}}}}));
 await page.route('**/api/conversations',r=>r.fulfill({json:r.request().method()==='POST'?chat:[chat]}));
 await page.route('**/api/conversations/section5-1/messages',r=>r.fulfill({json:chat}));
 await page.route('**/api/ask',r=>{
   const req=r.request().postDataJSON();
   expect(req.conversation_id).toBe(chat.id);
   expect(req.version).toBe(chat.version);
   expect(req.url).toBe('https://github.com/'+REPO);
   const n=chat.messages.length/2+1;
   chat={...chat,version:chat.version+2,messages:[...chat.messages,
     {id:'u'+n,position:n*2-1,role:'user',content:req.question,citations:[],uncertain:0},
     {id:'a'+n,position:n*2,role:'assistant',content:'Saved answer '+n,citations:[citation],uncertain:0}]};
   return r.fulfill({json:chat});
 });
 await page.goto('/dashboard/');
 await page.getByRole('button',{name:'Conversations',exact:true}).click();
 await page.getByRole('button',{name:'New chat'}).click();
 await page.getByLabel('Your question').fill('Where is the route?');
 await page.getByRole('button',{name:'Send question'}).click();
 await expect(page.getByText('Saved answer 1',{exact:true})).toBeVisible();
 await page.getByLabel('Your question').fill('How does it connect to dispatch?');
 await page.getByRole('button',{name:'Send question'}).click();
 await expect(page.getByText('Saved answer 2',{exact:true})).toBeVisible();
 await expect(page.getByText('Question 2',{exact:true})).toBeVisible();
 await page.reload();
 await page.getByRole('button',{name:'Conversations',exact:true}).click();
 await page.getByLabel('Saved conversations').selectOption(chat.id);
 await expect(page.getByText('Saved answer 1',{exact:true})).toBeVisible();
 await expect(page.getByText('Saved answer 2',{exact:true})).toBeVisible();
 await expect(page.getByRole('link',{name:'src/flask/app.py:L11–L13'}).first())
   .toHaveAttribute('href',`https://github.com/${REPO}/blob/${SHA}/src/flask/app.py#L11-L13`);
});
