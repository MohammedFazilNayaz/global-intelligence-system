@echo off
title Seeding Intelligence Data...
echo ========================================================
echo       Seeding Demo Intelligence Data
echo ========================================================
echo.

cd /d "%~dp0"
call .\.venv\Scripts\python.exe scripts\seed_dashboard_verification_data.py
echo.
echo ========================================================
echo  Demo intelligence data seeded successfully!
echo  Refresh your browser at http://localhost:5173
echo ========================================================
pause
