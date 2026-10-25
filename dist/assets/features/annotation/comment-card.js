import {T,esc,icon} from '../../core/ui.js?v=2a0a4e3abb7b';

export function commentCard(row){
 const youtube=row.source_kind==='youtube';
 const author=row.author||T('Không có tên tác giả','Unknown author');
 const initial=Array.from(author.replace(/^@/,''))[0]||'?';
 const date=row.published_at?new Date(row.published_at):null;
 const timestamp=date&&!Number.isNaN(date.getTime())?date.toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'}):'';
 const url=youtube&&row.video_id?`https://www.youtube.com/watch?v=${encodeURIComponent(row.video_id)}${row.external_id?'&lc='+encodeURIComponent(row.external_id):''}`:'';
 return `<article class="yt-comment-card" aria-label="${T('Bình luận gốc','Original comment')}">
 <div class="yt-comment-source"><span>${youtube?icon('youtube',18):icon('message',18)}${youtube?'YouTube':T('Bình luận','Comment')}</span>${url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${T('Xem trên YouTube','View on YouTube')} ${icon('arrow',14)}</a>`:''}</div>
 <div class="yt-comment-main"><span class="yt-comment-avatar" aria-hidden="true">${esc(initial.toUpperCase())}</span><div class="yt-comment-content"><div class="yt-comment-byline"><b>${esc(author)}</b>${timestamp?`<time datetime="${esc(row.published_at)}">${esc(timestamp)}</time>`:''}</div><p class="yt-comment-text">${esc(row.text)}</p>${row.context?`<details class="yt-comment-parent"><summary>${T('Xem bình luận cha','View parent comment')}</summary><p>${esc(row.context)}</p></details>`:''}</div></div>
 ${row.source?`<p class="yt-comment-video">${T('Nguồn','Source')}: ${esc(row.source)}</p>`:''}</article>`;
}
