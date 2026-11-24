; Paragon PR7-U installer (Inno Setup 6): the one download for the whole family.
;   iscc /DAppVersion=0.1.0 installer\pr7u.iss      (after pyinstaller pr7u.spec has made dist\PR7-U)
;
; Per-user (no admin rights) into %LOCALAPPDATA%\Programs\PR7-U, with a Start menu entry. The finish page starts
; PR7-U on "Install the family", where the apps are ticked and installed with their own installers. Uninstalling
; PR7-U leaves the apps it installed: each is in Installed apps on its own.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId is permanent: it's how a new version finds and upgrades the installed one. Never change it.
AppId={{12226380-56E6-4D77-8F5C-8052A0AE4183}
AppName=Paragon PR7-U
AppVersion={#AppVersion}
AppVerName=Paragon PR7-U {#AppVersion}
AppPublisher=Paragon
VersionInfoVersion={#AppVersion}
PrivilegesRequired=lowest
DefaultDirName={autopf}\PR7-U
DefaultGroupName=Paragon PR7-U
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=PR7-U-Setup-{#AppVersion}
SetupIconFile=..\pr7u\icons\app.ico
UninstallDisplayIcon={app}\PR7-U.exe
UninstallDisplayName=Paragon PR7-U
WizardStyle=modern
WizardImageFile=wizard-large-1x.bmp,wizard-large-2x.bmp
WizardSmallImageFile=wizard-small-1x.bmp,wizard-small-2x.bmp
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PR7-U\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Paragon PR7-U"; Filename: "{app}\PR7-U.exe"; Comment: "Install and update the Paragon family"
Name: "{autodesktop}\Paragon PR7-U"; Filename: "{app}\PR7-U.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PR7-U.exe"; Parameters: "--choose"; Description: "Choose the Paragon apps to install"; Flags: nowait postinstall skipifsilent
; Updates (Check PR7-U for updates runs this installer with /SILENT /relaunch=1): start PR7-U again when done.
Filename: "{app}\PR7-U.exe"; Flags: nowait runasoriginaluser; Check: Relaunch

[Code]
// True only when the updater asked for it (/relaunch=1): normal and CI installs behave as before.
function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;
