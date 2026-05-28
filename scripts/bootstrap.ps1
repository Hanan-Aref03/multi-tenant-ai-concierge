param(
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Starting core platform services..." -ForegroundColor Cyan
docker compose up -d postgres redis minio vault

if (-not $SkipDependencyInstall) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Cyan
    python -m pip install -r backend/requirements.txt
    python -m pip install pytest pytest-asyncio

    Write-Host "Installing widget dependencies..." -ForegroundColor Cyan
    Push-Location widget
    try {
        npm ci
    }
    finally {
        Pop-Location
    }

    Write-Host "Installing admin dependencies..." -ForegroundColor Cyan
    Push-Location admin
    try {
        python -m pip install -r requirements.txt
    }
    finally {
        Pop-Location
    }
}

Write-Host "Bootstrap complete. Next step: run scripts/run_team_checks.ps1." -ForegroundColor Green
