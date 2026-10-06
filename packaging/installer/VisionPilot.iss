; Inno Setup Script for VisionPilot Desktop AI Agent
; Generates a Windows standard installer for VisionPilot on Windows 11 (Snapdragon X / x64 Prism)

#define MyAppName "VisionPilot"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "VisionPilot Project"
#define MyAppURL "https://github.com/visionpilot/visionpilot"
#define MyAppExeName "VisionPilot.exe"

[Setup]
; App Identity
AppId={{5E97D4B6-7F31-4B9F-83C4-1A53E0341B2E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation Target
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Output Configuration
OutputDir=..\..\release
OutputBaseFilename=VisionPilot-Setup-{#MyAppVersion}
SetupIconFile=..\..\assets\icons\visionpilot.ico
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern

; Architecture support
ArchitecturesInstallIn64BitMode=x64 arm64
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\VisionPilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Safety rule: Keep user task history and configuration intact during uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Note: User data residing in %LOCALAPPDATA%\VisionPilot is preserved by design.
  end;
end;
