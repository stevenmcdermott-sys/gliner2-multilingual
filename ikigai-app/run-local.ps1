#!/usr/bin/env pwsh
# Run locally: backend on :8000, frontend on :8080
$root = $PSScriptRoot

# Backend
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}
& .venv\Scripts\Activate.ps1
pip install -q -r requirements.txt
if (Test-Path ".env") { Get-Content .env | ForEach-Object { if ($_ -match '^([^#][^=]*)=(.*)') { [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim()) } } }

Write-Host "Starting backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-Command cd '$root\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --port 8000 --reload"

# Frontend
Set-Location "$root\frontend"
Write-Host "Starting frontend on http://localhost:8080 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-Command cd '$root\frontend'; python -m http.server 8080"

Start-Sleep 2
Start-Process "http://localhost:8080"
Write-Host "Done! App running at http://localhost:8080" -ForegroundColor Cyan
Write-Host "Health check: http://localhost:8000/api/health" -ForegroundColor Cyan
