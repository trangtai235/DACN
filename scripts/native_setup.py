"""Interactive, localhost PostgreSQL 15-18 setup. Administrator password is never stored."""
from pathlib import Path
from getpass import getpass
import os,re,secrets
import psycopg
from psycopg import sql
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parent.parent
TARGET=ROOT/'.env.local'

def ask(label,default=''):
    value=input(label+(f' [{default}]' if default else '')+': ').strip()
    return value or default

def write_env(values):
    # python-dotenv supports JSON-style escaped double-quoted values.
    import json
    TARGET.write_text('\n'.join(k+'='+json.dumps(str(v),ensure_ascii=False) for k,v in values.items())+'\n',encoding='utf-8')
    try:TARGET.chmod(0o600)
    except OSError:pass

def configure():
    prior_path=TARGET if TARGET.exists() else TARGET.with_suffix('.local.backup') if TARGET.with_suffix('.local.backup').exists() else ROOT/'.env'
    prior=dict(dotenv_values(prior_path))
    if TARGET.exists():
        print('Da co .env.local. Giu cau hinh va kiem tra ket noi; dung --configure de doi.')
        return prior
    print('\nTHIET LAP LOCAL — PostgreSQL 15-18, khong Docker/Redis/WSL')
    print('Can cai PostgreSQL 15-18 va khoi dong service truoc. Admin password chi dung trong lan thiet lap nay.')
    host=ask('PostgreSQL host','127.0.0.1')
    if host not in ('127.0.0.1','localhost'):raise SystemExit('Wizard local chi ket noi localhost. Dat cau hinh may chu bang .env rieng neu can.')
    port=ask('PostgreSQL port','5432');db=ask('Ten database','annotaflow');role=ask('Tai khoan ung dung','annotaflow_app')
    if not all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}',v) for v in (db,role)):raise SystemExit('Ten database/role chi gom chu ASCII, so va dau _.')
    admin=ask('Tai khoan quan tri PostgreSQL','postgres');admin_password=getpass('Mat khau quan tri PostgreSQL (khong hien ky tu): ')
    try:conn=psycopg.connect(host=host,port=port,dbname='postgres',user=admin,password=admin_password,connect_timeout=10,autocommit=True)
    except psycopg.Error:raise SystemExit('Khong ket noi duoc PostgreSQL. Kiem tra service, port va mat khau quan tri.')
    with conn:
        version=int(conn.execute('SHOW server_version_num').fetchone()[0])//10000
        if not 15 <= version <= 18:raise SystemExit(f'Dang ket noi PostgreSQL {version}; de tai nay yeu cau PostgreSQL 15-18.')
        exists=conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone()
        if exists:
            password=getpass(f'Mat khau hien tai cua role {role}: ')
        else:
            password=secrets.token_urlsafe(24)
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
            print('Da tao role ung dung rieng, khong cap quyen superuser.')
        exists=conn.execute('SELECT 1 FROM pg_database WHERE datname=%s',(db,)).fetchone()
        if not exists:
            conn.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(db),sql.Identifier(role)))
            print('Da tao database rieng cua ung dung.')
    try:
        with psycopg.connect(host=host,port=port,dbname=db,user=role,password=password,connect_timeout=10) as check:check.execute('SELECT 1')
    except psycopg.Error:
        # Keep newly created role credentials recoverable rather than silently resetting an existing role.
        prior.update({'DB_HOST':host,'DB_PORT':port,'DB_NAME':db,'DB_USER':role,'DB_PASSWORD':password})
        write_env(prior);raise SystemExit('Role/database da duoc ghi vao .env.local. Ket noi ung dung chua thanh cong; kiem tra quyen database roi chay lai.')
    values={**{k:v for k,v in prior.items() if v is not None},'DJANGO_SECRET_KEY':prior.get('DJANGO_SECRET_KEY') or secrets.token_urlsafe(48),'DEBUG':'1','ALLOWED_HOSTS':'localhost,127.0.0.1','CSRF_TRUSTED_ORIGINS':'http://localhost:8000,http://127.0.0.1:8000','SITE_URL':'http://127.0.0.1:8000','DB_HOST':host,'DB_PORT':port,'DB_NAME':db,'DB_USER':role,'DB_PASSWORD':password,'DB_SSLMODE':'prefer','JOB_RUNNER':'threads','TASK_ALWAYS_EAGER':'0','REDIS_URL':'memory://','DEMO_PASSWORD':prior.get('DEMO_PASSWORD') or secrets.token_urlsafe(16),'COOKIE_SECURE':'0','REQUIRE_EMAIL_VERIFICATION':'0'}
    # Replace the old example placeholders, never use a shared default secret/password.
    for k,n in [('DJANGO_SECRET_KEY',48),('DEMO_PASSWORD',16)]:
        if not values[k] or values[k].startswith('generate-with-'):values[k]=secrets.token_urlsafe(n)
    write_env(values)
    print('Da tao .env.local. Tai khoan: tv1 / tv2 / tv3')
    print('Mat khau demo (chi hien tai may ban):',values['DEMO_PASSWORD'])
    print('Lan sau chi can RUN_NATIVE_WINDOWS.bat.')
    return values

if __name__=='__main__':
    import sys
    if '--configure' in sys.argv and TARGET.exists():
        backup=TARGET.with_suffix('.local.backup');backup.write_bytes(TARGET.read_bytes());TARGET.unlink()
    configure()
