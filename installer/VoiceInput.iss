#define AppVersion "0.2.0"
#define AppName "Voice Input"
#define AppExe "VoiceInput.exe"

[Setup]
AppId={{D2395A84-087B-4BAA-8651-79C16EFDCDE1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Local Voice Input
DefaultDirName={localappdata}\Programs\VoiceInput
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\build\installer
OutputBaseFilename=VoiceInput-Setup-{#AppVersion}-x64
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "autostart"; Description: "Запускать Voice Input при входе в Windows"; GroupDescription: "Дополнительные параметры:"; Flags: unchecked

[Files]
Source: "..\dist\VoiceInput\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Voice Input"; Filename: "{app}\{#AppExe}"
Name: "{group}\Удалить Voice Input"; Filename: "{uninstallexe}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Voice Input"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "Запустить Voice Input"; Flags: postinstall nowait skipifsilent
