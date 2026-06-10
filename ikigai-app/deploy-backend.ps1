#!/usr/bin/env pwsh
# Deploy backend to Railway
Set-Location "$PSScriptRoot\backend"
Write-Host "Deploying backend to Railway..." -ForegroundColor Cyan
railway up --detach
Write-Host "Backend deployed. Getting domain..." -ForegroundColor Green
railway domain
