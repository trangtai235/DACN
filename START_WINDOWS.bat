@echo off
setlocal
cd /d "%~dp0"
where docker >nul 2>&1
if errorlevel 1 (
  echo [LOI] Windows chua tim thay lenh docker.
  echo Cai Docker Desktop tu trang chinh thuc:
  echo https://docs.docker.com/desktop/setup/install/windows-install/
  echo Sau khi cai: mo Docker Desktop, cho Engine running, dong va mo lai VS Code.
  echo Xem docs\WINDOWS_SETUP.md de biet chi tiet.
  pause
  exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
  echo [LOI] Chua co Docker Compose v2. Hay cap nhat Docker Desktop.
  pause
  exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
  echo [LOI] Docker Engine chua san sang. Mo Docker Desktop va cho Engine running.
  echo Du an dung Linux containers va PostgreSQL 15.
  pause
  exit /b 1
)
if not exist .env (
  py -3 --version >nul 2>&1
  if not errorlevel 1 (
    py -3 scripts\setup_env.py
  ) else (
    python --version >nul 2>&1
    if errorlevel 1 (
      echo [LOI] Can Python 3 de tao file .env. Cai Python roi chay lai.
      pause
      exit /b 1
    )
    python scripts\setup_env.py
  )
  if not exist .env (
    echo [LOI] Khong tao duoc .env. Xem thong bao ben tren.
    pause
    exit /b 1
  )
)
echo Dang khoi dong AnnotaFlow voi PostgreSQL 15...
echo Khi web san sang, mo http://localhost:8000
docker compose up --build
