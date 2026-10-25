import {state,DEMO} from '../../core/state.js?v=f62135f1ecf7';
import {api} from '../../core/api.js?v=f62135f1ecf7';
import {refresh} from '../../core/events.js?v=f62135f1ecf7';
import {T,esc,heading,btn,panel,select,formEnd,modal,closeModal,toast,num,pct,date,nativeRequired} from '../../core/ui.js?v=f62135f1ecf7';

let listing={runs:[],api_ready:false},detail=null,selected=null,projectId=null,page=1,onlyDifferent=false,query='';
const active=job=>job&&['queued','running'].includes(job.status);
const duration=ms=>ms==null?'—':ms<1000?`${Math.round(ms)} ms`:ms<60000?`${(ms/1000).toFixed(1)} ${T('giây','sec')}`:`${Math.floor(ms/60000)} ${T('phút','min')} ${Math.round(ms%60000/1000)} ${T('giây','sec')}`;
const status=job=>({queued:T('Đang chờ','Queued'),running:T('Đang chạy','Running'),complete:T('Hoàn tất','Complete'),failed:T('Có lỗi','Failed'),cancelled:T('Đã dừng','Stopped')})[job?.status]||'—';
export async function load(){
 const id=state.workspace.project.id;
 if(projectId!==id){projectId=id;selected=null;page=1;onlyDifferent=false;query='';}
 if(DEMO){listing={runs:[],api_ready:false};detail=null;return;}
 listing=await api('studio/auto-label/runs?project='+id);
 if(!listing.runs.some(r=>r.id===selected))selected=listing.runs[0]?.id||null;
 detail=selected?await api(`studio/auto-label/runs/${selected}?page=${page}&different=${onlyDifferent?1:0}&q=${encodeURIComponent(query)}`):null;
}
export const hasActiveJobs=()=>Boolean(detail&&(active(detail.run.local)||active(detail.run.llm)));
function label(result,labels){if(!result)return `<span class="auto-pending">${T('Chưa có kết quả','Pending')}</span>`;const item=labels.find(l=>l.key===result.label);return `<span class="auto-label" style="--label:${safeColor(item?.color)}">${esc(item?.name||result.label)}</span>`;}
const safeColor=value=>/^#[\da-f]{6}$/i.test(value||'')?value:'#5479a5';
function chart(job){
 const total=job.completed;let offset=0;
 const slices=job.distribution.map(l=>{const start=offset;offset+=total?l.count/total*100:0;return `${safeColor(l.color)} ${start}% ${offset}%`;});
 return `<div class="auto-chart-layout"><div class="auto-donut" role="img" aria-label="${esc(job.distribution.map(l=>`${l.name}: ${l.count} (${pct(total?l.count/total:0)})`).join(', '))}" style="background:${total?'conic-gradient('+slices.join(',')+')':'#e9eef4'}"><div><strong>${num(total)}</strong><small>${T('đã gán','labelled')}</small></div></div><ul class="auto-legend">${job.distribution.map(l=>`<li><span class="auto-dot" style="background:${safeColor(l.color)}"></span><span>${esc(l.name)}</span><b>${pct(total?l.count/total:0)}</b><small>${num(l.count)}</small></li>`).join('')}</ul></div>`;
}
function branchCard(run,key){
 const job=run[key];if(!job)return '';
 const can=state.workspace.project.can_manage;
 return `<section class="panel auto-branch"><div class="auto-branch-head"><div><span class="auto-eyebrow">${key==='local'?'ML LOCAL':'LLM · API'}</span><h2>${esc(key==='local'?run.model:run.connection)}</h2></div><span class="auto-status ${job.status}">${status(job)}</span></div><div class="auto-branch-body">${chart(job)}<div class="auto-metrics"><div><span>${T('Tổng thời gian chạy','Elapsed processing time')}</span><strong>${duration(job.elapsed_ms)}</strong></div><div><span>${T('Trung bình / bình luận','Average / comment')}</span><strong>${job.completed?duration(job.elapsed_ms/job.completed):'—'}</strong></div><div><span>${T('Tiến độ','Progress')}</span><strong>${num(job.completed)} / ${num(run.count)}</strong></div></div><div class="progress"><span style="width:${Math.min(100,job.progress)}%"></span></div><div class="auto-job-note"><span>${esc(job.message||'')}</span>${can?(active(job)?btn(T('Dừng','Stop'),'annotation:control','sm danger','',`data-branch="${key}" data-mode="cancel"`):['failed','cancelled'].includes(job.status)?btn(T('Tiếp tục phần còn lại','Resume remaining'),'annotation:control','sm','refresh',`data-branch="${key}" data-mode="retry"`):''):''}</div></div></section>`;
}
function comparison(run){
 if(!run.llm)return `<div class="info-banner">${T('Lượt này chạy ML Local. Thêm API key trong Model & API để lượt tiếp theo chạy thêm LLM trên cùng dữ liệu.','This run uses ML Local. Add an API key in Models & API to include LLM in the next run.')}</div>`;
 const bothComplete=run.local?.status==='complete'&&run.llm.status==='complete';
 const ratio=run.local?.elapsed_ms>0?run.llm.elapsed_ms/run.local.elapsed_ms:null;
 return `<section class="auto-comparison"><div><span>${T('Đã có kết quả cả hai luồng','Completed by both branches')}</span><strong>${num(detail.paired_count)} / ${num(run.count)}</strong></div><div><span>${T('Nhãn khác nhau','Different labels')}</span><strong>${num(detail.different_count)} <small>(${pct(detail.paired_count?detail.different_count/detail.paired_count:0)})</small></strong></div><div><span>${T('Thời gian LLM / ML Local','LLM / ML Local time')}</span><strong>${bothComplete&&ratio?ratio.toFixed(2)+'×':T('Chờ hai luồng hoàn tất','Waiting for completion')}</strong></div></section>`;
}
export function render(){
 const can=state.workspace.project.can_manage,run=detail?.run;
 const running=listing.runs.some(r=>active(r.local)||active(r.llm));
 const actions=btn(T('Làm mới','Refresh'),'annotation:reload','','refresh')+(can?btn(T('Bắt đầu gán nhãn','Start auto labelling'),'annotation:start','primary','play',running?'disabled':''):'');
 let html=heading(T('Gán nhãn tự động','Automatic labelling'),T('ML Local và LLM chạy độc lập trên cùng bình luận, cùng bộ nhãn.','ML Local and LLM run independently on the same comments and label schema.'),actions);
 if(DEMO)return html+panel(T('Chạy trên backend','Run with the backend'),T('Mở source Django để chạy model, gọi API và lưu kết quả thực tế.','Run the Django source to execute models, call the API and store real results.'));
 html+=`<div class="auto-mode-banner"><span class="auto-dot" style="background:${listing.api_ready?'#159a82':'#527eb5'}"></span><div><b>${listing.api_ready?T('Sẵn sàng chạy 2 luồng song song','Ready for two parallel branches'):T('Sẵn sàng chạy ML Local','Ready for ML Local')}</b><p>${listing.api_ready?esc(listing.connection)+' · '+T('LLM sẽ dùng đúng bộ nhãn và số bình luận của ML Local. Gọi API có thể phát sinh phí.','LLM uses the exact same labels and comments as ML Local. API calls may incur charges.'):T('Chưa có API key. ML Local vẫn có thể gán nhãn toàn bộ dữ liệu.','No API key configured. ML Local can still label the entire dataset.')}</p></div><a class="btn sm" href="#models">${T('Model & API','Models & API')}</a></div>`;
 if(!run)return html+`<div class="auto-empty panel"><h2>${T('Chưa có lượt gán nhãn','No runs yet')}</h2><p>${T('Nhập dữ liệu, chọn model rồi bắt đầu. Kết quả và biểu đồ sẽ xuất hiện tại đây.','Import data, choose a model and start. Results and charts will appear here.')}</p><a href="#datasets" class="btn">${T('Đến dữ liệu','Open data')}</a></div>`;
 html+=`<div class="auto-run-picker"><label for="auto-run">${T('Lượt chạy','Run')}</label><select id="auto-run">${listing.runs.map(r=>`<option value="${r.id}" ${r.id===run.id?'selected':''}>#${r.id} · ${date(r.created_at)} · ${r.count} ${T('bình luận','comments')} · ${r.llm?'ML + LLM':'ML Local'}</option>`).join('')}</select><a class="btn sm" href="/api/studio/auto-label/runs/${run.id}?download=csv">${T('Tải kết quả CSV','Download CSV')}</a></div>`;
 html+=`<div class="auto-branches ${run.llm?'paired':''}">${branchCard(run,'local')}${branchCard(run,'llm')}</div>`+comparison(run);
 html+=`<p class="auto-timing-note">${T('Thời gian tính riêng từng luồng, gồm chuẩn bị model/API và lưu kết quả; không cộng thời gian chờ hàng đợi hoặc thời gian dừng. Biểu đồ tính trên kết quả đã gán của mỗi luồng. Nhãn khác nhau là khác nhãn câu, không phải kết luận đúng/sai.','Each branch is timed independently, including preparation and result storage; queue and paused time are excluded. Charts use completed results per branch. Disagreement means different sentence labels, not correctness.')}</p>`;
 const pages=Math.max(1,Math.ceil(detail.total/30));
 html+=panel(T('Danh sách kết quả','Results'),`<form class="auto-filters" data-submit="annotation:filter"><input name="q" value="${esc(query)}" placeholder="${T('Tìm bình luận…','Search comments…')}" aria-label="${T('Tìm bình luận','Search comments')}">${run.llm?`<label class="check-row"><input type="checkbox" name="different" ${onlyDifferent?'checked':''}>${T('Chỉ xem nhãn khác nhau','Only different labels')}</label>`:''}<button class="btn sm" type="submit">${T('Lọc','Filter')}</button><span>${num(detail.total)} ${T('bình luận','comments')}</span></form><div class="table-wrap"><table class="auto-results"><thead><tr><th>${T('Bình luận','Comment')}</th><th>ML Local</th>${run.llm?'<th>LLM API</th><th>'+T('So sánh','Comparison')+'</th>':''}</tr></thead><tbody>${detail.rows.map(row=>`<tr class="${row.different?'auto-disagreement':''}"><td><small>#${row.id} · ${esc(row.source)}</small><p>${esc(row.text)}</p></td><td>${label(row.local,run.labels)}${row.local?`<small class="auto-latency">${duration(row.local.latency_ms)}</small>`:''}</td>${run.llm?`<td>${label(row.llm,run.labels)}${row.llm?`<small class="auto-latency">${duration(row.llm.latency_ms)}</small>`:''}</td><td>${row.different?`<span class="auto-diff-badge">${T('Khác nhãn','Different')}</span>`:row.local&&row.llm?`<span class="auto-agree">${T('Cùng nhãn','Same label')}</span>`:'—'}</td>`:''}</tr>`).join('')||`<tr><td colspan="${run.llm?4:2}" class="auto-empty">${onlyDifferent?T('Chưa có bình luận khác nhãn trong các mẫu đã có đủ hai kết quả.','No different labels among paired results.'):T('Chưa có kết quả phù hợp.','No matching results yet.')}</td></tr>`}</tbody></table></div><div class="auto-pagination">${btn(T('Trước','Previous'),'annotation:page','sm','',`data-page="${Math.max(1,page-1)}" ${page===1?'disabled':''}`)}<span>${page} / ${pages}</span>${btn(T('Tiếp','Next'),'annotation:page','sm','',`data-page="${page+1}" ${page>=pages?'disabled':''}`)}</div>`);
 return html;
}
export async function action(name,el){
 if(name==='reload'){await refresh();return;}
 if(DEMO){nativeRequired();return;}
 if(name==='start'){
  const source=sessionStorage.getItem('annotaflow.annotationSource.'+state.workspace.project.id)||'';
  modal(T('Bắt đầu gán nhãn tự động','Start automatic labelling'),`<form data-submit="annotation:start">${select('model_id',T('ML Local','ML Local'),state.workspace.models.map(m=>[m.id,m.name]),state.workspace.preferences.active_model_id)}${select('source_id',T('Dữ liệu cần gán','Data scope'),[['',T('Tất cả nguồn','All sources')],...state.workspace.sources.map(s=>[s.id,s.name+' · '+s.count])],source)}<div class="info-banner">${listing.api_ready?T('Chạy ML Local và LLM song song trên cùng dữ liệu. Luồng LLM sẽ gọi API thật và có thể phát sinh phí.','Run ML Local and LLM in parallel on the same data. LLM sends real API requests and may incur charges.'):T('Chưa có API key: chỉ chạy ML Local.','No API key: run ML Local only.')}</div><p class="form-hint">${T('Mỗi lượt lưu riêng kết quả và bộ nhãn tại thời điểm bắt đầu.','Each run saves its own results and the label schema at launch.')}</p>${formEnd(T('Chạy gán nhãn','Run labelling'))}</form>`);return;
 }
 if(name==='page'){page=Number(el.dataset.page);await refresh();return;}
 if(name==='control'){await api(`studio/auto-label/runs/${selected}/control`,{branch:el.dataset.branch,action:el.dataset.mode});await refresh();}
}
export async function submit(name,form){
 if(name==='filter'){query=form.q.value;onlyDifferent=Boolean(form.different?.checked);page=1;await refresh();return;}
 if(name==='start'){
  const values=Object.fromEntries(new FormData(form));const result=await api('studio/auto-label/start',{...values,project:state.workspace.project.id});
  selected=result.id;page=1;onlyDifferent=false;query='';sessionStorage.removeItem('annotaflow.annotationSource.'+state.workspace.project.id);closeModal();await refresh();toast(T('Đã bắt đầu gán nhãn tự động.','Automatic labelling started.'));
 }
}
export async function change(event){if(event.target.id==='auto-run'){selected=Number(event.target.value);page=1;onlyDifferent=false;await refresh();}}
export function keyboard(){}
