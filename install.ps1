# Local Market Lab — Installation & Setup
# Install.ps1 — PowerShell-Installer für Windows
#
# Aufruf: .\install.ps1
#   oder: powershell -ExecutionPolicy Bypass -File install.ps1

param(
    [switch]$Help,
    [switch]$NoVenv,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

function Write-Header($text) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step($text) {
    Write-Host "  → $text" -ForegroundColor Yellow
}

function Write-OK($text) {
    Write-Host "  ✓ $text" -ForegroundColor Green
}

function Test-Command($cmd) {
    return [bool](Get-Command -Name $cmd -ErrorAction SilentlyContinue)
}

function Install-Venv {
    if (Test-Path ".venv") {
        Write-Step "VENV bereits vorhanden"
        return
    }
    Write-Step "Erstelle virtuelle Umgebung (.venv)..."
    python -m venv .venv
    Write-OK "VENV erstellt"
}

function Install-Deps {
    Write-Step "Installiere Python-Abhängigkeiten..."
    
    $pipCmd = if (Test-Path ".venv\Scripts\pip.exe") {
        ".venv\Scripts\pip.exe"
    } else {
        "pip"
    }
    
    & $pipCmd install -e ".[dev]"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Fehler bei pip install" -ForegroundColor Red
        exit 1
    }
    Write-OK "Abhängigkeiten installiert"
}

function Start-Demo {
    Write-Start "Demo aus..."
    $pythonCmd = if (Test-Path ".venv\Scripts\python.exe") {
        ".venv\Scripts\python.exe"
    } else {
        "python"
    }
    
    & $pythonCmd -m apps.cli demo
    Write-OK "Demo abgeschlossen"
}

function Start-APIServer {
    Write-Start "Starte API-Server..."
    $pythonCmd = if (Test-Path ".venv\Scripts\python.exe") {
        ".venv\Scripts\python.exe"
    } else {
        "python"
    }
    
    Start-Process -FilePath $pythonCmd -ArgumentList "-m","apps.api" -WindowStyle Normal
    Write-OK "API-Server gestartet (http://127.0.0.1:8322)"
}

function Build-EXE {
    Write-Start "Baue Windows-EXE..."
    $pythonCmd = if (Test-Path ".venv\Scripts\python.exe") {
        ".venv\Scripts\python.exe"
    } else {
        "python"
    }
    
    & $pythonCmd -m PyInstaller --clean --distpath windows/src/dist --workpath windows/src/build windows/src/build.spec
    
    if ($LASTEXITCODE -eq 0) {
        Write-OK "EXE gebaut: windows/src/dist/LocalMarketLab.exe"
    } else {
        Write-Host "Build fehlgeschlagen" -ForegroundColor Red
    }
}

function Show-Menu {
    Write-Header "Local Market Lab — Installation"
    
    Write-Host "  1) Vollinstallation (VENV + Deps + Demo)"
    Write-Host "  2) Nur Abhängigkeiten installieren"
    Write-Host "  3) Demo starten"
    Write-Host "  4) API-Server starten"
    Write-Host "  5) Windows-EXE bauen"
    Write-Host "  6) Alles (Install + Demo + API)"
    Write-Host "  0) Beenden"
    Write-Host ""
    
    $choice = Read-Host "  Wahl (0-6)"
    return $choice
}

function Invoke-FullInstall {
    Write-Header "Vollinstallation"
    
    if (-not (Test-Command "python")) {
        Write-Host "Python nicht gefunden!" -ForegroundColor Red
        Write-Host "Bitte Python 3.10+ installieren: https://python.org" -ForegroundColor Yellow
        exit 1
    }
    
    if (-not $NoVenv) {
        Install-Venv
    }
    
    Install-Deps
    Start-Demo
    
    Write-Header "Installation abgeschlossen!"
    Write-Host "  Starte mit: .\start.ps1" -ForegroundColor Cyan
}

# --- Main ---
if ($Help) {
    Write-Host "Local Market Lab Installer"
    Write-Host ""
    Write-Host "Aufruf:"
    Write-Host "  .\install.ps1          # Interaktives Menü"
    Write-Host "  .\install.ps1 -Yes     # Vollinstallation ohne Nachfrage"
    Write-Host "  .\install.ps1 -NoVenv  # Ohne virtuelle Umgebung"
    Write-Host ""
    Write-Host "Nach Installation:"
    Write-Host "  .\start.ps1            # Demo + API-Server starten"
    exit 0
}

if ($Yes) {
    Invoke-FullInstall
    exit 0
}

# Prüfe Python
if (-not (Test-Command "python")) {
    Write-Host "Python nicht gefunden!" -ForegroundColor Red
    Write-Host "Bitte Python 3.10+ installieren: https://python.org" -ForegroundColor Yellow
    exit 1
}

# Zeige Menü
do {
    $choice = Show-Menu
    
    switch ($choice) {
        "1" { Invoke-FullInstall }
        "2" { Install-Deps }
        "3" { Start-Demo }
        "4" { Start-APIServer }
        "5" { Build-EXE }
        "6" { 
            Invoke-FullInstall
            Start-APIServer
        }
        "0" { exit 0 }
        default { Write-Host "Ungültige Wahl" -ForegroundColor Red }
    }
    
    Write-Host ""
    $continue = Read-Host "Weiter? (j/n)"
} while ($continue -eq "j")
