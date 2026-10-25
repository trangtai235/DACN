"""Start only the PostgreSQL cluster already created inside this project."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def ensure_local_postgres():
    data = ROOT / 'backend/private_data/postgres18'
    version_file = data / 'PG_VERSION'
    if not version_file.exists():
        return

    from dotenv import dotenv_values
    config = dotenv_values(ROOT / '.env.local')
    config = {**os.environ, **{k: v for k, v in config.items() if v is not None}}
    host = config.get('DB_HOST') or '127.0.0.1'
    if host not in ('127.0.0.1', 'localhost'):
        return
    port = config.get('DB_PORT') or '5432'
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise SystemExit('DB_PORT phai la so tu 1 den 65535.')

    # A healthy configured database needs no process inspection or startup.
    import psycopg
    try:
        with psycopg.connect(host=host, port=port,
                             dbname=config.get('DB_NAME') or 'annotaflow',
                             user=config.get('DB_USER') or 'annotaflow_app',
                             password=config.get('DB_PASSWORD') or '',
                             sslmode=config.get('DB_SSLMODE') or 'prefer',
                             connect_timeout=3) as connection:
            connection.execute('SELECT 1')
        return
    except psycopg.Error:
        pass

    version = version_file.read_text(encoding='ascii').strip()
    if version != '18':
        raise SystemExit('Thu muc postgres18 khong phai PostgreSQL 18; dung de bao ve du lieu.')
    binary = Path(os.getenv('ProgramFiles', r'C:\Program Files')) / 'PostgreSQL' / version / 'bin/pg_ctl.exe'
    if not binary.is_file():
        raise SystemExit(f'Khong tim thay {binary}. Cai lai PostgreSQL {version} de khoi dong database local.')

    options = {'stdout': subprocess.PIPE, 'stderr': subprocess.STDOUT,
               'text': True, 'encoding': 'utf-8', 'errors': 'replace'}
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    status = subprocess.run([str(binary), '-D', str(data), 'status'], **options)
    if status.returncode == 0:
        return
    print('Khoi dong PostgreSQL local cua du an...', flush=True)
    # Use a file so a detached server cannot keep a captured pipe open.
    startup_log = data.parent / 'postgres-start.log'
    with startup_log.open('w', encoding='utf-8') as output:
        start_options = {**options, 'stdout': output}
        result = subprocess.run([
            str(binary), '-D', str(data), '-l', str(data.parent / 'postgres18.log'),
            '-o', f'-h 127.0.0.1 -p {int(port)}', '-w', 'start',
        ], **start_options)
    if result.returncode:
        details = startup_log.read_text(encoding='utf-8', errors='replace')
        raise SystemExit('Khong khoi dong duoc PostgreSQL local. Xem backend/private_data/postgres18.log.\n' + details)

