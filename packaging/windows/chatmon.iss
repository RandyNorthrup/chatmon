; Chatmon's Windows installer (Inno Setup 6). packaging/build.py windows builds it:
;   ISCC /DAppVersion=x.y.z /DSourceDir=<Nuitka's Chatmon folder> /DOutputDir=<folder> chatmon.iss
; A release's is built signed (.github/workflows/packages.yml), around Chatmon's programs signed already:
; /DSignWith=<name> /S<name>=<command $f> has Inno Setup sign the uninstaller and the installer as it makes them.
;
; Installs for you alone (no administrator needed) or, if you choose, for everyone. Its choices:
; a Start menu entry, a desktop icon (off unless you tick it), chatmon on PATH for your coding agents'
; hooks, and starting at login. Uninstalling takes all of them back out, and leaves your settings.

#ifndef AppVersion
  #error Pass the version: /DAppVersion=x.y.z
#endif
#ifndef SourceDir
  #define SourceDir "..\..\build\nuitka\Chatmon"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{5E4C1C2B-0B6F-4E57-9C7E-6A1C3B9E2F41}
AppName=Chatmon
AppVersion={#AppVersion}
AppVerName=Chatmon {#AppVersion}
AppPublisher=Randy Northrup
AppPublisherURL=https://github.com/RandyNorthrup/chatmon
AppSupportURL=https://github.com/RandyNorthrup/chatmon/issues
AppUpdatesURL=https://github.com/RandyNorthrup/chatmon/releases
AppCopyright=Copyright (c) 2026 Randy Northrup
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Chatmon
VersionInfoDescription=Chatmon Setup
DefaultDirName={autopf}\Chatmon
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=Chatmon-{#AppVersion}-windows-x64-setup
SetupIconFile=..\icons\chatmon.ico
UninstallDisplayIcon={app}\chatmonw.exe
UninstallDisplayName=Chatmon
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no
#ifdef SignWith
SignTool={#SignWith}
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startmenu"; Description: "Add Chatmon to the &Start menu"; GroupDescription: "Shortcuts:"
Name: "desktop"; Description: "Put a Chatmon icon on the &desktop"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "path"; Description: "Let my coding agents' hooks run chatmon (adds it to &PATH)"; GroupDescription: "Coding agents:"
Name: "autostart"; Description: "Start Chatmon when I &log in"; GroupDescription: "Starting:"; Flags: unchecked

[InstallDelete]
; An update's files replace the last version's whole: nothing of it is left behind to be loaded. Each
; folder this version installs goes first, as do the last version's libraries, and PyInstaller's
; _internal, from versions before Chatmon was compiled with Nuitka.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\*.dll"
Type: files; Name: "{app}\*.pyd"
#define Found
#define Search = FindFirst(AddBackslash(SourceDir) + "*", faDirectory)
#sub InstalledFolder
  #define Name = FindGetFileName(Search)
  #if Name != "." && Name != ".." && DirExists(AddBackslash(SourceDir) + Name)
Type: filesandordirs; Name: "{app}\{#Name}"
  #endif
#endsub
#for {Found = Search; Found; Found = FindNext(Search)} InstalledFolder
#if Search
  #expr FindClose(Search)
#endif

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; AppUserModelID: the same identity Chatmon gives itself (app.py), so Windows knows the shortcut and the app as one.
Name: "{autoprograms}\Chatmon"; Filename: "{app}\chatmonw.exe"; Comment: "Your desktop companion"; AppUserModelID: "RandyNorthrup.Chatmon"; Tasks: startmenu
Name: "{autodesktop}\Chatmon"; Filename: "{app}\chatmonw.exe"; Comment: "Your desktop companion"; AppUserModelID: "RandyNorthrup.Chatmon"; Tasks: desktop

[Registry]
; The same value Chatmon's own "Start when I log in" sets, so its menu shows it ticked.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Chatmon"; ValueData: """{app}\chatmonw.exe"""; Tasks: autostart

[Run]
Filename: "{app}\chatmonw.exe"; Description: "Start Chatmon now"; Flags: nowait postinstall skipifsilent
; Chatmon updating itself runs this silently with /relaunch=1: it starts again once the update is in, as you.
Filename: "{app}\chatmonw.exe"; Flags: nowait runasoriginaluser; Check: Relaunch

[Code]
const
  UserEnvironment = 'Environment';
  MachineEnvironment = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
  RunKey = 'Software\Microsoft\Windows\CurrentVersion\Run';

{ PATH: your own for an install for you, the computer's for one for everyone. }
function EnvRoot: Integer;
begin
  if IsAdminInstallMode then Result := HKLM else Result := HKCU;
end;

function EnvKey: String;
begin
  if IsAdminInstallMode then Result := MachineEnvironment else Result := UserEnvironment;
end;

#include "path.iss"

{ Ask a running Chatmon to quit (it saves first), so its files can be replaced or removed. }
procedure QuitChatmon;
var
  Code: Integer;
begin
  if FileExists(ExpandConstant('{app}\chatmon.exe')) then
    if Exec(ExpandConstant('{app}\chatmon.exe'), 'quit', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0) then
      Sleep(1500);
end;

function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  QuitChatmon;
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if WizardIsTaskSelected('path') then
      AddToPath(EnvRoot, EnvKey, ExpandConstant('{app}'))
    else
      RemoveFromPath(EnvRoot, EnvKey, ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    QuitChatmon;
    RemoveFromPath(EnvRoot, EnvKey, ExpandConstant('{app}'));
    { Starting at login, whether set here or from Chatmon's own menu, if it starts this one. }
    if RegQueryStringValue(HKCU, RunKey, 'Chatmon', Command) then
      if Pos(Uppercase(ExpandConstant('{app}')), Uppercase(Command)) > 0 then
        RegDeleteValue(HKCU, RunKey, 'Chatmon');
  end;
end;
