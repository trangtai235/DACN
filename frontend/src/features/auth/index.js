import {authMarkup} from './view.js';
import {state,DEMO,T} from '../../core/state.js';
import {api} from '../../core/api.js';
import {toast} from '../../core/ui.js';
export function render(view='login'){
 document.body.classList.add('is-auth');
 document.documentElement.lang=state.language;
 document.querySelector('#app').innerHTML=authMarkup({view,lang:state.language,demo:DEMO});
}
export async function submit(form){const v=Object.fromEntries(new FormData(form));
 if(DEMO)return;
 if(form.id==='recovery-form'){
  if(form.dataset.view==='forgot')await api('studio/password/request',v);
  else {const [user_id,token]=(sessionStorage.getItem('annotaflow.reset')||'').split('~');await api('studio/password/reset',{...v,user_id,token});}
  toast(T('Đã xử lý. Kiểm tra kênh email được cấu hình hoặc đăng nhập bằng mật khẩu mới.','Request processed. Check the configured email channel or sign in with your new password.'));location.hash='login';return false;
 }
 const result=await api(form.id==='register-form'?'register':'login',v);
 if(result.verification_required){toast(T('Tài khoản đã tạo. Mở email xác minh trước khi đăng nhập.','Account created. Verify your email before signing in.'));location.hash='login';return false;}
 return true;
}
