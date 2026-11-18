import {test,expect} from '@playwright/test';

test('Relay-inspired homepage is reachable and keeps product authentication links',async({page})=>{
 await page.goto('/');
 await expect(page.getByRole('heading',{name:/The code makes more sense now/})).toBeVisible();
 await expect(page.getByRole('link',{name:/Start exploring/})).toHaveAttribute('href','/signup/');
 await expect(page.getByRole('navigation',{name:'Main navigation'}).getByRole('link',{name:/Log in/})).toHaveAttribute('href','/login/');
 await expect(page.getByRole('navigation',{name:'Main navigation'}).getByRole('link',{name:'Public gallery'})).toHaveAttribute('href','/gallery/');
 await expect(page.locator('.glass-frame')).toBeVisible();
 const background=await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundColor);
 expect(background).toBe('rgb(18, 20, 22)');
});

test('hero source preview tabs display appropriate illustration without API requests',async({page})=>{
 const api=[];page.on('request',req=>{if(req.url().includes('/api/'))api.push(req.url());});
 await page.goto('/');
 await page.getByRole('button',{name:'Code flow'}).click();
 await expect(page.locator('[data-panel="flow"]')).toBeVisible();
 await expect(page.locator('[data-panel="architecture"]')).toBeHidden();
 await expect(page.getByRole('button',{name:'Code flow'})).toHaveAttribute('aria-pressed','true');
 await page.getByRole('button',{name:'Evidence'}).click();
 await expect(page.locator('[data-panel="evidence"]')).toBeVisible();
 await expect(page.getByText('src/flask/app.py')).toBeVisible();
 expect(api).toEqual([]);
});

test('landing responds on narrow screens without horizontal overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});
 await page.goto('/');
 await expect(page.getByRole('heading',{name:/The code makes more sense now/})).toBeVisible();
 await expect(page.getByRole('link',{name:/Start exploring/})).toBeVisible();
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth > innerWidth+2);
 expect(overflow).toBe(false);
 await expect(page.getByRole('navigation',{name:'Product resources'})).toBeVisible();
});

test('reduced-motion preference preserves all content and functional tabs',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/');
 await expect(page.getByRole('heading',{name:/The code makes more sense now/})).toBeVisible();
 await page.getByRole('button',{name:'Evidence'}).click();
 await expect(page.locator('[data-panel="evidence"]')).toBeVisible();
 const animation=await page.locator('.live-dot').evaluate(el=>getComputedStyle(el).animationName);
 expect(animation).toBe('none');
});

test('3D depth scene renders as decoration and follows a fine pointer',async({page})=>{
 await page.setViewportSize({width:1440,height:900});
 await page.goto('/');
 await expect(page.locator('.hero-depth-field')).toBeVisible();
 const canvas=page.locator('#stream-canvas');
 await expect(canvas).toBeVisible();
 expect(await canvas.evaluate(node=>node.width>500 && node.height>300)).toBe(true);
 const art=page.locator('.hero-art');
 const box=await art.boundingBox();
 await page.mouse.move(box.x + box.width*.84,box.y + box.height*.25);
 await expect.poll(()=>art.evaluate(node=>node.style.getPropertyValue('--tilt-y'))).not.toBe('');
 const transform=await page.locator('.glass-frame').evaluate(el=>getComputedStyle(el).transform);
 expect(transform).not.toBe('none');
 await page.mouse.move(3,3);
 await expect.poll(()=>art.evaluate(node=>node.style.getPropertyValue('--tilt-y'))).toBe('');
});

test('reduced-motion disables interactive 3D parallax but keeps source preview usable',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.goto('/');
 const art=page.locator('.hero-art');
 const box=await art.boundingBox();
 await page.mouse.move(box.x+box.width*.8,box.y+box.height*.2);
 expect(await art.evaluate(node=>node.style.getPropertyValue('--tilt-y'))).toBe('');
 await page.getByRole('button',{name:'Code flow'}).click();
 await expect(page.locator('[data-panel="flow"]')).toBeVisible();
});
