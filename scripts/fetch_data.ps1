$ErrorActionPreference = "Stop"

$datasetUrl = "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
$outputDirectory = Join-Path $PSScriptRoot "..\data\raw"
$outputPath = Join-Path $outputDirectory "Telco-Customer-Churn.csv"
$expectedSha256 = "16320c9c1ec72448db59aa0a26a0b95401046bef5d02fd3aeb906448e3055e91"

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Invoke-WebRequest -Uri $datasetUrl -OutFile $outputPath
$actualSha256 = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant()

if ($actualSha256 -ne $expectedSha256) {
    throw "Checksum mismatch. Expected $expectedSha256, got $actualSha256"
}

Write-Output "Downloaded verified dataset to $outputPath"

