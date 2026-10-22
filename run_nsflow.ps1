# Launch the Neuro SAN server + nsflow web UI against THIS project's agent network.
#
# nsflow is not part of this project — it ships with neuro-san-studio and lives in
# that repo's venv. `ns run` starts two processes:
#   * the Neuro SAN server  (serves the networks in registries/manifest.hocon)
#   * the nsflow client     (the web UI that draws and chats with them)
#
# It resolves the manifest, coded tools, PYTHONPATH and .env from the directory it
# runs in, which is why this script sets its location to the project root.
#
# Usage:
#     .\run_nsflow.ps1                                   # server 8095, nsflow 4190
#     .\run_nsflow.ps1 -ServerPort 8100 -NsflowPort 4200
#     .\run_nsflow.ps1 -ServerOnly                       # no web UI
#
# NOTE: this is only for exploring the network in nsflow. The Streamlit dashboard
# (`python -m streamlit run app.py`) does NOT need it — the dashboard opens
# a direct in-process session and never talks to the server.

[CmdletBinding()]
param(
    [int]$ServerPort = 8095,
    [int]$NsflowPort = 4190,
    [switch]$ServerOnly,
    [string]$StudioRepo = 'C:\Users\2065538\Costco\neuro-san-studio'
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$ns = Join-Path $StudioRepo '.venv\Scripts\ns.exe'
$py = Join-Path $StudioRepo '.venv\Scripts\python.exe'

if (-not (Test-Path $ns)) {
    Write-Host "ns.exe not found: $ns" -ForegroundColor Red
    Write-Host 'nsflow ships with neuro-san-studio. Point -StudioRepo at your clone.' -ForegroundColor Yellow
    exit 1
}

# Self-repair the server's logging config. neuro-san's wheel omits a file the
# server requires at startup, and no env var can redirect the lookup, so the
# server dies and nsflow reports a misleading "503 not reachable".
# See scripts/repair_neuro_san_logging.py for the full explanation.
Write-Host 'Checking Neuro SAN server logging config...' -ForegroundColor Cyan
& $py 'scripts\repair_neuro_san_logging.py' --studio-repo $StudioRepo
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Could not prepare the server logging config; aborting.' -ForegroundColor Red
    exit 1
}

# Free the ports first. When they are busy, `ns run` stops at an INTERACTIVE
# prompt ("Do you want to kill the processes using these ports? (yes/no)"), which
# hangs the launch whenever stdin is not attached.
foreach ($port in @($ServerPort, $NsflowPort)) {
    $held = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $held) {
        Write-Host "Port $port in use by PID $($conn.OwningProcess) - stopping it." -ForegroundColor Yellow
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

# Verify the ports are ACTUALLY free, and stop if not.
#
# Silently continuing here is worse than failing. A listener can survive the
# kill above — most often an orphaned socket whose owning process is already
# gone, so Stop-Process reports success on a PID that no longer exists while the
# port stays held. `ns run` then reaches its interactive prompt ("Do you want to
# kill the processes using these ports?"), and with no stdin attached it simply
# hangs: no error, no server, nothing in the log. Diagnosing that from the
# outside is miserable, so name it here.
$blocked = @()
foreach ($port in @($ServerPort, $NsflowPort)) {
    $still = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($still) { $blocked += "$port (PID $($still[0].OwningProcess))" }
}
if ($blocked.Count -gt 0) {
    Write-Host ''
    Write-Host "Could not free: $($blocked -join ', ')" -ForegroundColor Red
    Write-Host 'ns run would stop at an interactive prompt and hang, so aborting instead.' -ForegroundColor Red
    Write-Host 'If the owning PID no longer exists the socket is orphaned and will not clear' -ForegroundColor Yellow
    Write-Host 'without a reboot. Use different ports:' -ForegroundColor Yellow
    Write-Host "  .\run_nsflow.ps1 -ServerPort $($ServerPort + 1) -NsflowPort $($NsflowPort + 10)"
    exit 1
}

$nsArgs = @('run', '--server-http-port', "$ServerPort", '--nsflow-port', "$NsflowPort")
if ($ServerOnly) { $nsArgs += '--server-only' }

$manifest = Join-Path $PSScriptRoot 'registries\manifest.hocon'

# Point the server at THIS project explicitly. Setting the location to the
# project root is NOT enough: `ns run` does not resolve the manifest relative to
# the working directory, it falls back to the manifest that ships with
# neuro-san-studio. The symptom is nsflow starting cleanly and listing the
# studio's own networks (banking_ops, the basic examples, ...) with no sign of
# this project's network — which reads as "my agents are missing" rather than
# "the wrong registry was loaded".
#
# These are the same variables services/neuro_san_client.py sets for the
# in-process Streamlit session.
$env:AGENT_MANIFEST_FILE = $manifest
$env:AGENT_TOOL_PATH = Join-Path $PSScriptRoot 'phygital_coded_tools'

# PYTHONPATH is not optional: neuro-san maps the absolute AGENT_TOOL_PATH onto a
# dotted module path and imports the coded tools through it. Without the project
# root here the server cannot import the coded-tool package.
$projectRoot = $PSScriptRoot
$existing = $env:PYTHONPATH
if ([string]::IsNullOrWhiteSpace($existing)) {
    $env:PYTHONPATH = $projectRoot
} elseif (($existing -split [IO.Path]::PathSeparator) -notcontains $projectRoot) {
    $env:PYTHONPATH = $existing + [IO.Path]::PathSeparator + $projectRoot
}

if (-not (Test-Path $manifest)) {
    Write-Host "Manifest not found: $manifest" -ForegroundColor Red
    exit 1
}
Write-Host ''
Write-Host "Project   : $PSScriptRoot"
Write-Host "Manifest  : $manifest"
Write-Host "Network   : phygital_operations_intelligence (frontman + 6 specialist agents)"
Write-Host "Tool path : $env:AGENT_TOOL_PATH"
Write-Host "Server    : http://127.0.0.1:$ServerPort"
if (-not $ServerOnly) {
    # Use 127.0.0.1, NOT localhost. nsflow binds to 127.0.0.1 only (IPv4), while
    # "localhost" resolves to ::1 (IPv6) first on Windows. Browsers try ::1 and
    # get ERR_CONNECTION_REFUSED, which looks like nsflow failed to start.
    # The neuro-san server and Streamlit both bind dual-stack, so only nsflow
    # is affected.
    Write-Host "nsflow UI : http://127.0.0.1:$NsflowPort" -ForegroundColor Green
    Write-Host "            (use 127.0.0.1, not localhost - nsflow is IPv4-only)" -ForegroundColor DarkGray
}
Write-Host ''

# ns writes normal log lines to stderr. Under 'Stop', Windows PowerShell 5.1 turns
# those into terminating errors whenever output is redirected, killing the launch.
$ErrorActionPreference = 'Continue'
& $ns @nsArgs
