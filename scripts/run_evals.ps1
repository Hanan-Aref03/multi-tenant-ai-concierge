param(
    [switch]$Live
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:PYTHONPATH = $root

function Invoke-PythonEval {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

try {
    $stubSuffix = if ($Live) { @() } else { @("--stub") }
    $liveSuffix = if ($Live) { @("--live") } else { @() }

    Invoke-PythonEval -Name "Classifier gate" -Arguments (@("evals/classifier.py", "--thresholds", "eval_thresholds.yaml") + $stubSuffix)
    Invoke-PythonEval -Name "Agent tool-selection gate" -Arguments (@("evals/agent_tool_selection.py", "--thresholds", "eval_thresholds.yaml") + $stubSuffix)
    Invoke-PythonEval -Name "RAG eval suite" -Arguments (@("evals/rag/run_evals.py") + $liveSuffix)
    Invoke-PythonEval -Name "Agent eval suite" -Arguments (@("evals/agent/run_evals.py") + $liveSuffix)
    Invoke-PythonEval -Name "Injection red-team gate" -Arguments (@("evals/injection_redteam.py", "--thresholds", "eval_thresholds.yaml") + $stubSuffix)
    Invoke-PythonEval -Name "Redaction gate" -Arguments (@("evals/redaction.py", "--thresholds", "eval_thresholds.yaml") + $stubSuffix)
}
finally {
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "All eval gates completed successfully." -ForegroundColor Green
