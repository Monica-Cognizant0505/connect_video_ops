# One-time setup: project venv + Streamlit app + Neuro SAN (in-process runtime).
#
# Usage:
#     .\setup.ps1              # creates .venv, installs everything, verifies Neuro SAN
#     .\setup.ps1 -DemoOnly    # Streamlit only (no neuro-san); app runs in Demo Mode
#
# If script execution is blocked:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

[CmdletBinding()]
param(
    [switch]$DemoOnly,
    [string]$Python = 'py'
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$venvPy = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host 'Creating virtual environment in .venv ...' -ForegroundColor Cyan
    if ($Python -eq 'py') { & py -3 -m venv .venv } else { & $Python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { Write-Host 'venv creation failed.' -ForegroundColor Red; exit 1 }
}

& $venvPy -m pip install --upgrade pip
$reqs = if ($DemoOnly) { 'requirements.txt' } else { 'requirements-neuro-san.txt' }
Write-Host "Installing $reqs ..." -ForegroundColor Cyan
& $venvPy -m pip install -r $reqs
if ($LASTEXITCODE -ne 0) { Write-Host 'pip install failed.' -ForegroundColor Red; exit 1 }

# Secrets: the app reads .streamlit/secrets.toml first, then .env (AZURE_OPENAI_*).
$secrets = Join-Path $PSScriptRoot '.streamlit\secrets.toml'
if (-not (Test-Path $secrets) -and -not (Test-Path (Join-Path $PSScriptRoot '.env'))) {
    Copy-Item (Join-Path $PSScriptRoot '.streamlit\secrets.toml.example') $secrets
    Write-Host 'Created .streamlit\secrets.toml - fill in AZURE_API_KEY / AZURE_ENDPOINT.' -ForegroundColor Yellow
}

if ($DemoOnly) {
    Write-Host "`nSetup done (Demo Mode only). Run: .\run_app.ps1" -ForegroundColor Green
    exit 0
}

Write-Host "`nVerifying Neuro SAN (loads the agent network, no LLM call) ..." -ForegroundColor Cyan
& $venvPy 'scripts\check_neuro_san.py'
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "`nSetup done. Run: .\run_app.ps1" -ForegroundColor Green
