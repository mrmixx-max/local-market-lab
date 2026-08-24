# Local Market Lab — Start
# Start.ps1 — Demo + API-Server

param(
    [switch]$NoDemo
)

$ErrorActionPreference = "Continue"

function Write-Header($text) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

$pythonCmd = if (Test-Path ".venv\Scripts\python.exe") {
    ".venv\Scripts\python.exe"
} else {
    "python"
}

if (-not $NoDemo) {
    Write-Header "Demo starten"
    & $pythonCmd -m apps.cli demo
}

Write-Header "API-Server starten"
Write-Host "  http://127.0.0.1:8322" -ForegroundColor Yellow
Write-Host "  STRG+C zum Beenden"
Write-Host ""

& $pythonCmd -m apps.api
