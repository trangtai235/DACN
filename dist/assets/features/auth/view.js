import {icon} from '../../core/icons.js?v=f62135f1ecf7';

export const authText = {
 vi: {
  user:'Tên đăng nhập', userHint:'Tên đăng nhập của bạn', password:'Mật khẩu', passwordHint:'Nhập mật khẩu',
  remember:'Ghi nhớ đăng nhập', login:'Đăng nhập', register:'Tạo tài khoản', name:'Họ và tên', nameHint:'Nguyễn Minh Anh',
  email:'Địa chỉ email', emailHint:'ban@example.com', confirm:'Nhập lại mật khẩu', confirmHint:'Xác nhận mật khẩu',
  passwordHelp:'Ít nhất 8 ký tự; tránh mật khẩu phổ biến hoặc chỉ gồm số.', show:'Hiện mật khẩu', hide:'Ẩn mật khẩu',
  noAccount:'Chưa có tài khoản?', hasAccount:'Đã có tài khoản?', forgot:'Quên mật khẩu?', back:'Về đăng nhập',
  eyebrow:'KHÔNG GIAN CỦA BẠN', loginTitle:'Rất vui được\ngặp lại bạn.', registerTitle:'Khởi đầu mới.\nCùng nhau tạo giá trị.',
  loginIntro:'Đăng nhập để tiếp tục hành trình cùng dữ liệu.', registerIntro:'Tạo tài khoản và bắt đầu không gian làm việc của bạn.',
  storyEyebrow:'DỮ LIỆU TỐT BẮT ĐẦU TỪ BẠN', storyTitle:'Mỗi góc nhìn.\nMột giá trị mới.',
  storyCopy:'Kết nối con người và AI để biến những bình luận tiếng Việt thành dữ liệu có ý nghĩa.',
  preview:'MỘT GÓC KHÔNG GIAN LÀM VIỆC', previewStatus:'Mẫu minh họa', quote:'Video giải thích rất rõ ràng,', quoteAccent:'cảm ơn bạn đã chia sẻ!',
  context:'BÌNH LUẬN TIẾNG VIỆT', label:'Tích cực', annotation:'Gán nhãn cùng ngữ cảnh', annotationNote:'Một câu chữ. Nhiều góc nhìn.',
  stepOne:'Kết nối dữ liệu', stepTwo:'Gán nhãn cùng nhau', stepThree:'Tạo giá trị mới',
  footer:'Gán nhãn rõ ràng. Nghiên cứu có chiều sâu.', realNote:'Tài khoản mới có không gian riêng. Tham gia dự án khác bằng lời mời.',
  secure:'Sẵn sàng cho không gian làm việc của bạn', demoTitle:'Khám phá AnnotaFlow',
  demoNote:'Đây là bản minh họa trên trình duyệt. Đăng nhập và đăng ký được mở ở bản backend.', demoButton:'Trải nghiệm không gian demo',
  forgotTitle:'Tìm lại\nkhông gian của bạn.', forgotIntro:'Nhập email tài khoản để nhận hướng dẫn đặt lại mật khẩu.',
  resetTitle:'Một mật khẩu mới.\nMột khởi đầu mới.', resetIntro:'Chọn mật khẩu mới để quay lại không gian làm việc.', newPassword:'Mật khẩu mới', continue:'Tiếp tục',
 },
 en: {
  user:'Username', userHint:'Your username', password:'Password', passwordHint:'Enter your password',
  remember:'Remember me', login:'Sign in', register:'Create account', name:'Full name', nameHint:'Alex Nguyen',
  email:'Email address', emailHint:'you@example.com', confirm:'Confirm password', confirmHint:'Enter it once more',
  passwordHelp:'At least 8 characters. Avoid common or entirely numeric passwords.', show:'Show password', hide:'Hide password',
  noAccount:'New around here?', hasAccount:'Already have an account?', forgot:'Forgot password?', back:'Back to sign in',
  eyebrow:'YOUR WORKSPACE', loginTitle:'Good to\nsee you again.', registerTitle:'A fresh start.\nA shared purpose.',
  loginIntro:'Sign in and pick up your journey with data.', registerIntro:'Create an account. Make room for your next idea.',
  storyEyebrow:'BETTER DATA BEGINS WITH YOU', storyTitle:'Every perspective.\nA new possibility.',
  storyCopy:'Bring people and AI together to turn Vietnamese comments into meaningful data.',
  preview:'A GLIMPSE OF YOUR WORKSPACE', previewStatus:'Illustrative sample', quote:'This video explains it so clearly,', quoteAccent:'thanks for sharing!',
  context:'VIETNAMESE COMMENT', label:'Positive', annotation:'Annotate with context', annotationNote:'One sentence. Many perspectives.',
  stepOne:'Connect your data', stepTwo:'Annotate together', stepThree:'Create new value',
  footer:'Clear annotations. Deeper understanding.', realNote:'Your new account starts with a private workspace. Join other projects by invitation.',
  secure:'A place for your next great piece of work', demoTitle:'Meet AnnotaFlow',
  demoNote:'This is a browser demo. Sign-in and registration are available in the backend edition.', demoButton:'Explore the demo workspace',
  forgotTitle:'Find your\nway back.', forgotIntro:'Enter your account email to receive password reset instructions.',
  resetTitle:'A new password.\nA fresh start.', resetIntro:'Choose a new password to return to your workspace.', newPassword:'New password', continue:'Continue',
 },
};

export function authMarkup({view='login', lang='vi', demo=false}) {
 const t = authText[lang] || authText.vi;
 const register = view === 'register';
 const recovery = view === 'forgot' || view === 'reset';
 const intro = recovery ? (view === 'forgot' ? t.forgotIntro : t.resetIntro) : register ? t.registerIntro : t.loginIntro;
 const field = (id, name, label, placeholder, type='text', autocomplete='') => {
  const password = type === 'password';
  const symbol = password ? 'lock' : name === 'email' ? 'globe' : 'users';
  const help = password && (register || view === 'reset') && name === 'password';
  return `<div class="auth-field"><label for="${id}">${label}</label><div class="auth-input-wrap">${icon(symbol,18)}<input id="${id}" name="${name}" type="${type}" placeholder="${placeholder}" autocomplete="${autocomplete}" required ${name==='email'?'maxlength="254"':!password?'maxlength="150"':''} ${password && (register || view==='reset')?'minlength="8"':''} ${help?'aria-describedby="auth-password-help"':''} ${demo?'disabled':''}>${password?`<button type="button" class="auth-eye" data-action="togglePassword" data-target="${id}" aria-label="${t.show}" data-show-label="${t.show}" data-hide-label="${t.hide}" aria-pressed="false" ${demo?'disabled':''}>${icon('eye',18)}</button>`:''}</div></div>`;
 };
 const passwordHelp = `<p id="auth-password-help" class="auth-password-help">${icon('info',14)}<span>${t.passwordHelp}</span></p>`;
 let fields;
 if (view === 'forgot') {
  fields = field('auth-email','email',t.email,t.emailHint,'email','email');
 } else if (view === 'reset') {
  fields = field('auth-password','password',t.newPassword,t.passwordHint,'password','new-password') + field('auth-confirm','password_confirm',t.confirm,t.confirmHint,'password','new-password') + passwordHelp;
 } else if (register) {
  fields = `<div class="auth-field-grid">${field('auth-name','first_name',t.name,t.nameHint,'text','name')}${field('auth-username','username',t.user,t.userHint,'text','username')}</div>${field('auth-email','email',t.email,t.emailHint,'email','email')}<div class="auth-field-grid">${field('auth-password','password',t.password,t.passwordHint,'password','new-password')}${field('auth-confirm','password_confirm',t.confirm,t.confirmHint,'password','new-password')}</div>${passwordHelp}`;
 } else {
  fields = field('auth-username','username',t.user,t.userHint,'text','username') + field('auth-password','password',t.password,t.passwordHint,'password','current-password') + `<div class="auth-options"><label class="auth-remember"><input type="checkbox" name="remember" ${demo?'disabled':''}><span>${t.remember}</span></label>${!demo?`<a href="#forgot">${t.forgot}</a>`:''}</div>`;
 }
 const action = recovery ? t.continue : register ? t.register : t.login;
 return `<main class="auth-screen ${register?'auth-register':''}">
  <header class="auth-topbar"><a class="auth-wordmark" href="#login">${icon('layers',24)}<span>AnnotaFlow</span></a><div class="auth-languages" role="group" aria-label="${lang==='en'?'Language':'Ngôn ngữ'}">${['vi','en'].map(code=>`<button type="button" class="${lang===code?'active':''}" data-action="authLanguage" data-lang="${code}" aria-label="${code==='vi'?'Tiếng Việt':'English'}" aria-pressed="${lang===code}">${code.toUpperCase()}</button>`).join('')}</div></header>
  <section class="auth-form-area" aria-labelledby="auth-title"><div class="auth-card">
   <header class="auth-card-head"><h1 id="auth-title">${recovery?(view==='forgot'?t.forgot:t.newPassword):register?t.register:t.login}</h1><p class="auth-intro">${recovery?intro:lang==='en'?'Manage and annotate your data.':'Quản lý và gán nhãn dữ liệu của bạn.'}</p></header>
   ${demo?`<div class="auth-demo-notice">${t.demoNote}</div>`:''}
   <form id="${recovery?'recovery':register?'register':'login'}-form" ${recovery?`data-view="${view}"`:''}>${fields}<div id="form-error" aria-live="polite" aria-atomic="true"></div><button class="auth-submit" type="submit" ${demo?'disabled':''}>${action}</button></form>
   ${recovery?`<a class="auth-back" href="#login">${t.back}</a>`:`<footer class="auth-card-footer">${register?t.hasAccount:t.noAccount} <a href="#${register?'login':'register'}">${register?t.login:t.register}</a></footer>`}
   ${demo?`<div class="auth-demo"><button type="button" class="auth-demo-button" data-action="enterDemo">${t.demoButton}</button></div>`:''}
  </div><footer class="auth-page-footer">AnnotaFlow · ${lang==='en'?'Data annotation':'Gán nhãn dữ liệu'}</footer></section>
 </main>`;
}
