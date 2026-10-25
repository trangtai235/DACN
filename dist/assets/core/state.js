export const state={workspace:null,route:'overview',data:null,language:localStorage.getItem('annotaflow.language')==='en'?'en':'vi',busy:false};
export const DEMO=document.body.dataset.mode!=='api';
export const T=(vi,en)=>state.language==='en'?(en||vi):vi;
export const setWorkspace=value=>state.workspace=value;
export const currentModel=()=>state.workspace?.models?.find(m=>m.id===state.workspace.preferences?.active_model_id)||state.workspace?.models?.[0];
