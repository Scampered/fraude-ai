; Fraude App — Inno Setup installer script
; Produces a professional setup wizard (not a Tkinter window) that installs
; into %LOCALAPPDATA%\Fraude, adds Start Menu shortcuts, and optionally
; registers a run-at-startup entry.
;
; Build with Inno Setup 6+: https://jrsoftware.org/isinfo.php
; Compile: ISCC.exe fraude_setup.iss
; Output: installer/output/Fraude-Setup.exe

#define MyAppName "Fraude"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Fraude AI"
#define MyAppURL "https://fraude-ai.vercel.app"
#define MyAppExeName "Fraude.exe"

[Setup]
AppId={{8F3C2A1D-4E5B-4A9C-9D1E-FRAUDE000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/downloads
; Installs per-user into LocalAppData — no admin rights required
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=Fraude-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Use a custom wizard image matching the Fraude brand (terracotta/cream theme)
WizardImageFile=wizard_large.bmp
WizardSmallImageFile=wizard_small.bmp
WizardImageStretch=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startup"; Description: "Start Fraude automatically when Windows starts"; GroupDescription: "Additional options:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional options:"

[Files]
; Pulls in everything PyInstaller collected under dist/Fraude/
Source: "..\dist\Fraude\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Run-at-startup via Startup folder shortcut (no registry write needed)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Fraude now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up generated runtime files on uninstall (but never touch user workspaces
; under fraude-code-memory — those live outside %LOCALAPPDATA%\Fraude by design)
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
// Friendly check: warn if Ollama isn't detected, with a link to install it.
// Doesn't block setup — Fraude's proxy/automations work without Ollama too.
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if not Exec(ExpandConstant('{cmd}'), '/C where ollama', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    // Exec call itself failed (shouldn't normally happen) — don't block install
  end;
  if ResultCode <> 0 then
  begin
    if MsgBox('Ollama was not found on this system. Fraude works without it, but local AI ' +
              '(HighKu) features need Ollama installed.' + #13#10#13#10 +
              'Continue installing Fraude now and install Ollama later from ollama.com?',
              mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;
