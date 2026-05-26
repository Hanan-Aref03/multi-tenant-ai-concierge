$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Invoke-InDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Push-Location $Path
    try {
        & $Action
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed in $Path with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-WithWorkspaceTemp {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    $tempRoot = Join-Path $root ("tmp\pytest-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

    $originalTemp = $env:TEMP
    $originalTmp = $env:TMP
    $originalTmpDir = $env:TMPDIR

    $env:TEMP = $tempRoot
    $env:TMP = $tempRoot
    $env:TMPDIR = $tempRoot

    try {
        & $Action
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        if ($null -ne $originalTemp) { $env:TEMP = $originalTemp } else { Remove-Item Env:TEMP -ErrorAction SilentlyContinue }
        if ($null -ne $originalTmp) { $env:TMP = $originalTmp } else { Remove-Item Env:TMP -ErrorAction SilentlyContinue }
        if ($null -ne $originalTmpDir) { $env:TMPDIR = $originalTmpDir } else { Remove-Item Env:TMPDIR -ErrorAction SilentlyContinue }
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Invoke-Step -Name "Compile Python sources" -Action {
    python -m compileall apps services tests backend admin
}

Invoke-Step -Name "Run root unittest suite" -Action {
    python -m unittest discover -s tests -t . -p "test_*.py"
}

Invoke-Step -Name "Run root pytest suite" -Action {
    Invoke-WithWorkspaceTemp -Action {
        python -m pytest tests -q -p no:cacheprovider
    }
}

Invoke-Step -Name "Run backend pytest suite" -Action {
    Invoke-WithWorkspaceTemp -Action {
        Invoke-InDirectory -Path "backend" -Action {
            $env:PYTHONPATH = "."
            try {
                python -m pytest tests -q -p no:cacheprovider
            }
            finally {
                Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
            }
        }
    }
}

Invoke-Step -Name "Run widget lint" -Action {
    $widgetPath = Join-Path $root "widget"
    docker run --rm -v "${widgetPath}:/widget" -w /widget node:20-alpine sh -lc "npm ci && npm run lint"
    if ($LASTEXITCODE -ne 0) {
        throw "Widget lint failed with exit code $LASTEXITCODE"
    }
}

Invoke-Step -Name "Run widget build and size gate" -Action {
    $widgetPath = Join-Path $root "widget"
    docker run --rm -v "${widgetPath}:/widget" -w /widget node:20-alpine sh -lc "npm ci && npm run size"
    if ($LASTEXITCODE -ne 0) {
        throw "Widget build and size gate failed with exit code $LASTEXITCODE"
    }
}

Invoke-Step -Name "Verify tenant isolation rules" -Action {
    powershell -ExecutionPolicy Bypass -File scripts/verify_isolation.ps1
}

Invoke-Step -Name "Validate docker compose" -Action {
    docker compose config
}

Invoke-Step -Name "Build API smoke image" -Action {
    docker build -f apps/api/Dockerfile -t concierge-api-smoke .
}

Invoke-Step -Name "Build modelserver image" -Action {
    docker build -f apps/modelserver/Dockerfile -t concierge-modelserver .
}

Invoke-Step -Name "Build guardrails image" -Action {
    docker build -f apps/guardrails/Dockerfile -t concierge-guardrails .
}

Invoke-Step -Name "Build widget image" -Action {
    docker build -f widget/Dockerfile -t concierge-widget widget
}

Invoke-Step -Name "Build admin image" -Action {
    docker build -f admin/Dockerfile -t concierge-admin admin
}

Invoke-Step -Name "Build backend image" -Action {
    docker build -f backend/Dockerfile -t concierge-backend .
}

Write-Host ""
Write-Host "All teammate checks passed. The repository is ready for PR review or merge." -ForegroundColor Green
