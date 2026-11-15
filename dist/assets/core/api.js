import {DEMO,state} from './state.js?v=5b47e3c89a10';
import {download} from './ui.js?v=5b47e3c89a10';
export async function api(path,body,options={}){
 if(DEMO){const {demoRequest}=await import('./demo.js?v=5b47e3c89a10');return demoRequest(path,body);}
 const csrf=document.cookie.split('; ').find(s=>s.startsWith('csrftoken='))?.split('=')[1]||'';
 const opts={method:body?'POST':'GET',credentials:'same-origin',headers:{'X-CSRFToken':csrf}};
 if(body instanceof FormData)opts.body=body;else if(body){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body);}
 const controller=options.timeoutMs?new AbortController():null;
 const timer=controller?setTimeout(()=>controller.abort(),options.timeoutMs):null;if(controller)opts.signal=controller.signal;
 try{
  const r=await fetch('/api/'+path,opts);let data;try{data=await r.json();}catch{throw new Error(r.status>=500?`Máy chủ gặp lỗi (HTTP ${r.status}). Kiểm tra log backend.`:r.status===403?'Yêu cầu bị từ chối (HTTP 403). Tải lại trang để cập nhật phiên đăng nhập.':`API trả phản hồi không hợp lệ (HTTP ${r.status}). Kiểm tra phiên bản backend đang chạy.`);}
  if(!r.ok){const error=new Error(data.error||'Không thể thực hiện thao tác ('+r.status+').');error.status=r.status;throw error;}return data;
 }catch(error){if(controller?.signal.aborted)throw new Error('Máy chủ phản hồi quá lâu. Bấm Thử lại để kết nối lại.');throw error;}
 finally{if(timer)clearTimeout(timer);}
}
export async function boot(id){state.workspace=await api('bootstrap?compact=1'+(id?'&project='+encodeURIComponent(id):''),null,{timeoutMs:15000});return state.workspace;}
export async function exportFile(path,name){
 if(DEMO){const {demoRequest}=await import('./demo.js?v=5b47e3c89a10');const value=await demoRequest(path);download(value.body,name,value.type);return;}
 const response=await fetch('/api/'+path,{credentials:'same-origin'});
 if(!response.ok){let v;try{v=await response.json();}catch{}throw new Error(v?.error||'Không xuất được dữ liệu.');}
 download(await response.blob(),name);
}
export const projectQuery=()=>'?project='+state.workspace.project.id;
