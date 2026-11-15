import {annotationSourceId,selectAnnotationSource,sourceScopeBar,sourceQuery,scopeDraftKind} from '../../core/annotation-scope.js';
import {state,DEMO} from '../../core/state.js';
import {api,projectQuery,exportFile} from '../../core/api.js';
import {refresh,navigate} from '../../core/events.js';
import {readDraft,writeDraft,clearDraft,rememberWorkspace} from '../../core/workspace-drafts.js';
import {esc,heading,btn,select,textarea,field,formEnd,modal,closeModal,toast,empty} from '../../core/ui.js';
import {workspace,suggestion,translationView} from './workspace.js';
import {administration} from './administration.js';

let data={},rows=[],runId='',current=null,inspection=null,projectId=null,queueFilter='all',scopeId='';
let labelCatalog={labels:[]},pairDraft=null,restorePairId=null,requestSequence=0,predictionRefreshing=false;
const translationTasks=new Map();
const names={pending:'Đang chạy',queued:'Chờ chạy',interrupted:'Đã dừng tạo gợi ý',agreement:'Hai model đồng thuận',disagreement:'Hai model bất đồng',partial_error:'Thiếu/lỗi nhánh',incompatible:'Local không tương thích',stale:'Phiên bản cũ'};
const humanStatus={confirmed:'Đã xác nhận',draft:'Chưa xác nhận',blind:'Đang chọn độc lập',preliminary:'Đã lưu lựa chọn',escalated:'Chờ phân xử',resolved:'Đã phân xử',needs_context:'Cần ngữ cảnh',undecidable:'Không thể quyết định',skipped:'Đã bỏ qua'};
const reviewStatus={awaiting_review:'Chờ người duyệt',awaiting_adjudication:'Cần phân xử',reviewed:'Đã có nhãn người',adjudicated:'Đã phân xử'};
const choices=labels=>[['','— Chọn nhãn —'],...labels.filter(l=>l.enabled!==false).map(l=>[l.key,l.name])];
const form=()=>document.querySelector('form[data-submit="collaboration:decision"]');
const locked=()=>state.workspace.preferences.locked||state.workspace.preferences.archived;
const viewState=()=>writeDraft(scopeDraftKind('pair-view',scopeId),{run_id:runId,queue_filter:queueFilter});
function defaultDraft(c){return {pair_id:c.id,run_id:runId,source_id:c.source_id,text:c.text,selected_label:c.mine.label||c.mine.preliminary_label||'',note:c.mine.note||'',action:c.requires_preliminary?'preliminary':'confirm',spans:structuredClone(c.my_spans||[]),picked:[],last_pick:null,revision:c.mine.revision,annotation_revision:c.annotation_revision,queue_filter:queueFilter,open:true};}
export async function load(){
 if(DEMO)return;
 if(projectId!==state.workspace.project.id||scopeId!==annotationSourceId()){projectId=state.workspace.project.id;scopeId=annotationSourceId();runId='';queueFilter='all';current=null;pairDraft=null;}
 const view=readDraft(scopeDraftKind('pair-view',scopeId));if(view){runId=view.run_id;queueFilter=view.queue_filter;}
 const saved=readDraft(scopeDraftKind('pair',scopeId));restorePairId=saved?.open?saved.pair_id:null;if(saved?.open){runId=saved.run_id;queueFilter=saved.queue_filter||'all';}
 labelCatalog=await api('studio/labels'+projectQuery());state.workspace.labels=labelCatalog.labels;
 const incoming=sessionStorage.getItem('annotaflow.humanRun');
 if(incoming){const selection=JSON.parse(incoming);sessionStorage.removeItem('annotaflow.humanRun');if(selection.project===projectId){persistDraft();runId=selection.id;current=null;restorePairId=null;clearDraft(scopeDraftKind('pair',scopeId));viewState();}}
 data=await api('studio/collaboration'+projectQuery()+sourceQuery());if(data.blind){rows=[];return;}
 if(scopeId&&String(data.scope_source_id)!==scopeId)throw new Error('Backend chưa hỗ trợ hàng đợi theo video. Khởi động lại backend trước khi gán nhãn.');
 if(!data.runs.some(r=>String(r.id)===String(runId))){runId=data.runs[0]?.id||'';restorePairId=null;current=null;}
 rows=runId?await fetchRows():[];
 if(restorePairId&&!rows.some(r=>r.id===restorePairId))restorePairId=null;
}
async function fetchRows(){
 const result=await api('studio/collaboration/runs/'+runId+(scopeId?'?source='+encodeURIComponent(scopeId):''));
 if(scopeId&&String(result.scope_source_id)!==scopeId)throw new Error('Backend chưa lọc hàng đợi theo video. Khởi động lại backend trước khi tiếp tục.');
 return result.rows;
}
export function render(){
 const title=sourceScopeBar('human-review')+heading('Duyệt nhãn · HITL','Đọc bình luận, kiểm tra gợi ý và bấm nhãn để lưu.',btn(state.workspace.project.can_manage?'Quản lý nhãn':'Xem bộ nhãn','collaboration:manageLabels')+btn('Hướng dẫn','collaboration:guide'));
 if(DEMO)return title+empty('Duyệt hai gợi ý cần backend','Mở backend để dùng dữ liệu, dự đoán và lịch sử duyệt thật.','<a class="btn" href="#manual-annotation">Gán nhãn thủ công</a>');
 if(data.blind)return title+`<div id="hitl-workspace-slot">${empty('Tiếp tục mẫu đang làm','Hoàn tất lượt độc lập đang mở trước khi nhận mẫu khác.')}${(data.blind_pairs||[]).map(id=>btn('Mở mẫu đang làm','collaboration:open','primary','',`data-id="${id}"`)).join('')}</div>`;
 return title+`<div id="hitl-progress">${progressMarkup()}</div>`+
 (state.workspace.project.is_demo?'<p class="hitl-demo-notice">Dữ liệu minh họa · Không phải kết quả thực nghiệm.</p>':'')+
 `<div id="hitl-workspace-slot">${current&&pairDraft?workspace(current,pairDraft,labelCatalog.labels,state.workspace.preferences,workspacePosition()):empty(rows.length?'Đang mở bình luận…':'Chưa có lượt hỗ trợ gán nhãn','Tạo lượt hỗ trợ hoặc mở Gán nhãn thủ công để bắt đầu mà chưa cần model/API.','<a class="btn" href="#manual-annotation">Gán nhãn thủ công</a>')}</div>`+
 `<details class="annotation-extra hitl-queue"><summary>Hàng đợi người duyệt · ${rows.length} bình luận</summary><div id="hitl-queue-body">${humanQueue()}</div></details>`+
 `<details class="annotation-extra hitl-administration"><summary>Cấu hình, phản hồi và báo cáo</summary>${administration(data,runId)}</details>`;
}
function workspacePosition(){return {index:rows.findIndex(r=>r.id===current?.id)+1,total:rows.length,can_manage:state.workspace.project.can_manage};}
function progressMarkup(){
 const count=rows.filter(r=>r.mine?.status==='confirmed').length;
 return `<div class="hitl-progress-rail"><div class="hitl-progress-count"><b>${count}<span> / ${rows.length}</span></b><span>đã xác nhận</span></div><progress value="${count}" max="${Math.max(1,rows.length)}" aria-label="Tiến độ duyệt nhãn"></progress>
 <details class="hitl-run-options"><summary>Lượt hỗ trợ ${runId?'#'+esc(runId):''}</summary><div class="hitl-run-controls"><label for="paired-run">Chọn lượt</label><select id="paired-run">${(data.runs||[]).map(r=>`<option value="${r.id}" ${String(runId)===String(r.id)?'selected':''}>#${r.id} · ${r.count} mẫu</option>`).join('')}</select>${btn('Tải tiến độ','collaboration:reload','sm')}${state.workspace.project.can_manage?btn('Tạo lượt hỗ trợ gán nhãn','collaboration:start','sm'):''}</div></details></div>`;
}
function humanQueue(){
 const filtered=rows.filter(r=>queueFilter==='all'||(queueFilter==='mine'?r.mine?.status==='confirmed':r.review_state===queueFilter));
 return `<label for="human-queue-filter">Lọc hàng đợi</label><select id="human-queue-filter">${[['all','Tất cả'],['awaiting_review','Chờ người duyệt'],['awaiting_adjudication','Cần phân xử'],['mine','Tôi đã xác nhận']].map(([v,n])=>`<option value="${v}" ${v===queueFilter?'selected':''}>${n}</option>`).join('')}</select><div class="table-wrap"><table><thead><tr><th>Bình luận</th><th>Gợi ý máy</th><th>Người duyệt</th><th>Thao tác</th></tr></thead><tbody>${filtered.map(r=>`<tr ${current?.id===r.id?'aria-current="true"':''}><td>${esc(r.text)}</td><td>${esc(names[r.state]||r.state)}</td><td><b>${esc(reviewStatus[r.review_state])}</b><p>${esc(humanStatus[r.mine?.status]||'Bạn chưa quyết định')}</p>${r.feedback_approved?'<small>Đã duyệt dùng làm phản hồi</small>':''}</td><td>${btn('Duyệt / sửa nhãn','collaboration:open','sm','',`data-id="${r.id}"`)}${state.workspace.project.can_manage?btn('Xem nhãn người & duyệt phản hồi','collaboration:inspect','sm','',`data-id="${r.id}"`):''}${r.escalated&&r.can_adjudicate?btn('Phân xử','collaboration:gold','sm','',`data-id="${r.id}"`):''}</td></tr>`).join('')||'<tr><td colspan="4">Không có mẫu trong bộ lọc này.</td></tr>'}</tbody></table></div>`;
}
function humanDecisions(c,approval=true){return c.decisions.map(d=>`<article class="review-run"><b>${esc(d.user_name||'Người gán #'+d.user_id)}</b><p>${esc(humanStatus[d.status]||d.status)} · ${esc((d.schema_snapshot?.labels||c.schema.labels).find(l=>l.key===d.label)?.name||d.label||'Chưa có nhãn cuối')}</p><p>${esc(d.note||'')}</p>${approval&&d.status==='confirmed'?d.approved?'<small>Đã duyệt làm phản hồi</small>':btn('Duyệt phản hồi này','collaboration:approve','sm','',`data-id="${d.id}"`):''}</article>`).join('')||'<p>Chưa có quyết định của con người.</p>';}
export async function afterRender(){const id=data.blind?(data.blind_pairs.includes(restorePairId)?restorePairId:data.blind_pairs[0]):restorePairId||current?.id||rows.find(r=>r.review_state==='awaiting_review'&&r.state!=='stale'&&!['confirmed','skipped','needs_context','undecidable'].includes(r.mine?.status))?.id||rows[0]?.id;restorePairId=null;if(id)await openPair(id,false);}
export function persistDraft(){const f=form();if(!f||!current?.mine||!pairDraft)return;Object.assign(pairDraft,{selected_label:f.elements.label.value,note:f.elements.note.value,action:f.elements.action.value,tools_open:Boolean(f.querySelector('.hitl-tools')?.open),queue_filter:queueFilter,open:true});writeDraft(scopeDraftKind('pair',scopeId),pairDraft);writeDraft('pair-'+current.id,pairDraft);}
export async function beforeLeave(route){persistDraft();viewState();rememberWorkspace(state.route==='collaboration'?'collaboration':'human-review');if(!['collaboration','human-review'].includes(route))await decisionClock('pause').catch(()=>{});}
async function openPair(id,preserve=true){
 if(preserve)persistDraft();
 if(current&&String(current.id)!==String(id)&&['blind','preliminary'].includes(current.mine.status)&&!current.mine.exposed_at){toast('Lưu quyết định hoặc bỏ qua mẫu độc lập hiện tại trước khi chuyển.');return;}
 if(current&&String(current.id)!==String(id))await decisionClock('pause').catch(()=>{});
 const sequence=++requestSequence;
 let value=await api('studio/collaboration/pairs/'+id+(scopeId?'?source='+encodeURIComponent(scopeId):''));
 if(value.workspace_version!==1||!value.prediction_status||(scopeId&&String(value.source_id)!==scopeId)||!Number.isInteger(value.comment_id)||!Number.isInteger(value.annotation_revision)||!Array.isArray(value.tokens)){
  const message='Backend đang chạy phiên bản cũ hoặc thiếu dữ liệu HITL. Khởi động lại server rồi tải lại trang; bản nháp vẫn được giữ.';
  const slot=document.querySelector('#hitl-workspace-slot');
  if(slot&&!current)slot.innerHTML=empty('Cần cập nhật backend',message,btn('Thử lại sau khi khởi động server','collaboration:reload'));
  throw new Error(message);
 }
 // Exposure records visibility only: it neither infers nor creates a human annotation.
 if(canExposePredictions(value))value=await exposePredictions(id);
 const catalog=await api('studio/labels'+projectQuery());
 if(sequence!==requestSequence)return;
 current=value;labelCatalog=catalog;state.workspace.labels=catalog.labels;
 const pointer=readDraft(scopeDraftKind('pair',scopeId)),saved=pointer?.pair_id===current.id?pointer:readDraft('pair-'+current.id);
 pairDraft=saved&&saved.text===current.text?{...defaultDraft(current),...saved}:defaultDraft(current);
 if(current.requires_preliminary&&pairDraft.action==='confirm')pairDraft.action='preliminary';if(!current.requires_preliminary&&pairDraft.action==='preliminary')pairDraft.action='confirm';drawPair();persistDraft();
 if(data.blind&&value.revealed){await refresh();return;}
 if(pairDraft.translation?.status==='running')startTranslation(true);
}
function drawPair(){const slot=document.querySelector('#hitl-workspace-slot');if(slot&&current&&pairDraft)slot.innerHTML=workspace(current,pairDraft,labelCatalog.labels,state.workspace.preferences,workspacePosition());}
function canExposePredictions(value){return !locked()&&!value.revealed&&!['stale','incompatible'].includes(value.state)&&(!value.requires_preliminary||value.assisted_view_supported)&&Object.values(value.prediction_status||{}).some(s=>s.state==='complete');}
async function exposePredictions(id){const value=await api(`studio/collaboration/pairs/${id}/expose`,{source_id:scopeId||null,assisted_view:true,include_workspace:true});return value.workspace_version===1?value:api('studio/collaboration/pairs/'+id+(scopeId?'?source='+encodeURIComponent(scopeId):''));}
function startTranslation(checkOnly=false){
 if(!current||!pairDraft||translationTasks.has(current.id))return;
 const view=current,source=scopeId,project=state.workspace.project.id;
 const payload={project,source_id:source||null,text_hash:view.text_hash};
 const path=`studio/comments/${view.comment_id}/translation`,query='?'+new URLSearchParams(Object.fromEntries(Object.entries(payload).filter(([,v])=>v!==null)));
 const update=value=>{
  const saved=readDraft('pair-'+view.id);if(saved)writeDraft('pair-'+view.id,{...saved,translation:value});
  if(current?.id===view.id&&scopeId===source&&state.workspace.project.id===project){pairDraft.translation=value;persistDraft();const slot=document.querySelector('#hitl-translation');if(slot)slot.outerHTML=translationView(value);}
 };
 update({status:'running'});
 const task=(async()=>{
  try{
   let value=checkOnly?await api(path+query):await api(path,payload);
   while(value.status==='running'){
    if(current?.id!==view.id||scopeId!==source)return;
    await new Promise(resolve=>setTimeout(resolve,1000));value=await api(path+query);
   }
   if(value.status!=='complete')throw new Error(value.error||'Chưa có bản dịch. Bấm thử dịch lại.');
   if(value.comment_id!==view.comment_id)throw new Error('Bản dịch không khớp bình luận.');
   update(value);
  }catch(error){update({status:'failed',error:error.message});}
  finally{translationTasks.delete(view.id);}
 })();translationTasks.set(view.id,task);
}
async function refreshPredictions(manual=false){
 if(!current||predictionRefreshing)return;
 predictionRefreshing=true;
 const id=current.id,scope=scopeId,sequence=requestSequence;
 try{
  let value=await api(`studio/collaboration/pairs/${id}${scope?'?source='+encodeURIComponent(scope):''}`);
  if(sequence!==requestSequence||current?.id!==id||scopeId!==scope||(!manual&&state.busy))return;
  if(canExposePredictions(value))value=await exposePredictions(id);
  if(sequence!==requestSequence||current?.id!==id||scopeId!==scope||(!manual&&state.busy)||!['human-review','collaboration'].includes(state.route))return;
  persistDraft();const phaseChanged=current.requires_preliminary!==value.requires_preliminary;current=value;
  if(phaseChanged){if(value.requires_preliminary)pairDraft.action='preliminary';else if(pairDraft.action==='preliminary')pairDraft.action='confirm';drawPair();persistDraft();}
  else{const slot=document.querySelector('.hitl-suggestions');if(slot)slot.outerHTML=suggestion(current,labelCatalog.labels,locked(),state.workspace.project.can_manage);}
  const row=rows.find(r=>r.id===id);if(row)row.state=value.state;
  if(manual)toast('Đã cập nhật trạng thái và gợi ý.');
 }finally{predictionRefreshing=false;}
}
setInterval(()=>{if(!DEMO&&['human-review','collaboration'].includes(state.route)&&!state.busy&&!document.hidden&&!document.querySelector('[role=dialog]')&&Object.values(current?.prediction_status||{}).some(s=>['queued','running'].includes(s.state)))refreshPredictions().catch(()=>{});},1000);
async function decisionClock(action){const c=current;if(!c||!['blind','draft','preliminary'].includes(c.mine?.status))return;const response=await api(`studio/collaboration/pairs/${c.id}/clock`,{action,source_id:scopeId||null});c.clock=response.clock;}
setInterval(()=>{if(!DEMO&&['collaboration','human-review'].includes(state.route)&&current?.clock?.state==='active'&&!state.busy&&!document.hidden&&form())decisionClock('heartbeat').catch(()=>{});},10000);
document.addEventListener('visibilitychange',()=>{if(['collaboration','human-review'].includes(state.route)&&form()){persistDraft();decisionClock(document.hidden?'pause':'resume').catch(()=>{});}});
async function adjacent(direction=1,eligible=false){const candidates=rows.length?rows:(data.blind_pairs||[]).map(id=>({id})),index=candidates.findIndex(r=>r.id===current?.id);const ordered=direction>0?[...candidates.slice(index+1),...candidates.slice(0,index)]:candidates.slice(0,index).reverse();const next=ordered.find(r=>!eligible||(r.review_state==='awaiting_review'&&r.state!=='stale'&&!['confirmed','skipped','needs_context','undecidable'].includes(r.mine?.status)));if(next)await openPair(next.id);else toast('Không còn mẫu phù hợp. Bạn có thể chọn lại trong hàng đợi.');}
export async function action(name,el,event){
 const project=state.workspace.project.id;
 if(name==='translate'){persistDraft();startTranslation();return;}
 if(name==='refreshSuggestions'){await refreshPredictions(true);return;}
 if(name==='resumePredictions'){
  persistDraft();const status=current.prediction_status||{};
  modal('Tiếp tục tạo gợi ý',`<form data-submit="collaboration:resumePredictions" data-request-key="${crypto.randomUUID()}"><p>Chỉ xử lý các mẫu còn thiếu gợi ý trong video <b>${esc(current.source)}</b>. Kết quả đã có và nhãn người được giữ nguyên.</p><input type="hidden" name="source_id" value="${current.source_id}"><label class="check-row"><input type="checkbox" name="branch" value="local" ${status.local?.can_resume?'checked':'disabled'}> Local · model đã chọn của lượt cũ</label><label class="check-row"><input type="checkbox" name="branch" value="api" ${status.api?.can_resume?'':'disabled'}> LLM API · gọi nhà cung cấp và có thể phát sinh phí</label><p class="form-hint">API chỉ chạy khi bạn đánh dấu nhánh này. Lượt tiếp tục chỉ gồm video đang chọn.</p><div class="form-error-slot"></div><div class="flex gap8"><button type="button" class="btn" data-action="ui:close">Hủy</button><button type="submit" class="btn primary">Tiếp tục tạo gợi ý</button></div></form>`);return;
 }
 if(name==='manageLabels'){persistDraft();rememberWorkspace(state.route);await decisionClock('pause').catch(()=>{});closeModal();navigate('label-management');return;}
 if(name==='guide'){modal('Hướng dẫn gán nhãn',`<p>${esc(state.workspace.preferences.guidelines||current?.human_schema?.guidelines||'Chọn nhãn theo quy tắc của dự án.')}</p>${labelCatalog.labels.filter(l=>l.enabled).map(l=>`<p><b>${esc(l.name)}</b>: ${esc(l.description)}. ${esc(l.exclusions||'')}</p>`).join('')}<p>Bấm nhãn hoặc Dùng gợi ý sẽ lưu ngay và chuyển mẫu sau khi lưu thành công. Thêm ghi chú/cụm từ trước khi chọn nhãn. Khi bất đồng, xem nhãn Local và API rồi chọn nhãn cuối; hệ thống ghi nhận lượt có hỗ trợ máy. Nhãn mới không tự được model hỗ trợ. Phím 1–9: chọn và lưu nhãn; Enter: lưu; Shift + Enter: lưu và tiếp tục.</p>`);return;}
 if(name==='next'||name==='previous'){await adjacent(name==='next'?1:-1);return;}
 if(name==='open'){await openPair(el.dataset.id);document.querySelector('#hitl-workspace-slot')?.scrollIntoView({block:'start'});return;}
 if(name==='skip'){if(!current||locked())return;persistDraft();form().elements.action.value='skip';persistDraft();await submit('decision',form(),{submitter:{dataset:{intent:'next'}}});return;}
 if(['sentence','token','addSpan','removeSpan','clearPick','useLocal','useApi','useConsensus'].includes(name)){
  if(!current||locked())return;persistDraft();
  if(name==='sentence'){if(!labelCatalog.labels.some(l=>l.enabled&&l.key===el.dataset.label))return;pairDraft.selected_label=el.dataset.label;}
  if(name.startsWith('use')){const p=name==='useApi'?current.api:current.local;if(!current.revealed||!p||!labelCatalog.labels.some(l=>l.enabled&&l.key===p.label))return;if(name==='useConsensus'&&(current.state!=='agreement'||p.label!==current.api?.label))return;pairDraft.selected_label=p.label;pairDraft.action='confirm';}
  if(name==='token'){const i=Number(el.dataset.index),picked=new Set(pairDraft.picked);if(event?.shiftKey&&pairDraft.last_pick!==null){for(let j=Math.min(i,pairDraft.last_pick);j<=Math.max(i,pairDraft.last_pick);j++)picked.add(j);}else if(picked.has(i))picked.delete(i);else picked.add(i);pairDraft.picked=[...picked];pairDraft.last_pick=i;}
  if(name==='clearPick')pairDraft.picked=[];
  if(name==='removeSpan')pairDraft.spans.splice(Number(el.dataset.index),1);
  if(name==='addSpan'){const key=document.querySelector('#hitl-span-label').value,groups=[];for(const i of [...pairDraft.picked].sort((a,b)=>a-b)){if(!groups.length||groups.at(-1).at(-1)!==i-1)groups.push([i]);else groups.at(-1).push(i);}for(const group of groups){const start=current.tokens[group[0]].start,end=current.tokens[group.at(-1)].end;pairDraft.spans=pairDraft.spans.filter(s=>s.end<=start||s.start>=end);pairDraft.spans.push({start,end,label:key});}pairDraft.spans.sort((a,b)=>a.start-b.start);pairDraft.picked=[];}
  const savesLabel=name==='sentence'||name.startsWith('use');
  if(savesLabel)pairDraft.action=current.requires_preliminary?'preliminary':'confirm';
  drawPair();persistDraft();
  if(savesLabel){
   try{await submit('decision',form(),{submitter:{dataset:{intent:'next'}}});}
   catch(error){const slot=form()?.querySelector('.form-error-slot');if(slot)slot.innerHTML=`<p class="form-error" role="alert">${esc(error.message)}. Chưa chuyển bình luận; bản nháp được giữ để thử lại.</p>`;throw error;}
  }
  return;
 }
 if(name==='inspect'){persistDraft();inspection=await api(`studio/collaboration/pairs/${el.dataset.id}?supervision=1${sourceQuery()}`);modal('Nhãn con người & duyệt phản hồi',`<p>${esc(inspection.text)}</p>${humanDecisions(inspection)}${inspection.gold?`<p>Gold hiện hành: ${esc(inspection.gold.label)}. ${esc(inspection.gold.note)}</p>`:''}<p>Chỉ phản hồi đã duyệt, đúng phiên bản và không thuộc tập giữ riêng mới được dùng hỗ trợ/train.</p>`);return;}
 if(name==='pause'||name==='resume'){await decisionClock(name);toast(name==='pause'?'Đã tạm dừng':'Đã tiếp tục');return;}
 if(name==='reload'){persistDraft();await refresh();return;}
 if(name==='retry'){persistDraft();await api(`studio/collaboration/runs/${runId}/retry`,{branch:el.dataset.branch,source_id:scopeId||null});await refresh();return;}
 if(name==='report'){modal('Xuất báo cáo ghép cặp',`<form data-submit="collaboration:report">${field('runs','ID lượt cùng schema, cách nhau bằng dấu phẩy',runId,'text','required')}<p>So sánh trên cùng ID/hash; thiếu tham chiếu để metrics trống.</p>${formEnd('Tải JSON')}</form>`);return;}
 if(name==='expose'){persistDraft();await api(`studio/collaboration/pairs/${current.id}/expose`,{source_id:scopeId||null});await openPair(current.id,false);if(data.blind)await refresh();return;}
 if(name==='approve'){await api(`studio/collaboration/decisions/${el.dataset.id}/approve`,{});if(inspection)await action('inspect',{dataset:{id:inspection.id}});toast('Đã duyệt phản hồi.');return;}
 if(name==='start'){modal('Tạo lượt phối hợp',`<form data-submit="collaboration:start"><input type="hidden" name="source_id" value="${scopeId}">${select('model_id','Local',[['','Human/API-only'],...data.models.map(m=>[m.id,m.name+' · '+m.compatibility.state])],state.workspace.preferences.active_model_id||'')}${select('connection_id','LLM API',[['','Không gọi API'],...data.connections.map(c=>[c.id,c.name+' · '+c.model])],state.workspace.preferences.active_connection_id||'')}<label><input name="few_shot" type="checkbox" checked> Truy xuất ví dụ đã duyệt</label><p>Chọn API sẽ gửi bình luận đến nhà cung cấp và có thể phát sinh phí. Chưa có local tương thích thì không có đồng thuận hai model.</p>${formEnd('Bắt đầu')}</form>`);return;}
 if(name==='gold'){persistDraft();inspection=await api(`studio/collaboration/pairs/${el.dataset.id}?adjudication=1${sourceQuery()}`);modal('Người thứ ba phân xử',`<p>${esc(inspection.text)}</p>${humanDecisions(inspection,false)}<form data-submit="collaboration:gold">${select('label','Nhãn cuối',choices(inspection.schema.labels),'')}${textarea('note','Lý do bắt buộc')}${formEnd('Lưu gold')}</form>`);return;}
 if(name==='dataset'){persistDraft();await api('studio/collaboration/dataset',{project,seed:42});await refresh();return;}
 if(name==='train'){const r=await api('studio/collaboration/train',{project,dataset_id:Number(el.dataset.id)});toast('Đã tạo job #'+r.job_id+'. Theo dõi ở Dữ liệu.');return;}
 if(name==='activate')modal('Kích hoạt hoặc rollback',`<form data-submit="collaboration:activate" data-id="${el.dataset.id}">${textarea('note','Lý do sau khi xem validation')}${formEnd('Kích hoạt')}</form>`);
}
export async function submit(name,f,event){
 const project=state.workspace.project.id,v=Object.fromEntries(new FormData(f));
 if(name==='resumePredictions'){
  persistDraft();const editing=structuredClone(pairDraft),branches=[...f.querySelectorAll('input[name=branch]:checked')].map(input=>input.value);
  if(!branches.length)throw new Error('Chọn ít nhất một nhánh để tiếp tục.');
  const result=await api(`studio/collaboration/runs/${runId}/resume`,{source_id:v.source_id,branches,request_key:f.dataset.requestKey,comment_id:current.comment_id});
  if(result.pair_id)writeDraft(scopeDraftKind('pair',v.source_id),{...editing,pair_id:result.pair_id,run_id:result.id,revision:0,source_id:Number(v.source_id),open:true});
  selectAnnotationSource(v.source_id);scopeId=String(v.source_id);runId=result.id;current=null;pairDraft=null;viewState();closeModal();await refresh();toast('Đã tạo lượt tiếp tục cho video này. Gợi ý sẽ tự cập nhật.');return;
 }
 if(name==='report'){await exportFile(`studio/collaboration/report?project=${project}&runs=${encodeURIComponent(v.runs)}&bootstrap=1`,'paired-experiment.json');closeModal();return;}
 if(name==='decision'){
  persistDraft();if(['confirm','preliminary'].includes(v.action)&&!labelCatalog.labels.some(l=>l.enabled&&l.key===v.label))throw new Error('Chọn nhãn đang dùng; bản nháp được giữ.');
  const id=current.id,editing=structuredClone(pairDraft),fields=f.querySelector('fieldset');
  fields.disabled=true;
  try{await api(`studio/collaboration/pairs/${id}/decision`,{...v,spans:editing.spans,revision:editing.revision,annotation_revision:editing.annotation_revision,source_id:scopeId||null});}
  finally{fields.disabled=false;}
  clearDraft(scopeDraftKind('pair',scopeId));clearDraft('pair-'+id);pairDraft=null;
  await openPair(id,false);
  // Preliminary labels are server-side, while unfinished phrase selections remain a browser draft.
  if(v.action==='preliminary'){Object.assign(pairDraft,{spans:editing.spans,picked:editing.picked,last_pick:editing.last_pick});drawPair();persistDraft();}
  const unexposedBlind=['blind','preliminary'].includes(current.mine.status)&&!current.mine.exposed_at;
  if(!unexposedBlind){if(data.blind)await refresh();else rows=await fetchRows();}
  const queue=document.querySelector('#hitl-queue-body');if(queue)queue.innerHTML=humanQueue();
  const progress=document.querySelector('#hitl-progress');if(progress)progress.innerHTML=progressMarkup();
  if(event?.submitter?.dataset.intent==='next'&&v.action!=='preliminary')await adjacent(1,true);
  toast(v.action==='preliminary'?'Đã lưu nhãn độc lập. Bạn có thể mở hai gợi ý.':'Đã lưu quyết định.');return;
 }
 if(name==='gold')await api(`studio/collaboration/pairs/${inspection.id}/adjudicate`,{...v,source_id:scopeId||null,revision:inspection.mine?.revision||0,annotation_revision:inspection.annotation_revision,gold_revision:inspection.gold_revision||0});
 if(name==='start'){persistDraft();const r=await api('studio/collaboration/start',{...v,project,model_id:v.model_id||null,connection_id:v.connection_id||null,few_shot:f.few_shot.checked,request_key:crypto.randomUUID()});runId=r.id;current=null;clearDraft(scopeDraftKind('pair',scopeId));viewState();}
 if(name==='activate')await api('studio/collaboration/activate',{...v,project,model_id:Number(f.dataset.id)});
 closeModal();await refresh();
}
export async function change(e){
 if(e.target.id==='annotation-source-scope'){if(state.busy){e.target.value=annotationSourceId();return;}state.busy=true;try{persistDraft();await decisionClock('pause').catch(()=>{});selectAnnotationSource(e.target.value);current=null;pairDraft=null;await refresh();}finally{state.busy=false;}return;}
 if(e.target.id==='human-queue-filter'){persistDraft();queueFilter=e.target.value;viewState();if(pairDraft){pairDraft.queue_filter=queueFilter;writeDraft(scopeDraftKind('pair',scopeId),pairDraft);}document.querySelector('#hitl-queue-body').innerHTML=humanQueue();}
 if(e.target.id==='paired-run'){persistDraft();if(current&&['blind','preliminary'].includes(current.mine.status)&&!current.mine.exposed_at){e.target.value=runId;toast('Hoàn tất hoặc bỏ qua mẫu độc lập trước khi đổi lượt.');return;}await decisionClock('pause').catch(()=>{});clearDraft(scopeDraftKind('pair',scopeId));runId=e.target.value;current=null;pairDraft=null;viewState();await refresh();}
}
export function keyboard(e){if(!current||!form())return;if(/^[1-9]$/.test(e.key)){const l=labelCatalog.labels.filter(l=>l.enabled)[Number(e.key)-1];if(l)[...document.querySelectorAll('[data-action="collaboration:sentence"]')].find(b=>b.dataset.label===l.key)?.click();}if(e.key==='Enter'){e.preventDefault();form().querySelector(`[type="submit"][data-intent="${e.shiftKey?'next':'stay'}"]:not(:disabled)`)?.click();}}
