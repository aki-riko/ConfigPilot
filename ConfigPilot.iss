; ConfigPilot 安装脚本 (Inno Setup)
#define AppName "ConfigPilot"
#define AppLegacyName "Codex 配置助手"
#ifndef AppVer
  #define AppVer "1.0.7"
#endif
#define AppPublisher "9li"
#define AppExe "ConfigPilot.exe"
#define LegacyAppExe "CodexConfig.exe"

[Setup]
; 保留旧 AppId,确保已安装的 Codex 配置助手能原位升级到 ConfigPilot。
AppId={{8F3C2A91-CODEX-9LI-CONF-000000000001}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\ConfigPilot
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=ConfigPilot_Setup_{#AppVer}
SetupIconFile=resources\app_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline

[Languages]
Name: "chinesesimp"; MessagesFile: "installer_lang\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
; 打包整个 main.dist 目录(含 exe + 所有依赖、QML 和 JSON 配置)
Source: "build\main.dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; 同 AppId 升级时移除旧品牌留下的程序和快捷方式。
Type: files; Name: "{app}\{#LegacyAppExe}"
Type: files; Name: "{group}\{#AppLegacyName}.lnk"
Type: files; Name: "{group}\卸载 {#AppLegacyName}.lnk"
Type: files; Name: "{autodesktop}\{#AppLegacyName}.lnk"

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent
