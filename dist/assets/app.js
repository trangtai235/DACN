import {state,DEMO,T} from './core/state.js?v=2a0a4e3abb7b';
import {api,boot} from './core/api.js?v=2a0a4e3abb7b';
import {configureRefresh,navigate} from './core/events.js?v=2a0a4e3abb7b';
import {icon,esc,toast,modal,closeModal,btn,nativeRequired} from './core/ui.js?v=2a0a4e3abb7b';
import * as auth from './features/auth/index.js?v=2a0a4e3abb7b';
import * as projects from './features/projects/index.js?v=2a0a4e3abb7b';
import * as overview from './features/overview/index.js?v=2a0a4e3abb7b';
import * as datasets from './features/datasets/index.js?v=2a0a4e3abb7b';
import * as annotation from './features/annotation/index.js?v=2a0a4e3abb7b';
import * as research from './features/research/index.js?v=2a0a4e3abb7b';
import * as models from './features/models/index.js?v=2a0a4e3abb7b';
import * as evaluation from './features/evaluation/index.js?v=2a0a4e3abb7b';
import * as quality from './features/quality/index.js?v=2a0a4e3abb7b';
import * as versions from './features/versions/index.js?v=2a0a4e3abb7b';
import * as exportsPage from './features/exports/index.js?v=2a0a4e3abb7b';
import * as settings from './features/project-settings/index.js?v=2a0a4e3abb7b';
import * as members from './features/members/index.js?v=2a0a4e3abb7b';
import * as account from './features/account/index.js?v=2a0a4e3abb7b';
const features={projects,overview,datasets,annotation,research,models,evaluation,quality,versions,exports:exportsPage,'project-settings':settings,members,account};
import {nav,navigation} from './core/navigation.js?v=2a0a4e3abb7b';
let signed=false,currentFeature,refreshing=false;
const routeName=()=>location.hash.slice(1)||'overview';
async function refresh(route,reload=true){
 if(refreshing)return;refreshing=true;
 try{if(route){state.route=route;if(location.hash!=='#'+route)history.replaceState(null,'','#'+route);}else if(features[routeName()])state.route=routeName();
 if(!signed){auth.render(['register','forgot','reset'].includes(routeName())?routeName():'login');return;}
 document.body.classList.remove('is-auth');
 if(reload){try{await boot(state.workspace?.project?.id||localStorage.getItem('annotaflow.project'));}catch(error){localStorage.removeItem('annotaflow.project');state.workspace=null;await boot();}if(!state.workspace.project)state.route='projects';currentFeature=features[state.route]||overview;await currentFeature.load?.();}
 document.documentElement.lang=state.language;
 document.querySelector('#app').innerHTML=shell();
 }catch(e){toast(e.message,true);if(!state.workspace)document.querySelector('#app').innerHTML=`<main class="startup-error"><h1>AnnotaFlow Studio</h1><p>${esc(e.message)}</p><button class="btn primary" data-action="ui:retry">${T('Thử lại','Try again')}</button></main>`;}finally{refreshing=false;}
}
configureRefresh(refresh);
function shell(){const s=state.workspace,p=s.project;const link=nav.find(x=>x[0]===state.route);return `<aside class="sidebar" id="sidebar"><a class="brand" href="#overview"><span class="brand-mark">a</span><div><div class="brand-name">AnnotaFlow<span class="blue">.</span></div><div class="brand-tag"></div></div></a><button class="workspace-select" data-action="ui:projects"><span class="workspace-icon">${icon('layers',18)}</span><span><b class="workspace-name">${esc(p?.name||T('Chọn dự án','Select project'))}</b><small class="workspace-meta">${T('Đổi dự án','Switch project')} ${icon('chevron',10)}</small></span></button>${navigation(state.route)}<div class="sidebar-bottom"><a class="nav-item" href="#account">${icon('users',17)}${T('Tài khoản','Account')}</a><button class="sidebar-signout" data-action="ui:logout">${icon('logout',15)}${T('Đăng xuất','Sign out')}</button>${DEMO?`<div class="simple-demo-label">${T('Dữ liệu minh họa','Demo data')}</div>`:''}</div></aside><div class="app-shell"><header class="topbar"><div class="flex gap8"><button class="btn icon-btn mobile-menu" data-action="ui:menu" aria-label="Menu">${icon('layers',20)}</button><span class="breadcrumb">Workspace <span>/</span> <strong>${link?T(link[1],link[2]):state.route==='account'?T('Tài khoản','Account'):T('Dự án','Projects')}</strong></span></div><div class="topbar-right"><button class="top-search" data-action="ui:search">${icon('search',15)}<span>${T('Tìm bình luận…','Find comments…')}</span><span class="key">/</span></button><button class="language-switch" data-action="ui:language">${state.language==='vi'?'🇻🇳 VI':'🇬🇧 EN'}</button><a class="user-profile" href="#account"><span class="avatar">${esc((s.user?.name||s.user?.username||'A').slice(0,1))}</span><span class="user-copy"><b>${esc(s.user?.name||s.user?.username||'')}</b><small>${p?.can_manage?T('Quản lý dự án','Project manager'):T('Người gán nhãn','Annotator')}</small></span></a></div></header><main class="main"><div class="workspace-context"><span>${icon('layers',13)}${esc(p?.name||T('Tất cả dự án','All projects'))}</span><div><span class="context-pill">${icon(DEMO?'info':'shield',12)}${DEMO?T('Dữ liệu demo · lưu trên trình duyệt','Demo data · browser storage'):T('Phiên làm việc đã xác thực','Authenticated workspace')}</span>${p?.preferences?.locked||s.preferences?.locked?'<span class="context-pill">🔒 Locked</span>':''}</div></div>${currentFeature?.render()||''}</main></div>`;}
async function processLink(){let raw=routeName();if(signed&&features[raw]&&state.route!==raw)window.scrollTo(0,0);if(raw.startsWith('invite=')){sessionStorage.setItem('annotaflow.invite',raw.slice(7));if(!signed){location.hash='login';return;}await acceptInvite();return;}if(raw.startsWith('verify=')){if(DEMO){nativeRequired();return;}try{await api('studio/verify',{token:decodeURIComponent(raw.slice(7))});toast(T('Email đã xác minh. Bạn có thể đăng nhập.','Email verified. You can sign in.'));}catch(e){toast(e.message,true);}location.hash='login';return;}if(raw.startsWith('reset=')){sessionStorage.setItem('annotaflow.reset',decodeURIComponent(raw.slice(6)));location.hash='reset';return;}if(!signed){auth.render(['register','forgot','reset'].includes(raw)?raw:'login');return;}state.route=features[raw]?raw:'overview';await refresh();}
async function acceptInvite(){const token=sessionStorage.getItem('annotaflow.invite');if(!token)return;const r=await api('studio/accept-invite',{token});sessionStorage.removeItem('annotaflow.invite');state.workspace=null;if(r.project)localStorage.setItem('annotaflow.project',r.project);location.hash='overview';}
document.addEventListener('click',async e=>{const el=e.target.closest('[data-action]');if(!el||el.disabled||state.busy)return;const action=el.dataset.action;try{
 if(action==='togglePassword'){const i=document.getElementById(el.dataset.target);i.type=i.type==='password'?'text':'password';el.setAttribute('aria-pressed',i.type==='text');el.setAttribute('aria-label',i.type==='text'?(el.dataset.hideLabel||T('Ẩn mật khẩu','Hide password')):(el.dataset.showLabel||T('Hiện mật khẩu','Show password')));return;}
 if(action==='authLanguage'){state.language=el.dataset.lang;localStorage.setItem('annotaflow.language',state.language);auth.render(routeName());return;}
 if(action==='enterDemo'){signed=true;sessionStorage.setItem('annotaflow.demo.entered','1');location.hash='overview';await refresh('overview');return;}
 let [group,name]=action.split(':');group=({project:'projects',settings:'project-settings'})[group]||group;if(group==='ui'){
  if(name==='close')closeModal();if(name==='retry')await start();if(name==='menu')document.querySelector('#sidebar').classList.toggle('open');
  if(name==='projects')navigate('projects');if(name==='language'){state.language=state.language==='vi'?'en':'vi';localStorage.setItem('annotaflow.language',state.language);await refresh(undefined,false);}
  if(name==='search')modal(T('Tìm bình luận','Find comments'),`<form data-submit="ui:search"><div class="form-row"><label>${T('Nội dung tìm kiếm','Search text')}</label><input name="q" required autofocus></div><button type="submit" class="btn primary">${T('Tìm trong dữ liệu','Search data')}</button></form>`);
  if(name==='help')nativeRequired();
  if(name==='logout'){await api('logout',{});signed=false;sessionStorage.removeItem('annotaflow.demo.entered');localStorage.removeItem('annotaflow.project');state.workspace=null;location.hash='login';auth.render();}return;
 }
 state.busy=true;await features[group]?.action?.(name,el,e);
 }catch(error){toast(error.message,true);}finally{state.busy=false;}});
document.addEventListener('submit',async e=>{e.preventDefault();const f=e.target;if(state.busy)return;state.busy=true;const submit=f.querySelector('[type=submit]');if(submit)submit.disabled=true;try{if(['login-form','register-form','recovery-form'].includes(f.id)){const ok=await auth.submit(f);if(ok){signed=true;await acceptInvite();location.hash='overview';await refresh('overview');}return;}let [group,name]=(f.dataset.submit||'').split(':');group=({project:'projects',settings:'project-settings'})[group]||group;if(group==='ui'&&name==='search'){sessionStorage.setItem('annotaflow.search',f.q.value);closeModal();location.hash='datasets';await refresh('datasets');return;}await features[group]?.submit?.(name,f);}catch(error){const slot=f.querySelector('.form-error-slot,#form-error');if(slot)slot.innerHTML=`<p class="form-error" role="alert">${esc(error.message)}</p>`;else toast(error.message,true);}finally{state.busy=false;if(submit)submit.disabled=false;}});
document.addEventListener('change',e=>Promise.resolve(currentFeature?.change?.(e)).catch(error=>toast(error.message,true)));
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeModal();document.querySelector('#sidebar')?.classList.remove('open');return;}const dialog=document.querySelector('[role=dialog]');if(dialog){if(e.key==='Tab'){const list=[...dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),select,textarea,a[href]')];if(!list.length)return;const first=list[0],last=list.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}return;}if(e.target.closest('input,textarea,select,[contenteditable=true]'))return;if(e.key==='/'&&signed){e.preventDefault();document.querySelector('[data-action="ui:search"]')?.click();}if(state.route==='annotation'&&!state.busy)annotation.keyboard(e);});
window.addEventListener('hashchange',()=>processLink().catch(e=>toast(e.message,true)));
async function start(){try{signed=DEMO?sessionStorage.getItem('annotaflow.demo.entered')==='1':Boolean((await api('session')).user);await processLink();}catch(e){toast(e.message,true);auth.render();}}
start();

// Refresh job progress without disturbing annotation drafts or focused forms.
let lastJobs='';setInterval(async()=>{if(DEMO||!signed||state.busy||refreshing||state.route!=='datasets'||document.hidden||document.querySelector('[role=dialog]')||document.activeElement?.closest('input,textarea,select'))return;try{const value=await api('studio/jobs?project='+state.workspace.project.id);const signature=JSON.stringify(value.jobs.map(j=>[j.id,j.status,j.progress,j.message]));if(lastJobs&&signature!==lastJobs)await refresh();lastJobs=signature;}catch{}},5000);
