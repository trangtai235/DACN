import {state,DEMO} from '../../core/state.js';
import {api,projectQuery} from '../../core/api.js';
import {refresh,navigate} from '../../core/events.js';
import {returnWorkspace} from '../../core/workspace-drafts.js';
import {esc,heading,panel,btn,field,textarea,modal,closeModal,toast,empty} from '../../core/ui.js';

let catalog=null,query='',status='all',projectId=null;
const writable=()=>catalog?.can_manage&&!catalog.locked&&!catalog.archived;
const color=value=>/^#[0-9a-f]{6}$/i.test(value||'')?value:'#4f78a5';
const chip=(label,number)=>`<span class="schema-option label-preview" style="--label-color:${color(label.color)}" role="img" aria-label="Xem trước: ${esc(label.name||'Nhãn mới')}"><span class="schema-dot"></span><b>${esc(label.name||'Nhãn mới')}</b>${number?`<kbd>${number}</kbd>`:''}</span>`;
export async function load(){
 if(DEMO){catalog=null;return;}
 if(projectId!==state.workspace.project.id){projectId=state.workspace.project.id;query='';status='all';}
 catalog=await api('studio/labels'+projectQuery());
 state.workspace.labels=catalog.labels;
}
export function render(){
 if(DEMO)return heading('Quản lý nhãn','Bộ nhãn riêng của dự án')+empty('Cần backend để quản lý nhãn','Trang này lưu vào Django. Chạy bản Windows/native để tạo, sửa và kiểm tra quyền thật.');
 const rows=catalog.labels.filter(l=>(status==='all'||l.enabled===(status==='active'))&&(`${l.name} ${l.key}`).toLocaleLowerCase().includes(query.toLocaleLowerCase()));
 const actions=btn('Quay lại gán nhãn','label-management:back')+(writable()?btn('Thêm nhãn','label-management:add','primary','plus'):'');
 const body=rows.map(l=>`<article class="label-row" data-label-id="${l.id}"><div class="label-main"><span class="label-swatch" style="background:${color(l.color)}" aria-label="Màu ${esc(l.color)}"></span><div><h3>${esc(l.name)}</h3><code>${esc(l.key)}</code><p>${esc(l.description||'Chưa có mô tả.')}</p>${l.exclusions?`<p><b>Loại trừ:</b> ${esc(l.exclusions)}</p>`:''}</div></div><div class="label-meta"><span>Thứ tự: <b>${l.order}</b></span><span>${esc(l.color)}</span><span class="badge ${l.enabled?'green':'orange'}">${l.enabled?'Đang dùng':'Ngừng dùng'}</span>${l.used?'<small>Đã dùng — giữ lịch sử, không xóa</small>':''}</div><div class="label-chip">${chip(l,l.enabled?catalog.labels.filter(x=>x.enabled).findIndex(x=>x.id===l.id)+1:null)}</div><div class="label-actions">${writable()?btn('Sửa','label-management:edit','sm','',`data-id="${l.id}"`)+btn(l.enabled?'Ngừng dùng':'Kích hoạt lại','label-management:toggle','sm','',`data-id="${l.id}"`)+(l.can_delete?btn('Xóa','label-management:delete','sm danger','',`data-id="${l.id}"`):''):'<small>Chỉ xem</small>'}</div></article>`).join('');
 return heading('Quản lý nhãn',`Dự án: ${esc(catalog.project.name)}`,actions)+
 `<div class="info-banner">${catalog.locked||catalog.archived?'Dự án đã khóa/lưu trữ: chỉ được xem.':catalog.can_manage?'Thay đổi được lưu theo dự án; mã nhãn giữ ổn định, nhãn đã dùng được bảo toàn.':'Bạn được xem bộ nhãn. Chỉ quản lý dự án được thay đổi.'}</div>`+
 panel('Bộ nhãn dự án',`<form class="label-filters" data-submit="label-management:filter"><div class="form-row"><label for="label-search">Tìm theo tên hoặc mã</label><input id="label-search" name="q" value="${esc(query)}" placeholder="Nhập tên hoặc mã nhãn"></div><div class="form-row"><label for="label-status">Trạng thái</label><select id="label-status" name="status">${[['all','Tất cả'],['active','Đang dùng'],['inactive','Ngừng dùng']].map(([v,t])=>`<option value="${v}" ${status===v?'selected':''}>${t}</option>`).join('')}</select></div><button class="btn" type="submit">Tìm / lọc</button>${btn('Tải lại','label-management:reload')}</form><p>${rows.length} / ${catalog.labels.length} nhãn. Thứ tự nhãn đang dùng quyết định phím tắt khi gán nhãn.</p><div class="label-list">${body||empty('Chưa có nhãn phù hợp',catalog.labels.length?'Đổi từ khóa hoặc bộ lọc.':catalog.can_manage?'Bấm Thêm nhãn để bắt đầu.':'Liên hệ quản lý dự án để thêm nhãn.')}</div>`)+
 panel('Xem trước khi gán bình luận',`<p>Bình luận mẫu: “Cảm ơn bạn đã chia sẻ thông tin.”</p><div class="sentence-options">${catalog.labels.filter(l=>l.enabled).map((l,i)=>chip(l,i+1)).join('')||'<p>Chưa có nhãn đang dùng.</p>'}</div><p>Nhãn ngừng dùng không được chọn mới; dữ liệu và snapshot cũ vẫn được giữ.</p>`)+
 panel('Tương thích model',`<p>${esc(catalog.local_model.name||'Chưa chọn model local')}: ${esc(catalog.local_model.reason)}</p><p>Thêm nhãn không tự làm model hỗ trợ lớp mới. Kiểm tra lại schema, đánh giá hoặc huấn luyện model tương thích.</p>`);
}
function edit(label){
 const l=label||{key:'',name:'',description:'',exclusions:'',color:'#4f78a5',order:catalog.labels.length,enabled:true};
 modal(label?'Sửa nhãn':'Thêm nhãn',`<form data-submit="label-management:save" ${label?`data-id="${l.id}" data-revision="${l.revision}"`:''}>${field('name','Tên nhãn',l.name,'text','required maxlength="120"')}${field('key','Mã nhãn ổn định',l.key,'text',`required pattern="[A-Z][A-Z0-9_]{0,63}" maxlength="64" ${label?'readonly':''}`)}${field('color','Màu',l.color,'color')}${textarea('description','Mô tả / hướng dẫn',l.description,'maxlength="3000"')}${textarea('exclusions','Quy tắc loại trừ',l.exclusions,'maxlength="3000"')}${field('order','Thứ tự',l.order,'number','required min="0" max="9999" step="1"')}<label class="check-row"><input type="checkbox" name="enabled" ${l.enabled?'checked':''}> Đang dùng</label><div id="label-form-preview">${chip(l)}</div><div class="form-error-slot" role="alert"></div><div class="modal-actions"><button type="button" class="btn" data-action="ui:close">Hủy</button><button type="submit" class="btn primary">Lưu</button></div></form>`);
}
export async function action(name,el){
 if(name==='back'){navigate(returnWorkspace());return;}
 if(name==='reload'){await refresh();return;}
 if(!writable())throw new Error('Bạn không có quyền thay đổi bộ nhãn hoặc dự án đã khóa.');
 const label=catalog.labels.find(l=>String(l.id)===el?.dataset.id);
 if(name==='add'){edit();return;}
 if(name==='edit'){edit(label);return;}
 if(name==='toggle'){await api('studio/labels',{...label,project:catalog.project.id,action:'update',enabled:!label.enabled});await refresh();toast(label.enabled?'Đã ngừng dùng nhãn. Lịch sử được giữ.':'Đã kích hoạt lại nhãn.');return;}
 if(name==='delete'){modal('Xóa nhãn chưa sử dụng',`<form data-submit="label-management:delete" data-id="${label.id}" data-revision="${label.revision}" data-key="${esc(label.key)}"><p>Xóa nhãn <b>${esc(label.name)}</b> (${esc(label.key)})? Backend kiểm tra lại việc sử dụng và lịch sử trước khi xóa.</p><div class="form-error-slot" role="alert"></div><div class="modal-actions"><button type="button" class="btn" data-action="ui:close">Hủy</button><button type="submit" class="btn danger">Xóa nhãn</button></div></form>`);}
}
export async function submit(name,form){
 if(name==='filter'){query=form.elements.q.value.trim();status=form.elements.status.value;await refresh();return;}
 const values=Object.fromEntries(new FormData(form));
 const payload={...values,project:catalog.project.id,action:name==='delete'?'delete':form.dataset.id?'update':'create'};
 if(form.dataset.id)Object.assign(payload,{id:Number(form.dataset.id),revision:Number(form.dataset.revision)});
 if(name==='delete')payload.key=form.dataset.key;
 else{payload.name=values.name.trim();payload.key=values.key.trim().toUpperCase();payload.order=Number(values.order);payload.enabled=form.elements.enabled.checked;}
 await api('studio/labels',payload);
 closeModal();await refresh();toast(name==='delete'?'Đã xóa nhãn chưa sử dụng.':'Đã lưu nhãn vào dự án.');
}
document.addEventListener('input',event=>{
 const form=event.target.closest('form[data-submit="label-management:save"]');if(!form)return;
 form.querySelector('#label-form-preview').innerHTML=chip({name:form.elements.name.value,color:form.elements.color.value});
});
