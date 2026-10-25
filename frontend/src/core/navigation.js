import {T} from './state.js';
import {icon} from './icons.js';

export const nav = [
 ['overview','Tổng quan','Overview','chart'],
 ['datasets','Dữ liệu','Data','database'],
 ['annotation','Gán nhãn tự động','Auto labelling','brain'],
 ['exports','Xuất dữ liệu','Export','download'],
 ['members','Thành viên','Members','users'],
 ['project-settings','Cài đặt dự án','Project settings','settings'],
 ['models','Mô hình & API','Models & API','brain'],
 ['evaluation','Đánh giá','Evaluation','chart'],
];

export function navigation(route) {
 const link = ([id,vi,en,ico]) => `<a href="#${id}" class="nav-item ${route===id?'active':''}" ${route===id?'aria-current="page"':''}>${icon(ico,18)}<span>${T(vi,en)}</span></a>`;
 return `<nav aria-label="${T('Điều hướng dự án','Project navigation')}">${nav.slice(0,4).map(link).join('')}<details class="advanced-nav" ${nav.slice(4).some(item=>item[0]===route)?'open':''}><summary>${icon('settings',17)}${T('Nâng cao','Advanced')}</summary>${nav.slice(4).map(link).join('')}</details></nav>`;
}
