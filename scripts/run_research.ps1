param(
    [switch]$Quick,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

# Every stage is checked explicitly.  `$ErrorActionPreference = "Stop"` does NOT
# stop the script when a native process such as `python` exits non-zero, so a
# failing sub-run used to end with "pipeline complete" on screen (mutation Q17).
# `Invoke-Stage` fails the run instead, and nothing after a failure executes.

$script:Stages = @()

function Invoke-Stage {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Body,
        [string[]]$RequiredArtifacts = @()
    )

    Write-Host "==> $Name"
    $started = Get-Date
    & $Body
    $code = $LASTEXITCODE
    $missing = @($RequiredArtifacts | Where-Object { -not (Test-Path $_) })

    $status = "SUCCESS"
    if ($code -ne 0) {
        $status = "FAILED"
    }
    elseif ($missing.Count -gt 0) {
        $status = "MISSING_ARTIFACT"
    }

    $script:Stages += [pscustomobject]@{
        name              = $Name
        status            = $status
        returncode        = $code
        duration_s        = [math]::Round(((Get-Date) - $started).TotalSeconds, 2)
        missing_artifacts = $missing
    }

    if ($status -ne "SUCCESS") {
        Write-Host ""
        Write-Host "Stage '$Name' $status (exit code $code)."
        if ($missing.Count -gt 0) {
            Write-Host "Missing artifacts: $($missing -join ', ')"
        }
        Write-Host "Pipeline did not complete. No stage output may be published as evidence."
        $script:Stages | Format-Table -AutoSize | Out-Host
        exit 1
    }
}

if (-not $SkipInstall) {
    Invoke-Stage -Name "install" -Body { python -m pip install -e ".[dev]" }
}

# --- gates that must hold before anything is estimated ---------------------
Invoke-Stage -Name "lint" -Body { python -m ruff check . }
Invoke-Stage -Name "unit_tests" -Body { python -m pytest }
Invoke-Stage -Name "contract_validation" `
    -Body { python -m telco_churn.problem_contract_cli } `
    -RequiredArtifacts @("reports/v4/contracts.json")
Invoke-Stage -Name "challenge_suite" `
    -Body { python -m telco_churn.challenge_suite } `
    -RequiredArtifacts @("reports/v4/challenge_suite.json", "reports/v4/CHALLENGE_SUITE_REPORT.md")

$smokeWorlds = if ($Quick) { 100 } else { 1000 }
Invoke-Stage -Name "inference_smoke" `
    -Body { python -m telco_churn.inference_smoke --worlds $smokeWorlds } `
    -RequiredArtifacts @("reports/v4/inference_smoke.json")

# --- V3 research track ------------------------------------------------------
Invoke-Stage -Name "orange_fetch" -Body { python -m telco_churn.orange_data fetch }
Invoke-Stage -Name "orange_validate" -Body { python -m telco_churn.orange_data validate }

$benchmarkArgs = @("-m", "telco_churn.orange_benchmark")
if ($Quick) {
    $benchmarkArgs += "--quick"
}
Invoke-Stage -Name "orange_benchmark" `
    -Body { python @benchmarkArgs } `
    -RequiredArtifacts @("reports/uplift/locked_policy_decision.json")

if ($Quick) {
    Invoke-Stage -Name "stability" -Body { python -m telco_churn.stability --repeats 2 --folds 2 }
    Invoke-Stage -Name "tuning" -Body { python -m telco_churn.tuning --repeats 2 --folds 2 }
    Invoke-Stage -Name "tournament" -Body { python -m telco_churn.model_tournament --profile quick --repeats 2 --folds 2 }
    Invoke-Stage -Name "component_ablation" -Body { python -m telco_churn.component_ablation --folds 2 --quick }
}
else {
    Invoke-Stage -Name "stability" -Body { python -m telco_churn.stability --repeats 5 --folds 3 }
    Invoke-Stage -Name "tuning" -Body { python -m telco_churn.tuning --repeats 3 --folds 3 }
    Invoke-Stage -Name "tournament" -Body { python -m telco_churn.model_tournament --profile full --repeats 3 --folds 3 }
    Invoke-Stage -Name "component_ablation" -Body { python -m telco_churn.component_ablation --folds 3 }
}

Invoke-Stage -Name "temporal_lab" `
    -Body { python -m telco_churn.temporal_lab } `
    -RequiredArtifacts @("reports/temporal_lab/summary.json")
Invoke-Stage -Name "build_notebooks" -Body { python scripts/build_research_notebooks.py }

$notebooks = @(
    "notebooks/03_orange_causal_audit.ipynb",
    "notebooks/04_temporal_policy_lab.ipynb",
    "notebooks/05_model_stability_and_tuning.ipynb",
    "notebooks/06_policy_value_and_failure_analysis.ipynb"
)
foreach ($notebook in $notebooks) {
    Invoke-Stage -Name "execute_$([System.IO.Path]::GetFileNameWithoutExtension($notebook))" -Body {
        jupyter nbconvert --execute --to notebook --inplace $notebook `
            --ExecutePreprocessor.timeout=300
    }
}

# --- evidence index last: it reads what the stages above produced ----------
Invoke-Stage -Name "evidence_index" `
    -Body { python -m telco_churn.evidence } `
    -RequiredArtifacts @("reports/v4/evidence_index.json", "reports/v4/EVIDENCE_INDEX.md")

$script:Stages | Format-Table -AutoSize | Out-Host
Write-Host "Research pipeline COMPLETE. Start with reports/v4/EVIDENCE_INDEX.md, then"
Write-Host "reports/uplift/CAUSAL_BENCHMARK_REPORT.md. The console reads the same artifacts:"
Write-Host "  python -m telco_churn.dashboard"
exit 0
