import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const {chromium}=createRequire(import.meta.url)(process.env.ANNOTAFLOW_PLAYWRIGHT_MODULE);
const browser=await chromium.launch({headless:true,...(process.env.ANNOTAFLOW_BROWSER_EXECUTABLE?{executablePath:process.env.ANNOTAFLOW_BROWSER_EXECUTABLE}:{})});
const context=await browser.newContext({viewport:{width:1366,height:950}}),base=process.argv[2];
await context.addCookies([{name:'sessionid',value:process.env.ANNOTAFLOW_STARTUP_SESSION,url:base}]);
const page=await context.newPage(),requests=[],errors=[],externalRequests=[];
await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==new URL(base).origin){externalRequests.push(route.request().url());return route.abort();}return route.continue();});
page.on('request',r=>requests.push(new URL(r.url()).pathname+new URL(r.url()).search));
page.on('pageerror',e=>errors.push(e.message));
const folder=path.resolve('backend/private_data/verification');
const ready=()=>page.waitForFunction(()=>document.querySelector('#sidebar')&&!document.querySelector('.route-loading')&&document.querySelector('.main h1,.main .panel'));
async function go(route){await page.locator('.advanced-nav').evaluate(el=>el.open=true);await page.locator(`#sidebar a[href="#${route}"]`).click();await page.waitForFunction(route=>document.querySelector(`#sidebar a[href="#${route}"]`)?.classList.contains('active')&&!document.querySelector('.route-loading'),route);await ready();}
try{
 const started=Date.now();await page.goto(base+'/#overview');await ready();
 const startupMs=Date.now()-started,bootstrapCount=requests.filter(r=>r.startsWith('/api/bootstrap?')).length;
 assert.equal(bootstrapCount,1);assert.ok(requests.some(r=>r.includes('compact=1')));
 assert.equal(requests.some(r=>r.includes('/features/collaboration/')||r.includes('/features/evaluation/')||r.includes('/core/demo.js')),false);
 const initialModules=requests.filter(r=>r.includes('.js')).length;
 assert.deepEqual(externalRequests,[],'Native startup must work without external font/CDN requests');
 await go('datasets');await go('models');await go('project-settings');
 assert.equal(requests.filter(r=>r.startsWith('/api/bootstrap?')).length,bootstrapCount);
 // Metadata remains responsive while the requested page is still loading.
 let release;const blocked=new Promise(resolve=>release=resolve);
 await page.route('**/api/studio/labels?*',async route=>{await blocked;await route.continue();});
 await page.locator('#sidebar a[href="#label-management"]').click();
 await page.locator('.route-loading').waitFor();
 assert.equal(await page.locator('#sidebar').isVisible(),true);
 await page.locator('#sidebar a[href="#datasets"]').click();
 release();await page.waitForFunction(()=>location.hash==='#datasets'&&document.querySelector('#sidebar a[href="#datasets"]')?.classList.contains('active')&&!document.querySelector('.route-loading'));
 await page.unroute('**/api/studio/labels?*');
 await go('evaluation');assert.ok(requests.some(r=>r.startsWith('/api/model-reports?')));
 await page.route('**/api/bootstrap?*',route=>route.fulfill({status:503,contentType:'application/json',body:'{"error":"Fixture startup failure"}'}));
 await page.reload();await page.locator('.startup-error').waitFor();
 assert.equal(await page.locator('.initial-loader').count(),0);
 await page.unroute('**/api/bootstrap?*');
 await page.locator('[data-action="ui:retry"]').click();await ready();
 assert.equal(await page.locator('#sidebar').isVisible(),true);
 const demoContext=await browser.newContext();const demoPage=await demoContext.newPage();
 await demoPage.route(base+'/',async route=>{const response=await route.fetch();await route.fulfill({response,body:(await response.text()).replace('data-mode="api"','data-mode="demo"')});});
 await demoPage.goto(base+'/');await demoPage.locator('[data-action="enterDemo"]').click();
 await demoPage.locator('.simple-steps').waitFor();
 assert.equal(await demoPage.locator('#sidebar').isVisible(),true);await demoContext.close();
 assert.deepEqual(errors,[]);
 fs.writeFileSync(path.join(folder,'startup-browser.json'),JSON.stringify({status:'STARTUP_BROWSER_OK',synthetic:true,startupMs,initialModules,bootstrapCount,externalRequests,flows:['compact-startup','lazy-route-modules','self-hosted-fonts-with-external-network-blocked','no-demo-modules-in-native','reuse-metadata-on-navigation','shell-visible-while-loading','latest-navigation-wins','evaluation-loads-reports-on-demand','startup-error-and-retry','static-demo-lazy-import-works'],pageErrors:errors},null,2));
 console.log('STARTUP_BROWSER_OK');
}catch(error){await page.screenshot({path:path.join(folder,'startup-browser-failure.png'),fullPage:true}).catch(()=>{});console.error(JSON.stringify({requests,errors,body:await page.locator('main').innerText().catch(()=>''),toasts:await page.locator('#toast-root').innerText().catch(()=>''),url:page.url()}));throw error;}
finally{await browser.close();}
