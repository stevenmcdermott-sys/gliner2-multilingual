#!/usr/bin/env pwsh
# Run the full stack locally: backend on :8000, frontend on :8080
$root = $PSScriptRoot
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

# ── Backend ──
Set-Location $backendDir

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
& .venv\Scripts\Activate.ps1
pip install -q -r requirements.txt

# Load .env if present
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^([^#\s][^=]*)=(.*)') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    Write-Host "Loaded .env" -ForegroundColor DarkGray
}

Write-Host "Starting backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendDir'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --port 8000 --reload"

# ── Frontend ──
Write-Host "Starting frontend on http://localhost:8080 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendDir'; python -m http.server 8080"

Start-Sleep -Seconds 2
Start-Process "http://localhost:8080"

Write-Host ""
Write-Host "App running at    http://localhost:8080" -ForegroundColor Cyan
Write-Host "Health check at   http://localhost:8000/api/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "To test Claude locally, copy backend\.env.example to backend\.env" -ForegroundColor DarkGray
Write-Host "and set ANTHROPIC_API_KEY. Also set window.IKIGAI_API_BASE in frontend\config.js." -ForegroundColor DarkGray
