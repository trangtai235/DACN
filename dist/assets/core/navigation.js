import {T} from './state.js?v=00d8c624ac88';
import {icon} from './icons.js?v=00d8c624ac88';

export const nav = [
 ['overview','Tổng quan','Overview','chart'],
 ['datasets','Dữ liệu','Data','database'],
 ['annotation','Gán nhãn tự động','Auto labelling','brain'],
 ['human-review','Người duyệt nhãn (HITL)','Human-in-the-loop','users'],
 ['manual-annotation','Gán nhãn thủ công','Manual annotation','edit'],
 ['label-management','Quản lý nhãn','Label management','layers'],
 ['budget','Kiểm tra theo ngân sách','Budgeted review','chart'],
 ['exports','Xuất dữ liệu','Export','download'],
 ['members','Thành viên','Members','users'],
 ['project-settings','Cài đặt dự án','Project settings','settings'],
 ['models','Mô hình & API','Models & API','brain'],
 ['evaluation','Đánh giá','Evaluation','chart'],
];

export function navigation(route) {
 const link = ([id,vi,en,ico]) => `<a href="#${id}" class="nav-item ${route===id?'active':''}" ${route===id?'aria-current="page"':''}>${icon(ico,18)}<span>${T(vi,en)}</span></a>`;
 return `<nav aria-label="${T('Điều hướng dự án','Project navigation')}">${nav.slice(0,6).map(link).join('')}<details class="advanced-nav" ${nav.slice(6).some(item=>item[0]===route)?'open':''}><summary>${icon('settings',17)}${T('Nâng cao','Advanced')}</summary>${nav.slice(6).map(link).join('')}</details></nav>`;
}
