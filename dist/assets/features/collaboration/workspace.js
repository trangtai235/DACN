import {esc,icon} from '../../core/ui.js?v=00d8c624ac88';
import {commentCard} from '../annotation/comment-card.js?v=00d8c624ac88';

const button=(text,action,extra='',style='')=>`<button type="button" class="btn ${style}" data-action="collaboration:${action}" ${extra}>${text}</button>`;
const color=l=>/^#[0-9a-f]{6}$/i.test(l?.color||'')?l.color:'#6d85a4';
const name=(labels,key)=>labels.find(l=>l.key===key)?.name||key;
const chip=(labels,key)=>`<strong class="hitl-label-chip" style="--label-color:${color(labels.find(l=>l.key===key))}"><span class="schema-dot"></span>${esc(name(labels,key))}</strong>`;

export function suggestion(c,labels,locked,canManage=false){
 const statuses=c.prediction_status||{};
 const ready=Object.entries(statuses).filter(([,s])=>s.state==='complete').map(([key])=>key==='local'?'Local':'LLM API');
 const running=Object.entries(statuses).filter(([,s])=>s.state==='running').map(([key])=>key==='local'?'Local':'LLM API');
 const canResume=canManage&&!locked&&!['stale','incompatible'].includes(c.state)&&Object.values(statuses).some(s=>s.can_resume);
 const consensus=c.state==='agreement'&&c.revealed&&c.local&&c.api&&c.local.label===c.api.label;
 const prediction=(p,branch,action)=>`<article class="hitl-prediction"><b>${branch}</b>${p?`${chip(c.schema.labels,p.label)}${!consensus?button('Chọn nhãn',action,!labels.some(l=>l.enabled&&l.key===p.label)||locked?'disabled':'','sm'):''}<small>${esc(p.model)} · Prediction #${p.id}</small>`:'<small>Chưa có kết quả hợp lệ.</small>'}</article>`;
 const messages={
  stale:'Gợi ý cũ. Hãy chọn nhãn theo bộ nhãn hiện tại.',
  pending:(running.join(' và ')||'Mô hình')+' đang chạy. Gợi ý sẽ tự cập nhật.',
  queued:'Job đang chờ xử lý. Bạn vẫn có thể gán nhãn trực tiếp.',
  interrupted:'Lượt tạo gợi ý đã dừng. Model hiện không chạy.',
  partial_error:ready.length?'Đã có gợi ý '+ready.join(' và ')+'. Chưa đủ hai kết quả để kết luận đồng thuận.':'Chưa có kết quả hợp lệ từ mô hình.',
  incompatible:'Model chưa hỗ trợ bộ nhãn hiện tại.',
  disagreement:'Đã lưu lựa chọn độc lập. Mở gợi ý để đối chiếu.'
 };
 let body='';
 if(consensus){
  const label=labels.find(l=>l.key===c.local.label&&l.enabled);
  body=`<div class="hitl-suggestion-line hitl-consensus" data-consensus="${esc(c.local.label)}"><span>${icon('spark',16)}Hai mô hình đồng thuận</span>${chip(labels,c.local.label)}${button('Dùng gợi ý','useConsensus',!label||locked?'disabled':'','sm')}</div>`;
 }else if(c.requires_preliminary){
  body=`<div class="hitl-suggestion-line">${icon('eye',16)}<span>Hai mô hình bất đồng. Chọn nhãn độc lập trước khi xem gợi ý.</span></div>`;
 }else{
  body=`<div class="hitl-suggestion-line">${icon('info',16)}<span>${c.revealed&&c.state==='disagreement'?'Đối chiếu hai gợi ý và chọn nhãn cuối.':messages[c.state]||'Chưa có gợi ý đồng thuận.'}</span>${canResume?button('Tiếp tục tạo gợi ý','resumePredictions','','sm'):''}${['pending','queued'].includes(c.state)?button('Tải gợi ý','refreshSuggestions','','sm'):!c.revealed&&ready.length?button('Xem gợi ý','expose','','sm'):''}</div>`;
  if(!c.revealed&&Object.keys(statuses).length)body+=`<div class="hitl-branch-status">${Object.entries(statuses).map(([key,s])=>`<span title="${esc(s.message)}">${key==='local'?'Local':'LLM API'} · ${esc({queued:'Chờ chạy',running:'Đang chạy',interrupted:'Đã dừng',error:'Lỗi',paused:'Chưa chạy',missing:'Chưa cấu hình',incompatible:'Không tương thích',complete:'Đã có kết quả'}[s.state]||s.state)}</span>`).join('')}</div>`;
 }
 if(c.revealed){
  body+=`<details class="hitl-model-detail" ${consensus?'':'open'}><summary>Chi tiết mô hình</summary><div class="hitl-model-results">${prediction(c.local,'Local','useLocal')}${prediction(c.api,'LLM API','useApi')}</div>
  ${Object.entries(c.branches).filter(([,v])=>v.error).map(([key,v])=>`<p class="form-error" role="alert">${esc(key)}: ${esc(v.error)}</p>`).join('')}
  <details class="hitl-trace"><summary>Thông tin dự đoán</summary><pre>${esc(JSON.stringify({local:c.local,api:c.api,branches:c.branches},null,2))}</pre></details></details>`;
 }
 return `<section class="hitl-suggestions" aria-label="Gợi ý từ mô hình">${body}</section>`;
}

function tokens(c,draft,labels){
 const chars=Array.from(c.text),picked=new Set(draft.picked||[]);let cursor=0;
 return (c.tokens||[]).map((t,i)=>{
  const gap=esc(chars.slice(cursor,t.start).join(''));cursor=t.end;
  const span=draft.spans.find(s=>s.start<=t.start&&s.end>=t.end);
  return gap+`<button type="button" class="word-token ${picked.has(i)?'picked':''} ${span?'marked':''}" style="--span-color:${color(labels.find(l=>l.key===span?.label))}" data-action="collaboration:token" data-index="${i}" aria-pressed="${picked.has(i)}">${esc(t.text)}</button>`;
 }).join('')+esc(chars.slice(cursor).join(''));
}

function tools(c,draft,labels,active){
 const actions=c.requires_preliminary?[['preliminary','Lưu nhãn độc lập']]:[['confirm','Xác nhận nhãn đã chọn']];
 actions.push(['skip','Bỏ qua'],['needs_context','Cần thêm ngữ cảnh'],['undecidable','Không thể quyết định'],['escalate','Chuyển phân xử']);
 return `<details class="annotation-extra hitl-tools" ${draft.tools_open||draft.note||draft.picked.length||draft.spans.length||!['confirm','preliminary'].includes(draft.action)?'open':''}>
 <summary>${icon('edit',14)}Công cụ bổ sung${draft.note||draft.spans.length?'<span class="hitl-tool-indicator">Có ghi chú / cụm từ</span>':''}</summary>
 <details class="annotation-extra" ${draft.note?'open':''}><summary>Thêm ghi chú</summary><label for="hitl-note">Lý do / thông tin còn thiếu</label><textarea id="hitl-note" name="note" class="workspace-note">${esc(draft.note)}</textarea></details>
 <details class="annotation-extra" ${draft.picked.length||draft.spans.length?'open':''}><summary>Gán nhãn từ / cụm từ (tùy chọn)</summary>
 <div class="text-editor">${tokens(c,draft,labels)}</div><div class="span-toolbar"><span>${draft.picked.length} từ đã chọn</span><select id="hitl-span-label" aria-label="Nhãn cụm từ">${active.map(l=>`<option value="${esc(l.key)}">${esc(l.name)}</option>`).join('')}</select>${button('Gán cụm từ','addSpan',!draft.picked.length?'disabled':'','sm')}${button('Bỏ chọn','clearPick','','sm')}</div><p class="annotation-hint">Bấm từng từ; giữ Shift để chọn một dải.</p>
 <div class="span-list">${draft.spans.map((s,i)=>`<div class="span-chip" style="--span-color:${color(labels.find(l=>l.key===s.label))}"><span>“${esc(Array.from(c.text).slice(s.start,s.end).join(''))}”</span><b>${esc(name(labels,s.label))}</b>${button('×','removeSpan',`data-index="${i}" aria-label="Xóa cụm từ ${i+1}"`,'icon-btn')}</div>`).join('')||'<p class="muted">Chưa đánh dấu cụm từ nào.</p>'}</div></details>
 <div class="hitl-action-row"><label for="hitl-decision-action">Xử lý khác</label><select id="hitl-decision-action" name="action">${actions.map(([key,text])=>`<option value="${key}" ${key===draft.action?'selected':''}>${text}</option>`).join('')}</select><button class="btn sm" type="submit" data-intent="next">Áp dụng & tiếp tục</button><button class="btn sm" type="submit" data-intent="stay">Lưu tại đây</button></div>
 <details class="hitl-timing"><summary>Lịch sử và thời gian</summary><p>${Math.round(c.clock?.active||0)} giây hoạt động · ${Math.round(c.clock?.idle||0)} giây nghỉ.</p>${button('Tạm dừng','pause','','sm')}${button('Tiếp tục','resume','','sm')}
 ${c.prior_assistance?'<p>Đã xem gợi ý hoặc nhãn người khác trong lượt trước.</p>':''}${(c.mine.history||[]).map(h=>`<p>${esc(h.action)} · ${esc(name(h.schema_snapshot?.labels||labels,h.label))} · ${esc(h.at)}</p>`).join('')}</details>
 </details>`;
}

export function workspace(c,draft,labels,preferences,position={}){
 const locked=preferences.locked||preferences.archived,active=labels.filter(l=>l.enabled);
 const invalid=(draft.selected_label&&!active.some(l=>l.key===draft.selected_label))||draft.spans.some(s=>!active.some(l=>l.key===s.label));
 const independent=['blind','preliminary'].includes(c.mine.status)&&!c.mine.exposed_at;
 const status={confirmed:'Đã lưu',preliminary:'Đã chọn độc lập',blind:'Chọn độc lập',skipped:'Đã bỏ qua',escalated:'Chờ phân xử',needs_context:'Cần ngữ cảnh',undecidable:'Chưa thể quyết định',resolved:'Đã phân xử'}[c.mine.status]||'Chưa gán nhãn';
 return `<div class="annotation-layout hitl-annotation"><section class="panel annotation-panel">
 <div class="panel-head"><div><h2>Bình luận #${c.comment_id}</h2>${position.total?`<span class="hitl-position">Mẫu ${position.index} / ${position.total}</span>`:''}</div><span class="count-pill ${c.mine.status==='confirmed'?'hitl-saved':''}">${esc(status)}</span></div>
 <div class="annotation-body">${locked?'<p class="info-banner">Dự án đã khóa. Quản lý cần mở khóa trước khi lưu.</p>':''}
 ${commentCard(c,{compact:true})}${suggestion(c,labels,locked,position.can_manage)}
 <form data-submit="collaboration:decision"><fieldset ${locked?'disabled':''} class="hitl-fields"><input type="hidden" name="label" value="${esc(draft.selected_label)}">
 <div class="hitl-label-heading"><label>Chọn nhãn</label><span>${c.requires_preliminary?'Lưu lựa chọn độc lập':'Bấm để lưu & chuyển tiếp'}</span></div>
 ${invalid?'<p class="info-banner" role="alert">Nhãn trong bản nháp đã ngừng dùng. Chọn nhãn đang dùng hoặc sửa cụm từ trước khi lưu.</p>':''}
 <div class="sentence-options">${active.map((l,i)=>`<button type="button" class="schema-option ${draft.selected_label===l.key?'selected':''}" style="--label-color:${color(l)}" data-action="collaboration:sentence" data-label="${esc(l.key)}" aria-pressed="${draft.selected_label===l.key}" title="${esc(l.description||'')}"><span class="schema-dot"></span><b>${esc(l.name)}</b>${i<9?`<kbd>${i+1}</kbd>`:''}</button>`).join('')||'<p>Chưa có nhãn đang dùng. Mở Quản lý nhãn hoặc liên hệ người quản lý.</p>'}</div>
 ${tools(c,draft,labels,active)}<div class="form-error-slot" aria-live="polite"></div>
 <div class="hitl-footer"><div class="hitl-secondary-actions">${button('Bỏ qua','skip','','sm')}<span title="Bấm số để chọn và lưu nhãn">${icon('help',14)}Phím 1–9 chọn nhãn</span></div><div class="hitl-navigation">${button('Trước','previous',!position.index||position.index<=1||independent?'disabled':'','sm')}${button('Tiếp '+icon('arrow',14),'next',independent?'disabled':'','sm')}</div></div>
 </fieldset></form></div></section></div>`;
}
