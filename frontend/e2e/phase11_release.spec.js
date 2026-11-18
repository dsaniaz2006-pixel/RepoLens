import {test, expect} from '@playwright/test';

// Phase 11 browser regression (mocked provider failure, real Vite-rendered UI).
// Production OAuth and deployed TLS are deliberately separate live gates.
test('Phase 11 session outage never mounts a private dashboard', async ({page}) => {
 await page.route('**/api/auth/me',r=>r.fulfill({status:503,json:{detail:'Authentication temporarily unavailable'}}));
 await page.goto('/dashboard/');
 await expect(page.getByRole('alert')).toContainText('Unable to check your session');
 await expect(page.getByRole('link',{name:'Go to login'})).toHaveAttribute('href','/login/');
 await expect(page.getByRole('button',{name:'Analyze Repo'})).toHaveCount(0);
});

test('Phase 11 anonymous gallery never claims unapproved reports are reviewed', async ({page}) => {
 await page.goto('/gallery/');
 const cards=page.locator('.catalog article');
 await expect(cards).toHaveCount(20);
 await expect(page.getByRole('link',{name:'Dashboard',exact:true})).toHaveAttribute('href','/dashboard/');
 // A review may eventually be completed; each card must disclose its real status.
 for(const card of await cards.all()){
   await expect(card.locator('p')).toContainText(/Reviewed AI architecture report|Source snapshot — AI review pending/);
 }
});
