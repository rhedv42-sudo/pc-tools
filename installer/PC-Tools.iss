; PC-Tools - Installationsprogramm (Inno Setup 6). Gebaut in GitHub Actions aus dem Quellcode.
; Installiert nach C:\ProgramData\PCPflege (dort aktualisiert sich PC-Tools selbst), Startmenü/Desktop, saubere Deinstallation.
#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#ifndef SrcDir
  #define SrcDir ".."
#endif
#ifndef OutDir
  #define OutDir "..\dist"
#endif

[Setup]
AppId={{6F1C2B3A-5D4E-4F70-9A1B-0C7005A10000}
AppName=PC-Tools
AppVersion={#AppVersion}
AppVerName=PC-Tools {#AppVersion}
AppPublisher=PC-Tools Open Source Project
AppPublisherURL=https://github.com/rhedv42-sudo/pc-tools
AppSupportURL=https://github.com/rhedv42-sudo/pc-tools/issues
AppUpdatesURL=https://github.com/rhedv42-sudo/pc-tools/releases
DefaultDirName={commonappdata}\PCPflege
DisableDirPage=yes
DisableProgramGroupPage=yes
UsePreviousAppDir=no
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutDir}
OutputBaseFilename=PC-Tools-Setup-{#AppVersion}
SetupIconFile={#SrcDir}\PCPflege.ico
UninstallDisplayIcon={app}\PC-Tools.exe
UninstallDisplayName=PC-Tools
LicenseFile={#SrcDir}\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=yes
VersionInfoVersion={#AppVersion}
VersionInfoProductName=PC-Tools
VersionInfoDescription=PC-Tools Setup
CloseApplications=no

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"
#ifexist AddBackslash(CompilerPath) + "Languages\Korean.isl"
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"
#endif
#ifexist AddBackslash(CompilerPath) + "Languages\ChineseSimplified.isl"
Name: "zh"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SrcDir}\dist\PC-Tools.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\PCPflege.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\PCPflege.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\PCPflege.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\Komplett-Reparatur.cmd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}\Zubehoer\*"; DestDir: "{app}\Zubehoer"; Flags: ignoreversion recursesubdirs
Source: "{#SrcDir}\lang\*.json"; DestDir: "{app}\lang"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#SrcDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\PC-Tools"; Filename: "{app}\PC-Tools.exe"; IconFilename: "{app}\PCPflege.ico"; AppUserModelID: "RHEDV.PCPflege"
Name: "{autodesktop}\PC-Tools"; Filename: "{app}\PC-Tools.exe"; IconFilename: "{app}\PCPflege.ico"; AppUserModelID: "RHEDV.PCPflege"; Tasks: desktopicon

[Run]
Filename: "{app}\PC-Tools.exe"; Description: "{cm:LaunchProgram,PC-Tools}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; geplante Aufgaben von PC-Tools entfernen
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Get-ScheduledTask | Where-Object {{ $_.TaskName -like 'PC-Tools*' -or $_.TaskName -like 'PC-Pflege*' -or $_.TaskName -like 'PCPflege*' } | Unregister-ScheduledTask -Confirm:$false"""; Flags: runhidden; RunOnceId: "RemoveTasks"

[UninstallDelete]
Type: files; Name: "{autodesktop}\PC-Tools.lnk"
Type: files; Name: "{autoprograms}\PC-Tools.lnk"
Type: filesandordirs; Name: "{app}\lang"
Type: filesandordirs; Name: "{app}\Update"

[Code]
function LangCode(): String;
begin
  case ActiveLanguage() of
    'en': Result := 'en-US';
    'fr': Result := 'fr-FR';
    'es': Result := 'es-ES';
    'it': Result := 'it-IT';
    'pl': Result := 'pl-PL';
    'ptbr': Result := 'pt-BR';
    'ru': Result := 'ru-RU';
    'tr': Result := 'tr-TR';
    'ja': Result := 'ja-JP';
    'ko': Result := 'ko-KR';
    'zh': Result := 'zh-CN';
  else
    Result := 'de-DE';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var f: String;
begin
  if CurStep = ssPostInstall then begin
    f := ExpandConstant('{app}\sprache.txt');
    if not FileExists(f) then SaveStringToFile(f, LangCode(), False);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    if MsgBox(SetupMessage(msgUninstalledAll) + #13#10#13#10 + 'Einstellungen, Protokolle und Sicherungen von PC-Tools ebenfalls löschen? / Also delete PC-Tools settings, logs and backups?', mbConfirmation, MB_YESNO) = IDYES then
      DelTree(ExpandConstant('{app}'), True, True, True);
  end;
end;
