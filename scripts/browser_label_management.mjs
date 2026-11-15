import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)(process.env.ANNOTAFLOW_PLAYWRIGHT_MODULE);
const sessions=JSON.parse(process.env.ANNOTAFLOW_BROWSER_SESSIONS),fixture=JSON.parse(process.env.ANNOTAFLOW_LABEL_FIXTURE),base=process.argv[2];
const browser=await chromium.launch({headless:true,...(process.env.ANNOTAFLOW_BROWSER_EXECUTABLE?{executablePath:process.env.ANNOTAFLOW_BROWSER_EXECUTABLE}:{})});
const folder=path.resolve('backend/private_data/verification');fs.mkdirSync(folder,{recursive:true});
const pageErrors=[],pages=[];
const idle=page=>page.waitForFunction(()=>window.__labelState?.busy===false);
async function attach(page){await page.waitForSelector('nav');await page.evaluate(async()=>{window.__labelState=(await import('/assets/core/state.js'+new URL(document.querySelector('script[type=module]').src).search)).state;});await idle(page);}
async function pageFor(role,route){const context=await browser.newContext({viewport:{width:1366,height:900}});await context.addCookies([{name:'sessionid',value:sessions[role],url:base}]);const page=await context.newPage();page.on('pageerror',e=>pageErrors.push(e.message));pages.push(page);await page.goto(base+'/#'+route);await attach(page);return page;}
async function reload(page){await page.reload();await attach(page);}
async function go(page,route){await page.evaluate(route=>{location.hash=route;},route);await page.waitForFunction(route=>window.__labelState.route===route,route);await page.waitForLoadState('networkidle');await idle(page);}
const row=(page,key)=>page.locator('.label-row').filter({has:page.locator('code',{hasText:new RegExp('^'+key+'$')})});
async function click(page,selector){await idle(page);await page.locator(selector).click();await idle(page);}
async function submit(page){await idle(page);await page.locator('[role=dialog] button[type=submit]').click();await idle(page);}
async function saveLabel(page){await submit(page);await page.locator('[role=dialog]').waitFor({state:'detached'});await idle(page);}
async function payload(page,value){return page.evaluate(async value=>{const csrf=document.cookie.split('; ').find(s=>s.startsWith('csrftoken='))?.split('=')[1];const r=await fetch('/api/studio/labels',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify(value)});return {status:r.status,body:await r.json()};},value);}
async function add(page,key,name){await click(page,'[data-action="label-management:add"]');await page.locator('[role=dialog] input[name=name]').fill(name);await page.locator('[role=dialog] input[name=key]').fill(key);await saveLabel(page);}
try{
 const page=await pageFor('owner','manual-annotation');
 await click(page,'[data-action="manual-annotation:sentence"][data-label="TOXIC"]');
 await page.locator('summary').filter({hasText:'Thêm ghi chú'}).click();
 await page.locator('#annotation-note').fill('Bản nháp tiếng Việt 😀 không được mất');
 await page.locator('summary').filter({hasText:'Gán nhãn từ / cụm từ'}).click();
 await click(page,'[data-action="manual-annotation:token"][data-index="0"]');
 await page.locator('#span-label').selectOption('TOXIC');
 await click(page,'[data-action="manual-annotation:addSpan"]');
 await click(page,'[data-action="manual-annotation:createLabel"]');
 await page.locator('h1').filter({hasText:'Quản lý nhãn'}).waitFor();await idle(page);
 assert.equal(new URL(page.url()).hash,'#label-management');
 assert.match(await page.locator('.page-heading').innerText(),/Dự án quản lý nhãn thật/);
 await reload(page);
 await add(page,'FEEDBACK','Chủ đề riêng');
 await row(page,'TOXIC').locator('[data-action="label-management:edit"]').click();await idle(page);
 assert.equal(await page.locator('[role=dialog] input[name=key]').getAttribute('readonly'),'');
 await page.locator('[role=dialog] input[name=name]').fill('Độc hại đã sửa');
 await page.locator('[role=dialog] textarea[name=description]').fill('Định nghĩa được lưu sau reload');
 await page.locator('[role=dialog] input[name=order]').fill('20');
 await page.locator('[role=dialog] input[name=color]').evaluate(el=>{el.value='#552288';el.dispatchEvent(new Event('input',{bubbles:true}));});
 assert.match(await page.locator('#label-form-preview').innerText(),/Độc hại đã sửa/);
 await saveLabel(page);await reload(page);
 assert.match(await row(page,'TOXIC').innerText(),/Định nghĩa được lưu sau reload/);
 assert.match(await row(page,'TOXIC').innerText(),/20/);
 assert.equal(await row(page,'TOXIC').locator('[data-action="label-management:delete"]').count(),0);
 await add(page,'UNUSED','Chưa dùng');
 await row(page,'UNUSED').locator('[data-action="label-management:delete"]').click();await idle(page);
 await saveLabel(page);await reload(page);assert.equal(await row(page,'UNUSED').count(),0);
 await row(page,'TOXIC').locator('[data-action="label-management:toggle"]').click();await idle(page);
 await page.locator('#label-status').selectOption('inactive');
 await page.locator('form[data-submit="label-management:filter"] button[type=submit]').click();await idle(page);
 assert.equal(await page.locator('.label-row').count(),1);
 await click(page,'[data-action="label-management:back"]');
 await page.locator('#annotation-note').waitFor({state:'attached'});await idle(page);
 assert.equal(await page.locator('#annotation-note').inputValue(),'Bản nháp tiếng Việt 😀 không được mất');
 assert.match(await page.locator('.annotation-panel .panel-head').innerText(),new RegExp('#'+fixture.manual));
 assert.equal(await page.locator('.span-chip').count(),1);
 assert.equal(await page.locator('[data-action="manual-annotation:save"]').isDisabled(),true);
 assert.match(await page.locator('[role=alert]').innerText(),/ngừng dùng/);
 await click(page,'[data-action="manual-annotation:createLabel"]');
 await page.locator('h1').filter({hasText:'Quản lý nhãn'}).waitFor();await idle(page);
 await row(page,'TOXIC').locator('[data-action="label-management:toggle"]').click();await idle(page);
 await click(page,'[data-action="label-management:back"]');
 await page.locator('#annotation-note').waitFor({state:'attached'});await idle(page);
 await reload(page);
 assert.equal(await page.locator('#annotation-note').inputValue(),'Bản nháp tiếng Việt 😀 không được mất');
 assert.equal(await page.locator('[data-action="manual-annotation:sentence"][data-label="TOXIC"]').getAttribute('aria-pressed'),'true');
 assert.match(await page.locator('[data-action="manual-annotation:sentence"][data-label="TOXIC"]').innerText(),/Độc hại đã sửa/);
 assert.equal(await page.locator('[data-action="manual-annotation:sentence"][data-label="TOXIC"] kbd').innerText(),'3');
 await click(page,'[data-action="manual-annotation:save"]');
 const exported=await (await page.request.get(base+`/api/studio/export?project=${fixture.project}&format=json_sentence&scope=human`)).json();
 const saved=exported.find(r=>r.id===fixture.manual);assert.equal(saved.label,'TOXIC');assert.equal(saved.annotators[0].note,'Bản nháp tiếng Việt 😀 không được mất');
 await go(page,'human-review');
 await page.locator('form[data-submit="collaboration:decision"]').waitFor();
 await page.locator('.hitl-tools').evaluate(el=>el.open=true);
 await page.locator('#hitl-workspace-slot summary').filter({hasText:'Thêm ghi chú'}).click();
 await page.locator('textarea[name=note]').fill('Bản nháp HITL sau đổi bộ nhãn');
 await page.locator('#hitl-workspace-slot summary').filter({hasText:'Gán nhãn từ / cụm từ'}).click();
 await click(page,'[data-action="collaboration:token"][data-index="0"]');
 await page.locator('#hitl-span-label').selectOption('FEEDBACK');
 await click(page,'[data-action="collaboration:addSpan"]');
 await click(page,'[data-action="collaboration:sentence"][data-label="FEEDBACK"]');
 await click(page,'[data-action="collaboration:manageLabels"]');
 await page.locator('h1').filter({hasText:'Quản lý nhãn'}).waitFor();await idle(page);
 await row(page,'FEEDBACK').locator('[data-action="label-management:edit"]').click();await idle(page);
 await page.locator('[role=dialog] input[name=name]').fill('Chủ đề đã sửa');await saveLabel(page);
 await reload(page);await click(page,'[data-action="label-management:back"]');
 await page.locator('form[data-submit="collaboration:decision"]').waitFor();await idle(page);
 assert.equal(await page.locator('input[name=label]').inputValue(),'FEEDBACK');
 assert.equal(await page.locator('textarea[name=note]').inputValue(),'Bản nháp HITL sau đổi bộ nhãn');
 assert.match(await page.locator('[data-action="collaboration:sentence"][data-label="FEEDBACK"]').innerText(),/Chủ đề đã sửa/);
 assert.equal(await page.locator('.span-chip').count(),1);
 await reload(page);
 assert.equal(await page.locator('input[name=label]').inputValue(),'FEEDBACK');
 assert.equal(await page.locator('textarea[name=note]').inputValue(),'Bản nháp HITL sau đổi bộ nhãn');
 assert.equal(await page.locator('.span-chip').count(),1);
 await page.locator('[data-action="collaboration:expose"]').waitFor();await idle(page);
 assert.equal(await page.locator('[data-consensus]').count(),0);
 await click(page,'[data-action="collaboration:expose"]');
 await click(page,'[data-action="collaboration:sentence"][data-label="FEEDBACK"]');
 const pairedExport=await (await page.request.get(base+`/api/studio/export?project=${fixture.project}&format=json_sentence&scope=human`)).json();
 const pairedSaved=pairedExport.find(r=>r.text.startsWith('Bình luận phối hợp'));
 assert.equal(pairedSaved.label,'FEEDBACK');assert.equal(pairedSaved.annotators[0].spans[0].label,'FEEDBACK');
 await go(page,'label-management');
 await row(page,'FEEDBACK').locator('[data-action="label-management:edit"]').click();await idle(page);
 await page.locator('[role=dialog] input[name=name]').fill('Tên đang soạn chưa lưu');
 const catalog=await (await page.request.get(base+`/api/studio/labels?project=${fixture.project}`)).json();
 const label=catalog.labels.find(l=>l.key==='FEEDBACK');
 assert.equal((await payload(page,{...label,project:fixture.project,action:'update',name:'Phiên khác đã lưu'})).status,200);
 await submit(page);
 assert.match(await page.locator('[role=dialog] .form-error-slot').innerText(),/phiên khác/);
 assert.equal(await page.locator('[role=dialog] input[name=name]').inputValue(),'Tên đang soạn chưa lưu');
 await click(page,'[role=dialog] button[type="button"][data-action="ui:close"]');
 await reload(page);
 assert.match(await row(page,'FEEDBACK').innerText(),/Phiên khác đã lưu/);
 assert.match(await page.locator('.panel').filter({hasText:'Tương thích model'}).innerText(),/khác bộ nhãn|cần train|cần đánh giá|không ánh xạ/i);
 for(const width of [360,768,1366]){
  await page.setViewportSize({width,height:900});await page.evaluate(()=>window.scrollTo(0,0));
  if(width<=960)await page.waitForFunction(()=>document.querySelector('#sidebar').getBoundingClientRect().right<=0);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,`Overflow at ${width}`);
  await page.screenshot({path:path.join(folder,`label-management-${width}.png`),fullPage:true,animations:'disabled'});
 }
 const reader=await pageFor('reader','label-management');
 assert.equal(await reader.locator('[data-action="label-management:add"]').count(),0);
 assert.equal(await reader.locator('[data-action="label-management:edit"]').count(),0);
 assert.equal((await payload(reader,{...label,project:fixture.project,action:'update',name:'Không có quyền'})).status,403);
 const other=await pageFor('other','label-management');
 assert.match(await other.locator('.page-heading').innerText(),/Dự án khác/);
 assert.match(await row(other,'FEEDBACK').innerText(),/Nhãn riêng dự án khác/);
 assert.equal((await other.request.get(base+`/api/studio/labels?project=${fixture.project}`)).status(),404);
 assert.deepEqual(pageErrors,[]);
 fs.writeFileSync(path.join(folder,'label-management-browser.json'),JSON.stringify({status:'LABEL_MANAGEMENT_BROWSER_OK',synthetic:true,
  widths:[360,768,1366],flows:['CRUD-and-reload','unused-delete','used-label-disable-reactivate','manual-draft-note-span-preserved',
  'paired-draft-and-current-labels','stale-AI-not-reinterpreted','revision-conflict-form-preserved','permissions','project-isolation'],pageErrors},null,2));
 console.log('LABEL_MANAGEMENT_BROWSER_OK');
}catch(error){for(const [index,page] of pages.entries()){await page.screenshot({path:path.join(folder,`label-failure-${index}.png`),fullPage:true}).catch(()=>{});console.error(await page.locator('#toast-root').innerText().catch(()=>''));}console.error(JSON.stringify(pageErrors));throw error;}finally{await browser.close();}
