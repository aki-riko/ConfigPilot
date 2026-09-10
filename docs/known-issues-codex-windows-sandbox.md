# 已知问题记录：Codex Windows 沙盒 provisioning 弹出「无法检查 Windows 设置」

> 记录时间：2026-09-11 · 相关版本：ConfigPilot v1.0.29 / Codex CLI 0.14x（Windows）

## 现象

在**另一台没有安装 Claude Desktop / Claude Code 的 Windows 机器**上，一次「应用更改」写入 Codex 配置之后，
有概率出现全屏的 Windows 首次登录界面：

```
（Microsoft 徽标）
无法检查 Windows 设置
重试以继续 Windows 设置
[ 重试 ]
继续使用受限访问
```

用 CC Switch 切换一轮 provider（重写 `config.toml` / `auth.json`）之后，现象消失。

## 结论：这是 Codex 的 Windows 沙盒 BUG，不是 ConfigPilot 写坏了配置

**上游 issue（标题即图上的原文 "Couldn't check Windows setup"）**

- [#42264 Windows setup loop — "Couldn't check Windows setup" / "Windows setup didn't finish", sandbox-setup.exe crashes silently on elevation](https://github.com/openai/codex/issues/42264)
- [#35349 Codex Desktop stuck in "Windows Setup Incomplete" loop despite Windows Sandbox feature enabled](https://github.com/openai/codex/issues/35349)
- [#17458 Windows sandbox users are created but their profiles are not initialized until manual first logon](https://github.com/openai/codex/issues/17458)
- [#40102 native sandbox setup fails, WSL works; unelevated fallback also fails](https://github.com/openai/codex/issues/40102)
- [#39251](https://github.com/openai/codex/issues/39251) · [#43416](https://github.com/openai/codex/issues/43416) · [#42513](https://github.com/openai/codex/issues/42513) · [#44185](https://github.com/openai/codex/issues/44185) · [#38898](https://github.com/openai/codex/issues/38898) · [#36235](https://github.com/openai/codex/issues/36235)

**本机二进制取证**（`%USERPROFILE%\.codex\.sandbox-bin\codex.exe`，281 MB，原始字符串命中）

- 提权助手 `codex-windows-sandbox-setup.exe`：`runas/ShellExecuteExW failed to launch setup helper`、`failed to launch setup helper (non-elevated)`
- provisioning 编排与状态文件：`windows-sandbox-setup`、`full / provision-only / refresh_only`、`setup_marker.json`、`setup_error.json`、`sandbox_users.json`、`.sandbox-secrets`、`elevated / unelevated`
- 本地沙盒账号 `CodexSandboxOffline` / `CodexSandboxOnline`（`offline_username` / `online_username`），并改防火墙：
  `offline firewall settings changed (stored_ports=…, desired_ports=…)`、`CODEX_WINDOWS_SANDBOX_PROXY_PORTS`
- 两套实现：受限令牌 + `CreateProcessAsUser` 的 `codex-command-runner.exe`，以及 `WindowsSandbox`(HCS)
  （`allowedWindowsSandboxImplementations`、`WindowsSandboxModeToml`、`[windows] sandbox = "elevated" | "unelevated"`）

**机制链**：写入配置 → Codex 带新配置启动 → 触发沙盒 provisioning / refresh → 创建或刷新本地沙盒账号 →
这些账号的 profile 未初始化（#17458）→ Windows 走首次登录的「Windows 设置」流程 → 联网校验失败 → 图上那一屏；
setup helper 提权静默崩溃时进入循环（#42264 / #35349）→ 所以是「有概率」而不是必现。
CC Switch 重写配置后 Codex 不再走那条 provisioning 路径，症状消失，但沙盒账号与 `setup_marker.json` 状态仍在机器上（治标）。

**排除实验（ConfigPilot 未改坏沙盒键）**

用 `CodexConfigStore._write_provider_block()` 对一份含沙盒配置的 `config.toml` 做纯文本写入（零副作用，见
`build/_probe_toml_preserve.py`），结果：`sandbox_mode`、`approval_policy`、`[windows] sandbox`、
`sandbox_private_desktop`、`[sandbox_workspace_write]`、`[projects.*]`、`[features]`、`notify` **全部原样保留**，
只改动 `base_url` / `model` / `model_reasoning_effort` / 上下文数值 / `[model_providers.X]`。

## 再次出现时的定位命令（只读）

```powershell
Get-LocalUser | Where-Object Name -like 'CodexSandbox*' | Format-Table Name,Enabled,PasswordExpired,LastLogon
Get-ChildItem "$env:USERPROFILE\.codex\.sandbox-bin" -Filter 'codex-windows-sandbox-setup*'
Get-ChildItem "$env:USERPROFILE\.codex\.sandbox-secrets" | Select Name,LastWriteTime
Get-Content "$env:USERPROFILE\.codex\.sandbox-secrets\setup_error.json" -ErrorAction SilentlyContinue
```

规避方向（属 Codex 侧配置，需按本机 Codex 版本核对可选值）：按 #40102 走 WSL 路径；
或在 `config.toml` 显式指定实现 `[windows] sandbox = "unelevated"`（#40102 中 unelevated 亦可能失败）。

## 与 ConfigPilot 的关系

ConfigPilot 只做两件事：写 `~/.codex/config.toml` + `auth.json`（保留其它键），随后由用户启动 Codex。
**写入本身不会破坏沙盒配置**，根治仍要靠上游 issue。

### 应用内临时止血（「沙盒止血（临时）」）

CC Switch 之所以能"治好"，是因为它每次切换都整体重写 Codex 配置，而它的通用配置模板
（`~/.cc-switch/cc-switch.db` 的 `settings.common_config_codex`）里硬编码了：

```toml
approval_policy = "never"
sandbox_mode = "danger-full-access"

[windows]
sandbox = "elevated"
```

`sandbox_mode = "danger-full-access"` 让 Codex 不再需要沙盒执行，也就不会再去 provisioning
沙盒账号，图 1 消失。ConfigPilot 原本是**保留**现有 `sandbox_mode`，所以那台机器（仍是
`workspace-write` 或没有该键）照旧触发。

因此 Codex 页「连接与认证」卡片新增 **沙盒止血（临时）** 按钮（与「修复中转站 401」同一行样式）：

- 只写一个键：`sandbox_mode = "danger-full-access"`，其余键与 `[windows]`、`[projects.*]`、
  `notify` 等段落原样保留；
- 写入前弹确认框，明确说明代价（Codex 失去沙盒隔离）；
- 写入记入 ConfigPilot 恢复记录，「恢复初始设置」可还原；
- 用户在外部改过该键时不会被覆盖。

对应实现：`CodexConfigStore.apply_sandbox_stopgap()`（`backend/codex_config_store.py`）、
`CodexConfig.applySandboxStopgap()`（`backend/codex_config.py`）、
`qml/views/ConnectionSection.qml` 的 `sandboxStopgapButton` 与 `qml/views/CodexView.qml`
的 `sandboxStopgapDialog`；测试见 `tests/test_codex_sandbox_stopgap.py`。

取值依据（非猜测）：`codex.exe`（0.148.0-alpha.9）里 `sandbox_mode` 的合法字面量为
`read-only` / `workspace-write` / `danger-full-access`（二进制字符串命中），
`[windows] sandbox` 只有 `elevated` / `unelevated`。

**已知局限（本机对照）**：本机 `~/.codex` 自 7/10 起所有 config 备份都是
`sandbox_mode = "danger-full-access"`，但 `CodexSandboxOffline` 仍有 `LastLogon`（8/16）——
说明 Codex Desktop 的某些功能仍可能用到沙盒账号。因此该止血针对的是**触发此循环的 CLI/会话执行路径**，
不保证覆盖桌面端全部沙盒用法；若仍在桌面端复现，按上文 A/B 步骤把 provisioning 补完。
