import {test,expect} from '@playwright/test';

// Runs against Vite's own dedicated test server, not production Neon/Gemini.
for(const [route,heading] of [
 ['/docs/','Start from source.'],
 ['/demo/','Explore before you analyze.'],
 ['/examples/','See the evidence.'],
 ['/pricing/','Use RepoLens without billing.'],
 ['/blog/','How RepoLens finds its footing.']
]) {
 test(`public product page ${route} is accessible and navigable`,async({page})=>{
  await page.goto(route);
  await expect(page.locator('main h1')).toHaveText(heading);
  await expect(page.getByRole('navigation',{name:'Public site navigation'})).toBeVisible();
  await expect(page.getByRole('link',{name:'Workspace'})).toHaveAttribute('href','/dashboard/');
  await page.getByRole('link',{name:'RepoLens home'}).click();
  await expect(page).toHaveURL('http://127.0.0.1:5175/');
 });
}
test('anonymous user follows all public navigation from landing',async({page})=>{
 await page.goto('/');
 for (const route of ['docs','demo','examples','pricing','blog']) {
  await page.getByRole('navigation',{name:'Product resources'}).getByRole('link',{name:route==='pricing'?'Access':route.charAt(0).toUpperCase()+route.slice(1)}).click();
  await expect(page).toHaveURL(new RegExp(`/${route}/$`));
  await page.goto('/');
 }
});
test('public demo is read-only and no AI API calls occur',async({page})=>{
 const apiCalls=[];
 page.on('request',request=>{if(request.url().includes('/api/')) apiCalls.push(request.url())});
 await page.goto('/demo/');
 await expect(page.getByText('No live AI requests are initiated from this public demo.')).toBeVisible();
 await expect(page.getByRole('link',{name:'Open sample report'})).toHaveAttribute('href','/reports/pallets-flask-report.md');
 expect(apiCalls).toEqual([]);
});
test('mobile public navigation and content remain visible',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto('/docs/');
 await expect(page.getByRole('navigation',{name:'Public site navigation'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Start from source.'})).toBeVisible();
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth > innerWidth + 2);
 expect(overflow).toBe(false);
});
