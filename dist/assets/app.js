import {state,DEMO,T} from './core/state.js?v=5b47e3c89a10';
import {api,boot} from './core/api.js?v=5b47e3c89a10';
import {configureRefresh,navigate} from './core/events.js?v=5b47e3c89a10';
import {icon,esc,toast,modal,closeModal,btn,nativeRequired} from './core/ui.js?v=5b47e3c89a10';
import * as auth from './features/auth/index.js?v=5b47e3c89a10';
const features={
 projects:()=>import('./features/projects/index.js?v=5b47e3c89a10'),overview:()=>import('./features/overview/index.js?v=5b47e3c89a10'),
 datasets:()=>import('./features/datasets/index.js?v=5b47e3c89a10'),annotation:()=>import('./features/automatic/index.js?v=5b47e3c89a10'),
 models:()=>import('./features/models/index.js?v=5b47e3c89a10'),evaluation:()=>import('./features/evaluation/index.js?v=5b47e3c89a10'),
 exports:()=>import('./features/automatic/exports.js?v=5b47e3c89a10'),'project-settings':()=>import('./features/project-settings/index.js?v=5b47e3c89a10'),
 members:()=>import('./features/members/index.js?v=5b47e3c89a10'),account:()=>import('./features/account/index.js?v=5b47e3c89a10'),
 collaboration:()=>import('./features/collaboration/index.js?v=5b47e3c89a10'),'human-review':()=>import('./features/collaboration/index.js?v=5b47e3c89a10'),
 'manual-annotation':()=>import('./features/annotation/index.js?v=5b47e3c89a10'),'label-management':()=>import('./features/label-management/index.js?v=5b47e3c89a10'),
 budget:()=>import('./features/budget/index.js?v=5b47e3c89a10')
};
const modules=new Map();
async function featureFor(name){
 const key=name==='human-review'?'collaboration':name;
 if(!features[key])return;
 if(!modules.has(key))modules.set(key,features[key]().catch(error=>{modules.delete(key);throw error;}));
 return modules.get(key);
}
import {nav,navigation} from './core/navigation.js?v=5b47e3c89a10';
let signed=false,currentFeature,refreshing=false,routeLoading=false,routeFailure=null,renderedRoute=null,workspaceLoadedAt=0;
const routeName=()=>location.hash.slice(1)||'overview';
async function refresh(route,reload=true,{reuseWorkspace=false}={}){
 if(refreshing)return;refreshing=true;state.loading=true;
 try{if(route){state.route=route;if(location.hash!=='#'+route)history.replaceState(null,'','#'+route);}else if(features[routeName()])state.route=routeName();
 if(!signed){auth.render(['register','forgot','reset'].includes(routeName())?routeName():'login');return;}
 document.body.classList.remove('is-auth');
 if(reload){
  if(!reuseWorkspace||!state.workspace||Date.now()-workspaceLoadedAt>15000){
   try{await boot(state.workspace?.project?.id||localStorage.getItem('annotaflow.project'));}
   catch(error){if(![403,404].includes(error.status))throw error;localStorage.removeItem('annotaflow.project');state.workspace=null;await boot();}
   workspaceLoadedAt=Date.now();
  }
  if(!state.workspace.project){state.route='projects';history.replaceState(null,'','#projects');}
  routeFailure=null;
  if(renderedRoute!==state.route||!document.querySelector('#sidebar')){routeLoading=true;document.querySelector('#app').innerHTML=shell();}
  currentFeature=await featureFor(state.route)||await featureFor('overview');
  await currentFeature.load?.();
  if(features[routeName()]&&routeName()!==state.route)return;
 }
 routeLoading=false;renderedRoute=state.route;
 document.documentElement.lang=state.language;
 document.querySelector('#app').innerHTML=shell();
 await currentFeature?.afterRender?.();
 }catch(e){
  toast(e.message,true);const failedWhileLoading=routeLoading;routeLoading=false;
  if(state.workspace?.project){if(failedWhileLoading){routeFailure=e.message;document.querySelector('#app').innerHTML=shell();}}else startupError(e.message);
 }finally{
  refreshing=false;state.loading=false;
  if(signed&&features[routeName()]&&routeName()!==state.route)queueMicrotask(()=>processLink().catch(e=>toast(e.message,true)));
 }

}
configureRefresh(refresh);
const routeLoader=()=>`<section class="panel route-loading" role="status" aria-live="polite"><span class="route-loading-indicator" aria-hidden="true"></span><div><b>${T('Đang tải nội dung…','Loading content…')}</b><p>${T('Bạn có thể chọn trang khác trong menu.','You can choose another page from the menu.')}</p></div></section>`;
const routeError=()=>`<section class="panel route-loading" role="alert"><div><b>${T('Chưa tải được nội dung','Unable to load content')}</b><p>${esc(routeFailure)}</p><button class="btn" data-action="ui:retryRoute">${T('Thử lại','Try again')}</button></div></section>`;
function startupError(message){document.querySelector('#app').innerHTML=`<main class="startup-error"><h1>AnnotaFlow Studio</h1><p>${esc(message)}</p><button class="btn primary" data-action="ui:retry">${T('Thử lại','Try again')}</button></main>`;}
function shell(){const s=state.workspace,p=s.project;const link=nav.find(x=>x[0]===state.route);return `<aside class="sidebar" id="sidebar"><a class="brand" href="#overview"><span class="brand-mark">a</span><div><div class="brand-name">AnnotaFlow<span class="blue">.</span></div><div class="brand-tag"></div></div></a><button class="workspace-select" data-action="ui:projects"><span class="workspace-icon">${icon('layers',18)}</span><span><b class="workspace-name">${esc(p?.name||T('Chọn dự án','Select project'))}</b><small class="workspace-meta">${T('Đổi dự án','Switch project')} ${icon('chevron',10)}</small></span></button>${navigation(state.route)}<div class="sidebar-bottom"><a class="nav-item" href="#account">${icon('users',17)}${T('Tài khoản','Account')}</a><button class="sidebar-signout" data-action="ui:logout">${icon('logout',15)}${T('Đăng xuất','Sign out')}</button>${DEMO?`<div class="simple-demo-label">${T('Dữ liệu minh họa','Demo data')}</div>`:''}</div></aside><div class="app-shell"><header class="topbar"><div class="flex gap8"><button class="btn icon-btn mobile-menu" data-action="ui:menu" aria-label="Menu">${icon('layers',20)}</button><span class="breadcrumb">Workspace <span>/</span> <strong>${link?T(link[1],link[2]):state.route==='account'?T('Tài khoản','Account'):T('Dự án','Projects')}</strong></span></div><div class="topbar-right"><button class="top-search" data-action="ui:search">${icon('search',15)}<span>${T('Tìm bình luận…','Find comments…')}</span><span class="key">/</span></button><button class="language-switch" data-action="ui:language">${state.language==='vi'?'🇻🇳 VI':'🇬🇧 EN'}</button><a class="user-profile" href="#account"><span class="avatar">${esc((s.user?.name||s.user?.username||'A').slice(0,1))}</span><span class="user-copy"><b>${esc(s.user?.name||s.user?.username||'')}</b><small>${p?.can_manage?T('Quản lý dự án','Project manager'):T('Người gán nhãn','Annotator')}</small></span></a></div></header><main class="main"><div class="workspace-context"><span>${icon('layers',13)}${esc(p?.name||T('Tất cả dự án','All projects'))}</span><div><span class="context-pill">${icon(DEMO?'info':'shield',12)}${DEMO?T('Dữ liệu demo · lưu trên trình duyệt','Demo data · browser storage'):T('Phiên làm việc đã xác thực','Authenticated workspace')}</span>${p?.preferences?.locked||s.preferences?.locked?'<span class="context-pill">🔒 Locked</span>':''}</div></div>${routeFailure?routeError():routeLoading?routeLoader():currentFeature?.render()||''}</main></div>`;}
async function processLink(){if(refreshing)return;let raw=routeName();if(signed&&raw!==state.route)await currentFeature?.beforeLeave?.(raw);if(signed&&features[raw]&&state.route!==raw)window.scrollTo(0,0);if(raw.startsWith('invite=')){sessionStorage.setItem('annotaflow.invite',raw.slice(7));if(!signed){location.hash='login';return;}await acceptInvite();return;}if(raw.startsWith('verify=')){if(DEMO){nativeRequired();return;}try{await api('studio/verify',{token:decodeURIComponent(raw.slice(7))});toast(T('Email đã xác minh. Bạn có thể đăng nhập.','Email verified. You can sign in.'));}catch(e){toast(e.message,true);}location.hash='login';return;}if(raw.startsWith('reset=')){sessionStorage.setItem('annotaflow.reset',decodeURIComponent(raw.slice(6)));location.hash='reset';return;}if(!signed){auth.render(['register','forgot','reset'].includes(raw)?raw:'login');return;}state.route=features[raw]?raw:'overview';await refresh(undefined,true,{reuseWorkspace:true});}
async function acceptInvite(){const token=sessionStorage.getItem('annotaflow.invite');if(!token)return;const r=await api('studio/accept-invite',{token});sessionStorage.removeItem('annotaflow.invite');state.workspace=null;if(r.project)localStorage.setItem('annotaflow.project',r.project);location.hash='overview';}
document.addEventListener('click',async e=>{const el=e.target.closest('[data-action]');if(!el||el.disabled||state.busy||state.loading)return;const action=el.dataset.action;try{
 if(action==='togglePassword'){const i=document.getElementById(el.dataset.target);i.type=i.type==='password'?'text':'password';el.setAttribute('aria-pressed',i.type==='text');el.setAttribute('aria-label',i.type==='text'?(el.dataset.hideLabel||T('Ẩn mật khẩu','Hide password')):(el.dataset.showLabel||T('Hiện mật khẩu','Show password')));return;}
 if(action==='authLanguage'){state.language=el.dataset.lang;localStorage.setItem('annotaflow.language',state.language);auth.render(routeName());return;}
 if(action==='enterDemo'){signed=true;sessionStorage.setItem('annotaflow.demo.entered','1');location.hash='overview';await refresh('overview');return;}
 let [group,name]=action.split(':');group=({project:'projects',settings:'project-settings'})[group]||group;if(group==='ui'){
  if(name==='close')closeModal();if(name==='retry')await start();if(name==='retryRoute')await refresh();if(name==='menu')document.querySelector('#sidebar').classList.toggle('open');
  if(name==='projects')navigate('projects');if(name==='language'){state.language=state.language==='vi'?'en':'vi';localStorage.setItem('annotaflow.language',state.language);await refresh(undefined,false);}
  if(name==='search')modal(T('Tìm bình luận','Find comments'),`<form data-submit="ui:search"><div class="form-row"><label>${T('Nội dung tìm kiếm','Search text')}</label><input name="q" required autofocus></div><button type="submit" class="btn primary">${T('Tìm trong dữ liệu','Search data')}</button></form>`);
  if(name==='help')nativeRequired();
  if(name==='logout'){await api('logout',{});signed=false;sessionStorage.removeItem('annotaflow.demo.entered');localStorage.removeItem('annotaflow.project');state.workspace=null;location.hash='login';auth.render();}return;
 }
 state.busy=true;const feature=await featureFor(group);await feature?.action?.(name,el,e);
 }catch(error){toast(error.message,true);}finally{state.busy=false;currentFeature?.persistDraft?.();}});
document.addEventListener('submit',async e=>{e.preventDefault();const f=e.target;if(state.busy||state.loading)return;state.busy=true;const submit=f.querySelector('[type=submit]');if(submit)submit.disabled=true;try{if(['login-form','register-form','recovery-form'].includes(f.id)){const ok=await auth.submit(f);if(ok){signed=true;await acceptInvite();location.hash='overview';await refresh('overview');}return;}let [group,name]=(f.dataset.submit||'').split(':');group=({project:'projects',settings:'project-settings'})[group]||group;if(group==='ui'&&name==='search'){sessionStorage.setItem('annotaflow.search',f.q.value);closeModal();location.hash='datasets';await refresh('datasets');return;}const feature=await featureFor(group);await feature?.submit?.(name,f,e);}catch(error){const slot=f.querySelector('.form-error-slot,#form-error');if(slot)slot.innerHTML=`<p class="form-error" role="alert">${esc(error.message)}</p>`;else toast(error.message,true);}finally{state.busy=false;if(submit)submit.disabled=false;}});
document.addEventListener('input',()=>currentFeature?.persistDraft?.());
window.addEventListener('beforeunload',()=>currentFeature?.persistDraft?.());
document.addEventListener('change',e=>{currentFeature?.persistDraft?.();return Promise.resolve(currentFeature?.change?.(e)).catch(error=>toast(error.message,true));});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeModal();document.querySelector('#sidebar')?.classList.remove('open');return;}const dialog=document.querySelector('[role=dialog]');if(dialog){if(e.key==='Tab'){const list=[...dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),select,textarea,a[href]')];if(!list.length)return;const first=list[0],last=list.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}return;}if(e.target.closest('input,textarea,select,[contenteditable=true]'))return;if(e.key==='/'&&signed){e.preventDefault();document.querySelector('[data-action="ui:search"]')?.click();}if(['annotation','manual-annotation','human-review','collaboration'].includes(state.route)&&!state.busy&&!refreshing)currentFeature?.keyboard?.(e);});
window.addEventListener('hashchange',()=>processLink().catch(e=>toast(e.message,true)));
async function start(){workspaceLoadedAt=0;try{signed=DEMO?sessionStorage.getItem('annotaflow.demo.entered')==='1':Boolean((await api('session',null,{timeoutMs:15000})).user);await processLink();}catch(e){toast(e.message,true);startupError(e.message);}}
start();

// Refresh job progress without disturbing annotation drafts or focused forms.
let lastJobs='';setInterval(async()=>{if(DEMO||!signed||state.busy||refreshing||state.route!=='datasets'||document.hidden||document.querySelector('[role=dialog]')||document.activeElement?.closest('input,textarea,select'))return;try{const value=await api('studio/jobs?project='+state.workspace.project.id);const signature=JSON.stringify(value.jobs.map(j=>[j.id,j.status,j.progress,j.message]));if(lastJobs&&signature!==lastJobs)await refresh();lastJobs=signature;}catch{}},5000);
setInterval(async()=>{if(DEMO||!signed||state.busy||refreshing||state.route!=='annotation'||document.hidden||document.querySelector('[role=dialog]')||document.activeElement?.closest('input,textarea,select')||!currentFeature?.hasActiveJobs?.())return;await refresh(undefined,true,{reuseWorkspace:true});},3000);
