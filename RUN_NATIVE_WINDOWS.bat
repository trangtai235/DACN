@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.12 --version >nul 2>&1
  if errorlevel 1 (
    echo Can cai Python 3.12 truoc: https://www.python.org/downloads/windows/
    echo Cai PostgreSQL 15-18 tu https://www.postgresql.org/download/windows/
    echo Khong can Docker, WSL hoac Redis.
    pause
    exit /b 1
  )
  py -3.12 -m venv .venv
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
.venv\Scripts\python.exe scripts\bootstrap_native.py
if errorlevel 1 pause
