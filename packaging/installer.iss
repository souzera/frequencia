; Compile after PyInstaller: ISCC.exe packaging\installer.iss
; Override the version without editing this file: ISCC.exe /DMyAppVersion=1.2.3 packaging\installer.iss
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif

[Setup]
AppId={{E084CB81-0F67-4C72-902E-5E629A3EAB5B}
AppName=Frequência
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\Frequencia
DefaultGroupName=Frequência
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=Frequencia-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
SetupIconFile=..\desktop\ui\assets\frequencia.ico
UninstallDisplayIcon={app}\Frequencia.exe

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "..\dist\Frequencia\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Frequência"; Filename: "{app}\Frequencia.exe"
Name: "{autodesktop}\Frequência"; Filename: "{app}\Frequencia.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Run]
Filename: "{app}\Frequencia.exe"; Description: "Abrir Frequência"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var Version: String;
begin
  Result := RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version)
    or RegQueryStringValue(HKLM32, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version)
    or RegQueryStringValue(HKLM64, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
  if not Result then
    MsgBox('Instale o Microsoft Edge WebView2 Runtime antes de continuar. Disponível em https://developer.microsoft.com/microsoft-edge/webview2/', mbError, MB_OK);
end;
