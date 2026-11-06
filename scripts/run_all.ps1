param(
    [switch]$Quick,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

if (-not $SkipInstall) {
    python -m pip install -e ".[dev]"
}

python -m telco_churn.data fetch
python -m telco_churn.eda
python -m pytest

$trainingArguments = @(
    "-m", "telco_churn.train",
    "--data", "data/raw/Telco-Customer-Churn.csv",
    "--output", "reports/benchmark",
    "--model-dir", "artifacts/models"
)
if ($Quick) {
    $trainingArguments += "--quick"
}
python @trainingArguments

Write-Host "Run: python -m uvicorn telco_churn.api:app --host 127.0.0.1 --port 8000"

