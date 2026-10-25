import {state,DEMO,currentModel} from '../../core/state.js?v=f62135f1ecf7';
import {api,projectQuery} from '../../core/api.js?v=f62135f1ecf7';
import {refresh,navigate} from '../../core/events.js?v=f62135f1ecf7';
import {esc,icon,modal,closeModal,toast,download,nativeRequired} from '../../core/ui.js?v=f62135f1ecf7';
let config={connections:[],active_connection_id:null},exported=null,discovered=[];
const button=(text,action,cls='',attrs='')=>`<button type="button" class="ps-button ${cls}" data-action="models:${action}" ${attrs}>${text}</button>`;
const controls=c=>c.enabled&&c.check_status==='success'?'success':c.enabled&&c.check_status==='failed'?'failed':'unknown';
const readable=c=>!c.enabled?'Đang tắt':c.check_status==='success'?'Kết nối thành công':c.check_status==='failed'?'Kiểm tra thất bại':'Chưa kiểm tra';
const idAttr=c=>`data-id="${c.id}"`;
export async function load(){
 if(!state.workspace.project.can_manage){config={connections:[]};return;}
 config=DEMO?{connections:[],active_connection_id:null}:await api('studio/connections'+projectQuery());
}
export function render(){
 if(!state.workspace.project.can_manage)return '<section class="panel auto-empty"><h2>Chỉ quản trị dự án được quản lý Mô hình & API.</h2></section>';
 const selected=config.active_connection_id;
 return `<section class="provider-settings"><aside class="ps-sidebar"><h2>Cài đặt</h2><nav aria-label="Cài đặt"><a href="#project-settings">${icon('settings',19)}<span>Chung</span></a><a href="#models" class="selected" aria-current="page">${icon('database',19)}<span>Mô hình</span></a><a href="#account" title="Mở tích hợp YouTube và cấu hình tài khoản hiện có">${icon('link',19)}<span>Plugin tích hợp</span></a><a href="#project-settings" title="Mở quy tắc, bộ nhãn và cấu hình dự án hiện có">${icon('brain',19)}<span>Cấu hình agent</span></a></nav><p class="ps-sidebar-note">Cấu hình theo dự án<br><b>${esc(state.workspace.project.name)}</b></p></aside><div class="ps-content"><header class="ps-heading"><div><span class="ps-eyebrow">CÀI ĐẶT / MÔ HÌNH</span><h1>Mô hình & API</h1><p>Quản lý nhà cung cấp API và mô hình sử dụng trong hệ thống.</p></div>${button(icon('file',16)+' Xem tệp cấu hình','configuration','ps-config',DEMO?'disabled':'')}</header>${DEMO?'<p class="ps-notice">Chạy backend Django để lưu cấu hình và kiểm tra kết nối thật. Bản demo không nhận API key.</p>':''}<div class="ps-default"><label for="ps-default">Nhà cung cấp mặc định</label><select id="ps-default" ${DEMO?'disabled':''}><option value="">Chưa chọn</option>${config.connections.map(c=>`<option value="${c.id}" ${selected===c.id?'selected':''} ${!c.enabled||(!c.key_configured&&c.kind!=='ollama')?'disabled':''}>${esc(c.name)} · ${esc(c.model)}</option>`).join('')}</select><small>Dùng cho luồng LLM khi gán nhãn tự động.</small></div><div class="ps-providers">${config.connections.map(c=>`<article class="ps-card"><div class="ps-card-title"><h2>${esc(c.name)}</h2>${!c.is_builtin?'<span class="ps-custom">Tùy chỉnh</span>':''}<span class="ps-dot ${controls(c)}" role="img" aria-label="${readable(c)}" title="${readable(c)}"></span>${selected===c.id?'<span class="ps-active">Mặc định</span>':''}<p>${esc(c.model)}<span>·</span>${readable(c)}</p></div><div class="ps-card-actions">${button('Chỉnh sửa','connection','',idAttr(c))}${!c.is_builtin?button('Xóa','delete','ps-danger',idAttr(c)):''}</div></article>`).join('')||'<div class="ps-empty">Chưa có nhà cung cấp API. Thêm kết nối để bắt đầu.</div>'}</div>${button(icon('plus',18)+' Thêm nhà cung cấp','connection','ps-add',DEMO?'disabled':'')}<details class="ps-local"><summary>${icon('brain',18)}<span>ML Local</span><small>${esc(currentModel()?.name||'Chưa chọn model')}</small></summary><div><label for="ps-local-model">Mô hình chạy trên máy</label><select id="ps-local-model">${state.workspace.models.map(m=>`<option value="${m.id}" ${currentModel()?.id===m.id?'selected':''}>${esc(m.name)}</option>`).join('')}</select><p>ML Local luôn chạy trong lượt tự gán nhãn. Nhà cung cấp có API key sẽ chạy thêm luồng LLM.</p><a href="#annotation" class="ps-button">Đến gán nhãn tự động ${icon('arrow',14)}</a></div></details></div></section>`;
}
function darkDialog(title,body,wide=false){modal(title,body,wide);document.querySelector('#modal-root .modal')?.classList.add('ps-dialog');}
function connectionForm(id){
 const c=config.connections.find(x=>x.id===Number(id)),kind=c?.kind||'openai_compatible';discovered=[];
 const field=(name,label,value='',type='text',attrs='')=>`<label class="ps-field">${label}<input name="${name}" type="${type}" value="${esc(value)}" ${attrs}></label>`;
 darkDialog(c?'Chỉnh sửa nhà cung cấp':'Thêm nhà cung cấp',`<form data-submit="models:connection" data-id="${c?.id||''}">${field('name','Tên hiển thị',c?.name||'','text','required maxlength="120"') }<label class="ps-field">Loại API<select name="kind" ${c?.is_builtin?'disabled':''}><option value="openai_compatible" ${kind==='openai_compatible'?'selected':''}>OpenAI-compatible</option>${kind!=='openai_compatible'?`<option value="${esc(kind)}" selected>${esc(kind)} · kết nối hiện có</option>`:''}</select></label>${field('base_url','Base URL',c?.base_url||'','url',`required placeholder="https://api.river.ai/v1" ${c?.is_builtin?'readonly':''}`)}<label class="ps-field">API key <span class="ps-key-state">${c?.key_configured?'Đã cấu hình khóa':'Chưa có khóa'}</span><div class="ps-key-input"><input id="provider-api-key" name="api_key" type="password" autocomplete="new-password" spellcheck="false" placeholder="${c?.key_configured?'Để trống để giữ khóa đã lưu':'Nhập API key'}" ${!c?.key_configured&&(!c||c.enabled)?'required':''}>${button('Hiện','toggleKey','','aria-controls="provider-api-key" aria-label="Hiện API key"')}</div></label><label class="ps-field">Danh sách Model ID<textarea name="model_ids" required rows="3" placeholder="Mỗi dòng một Model ID">${esc((c?.model_ids||[c?.model||'']).join('\n'))}</textarea><small>Mỗi dòng một Model ID; dùng đúng ID do nhà cung cấp công bố.</small></label><label class="ps-field">Mô hình mặc định<select name="model" required>${(c?.model_ids||[]).map(m=>`<option value="${esc(m)}" ${m===c.model?'selected':''}>${esc(m)}</option>`).join('')||'<option value="">Nhập Model ID ở trên</option>'}</select></label><div class="ps-form-options"><label><input name="enabled" type="checkbox" ${!c||c.enabled?'checked':''}> Bật nhà cung cấp</label><label><input name="make_default" type="checkbox" ${c?.id===config.active_connection_id?'checked':''}> Đặt làm nhà cung cấp mặc định</label></div><div id="provider-check" class="ps-check-result" aria-live="polite">${c?.check_message?esc(c.check_message):'Kiểm tra bằng GET /models, không gửi yêu cầu sinh nội dung.'}</div><input name="test_token" type="hidden" value=""><div class="form-error-slot" aria-live="polite"></div><div class="ps-dialog-actions">${button('Kiểm tra kết nối','testDraft','','data-test-button')}${button('Hủy','cancel')}<button type="submit" class="ps-button ps-primary">Lưu</button></div></form>`,true);
}
function ids(form){return [...new Set(form.model_ids.value.split(/[\n,]+/).map(x=>x.trim()).filter(Boolean))];}
function payload(form){
 const value=Object.fromEntries(new FormData(form));
 return {...value,project:state.workspace.project.id,id:form.dataset.id||null,kind:form.kind.value,
  model_ids:ids(form),enabled:form.enabled.checked,make_default:form.make_default.checked};
}
function syncModels(form){
 const previous=form.model.value,models=ids(form);
 form.model.innerHTML=models.map(id=>`<option value="${esc(id)}">${esc(id)}</option>`).join('')||'<option value="">Nhập Model ID ở trên</option>';
 if(models.includes(previous))form.model.value=previous;
}
export async function action(name,el){
 const project=state.workspace.project.id;
 if(name==='cancel'){closeModal();return;}
 if(name==='toggleKey'){const input=document.querySelector('#provider-api-key');input.type=input.type==='password'?'text':'password';el.textContent=input.type==='password'?'Hiện':'Ẩn';el.setAttribute('aria-label',input.type==='password'?'Hiện API key':'Ẩn API key');return;}
 if(DEMO){nativeRequired();return;}
 if(name==='connection'){connectionForm(el.dataset.id);return;}
 if(name==='configuration'){
  exported=await api('studio/connections/configuration'+projectQuery());
  darkDialog('Tệp cấu hình Mô hình & API',`<p class="ps-notice">Bản xuất không chứa API key, khóa mã hóa hoặc biến môi trường bí mật.</p><pre class="ps-json">${esc(JSON.stringify(exported,null,2))}</pre><div class="ps-dialog-actions">${button('Đóng','cancel')}${button('Tải xuống JSON','download','ps-primary')}</div>`,true);return;
 }
 if(name==='download'){download(JSON.stringify(exported,null,2),'annotaflow-providers.json');return;}
 if(name==='delete'){
  const c=config.connections.find(x=>x.id===Number(el.dataset.id));
  if(!c||c.is_builtin)return;
  darkDialog('Xóa nhà cung cấp',`<form data-submit="models:delete" data-id="${c.id}"><p>Xóa cấu hình và API key đã lưu của <b>${esc(c.name)}</b>. Các kết quả gán nhãn trước đây vẫn được giữ.</p><label class="ps-field">Nhập đúng tên để xác nhận<input name="confirm" required autocomplete="off" placeholder="${esc(c.name)}"></label><div class="form-error-slot"></div><div class="ps-dialog-actions">${button('Hủy','cancel')}<button type="submit" class="ps-button ps-danger">Xóa nhà cung cấp</button></div></form>`);return;
 }
 if(name==='testDraft'){
  const form=el.closest('form');syncModels(form);if(!form.reportValidity())return;
  const box=document.querySelector('#provider-check');box.className='ps-check-result';box.textContent='Đang kiểm tra GET /models…';el.disabled=true;
  try{
   const result=await api('studio/connections/test',payload(form));
   box.className='ps-check-result '+result.check.status;box.textContent=result.check.message;
   form.test_token.value=result.test_token;discovered=result.check.models||[];
   if(discovered.length){const p=document.createElement('p');p.textContent=`API trả ${discovered.length} Model ID. `;const b=document.createElement('button');b.type='button';b.className='ps-button';b.dataset.action='models:useModels';b.textContent='Dùng danh sách từ API';p.append(b);box.append(p);}
  }catch(error){box.className='ps-check-result failed';box.textContent=error.message;}finally{el.disabled=false;}return;
 }
 if(name==='useModels'){const form=el.closest('form');form.model_ids.value=discovered.join('\n');syncModels(form);form.test_token.value='';return;}
 if(name==='select'){await api('studio/selection',{project,model_id:Number(el.dataset.id)});await refresh();return;}
 if(name==='runLocal'||name==='runApi')navigate('annotation');
}
export async function submit(name,form){
 if(DEMO){nativeRequired();return;}
 if(name==='connection'){syncModels(form);await api('studio/connections/save',payload(form));closeModal();await refresh();toast('Đã lưu nhà cung cấp.');}
 if(name==='delete'){await api('studio/connections/delete',{project:state.workspace.project.id,id:form.dataset.id,confirm:form.confirm.value});closeModal();await refresh();toast('Đã xóa nhà cung cấp.');}
}
export async function change(event){
 if(event.target.id==='ps-default'){await api('studio/selection',{project:state.workspace.project.id,connection_id:event.target.value?Number(event.target.value):null});await refresh();return;}
 if(event.target.id==='ps-local-model'){await api('studio/selection',{project:state.workspace.project.id,model_id:Number(event.target.value)});await refresh();return;}
 const form=event.target.closest('[data-submit="models:connection"]');if(!form)return;
 if(event.target.name==='model_ids')syncModels(form);
 if(event.target.name==='enabled'){form.api_key.required=form.enabled.checked&&!config.connections.find(c=>c.id===Number(form.dataset.id))?.key_configured;if(!form.enabled.checked)form.make_default.checked=false;}
 if(event.target.name!=='test_token')form.test_token.value='';
}
