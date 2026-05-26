$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Running Python isolation tests..."
python -m unittest discover -s tests -t . -p "test_*.py"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$checks = @(
    @{
        Path = "infrastructure/postgres/migrations/0001_init.sql"
        Patterns = @(
            "CREATE TABLE IF NOT EXISTS app.tenants",
            "CREATE TABLE IF NOT EXISTS app.content_documents",
            "CREATE TABLE IF NOT EXISTS app.conversations"
        )
    },
    @{
        Path = "infrastructure/postgres/migrations/0002_rls.sql"
        Patterns = @(
            "ENABLE ROW LEVEL SECURITY",
            "FORCE ROW LEVEL SECURITY",
            "app.current_tenant_id()",
            "WITH CHECK (app.has_tenant_access(tenant_id))"
        )
    }
)

foreach ($check in $checks) {
    $content = Get-Content -Raw -Path $check.Path
    foreach ($pattern in $check.Patterns) {
        if ($content -notmatch [regex]::Escape($pattern)) {
            throw "Missing expected pattern '$pattern' in $($check.Path)."
        }
    }
}

Write-Host "Isolation verification passed."
