#ifndef AppVersion
  #define AppVersion "1.5.0"
#endif
[Setup]
AppId=Fetch
AppName=Fetch
AppVersion={#AppVersion}
AppPublisher=KALLOS
AppPublisherURL=https://github.com/MOONKYUNGJIN82/fetch
AppUpdatesURL=https://github.com/MOONKYUNGJIN82/fetch/releases/latest
DefaultDirName={code:DefaultInstall}
DefaultGroupName=Fetch
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release\standalone
OutputBaseFilename=Fetch.Setup
SetupIconFile=..\assets\fetch.ico
UninstallDisplayIcon={app}\Fetch.ico
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern dark
WizardSizePercent=110
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#AppVersion}
WizardSmallImageFile=..\build\fetch-wizard-small.bmp
WizardImageFile=..\build\fetch-wizard.bmp

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기"; Flags: checkedonce
[Files]
Source: "..\release\fetch-standalone\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\fonts\PretendardVariable.ttf"; Flags: dontcopy
[InstallDelete]
Type: files; Name: "{app}\runtime\pyvenv.cfg"
[Icons]
Name: "{group}\Fetch"; Filename: "{app}\Fetch.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Fetch.ico"
Name: "{group}\Uninstall Fetch"; Filename: "{uninstallexe}"; IconFilename: "{app}\Fetch.ico"
Name: "{autodesktop}\Fetch"; Filename: "{app}\Fetch.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Fetch.ico"; Tasks: desktopicon
[Run]
Filename: "{app}\Fetch.exe"; Description: "Fetch 실행"; Flags: nowait postinstall skipifsilent
Filename: "{app}\Fetch.exe"; Flags: nowait; Check: RestartRequested
[Code]
function AddFontResourceEx(lpszFilename: String; fl: Integer; pdv: Integer): Integer;
external 'AddFontResourceExW@gdi32.dll stdcall';
function RestartRequested: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:RESTARTFETCH|0}') = '1');
end;
function DefaultInstall(Param: String): String;
var Location: String;
begin
  Result := ExpandConstant('{localappdata}\Programs\Fetch');
  if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\Fetch', 'InstallLocation', Location) then
    if FileExists(Location + '\Launch Fetch.vbs') then Result := Location;
end;
procedure InitializeWizard;
var FontPath: String;
begin
  ExtractTemporaryFile('PretendardVariable.ttf');
  FontPath := ExpandConstant('{tmp}\PretendardVariable.ttf');
  AddFontResourceEx(FontPath, 16, 0);
  WizardForm.Font.Name := 'Pretendard Variable';
  WizardForm.Font.Size := 10;
  WizardForm.WelcomeLabel1.Caption := 'Fetch';
  WizardForm.WelcomeLabel2.Caption := 'CONTENTS DOWNLOADER';
end;
procedure CurStepChanged(CurStep: TSetupStep);
var Location: String;
begin
  if CurStep = ssDone then
    if RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\Fetch', 'InstallLocation', Location) then
      if CompareText(Location, ExpandConstant('{app}')) = 0 then
        RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\Fetch');
end;
