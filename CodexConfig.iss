; Codex 配置助手 安装脚本 (Inno Setup)
#define AppName "Codex 配置助手"
#ifndef AppVer
  #define AppVer "1.0.1"
#endif
#define AppPublisher "9li"
#define AppExe "CodexConfig.exe"

[Setup]
AppId={{8F3C2A91-CODEX-9LI-CONF-000000000001}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\CodexConfig
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=CodexConfig_Setup_{#AppVer}
SetupIconFile=resources\app_icon.ico
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
; 打包整个 main.dist 目录(含 exe + 所有依赖/qml/prismqml/providers.json)
Source: "build\main.dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent
