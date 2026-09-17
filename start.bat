@echo off
title Starting Global Intelligence Platform...
echo ========================================================
echo       Starting Global Intelligence Platform
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/4] Starting PostgreSQL Database...
call .\.venv\Scripts\python.exe scripts\postgres_manager.py start

echo [2/4] Checking and Applying Database Migrations...
call .\.venv\Scripts\alembic.exe upgrade head

echo [3/4] Launching FastAPI Backend Server (Port 8000)...
start "Global Intelligence - Backend API" cmd /k ".\.venv\Scripts\uvicorn.exe backend.app.main:app --reload --host 127.0.0.1 --port 8000"

echo [4/4] Launching Frontend Web Dashboard (Port 5173)...
start "Global Intelligence - Web Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================================
echo  Platform services are launching!
echo  - Web Application: http://localhost:5173
echo  - Swagger API Docs: http://127.0.0.1:8000/docs
echo ========================================================
echo.
echo Opening web dashboard in your default browser in 3 seconds...
timeout /t 3 >nul
start http://localhost:5173
