; ConfigPilot 安装脚本 (Inno Setup)
#define AppName "ConfigPilot"
#define AppLegacyName "Codex 配置助手"
#ifndef AppVer
  #define AppVer "1.0.13"
#endif
#define AppPublisher "9li"
#define AppExe "ConfigPilot.exe"
#define LegacyAppExe "CodexConfig.exe"
#define LegacyInstallDirName "CodexConfig"
#define AppUserModelID "PrismQML.ConfigPilot"
#define UninstallRegistryKey "Software\Microsoft\Windows\CurrentVersion\Uninstall\{8F3C2A91-CODEX-9LI-CONF-000000000001}_is1"

[Setup]
; 保留旧 AppId,确保已安装的 Codex 配置助手能原位升级到 ConfigPilot。
AppId={{8F3C2A91-CODEX-9LI-CONF-000000000001}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\ConfigPilot
DefaultGroupName={#AppName}
UsePreviousAppDir=no
UsePreviousGroup=no
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
CloseApplications=yes

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
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModelID}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\{#AppExe}"; AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "立即启动 {#AppName}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: ShouldAutoRestartApplication

[Code]
var
  PreviousInstallDir: String;

function HasCommandLineParam(const Expected: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
  begin
    if CompareText(ParamStr(I), Expected) = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function ShouldAutoRestartApplication(): Boolean;
begin
  Result := WizardSilent and HasCommandLineParam('/AUTORESTARTAPP');
end;

function InitializeSetup(): Boolean;
begin
  PreviousInstallDir := '';
  if not RegQueryStringValue(
    HKCU,
    '{#UninstallRegistryKey}',
    'InstallLocation',
    PreviousInstallDir
  ) then
  begin
    RegQueryStringValue(
      HKLM,
      '{#UninstallRegistryKey}',
      'InstallLocation',
      PreviousInstallDir
    );
  end;

  if PreviousInstallDir <> '' then
    Log('检测到上一版本安装目录: ' + PreviousInstallDir)
  else
    Log('未检测到上一版本安装目录');

  Result := True;
end;

function IsOwnedLegacyInstallDir(const Path: String): Boolean;
var
  NormalizedPath: String;
begin
  NormalizedPath := RemoveBackslashUnlessRoot(Path);
  Result :=
    (NormalizedPath <> '') and
    (CompareText(ExtractFileName(NormalizedPath), '{#LegacyInstallDirName}') = 0) and
    (CompareText(NormalizedPath, RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) <> 0);
end;

procedure RemoveLegacyDirectory(const Path, LabelText: String);
begin
  if not DirExists(Path) then
    exit;

  Log('清理' + LabelText + ': ' + Path);
  if not DelTree(Path, True, True, True) then
    Log('警告: 无法完整清理' + LabelText + ': ' + Path);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then
    exit;

  if IsOwnedLegacyInstallDir(PreviousInstallDir) then
    RemoveLegacyDirectory(RemoveBackslashUnlessRoot(PreviousInstallDir), '旧安装目录')
  else if PreviousInstallDir <> '' then
    Log('保留非标准旧安装目录，避免删除用户自定义路径: ' + PreviousInstallDir);

  RemoveLegacyDirectory(
    ExpandConstant('{userprograms}\{#AppLegacyName}'),
    '旧开始菜单目录'
  );
  RemoveLegacyDirectory(
    ExpandConstant('{commonprograms}\{#AppLegacyName}'),
    '旧公共开始菜单目录'
  );
end;
