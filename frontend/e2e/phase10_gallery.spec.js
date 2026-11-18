import {test, expect} from '@playwright/test';
import {mockAuthenticatedWorkspace} from './helpers/mockAuthenticatedWorkspace.mjs';

// Browser E2E: anonymous gallery and authenticated workspace navigation.
// Mock identity only; publication approval counts are never mocked.
test('Phase 10 anonymous visitor can open the gallery and follow a report',async({page})=>{
 await page.goto('/gallery/');
 await expect(page.getByRole('heading',{name:'Repository library'})).toBeVisible();
 await expect(page.locator('.catalog article')).toHaveCount(20);
 await page.getByRole('link',{name:'pallets/flask',exact:true}).click();
 await expect(page).toHaveURL(/\/gallery\/pallets-flask\/index\.html$/);
 await expect(page.getByText('Source snapshot — AI review pending')).toBeVisible();
 await expect(page.locator('main')).toContainText('Generation method: deterministic public-source inspection');
 await expect(page.getByRole('link',{name:'Try on your repo'})).toHaveAttribute('href','/dashboard/');
 await page.getByRole('button',{name:/Share/}).click();
 await expect(page.getByRole('status')).not.toBeEmpty();
});

test('Phase 10 gallery is integrated in the authenticated dashboard',async({page})=>{
 const unexpected=await mockAuthenticatedWorkspace(page,{user:{id:'alice',name:'Alice'},csrfToken:'csrf'});
 await page.goto('/dashboard/');
 await page.getByRole('button',{name:'Public Gallery'}).click();
 await expect(page).toHaveURL(/\/dashboard\/$/);
 await expect(page.getByRole('heading',{name:'Public Gallery'})).toBeVisible();
 await page.getByRole('button',{name:'Home',exact:true}).click();
 await expect(page.getByRole('heading',{name:/Welcome back/})).toBeVisible();
 expect(unexpected).toEqual([]);
});
