@echo off
title Stopping Global Intelligence Platform...
echo ========================================================
echo       Stopping Global Intelligence Platform
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/2] Stopping PostgreSQL Database...
call .\.venv\Scripts\python.exe scripts\postgres_manager.py stop

echo [2/2] Stopping any remaining background services...
echo Done! All services have been stopped.
timeout /t 3 >nul
