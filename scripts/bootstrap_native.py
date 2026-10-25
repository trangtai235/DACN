"""Native development startup. No activation script or execution-policy changes."""
from pathlib import Path
import hashlib,os,socket,subprocess,sys
ROOT=Path(__file__).resolve().parent.parent

def run(args,cwd=ROOT,env=None):
    subprocess.run([str(v) for v in args],cwd=cwd,env=env,check=True)

def main():
    if sys.version_info[:2]!=(3,12):raise SystemExit('Can Python 3.12 de dung dung moi truong da kiem tra.')
    requirements=ROOT/'requirements/windows.txt';stamp=Path(sys.prefix)/'.annotaflow-dependencies'
    digest=hashlib.sha256(requirements.read_bytes()+(ROOT/'requirements/base.txt').read_bytes()).hexdigest()
    if not stamp.exists() or stamp.read_text()!=digest:
        print('1/4 Cai thu vien Python. Lan dau can tai goi tu package index.',flush=True)
        run([sys.executable,'-m','pip','install','--only-binary=:all:','-r',requirements]);stamp.write_text(digest)
    sys.path.insert(0,str(ROOT/'scripts'))
    from local_postgres import ensure_local_postgres
    ensure_local_postgres()
    from native_setup import configure
    values=configure()
    env={**os.environ,**{k:str(v) for k,v in values.items() if v is not None},'ANNOTAFLOW_ENV_FILE':str(ROOT/'.env.local'),'JOB_RUNNER':'threads'}
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1',8000))==0:raise SystemExit('Cong 8000 dang duoc dung. Dong server cu truoc khi khoi dong lan nua.')
    print('2/4 Kiem tra PostgreSQL 15-18 va cap nhat schema.',flush=True)
    run([sys.executable,'manage.py','wait_for_db'],ROOT/'backend',env)
    run([sys.executable,'manage.py','migrate','--noinput'],ROOT/'backend',env)
    print('3/4 Chuan bi model va du lieu minh hoa.',flush=True)
    run([sys.executable,ROOT/'scripts/build_frontend.py'])
    run([sys.executable,'manage.py','seed_demo'],ROOT/'backend',env)
    run([sys.executable,'manage.py','recover_local_jobs'],ROOT/'backend',env)
    from server_lifecycle import bind_server_lifetime
    bind_server_lifetime()
    print('4/4 Mo http://127.0.0.1:8000 — Ctrl+C hoac dong terminal de dung server.',flush=True)
    run([sys.executable,'manage.py','runserver','127.0.0.1:8000','--noreload'],ROOT/'backend',env)

if __name__=='__main__':
    try:main()
    except subprocess.CalledProcessError:raise SystemExit('Buoc khoi dong chua thanh cong. Xem thong bao ben tren; cau hinh va du lieu duoc giu lai.')
    except KeyboardInterrupt:print('\nDa dung server local.')
