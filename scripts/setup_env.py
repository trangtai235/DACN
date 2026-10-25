"""Run on the user's machine. Creates secrets locally, never overwrite an existing .env."""
from pathlib import Path
import secrets
root=Path(__file__).resolve().parent.parent
target=root/'.env'
if target.exists():raise SystemExit('.env đã tồn tại; giữ nguyên cấu hình hiện tại.')
password=secrets.token_urlsafe(14)
text=(root/'.env.example').read_text(encoding='utf-8')
text=text.replace('DJANGO_SECRET_KEY=generate-with-scripts-setup-env','DJANGO_SECRET_KEY='+secrets.token_urlsafe(48))
text=text.replace('DB_PASSWORD=generate-with-scripts-setup-env','DB_PASSWORD='+secrets.token_urlsafe(24))
text=text.replace('DEMO_PASSWORD=generate-with-scripts-setup-env','DEMO_PASSWORD='+password)
target.write_text(text,encoding='utf-8');target.chmod(0o600)
print('Đã tạo .env tại máy bạn. Tài khoản: tv1 / tv2 / tv3')
print('Mật khẩu demo:',password)
print('Chạy docker compose up --build, sau đó mở http://localhost:8000')
