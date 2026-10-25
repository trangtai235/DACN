import {T,esc,heading,btn,panel,pct,num} from '../../core/ui.js?v=f62135f1ecf7';

export function renderSpans(model){
 const report=model.report,metrics=report.span_metrics||{};
 const rows=Object.entries(metrics).filter(([,v])=>v&&typeof v==='object'&&'f1' in v);
 return heading(T('Đánh giá model','Model evaluation'),esc(model.name),btn(T('Tải báo cáo','Download report'),'evaluation:download','','download'))+
 panel(T('Kết quả đánh giá span trên tập test','Test-set span evaluation'),
 `<p class="form-hint">${T('Chỉ số từ báo cáo model được cung cấp, chưa đo lại trong ứng dụng. Đây là đánh giá span, không phải độ chính xác phân loại câu.','Metrics from the supplied model report, not re-evaluated in this app. These evaluate spans, not sentence classification accuracy.')}</p>`+
 (rows.length?`<div class="table-wrap"><table><thead><tr><th>${T('Cách đo','Metric')}</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>${rows.map(([key,v])=>`<tr><td>${esc(key)}</td><td>${pct(v.precision)}</td><td>${pct(v.recall)}</td><td>${pct(v.f1)}</td></tr>`).join('')}</tbody></table></div>`:
 `<p>${T('Chưa có chỉ số span trên tập test trong báo cáo này.','This report contains no test-set span metrics.')}</p>`))+
 panel(T('Thông tin model','Model details'),`<div class="summary-list"><div><span>Model</span><b>${esc(report.original_metrics?.model||model.name)}</b></div><div><span>Train</span><b>${report.counts?.train==null?'—':num(report.counts.train)}</b></div></div><p class="form-hint">${T('Chưa có báo cáo phân loại câu hoặc so sánh API cho model này.','No sentence classification report or API comparison is available for this model.')}</p>`);
}
