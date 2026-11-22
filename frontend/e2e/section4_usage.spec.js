import {test,expect} from '@playwright/test';

test('usage widget shows real API counters and refreshes after expensive request',async({page})=>{
 let used=1;
 await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
 await page.route('**/api/auth/me',r=>r.fulfill({json:{user:{id:'alice',name:'Alice'},csrf_token:'csrf'}}));
 await page.route('**/api/history',r=>r.fulfill({json:[]}));
 await page.route('**/api/usage',r=>r.fulfill({json:{plan:'free',reset_at:1890000000,usage:{analyze:{used,limit:5},ask:{used:0,limit:20},index:{used:0,limit:2}}}}));
 await page.goto('/dashboard/');
 await expect(page.getByRole('heading',{name:'Your AI usage'})).toBeVisible();
 await expect(page.getByRole('progressbar',{name:'Repository analysis'})).toHaveAttribute('aria-valuenow','1');
 used=3;
 await page.getByRole('button',{name:'Refresh AI usage'}).click();
 await expect(page.getByRole('progressbar',{name:'Repository analysis'})).toHaveAttribute('aria-valuenow','3');
});

test('usage widget remains readable when usage endpoint errors',async({page})=>{
 await page.route('**/api/health', r => r.fulfill({ json: { status: 'ok' } }));
 await page.route('**/api/auth/me',r=>r.fulfill({json:{user:{id:'alice',name:'Alice'},csrf_token:'csrf'}}));
 await page.route('**/api/history',r=>r.fulfill({json:[]}));
 await page.route('**/api/usage',r=>r.fulfill({status:503,json:{detail:'Usage temporarily unavailable'}}));
 await page.goto('/dashboard/');
 await expect(page.getByRole('alert').filter({hasText:'Usage temporarily unavailable'})).toBeVisible();
});
