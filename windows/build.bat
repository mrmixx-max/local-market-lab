@echo off
:: ===================================================================
:: Local Market Lab - Windows Build Script
:: ===================================================================
:: Chains: PyInstaller -> Inno Setup Compiler
:: Output: windows/output/LocalMarketLab-Setup-v0.8.0.exe
::
:: Prerequisites:
::   - Python 3.10+ with PyInstaller installed
::   - Inno Setup 6 (ISCC.exe in PATH or default install location)
::   - UPX (optional, for additional compression)
::
:: Usage:
::   build.bat              Build EXE + installer
::   build.bat --no-installer   Build EXE only (skip Inno Setup)
::   build.bat --clean      Clean build artifacts first
::   build.bat --no-upx     Skip UPX compression
:: ===================================================================

setlocal enabledelayedexpansion

:: Configuration
set APP_NAME=LocalMarketLab
set APP_VERSION=0.9.1
set PROJECT_ROOT=%~dp0..\..

:: Resolve absolute paths
for %%I in ("%PROJECT_ROOT%") do set PROJECT_ROOT=%%~fI
set SRC_DIR=%~dp0
set BUILD_SPEC=%SRC_DIR%src\build.spec
set ISS_SCRIPT=%SRC_DIR%installer\setup.iss
set OUTPUT_DIR=%SRC_DIR%installer\output
set DIST_DIR=%SRC_DIR%src\dist
set INNO_SETUP_DIR=%ProgramFiles(x86)%\Inno Setup 6
:: escaped form for use inside echo/if blocks (parentheses break cmd parsing)
set INNO_SETUP_DIR_ESC=C:\Program Files ^(x86^)\Inno Setup 6
set UPX_DIR=
set BUILD_INSTALLER=1
set SKIP_INSTALLER=no
set CLEAN_BUILD=0
set USE_UPX=1

:: Parse arguments
:parse_args
if "%~1"=="" goto :main
if /i "%~1"=="--no-installer" set SKIP_INSTALLER=yes
if /i "%~1"=="--clean" set CLEAN_BUILD=1
if /i "%~1"=="--no-upx" set USE_UPX=0
shift
goto :parse_args

:main
echo.
echo ================================================================
echo  Local Market Lab v%APP_VERSION% - Windows Build
echo ================================================================
echo.

:: Check prerequisites
call :check_python
if errorlevel 1 goto :error

call :check_pyinstaller
if errorlevel 1 goto :error

if "%SKIP_INSTALLER%"=="no" (
    call :check_inno_setup
    if errorlevel 1 goto :error
)

:: Optional: check UPX
if "%USE_UPX%"=="1" (
    call :check_upx
) else (
    echo [INFO] UPX compression disabled (--no-upx)
)

:: Clean if requested
if "%CLEAN_BUILD%"=="1" (
    echo.
    echo [BUILD] Cleaning previous build artifacts...
    if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
    if exist "%SRC_DIR%src\build" rmdir /s /q "%SRC_DIR%src\build"
    if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
    echo [BUILD] Clean complete.
)

:: Create output directory
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: ===================================================================
:: Step 1: PyInstaller - Build EXE
:: ===================================================================
echo.
echo [BUILD] Step 1/2: Building %APP_NAME%.exe with PyInstaller...
echo.

cd /d "%PROJECT_ROOT%"

:: Set UPX path if available
if not "%UPX_DIR%"=="" (
    set UPX_PATH=%UPX_DIR%
)

pyinstaller "%BUILD_SPEC%" ^
    --distpath "%DIST_DIR%" ^
    --workpath "%SRC_DIR%src\build\build" ^
    --noconfirm ^
    --clean

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed!
    goto :error
)

:: Check EXE size
for %%F in ("%DIST_DIR%\%APP_NAME%.exe") do set EXE_SIZE=%%~zF
echo.
echo [BUILD] EXE built: %DIST_DIR%\%APP_NAME%.exe

:: Calculate size in MB (with decimal)
set /a SIZE_MB=%EXE_SIZE% / 1048576
set /a SIZE_KB_REMAINDER=(%EXE_SIZE% %% 1048576) / 10486
echo [BUILD] EXE size: %SIZE_MB%.%SIZE_KB_REMAINDER% MB

:: Warn if over 30MB
if %SIZE_MB% GTR 30 (
    echo.
    echo [WARNING] EXE size is %SIZE_MB%MB ^(target: ^<30MB^)
    echo [WARNING] Consider adding more excludes to build.spec
    echo [WARNING] Check that UPX is installed and working
) else (
    echo [BUILD] EXE size OK: %SIZE_MB%MB ^(target: ^<30MB^)
)

:: ===================================================================
:: Step 2: Inno Setup - Build Installer
:: Default: build installer. Only skip if SKIP_INSTALLER=yes.
if "%SKIP_INSTALLER%"=="yes" goto :skip_installer
echo.
echo [BUILD] Step 2/2: Building installer with Inno Setup...
echo [BUILD] Running: iscc "%ISS_SCRIPT%" /O"%OUTPUT_DIR%" /F"LocalMarketLab-Setup-v%APP_VERSION%"
echo.

iscc "%ISS_SCRIPT%" /O"%OUTPUT_DIR%" /F"LocalMarketLab-Setup-v%APP_VERSION%"
set ISCC_EXIT=%errorlevel%

if %ISCC_EXIT% neq 0 (
    echo.
    echo [ERROR] Inno Setup build failed with exit code %ISCC_EXIT%!
    echo [ERROR] Check that iscc is in PATH and the .iss source files exist.
    goto :error
)
    goto :error
)

:: Verify the installer was actually produced
if not exist "%OUTPUT_DIR%\LocalMarketLab-Setup-v%APP_VERSION%.exe" (
    echo.
    echo [ERROR] iscc reported success but installer EXE not found at %OUTPUT_DIR%\LocalMarketLab-Setup-v%APP_VERSION%.exe
    goto :error
)

:: Check installer size
for %%F in ("%OUTPUT_DIR%\LocalMarketLab-Setup-v%APP_VERSION%.exe") do set INSTALLER_SIZE=%%~zF
echo.
echo [BUILD] Installer built: %OUTPUT_DIR%\LocalMarketLab-Setup-v%APP_VERSION%.exe

set /a INSTALLER_MB=%INSTALLER_SIZE% / 1048576
set /a INSTALLER_KB_REMAINDER=(%INSTALLER_SIZE% %% 1048576) / 10486
echo [BUILD] Installer size: %INSTALLER_MB%.%INSTALLER_KB_REMAINDER% MB

goto :success

:skip_installer
echo.
echo [BUILD] Skipping installer build (--no-installer)
goto :success

:: ===================================================================
:: Subroutines
:: ===================================================================

:check_python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH!
    echo [ERROR] Install Python 3.10+ from https://www.python.org/downloads/
    exit /b 1
)
for /f "delims=" %%v in ('python --version') do echo [CHECK] %%v
exit /b 0

:check_pyinstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller not found!
    echo [ERROR] Install with: pip install pyinstaller
    exit /b 1
)
for /f "delims=" %%v in ('pyinstaller --version') do echo [CHECK] PyInstaller %%v
exit /b 0

:check_inno_setup
:: Check if ISCC is already in PATH
where iscc >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%v in ('iscc /? 2^>nul ^| findstr "Inno Setup"') do echo [CHECK] %%v
    exit /b 0
)
:: Check default install location
if exist "%INNO_SETUP_DIR%\ISCC.exe" (
    set "PATH=%PATH%;%INNO_SETUP_DIR%"
    call :safe_echo Inno Setup 6 found at "%INNO_SETUP_DIR%"
    exit /b 0
)
echo [ERROR] Inno Setup 6 not found!
echo [ERROR] Install from https://jrsoftware.org/isdl.php or add ISCC to PATH
exit /b 1

:check_upx
where upx >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%v in ('upx --version 2^>nul ^| findstr "UPX"') do echo [CHECK] %%v
    exit /b 0
)
:: Check common UPX locations
if exist "%~dp0tools\upx\upx.exe" (
    set "UPX_DIR=%~dp0tools\upx"
    set "PATH=%PATH%;%UPX_DIR%"
    echo [CHECK] UPX found at %~dp0tools\upx
    exit /b 0
)
:: Check if UPX is in a sibling directory
if exist "%~dp0..\tools\upx\upx.exe" (
    set "UPX_DIR=%~dp0..\tools\upx"
    set "PATH=%PATH%;%UPX_DIR%"
    echo [CHECK] UPX found at %~dp0..\tools\upx
    exit /b 0
)
echo [INFO] UPX not found ^(optional, for additional compression^)
echo [INFO] Download from https://github.com/upx/upx/releases
echo [INFO] Or install with: choco install upx
exit /b 0

:success
echo.
echo ================================================================
echo  BUILD SUCCESS
echo ================================================================
echo  EXE:       %DIST_DIR%\%APP_NAME%.exe
if "%SKIP_INSTALLER%"=="no" (
    echo  Installer:  %OUTPUT_DIR%\LocalMarketLab-Setup-v%APP_VERSION%.exe
)
echo ================================================================
echo.
goto :eof

:error
echo.
echo ================================================================
echo  BUILD FAILED
echo ================================================================
echo.
exit /b 1

:: Safely echo a string that may contain parentheses (e.g. "Program Files (x86)")
:: without breaking cmd.exe block parsing.
:safe_echo
echo [CHECK] %*
goto :eof
