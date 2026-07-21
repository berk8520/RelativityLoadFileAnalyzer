[Setup]
AppName=Page One Relativity Load File Tools
AppVersion=1.2.0
AppPublisher=Pageone
DefaultDirName={localappdata}\Page One Relativity Load File Tools
DefaultGroupName=Page One Relativity Load File Tools
UninstallDisplayIcon={app}\pyside_main.exe
Compression=lzma2
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=RelativityLoadFileAnalyzer_Setup
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\pyside_main\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "vcredist_x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\Page One Relativity Load File Tools"; Filename: "{app}\pyside_main.exe"
Name: "{group}\Uninstall Page One Relativity Load File Tools"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Page One Relativity Load File Tools"; Filename: "{app}\pyside_main.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Registry]
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.dat\shell\PageOneRelativityLoadFileTools"; ValueType: string; ValueData: "Open with Page One Relativity Load File Tools"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.dat\shell\PageOneRelativityLoadFileTools"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\pyside_main.exe"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.dat\shell\PageOneRelativityLoadFileTools\command"; ValueType: string; ValueData: """{app}\pyside_main.exe"" ""%1"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.csv\shell\PageOneRelativityLoadFileTools"; ValueType: string; ValueData: "Open with Page One Relativity Load File Tools"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.csv\shell\PageOneRelativityLoadFileTools"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\pyside_main.exe"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.csv\shell\PageOneRelativityLoadFileTools\command"; ValueType: string; ValueData: """{app}\pyside_main.exe"" ""%1"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.txt\shell\PageOneRelativityLoadFileTools"; ValueType: string; ValueData: "Open with Page One Relativity Load File Tools"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.txt\shell\PageOneRelativityLoadFileTools"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\pyside_main.exe"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.txt\shell\PageOneRelativityLoadFileTools\command"; ValueType: string; ValueData: """{app}\pyside_main.exe"" ""%1"""; Flags: uninsdeletekey

[Run]
Filename: "{tmp}\vcredist_x64.exe"; Parameters: "/install /passive /norestart"; StatusMsg: "Installing Microsoft Visual C++ Redistributable (may prompt for admin permission)..."; Flags: waituntilterminated
