# Development Runner for PowerShell
$ErrorActionPreference = "Stop"

Write-Host ">>> Checking database migrations..." -ForegroundColor Cyan
& .\.venv\Scripts\alembic.exe upgrade head

Write-Host ">>> Starting Global Intelligence Platform API..." -ForegroundColor Green
& .\.venv\Scripts\uvicorn.exe backend.app.main:app --reload --host 127.0.0.1 --port 8000
