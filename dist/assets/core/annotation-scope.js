import {state} from './state.js?v=78e859b430db';
import {esc} from './ui.js?v=78e859b430db';

const storageKey=()=>`annotaflow.annotationSource.${state.workspace.project.id}`;
export const annotationSourceId=()=>sessionStorage.getItem(storageKey())||'';
export const annotationSource=()=>state.workspace.sources.find(s=>String(s.id)===annotationSourceId());
export const sourceQuery=()=>annotationSourceId()?'&source='+encodeURIComponent(annotationSourceId()):'';
export const scopeDraftKind=(kind,id=annotationSourceId())=>id?`${kind}.source.${id}`:kind;
export function selectAnnotationSource(value){
 const id=String(value||'');
 if(id&&!state.workspace.sources.some(s=>String(s.id)===id))throw new Error('Video/nguồn không thuộc dự án hiện tại.');
 if(id)sessionStorage.setItem(storageKey(),id);else sessionStorage.removeItem(storageKey());
 sessionStorage.removeItem('annotaflow.openComment');
}
export function sourceScopeBar(route){
 const selected=annotationSourceId();
 return `<div class="annotation-source-scope"><label for="annotation-source-scope">Video / nguồn đang gán</label><select id="annotation-source-scope"><option value="">Toàn dự án</option>${state.workspace.sources.map(s=>`<option value="${s.id}" ${String(s.id)===selected?'selected':''}>${esc(s.name)} · ${s.count} bình luận</option>`).join('')}</select><a class="btn sm" href="#datasets">Chọn video</a>${route!=='human-review'?'<a class="btn sm" href="#human-review">Duyệt gợi ý (HITL)</a>':''}${route!=='manual-annotation'?'<a class="btn sm" href="#manual-annotation">Gán thủ công</a>':''}</div>`;
}
