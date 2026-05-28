$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Update secrets if you need to before sharing outside local dev." -ForegroundColor Yellow
}

Write-Host "Starting the full concierge stack..." -ForegroundColor Cyan
docker compose up -d --build --wait postgres redis minio vault modelserver guardrails api admin

Write-Host ""
Write-Host "Stack is up." -ForegroundColor Green
Write-Host "API: http://localhost:8000"
Write-Host "Admin: http://localhost:8501"
Write-Host "Model server: http://localhost:8010/healthz"
Write-Host "Guardrails: http://localhost:8011/healthz"
Write-Host "Widget loader: http://localhost:8000/widget.js"
Write-Host "Widget test page: open widget/test/embed-test.html in your browser"
Write-Host ""
Write-Host "To stop everything: docker compose down" -ForegroundColor Cyan
