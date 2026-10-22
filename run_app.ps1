# Run the Streamlit dashboard.
#
# Usage:
#     .\run_app.ps1                 # in-process Neuro SAN on Azure (NEURO_SAN_MODE=direct)
#     .\run_app.ps1 -Demo           # Demo Mode, no Azure / Neuro SAN calls
#     .\run_app.ps1 -Server         # talk to a running neuro-san server over HTTP
#                                   #   (start it first:  .\run_nsflow.ps1 -ServerOnly)
#     .\run_app.ps1 -Port 8502

[CmdletBinding()]
param(
    [switch]$Demo,
    [switch]$Server,
    [int]$ServerPort = 8095,
    [int]$Port = 8501
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) {
    Write-Host '.venv not found - run .\setup.ps1 first (falling back to python on PATH).' -ForegroundColor Yellow
    $py = 'python'
}

if ($Demo) {
    $env:DEMO_MODE = 'true'
} elseif ($Server) {
    $env:NEURO_SAN_MODE = 'neuro_san'
    $env:NEURO_SAN_API_URL = "http://127.0.0.1:$ServerPort"
    Write-Host "Using neuro-san server at $env:NEURO_SAN_API_URL" -ForegroundColor Cyan
} else {
    $env:NEURO_SAN_MODE = 'direct'
}

Write-Host "Dashboard: http://localhost:$Port" -ForegroundColor Green
& $py -m streamlit run app.py --server.port $Port
