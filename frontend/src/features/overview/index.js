import {api} from '../../core/api.js';
﻿import {state,DEMO} from '../../core/state.js';
import {T,esc,icon,heading,btn,num,pct} from '../../core/ui.js';
let latest=null;
export async function load(){latest=DEMO?null:(await api('studio/auto-label/runs?project='+state.workspace.project.id)).runs[0];}
export function render(){
 const s=state.workspace,total=latest?.count||s.stats.total||0,done=latest?.local?.completed||0;
 const progress=total?Math.min(100,done/total*100):0;
 return heading(esc(s.project.name),T('Nhập dữ liệu, gán nhãn và tải kết quả.','Import data, annotate and download results.'))+`
 <section class="simple-progress panel"><div><h2>${T('Tiến độ ML Local · lượt gần nhất','ML Local progress · latest run')}</h2><p><strong>${num(done)}</strong> / ${num(total)} ${T('bình luận đã có nhãn','comments labelled')}</p></div><b>${pct(total?done/total:0)}</b><div class="progress" role="progressbar" aria-label="${T('Tiến độ ML Local · lượt gần nhất','ML Local progress · latest run')}" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100"><span style="width:${progress}%"></span></div></section>
 <div class="simple-steps">
 <section class="panel simple-step"><span class="step-number">1</span><h2>${T('Nhập dữ liệu','Import data')}</h2><p>${T('Thêm bình luận từ YouTube, tệp CSV hoặc văn bản.','Add comments from YouTube, a CSV file or text.')}</p>${btn(T('Nhập dữ liệu','Import data'),'datasets:import',total?'':'primary','upload')}<a href="#datasets">${T('Xem dữ liệu','View data')} ${icon('arrow',14)}</a></section>
 <section class="panel simple-step"><span class="step-number">2</span><h2>${T('Gán nhãn','Annotate')}</h2><p>${T('ML Local tự gán nhãn; có API key thì LLM chạy song song để so sánh.','ML Local labels automatically; with an API key, LLM runs in parallel for comparison.')}</p><a class="btn ${total?'primary':''}" href="#annotation">${icon('edit',15)}${T('Bắt đầu gán nhãn','Start annotating')}</a></section>
 <section class="panel simple-step"><span class="step-number">3</span><h2>${T('Xuất dữ liệu','Export data')}</h2><p>${T('Tải dữ liệu và nhãn đã lưu về máy của bạn.','Download your data and saved annotations.')}</p><a class="btn" href="#exports">${icon('download',15)}${T('Tải kết quả','Download results')}</a></section>
 </div><p class="simple-help">${T('Cần quản lý thành viên, cấu hình nhãn hoặc dùng AI? Mở mục Nâng cao ở menu.','For members, label settings or AI tools, open Advanced in the menu.')}</p>`;
}
