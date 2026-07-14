# Seville 406 Legacy Listing Scanner -- Windows setup / run script.
#
# Usage (from the project root, in PowerShell):
#   .\scripts\start.ps1              # first-run setup + scan
#   .\scripts\start.ps1 -Command scan
#   .\scripts\start.ps1 -Command export -ScanId 3
#   .\scripts\start.ps1 -Command list-scans
#   .\scripts\start.ps1 -Command sample-report
#
# If script execution is blocked, run once per session:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

param(
    [ValidateSet("scan", "export", "list-scans", "sample-report")]
    [string]$Command = "scan",
    [int]$ScanId
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvPath = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    python -m venv $VenvPath
}

Write-Host "Installing/updating dependencies..."
& $VenvPython -m pip install --upgrade pip | Out-Null
& $VenvPython -m pip install -r requirements.txt

$EnvFile = Join-Path $RepoRoot ".env"
$EnvExample = Join-Path $RepoRoot ".env.example"
if (-not (Test-Path $EnvFile)) {
    Write-Host "No .env found -- copying .env.example to .env."
    Write-Host "Edit .env and add your BRAVE_API_KEY before running a real scan."
    Copy-Item $EnvExample $EnvFile
}

switch ($Command) {
    "scan" {
        & $VenvPython -m app.main scan
    }
    "export" {
        if (-not $ScanId) {
            Write-Error "Pass -ScanId <id> when using -Command export"
            exit 1
        }
        & $VenvPython -m app.main export --scan-id $ScanId
    }
    "list-scans" {
        & $VenvPython -m app.main list-scans
    }
    "sample-report" {
        & $VenvPython scripts\generate_sample_report.py
    }
}
