import {state} from './state.js?v=78e859b430db';
const key=kind=>`annotaflow.draft.${state.workspace?.user?.id}.${state.workspace?.project?.id}.${kind}`;
export function readDraft(kind){try{return JSON.parse(sessionStorage.getItem(key(kind))||'null');}catch{return null;}}
export function writeDraft(kind,value){sessionStorage.setItem(key(kind),JSON.stringify(value));}
export function clearDraft(kind){sessionStorage.removeItem(key(kind));}
export function rememberWorkspace(route){writeDraft('label-return',{route});}
export function returnWorkspace(){const route=readDraft('label-return')?.route;return ['manual-annotation','human-review','collaboration'].includes(route)?route:'manual-annotation';}
