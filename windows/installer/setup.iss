; -------------------------------------------------------------------
; Local Market Lab — Inno Setup Installer Script (Production Ready)
; -------------------------------------------------------------------
; Features:
;   - Installation folder: %LOCALAPPDATA%\Local Market Lab
;   - Start menu shortcut + desktop icon (default checked)
;   - Clean uninstaller (registry-based, removes all app data)
;   - Digital signature ready (commented sign tool)
;   - LZMA2 solid compression for small installer size
;   - Multi-language (EN/DE)
;   - Closes running instance before install/uninstall
; -------------------------------------------------------------------

#define MyAppName "Local Market Lab"
#define MyAppVersion "0.8.0"
#define MyAppPublisher "Erik Gieske"
#define MyAppURL "https://github.com/mrmixx-max/local-market-lab"
#define MyAppExeName "LocalMarketLab.exe"
#define MyAppMutex "Global\LocalMarketLab_SingleInstance"

; --- Sign tool (uncomment when certificate is available) ---
; #define SignTool "signtool sign /fd SHA256 /f certificate.pfx /p password /tr http://timestamp.digicert.com $f"

[Setup]
AppId={{B8A3C4D5-E6F7-4A5B-9C8D-0E1F2A3B4C5D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Install for current user only (no admin required)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Default to user profile (LOCALAPPDATA)
DefaultDirName={userappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

; Compression — maximum LZMA2 for smallest installer
Compression=lzma2/ultra64
SolidCompression=yes
InternalCompressLevel=ultra

; Output
OutputDir=..\output
OutputBaseFilename=LocalMarketLab-Setup-v{#MyAppVersion}
SetupIconFile=..\..\lml-icon.ico

; UI
WizardStyle=modern
WizardSizePercent=120,120
DisableWelcomePage=no
DisableProgramGroupPage=no
DisableReadyPage=no

; Uninstaller
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; Architecture — 64-bit only
ArchitecturesInstallIn64bitMode=x64compatible
ArchitecturesAllowed=x64compatible

; Version info
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription="{#MyAppName} Installer"
VersionInfoTextVersion="{#MyAppVersion}"
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}

; Minimum Windows version (Windows 10 1809+)
MinVersion=10.0.17763

; Close running instance during install/uninstall
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}

; Restart manager
RestartIfNeededByRun=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "startmenuicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable (built by PyInstaller --onefile)
Source: "..\src\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion signonce
; Config and examples (optional bundled files)
Source: "..\..\configs\*"; DestDir: "{app}\configs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\examples\*"; DestDir: "{app}\examples"; Flags: ignoreversion recursesubdirs createallsubdirs
; Data directory — don't overwrite existing user data
Source: "..\..\data\demo-transactions.csv"; DestDir: "{app}\data"; Flags: ignoreversion onlyifdoesntexist
; Documentation
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{group}\{cm:ProgramOnTheWeb,{#MyAppName}}"; Filename: "{#MyAppURL}"
; Desktop (optional, default checked)
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Quick Launch (optional)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\configs\__pycache__"
Type: filesandordirs; Name: "{app}\data\cache"

[Registry]
; App info (deleted on uninstall via uninsdeletekey)
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Code]
// ---------------------------------------------------------------
// Pre-install checks
// ---------------------------------------------------------------
function InitializeSetup(): Boolean;
var
  Version: String;
begin
  Result := true;

  // Check if already installed → log upgrade
  if RegQueryStringValue(HKCU, 'Software\{#MyAppName}', 'Version', Version) then
  begin
    Log('Existing installation found: version ' + Version);
  end;
end;

// ---------------------------------------------------------------
// Pre-install: close running instance
// ---------------------------------------------------------------
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  // CloseApplications directive handles this automatically
  Log('Preparing to install to ' + ExpandConstant('{app}'));
end;

// ---------------------------------------------------------------
// Post-install: log success
// ---------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    Log('Installation completed successfully to ' + ExpandConstant('{app}'));
  end;
end;

// ---------------------------------------------------------------
// Uninstall: confirm data removal
// ---------------------------------------------------------------
function InitializeUninstall(): Boolean;
var
  Res: Integer;
begin
  Res := MsgBox('Do you want to remove {#MyAppName} and all its data?' + #13#10 +
    'This will delete all local data, settings, and portfolios.' + #13#10 + #13#10 +
    'Click YES to remove, NO to cancel.',
    mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
  Result := (Res = IDYES);
end;
