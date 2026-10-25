import {DEMO,state} from './state.js?v=2a0a4e3abb7b';
import {demoRequest} from './demo.js?v=2a0a4e3abb7b';
import {download} from './ui.js?v=2a0a4e3abb7b';
export async function api(path,body){
 if(DEMO)return demoRequest(path,body);
 const csrf=document.cookie.split('; ').find(s=>s.startsWith('csrftoken='))?.split('=')[1]||'';
 const opts={method:body?'POST':'GET',credentials:'same-origin',headers:{'X-CSRFToken':csrf}};
 if(body instanceof FormData)opts.body=body;else if(body){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body);}
 const r=await fetch('/api/'+path,opts);let data;try{data=await r.json();}catch{throw new Error('Máy chủ không trả JSON. Kiểm tra backend và log tác vụ.');}
 if(!r.ok)throw new Error(data.error||'Không thể thực hiện thao tác ('+r.status+').');return data;
}
export async function boot(id){state.workspace=await api('bootstrap'+(id?'?project='+id:''));return state.workspace;}
export async function exportFile(path,name){
 if(DEMO){const value=await demoRequest(path);download(value.body,name,value.type);return;}
 const response=await fetch('/api/'+path,{credentials:'same-origin'});
 if(!response.ok){let v;try{v=await response.json();}catch{}throw new Error(v?.error||'Không xuất được dữ liệu.');}
 download(await response.blob(),name);
}
export const projectQuery=()=>'?project='+state.workspace.project.id;
