#!/usr/bin/env pwsh
# Deploy frontend to Netlify
Set-Location "$PSScriptRoot\frontend"
Write-Host "Deploying frontend to Netlify..." -ForegroundColor Cyan
netlify deploy --prod --dir .
