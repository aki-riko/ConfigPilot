# ConfigPilot

<p align="center">
  <img src="resources/app_icon.png" alt="ConfigPilot 图标" width="160">
</p>

**AI 工具配置与自动化中心。**

ConfigPilot 是一个用 [PrismQML](https://pypi.org/project/prismqml/) 构建的桌面工具。当前支持 OpenAI Codex CLI 与 Claude Desktop：既能管理 `~/.codex/config.toml`，也能一键启用 Claude Desktop Developer Mode 并配置 Third-Party Inference Gateway，免去手动编辑 TOML/JSON。

![ConfigPilot 主界面](docs/images/configpilot-main.png)

- **下载**：[GitHub Releases](../../releases)
- **自动更新**：启动后自动检查 GitHub Releases；Windows 可在应用内下载、静默安装并重启，macOS 会打开官方发布页完成升级。
- **适合**：需要频繁切换 Codex CLI provider，或希望让 Claude Desktop 使用第三方 `/v1/messages` Gateway，但不想手动编辑 TOML/JSON 的用户。

## 功能

- **Codex API 连接配置**：填写 `base_url`、provider、通信协议和模型；通信协议是下拉框，界面只显示 **Responses API** / **Chat Completions API（已废弃）**，写入 `config.toml` 的 `wire_api = "responses" / "chat"` 由 `backend/wire_api.py` 统一映射；地址末尾缺少 `/v1` 时自动补全，输入框失焦或回车即回填补全后的地址
- **高级选项**（都是 Codex 原生 `config.toml` 字段）：
  - `requires_openai_auth` —— 供应商用 Chat Completions 协议或非 GPT 模型时开启
  - `model_reasoning_effort` —— 优先从远端模型目录读取；GPT-5.6 提供“轻度 / 中 / 高 / 极高 / 最高”五档，“最高”的真实配置值为 `max`
  - `disable_response_storage` —— 禁用响应存储
- **上下文预设**：保留所有受支持模型的稳定值 `258400 / 245000 / 6000`，并可一键套用百万上下文 `1048576 / 943718 / 6000`
- **响应式界面**：连接、模型、上下文和兼容性分区展示，窄窗口自动切换为单列
- **获取模型**：请求中转的 `/v1/models`，结果填入 model 下拉（后台线程，不卡界面）
- **API key**：写入 `~/.codex/auth.json`
- **ChatGPT JSON 导入**：粘贴 Codex `auth.json`、codex2api 扁平 JSON 或 `accounts[].credentials` 单账号 JSON；完整凭据直接保存，仅有 `refresh_token` 时通过官方 OAuth 补齐
- **安全**：每次写入前自动备份 `config.toml.bak` / `auth.json.bak`，保留 `notify` 等其它原有配置不动
- **恢复初始设置**：只恢复 ConfigPilot 实际改过且此后未被外部修改的字段；保留 `[projects.*]` 工作区信任项和其它 Codex 配置
- **常驻操作栏**：随时查看未应用状态，并可重新读取或应用配置
- **沙盒止血（临时）**：把 Codex 顶层 `sandbox_mode` 写为 `danger-full-access`，绕过 Windows 上「无法检查 Windows 设置」的沙盒初始化循环；只改这一个字段，`[windows]`／`[projects.*]`／`notify` 全部保留，可用「恢复初始设置」还原
- **Claude Desktop Subpage**：直接写入 Claude 自己的本地配置库，一键启用 Developer Mode 与 `deploymentMode=3p`
- **第三方推理 Gateway**：配置 endpoint、`bearer` / `x-api-key`、API key、模型发现、模型 ID、显示名、1M 上下文、Tier alias 和额外 Header；endpoint 原样写入，Claude Desktop 自行请求 `/v1/messages`
- **Claude 配置安全**：编辑当前已应用配置，敏感字段留空默认保留；写入前创建 `.bak`，损坏的现有 JSON 会拒绝覆盖
- **余额监控桌宠**：NEWAPI 站点的悬浮小飞宠，气泡实时显示令牌余额与今日用量，点击展开调用明细（模型 / Tokens / 消耗金额）；主界面「设置」页有开关与设置入口，仅凭 API Key 轮询 new-api 只读接口，令牌耗尽或过期也能查余额
- **系统托盘与关闭确认**：程序常驻托盘图标（左键/双击叫回主窗口，右键出「显示主界面 / 退出程序」）。点窗口 ✕ **不会**静默缩进托盘，而是弹一次确认：`退出程序` / `最小化到托盘` / `取消`；选「最小化到托盘」时主窗口与桌宠一起隐藏，托盘图标仍在，随时可以叫回来

> Claude Desktop 配置写入后必须完全退出并重新打开。ConfigPilot 不会强制结束正在运行的 Cowork / Code 会话。

## 安装使用（终端用户）

### Windows

下载 [Releases](../../releases) 里的 `ConfigPilot_Setup_x.x.x.exe`，双击安装即可。无需 Python，VC++ 运行库已内置。

### macOS（Apple Silicon）

下载 `ConfigPilot_x.x.x_arm64.dmg`，打开后把 `ConfigPilot` 拖入 `Applications`。当前 macOS 包仅支持 Apple Silicon（M 系列芯片），暂不支持 Intel Mac。

> **首次打开说明：**维护者目前没有 Apple Developer Program 会员，因此 DMG 尚未使用 Developer ID 签名和 Apple 公证。macOS Gatekeeper 可能显示“应用已损坏”，但这不代表下载文件真的损坏。请只从本项目官方 Releases 下载，然后在“终端”执行一次：

```bash
xattr -dr com.apple.quarantine "/Applications/ConfigPilot.app"
open "/Applications/ConfigPilot.app"
```

同一已安装版本通常只需执行一次；重新下载或升级后，系统可能再次添加隔离标记。正式签名与公证会在具备 Apple Developer Program 会员后接入。

## 从源码运行（开发者）

需要 Python 3.11+（用到 `tomllib`）。

```bash
git clone https://github.com/aki-riko/ConfigPilot.git
cd configpilot
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

或直接双击 `run.cmd`（自动用 `.venv`，没有则回退系统 Python）。

<!--__BUILD_SECTION__-->
## 打包分发

**Nuitka 打包成 standalone：**

```bash
build_nuitka.cmd
```
产物在 `build\main.dist\`。可手动删除 `build\main.dist\` 下的 `qt6webengine*.dll` 和 `PySide6\qml\QtWebEngine` 省约 200MB（本工具用不到）。

**Inno Setup 制作安装程序**（需 [Inno Setup 6+](https://jrsoftware.org/isdl.php)）：

```bash
ISCC ConfigPilot.iss
```
产物在 `installer\ConfigPilot_Setup_x.x.x.exe`。

## 余额监控桌宠

右下角常驻一只小飞宠，气泡显示令牌余额与今日已用；点击桌宠展开明细面板（余额 / 今日已用（本令牌与全账户两个口径）/ 今日 Token / 最近调用记录），可拖动、右键打开菜单（立即刷新 / 明细面板 / 设置 / 退出程序）。

- **布局**：卡片与气泡水平居中，桌宠固定在右下角，底边位置不变，展开/收起都不跳动。明细卡片按固定行高排版（头部 / 三列数据卡（余额 · 今日已用本令牌 · 今日已用全账户）/ 口径对照行 / Token 条 / 状态行 / 三行调用记录 / 脚注），窗口高度由卡片内容反推，不会再出现内容被裁掉或行距错乱。
- **像素级点击遮罩**：悬浮窗尺寸恒定为最大形态，但可交互区由**实际渲染像素**决定（抓帧后按 alpha 游程生成系统窗口区域，`SetWindowRgn`）。遮罩之外的透明区域对系统等于不存在：不挡桌面点击、不参与合成。因此 pet 形态下只有右下角桌宠本体那一小块可点，卡片与桌宠之间的空白不再挡住桌面操作。抓帧/计算在后台线程，形态切换与姿势帧（瞌睡 / 挥手）变化后自动重算；抓帧失败一律回退整宽矩形，桌宠绝不会点不到。
- **寿命跟随主窗口**：桌宠属于主界面的一部分，主窗口隐藏（关闭到系统托盘）时桌宠一并隐藏，主窗口再次出现时按开关自动恢复；关掉开关后不会被主窗口显隐"复活"。
- **两种余额口径**：new-api 的 `/api/usage/token/` 只反映**这把令牌自己**的额度上限 —— 令牌勾了「无限额度」时它恒为 `∞`，跟钱包里还剩多少钱无关。要看**账户钱包余额**，桌宠改走 OpenAI 兼容的 `/v1/dashboard/billing/subscription` 与 `/usage`（差值即余额）。设置窗口「余额口径」三选一：`自动`（令牌无限额度时自动改用账户余额）/ `令牌额度` / `账户余额`；明细卡会把两套数字同时摊开，不藏任何一个。
  - 前提：站点必须关闭系统设置里的「显示 Token 统计信息」（`DisplayTokenStatEnabled`）。该开关为 `true` 时 billing 只返回令牌口径、且无限额度令牌会被写成假的 `100000000`，此时桌宠显示「账户余额未就绪」而不是乱码数字。
  - billing 返回的是**站点展示口径**的金额（USD / CNY / TOKENS 由站点决定），桌宠先按站点自己的 `quota_per_unit` / `usd_exchange_rate` / `custom_currency_exchange_rate`（取自公开的 `/api/status`）还原成原始额度，再按本地配置换算，避免重复乘汇率。
  - 账户余额变化慢，单独用 `account_poll_interval_seconds`（默认 300s）低频轮询，不占用令牌的 60s 轮询配额。
- **数字简写**：Token 与额度大数一律简写 —— `K` 千、`M` 百万、`B` 十亿，例如今日输入 `1,159,134,252` 显示为 **1.16B**、`54,818` 显示为 **54.8K**；卡片里超过一千的金额也简写成 `-¥48.15M` 这种形式，避免被宽度省略掉数量级；小额仍保留两位小数。负数一律写成 `-¥48.15M`（符号在货币符号前）。

数据只凭 API Key 轮询 new-api 的只读接口（无需登录，令牌耗尽 / 过期 / 禁用也能查余额）：

- `GET {base}/api/usage/token/` —— 令牌的总额度 / 已用 / 剩余。**只有终身累计值**，没有按天参数。
- `GET {base}/api/log/token` —— 该令牌最近 1000 条日志，用于「今日次数 / 今日 Token / 最近调用」与明细列表。该接口**只回最近 1000 条且无任何分页/时间参数**（`p` / `page_size` / `limit` / `type` / `start_timestamp` 全部被忽略，实测于 api.relyx.cc），单日超过 1000 次时窗口会滑掉更早的记录；桌宠把每轮窗口按稳定唯一键 `request_id` 增量并入本地缓存（`%LOCALAPPDATA%/ConfigPilot/pet_logs.json`，重启不丢）来覆盖全天。响应里的 `id` 是每次请求重排的相对序号，不能作去重键。
- **今日已用 = 远程累计值的零点差值**（`backend/daily_usage.py`）：站点没有任何一条「只用 API Key 就能返回当天」的接口（按天的 `/api/data/self`、`/api/log/self` 要登录态，拿 Key 访问 401），所以金额按 `当前累计值 − 今日零点累计值` 算，零点基线存 `%LOCALAPPDATA%/ConfigPilot/pet_daily.json`。两个口径并排给出：本令牌用 `total_used`，**全账户**（该账户下所有令牌合计）用 `/v1/dashboard/billing/usage` 还原出的终身已用。基线来源决定前缀：日志窗口能证明覆盖到今日零点时反推出精确基线（不加前缀）；跨零点沿用昨日最后一次采样会含零点前尾段，标 `≈`；当天第一次采样才锚上基线则零点到现在这段看不见，标 `≥`。日志窗口合计始终作为下限参与取大，所以限流冻结、进程重启、超 1000 次/天都不会让数字变小或钉死不动。
- `GET {base}/v1/dashboard/billing/{subscription,usage}` —— 账户钱包余额（走严格 `TokenAuth`，令牌被禁用/过期会 401，此时只影响该口径）
- `GET {base}/api/status` —— 公开接口，读站点的额度展示口径与换算参数

**凭证来源（默认自动复用，无需重复填 Key）**：桌宠默认 `source=auto`，直接复用你在 ConfigPilot 里已经配好的连接——优先用 **Codex 当前配置**（`config.toml` 的 `base_url` + `auth.json`/环境变量的 key），其次 **Claude Desktop Gateway**（endpoint + `inferenceGatewayApiKey`）；把推理端点自动归一化回站点根再查询。也可在设置窗口顶部切到指定来源或「手动」填写。凭证读取在后台线程完成，不阻塞界面。

**启用方式**：

1. **应用内开关（推荐）**：打开 ConfigPilot → 左侧「设置」页 → 「余额监控桌宠」分组 → 打开「显示余额桌宠」开关即可（已配 Codex/Claude 的话直接就能看余额）；点「打开设置」可切换来源、改轮询间隔与金额换算。开关状态持久化，下次启动自动恢复；桌宠右键「退出程序」退出整个应用（独立入口即桌宠进程），**不会**改动开关，同一进程内再打开开关可复用同一窗口。想只关掉桌宠，用设置页的开关。
2. **配置文件**：`%LOCALAPPDATA%\ConfigPilot\pet_config.json`（`source` 默认 `auto`）：

```json
{
  "source": "auto",
  "poll_interval_seconds": 120,
  "currency": "auto",
  "balance_source": "auto",
  "account_poll_interval_seconds": 300,
  "log_poll_interval_seconds": 180
}
```

手动模式才需要 `base_url` / `api_key`；也可用环境变量 `CONFIGPILOT_NEWAPI_BASE` / `CONFIGPILOT_NEWAPI_KEY` 覆盖。只想单独跑桌宠、不打开主窗口：`python pet_main.py`（同样自动复用 Codex/Claude 配置）。

> **限流友好**：new-api 的 `CriticalRateLimit` 是每 IP 每路由 20 次 / 20 分钟（约 1 次/分钟）。三条路由各自计配额，桌宠因此分开限频：令牌累计按 `poll_interval_seconds`（默认 120s），日志窗口按 `log_poll_interval_seconds`（默认 180s，60s 会正好顶在 20 次/20 分钟的死线上），账户余额按 `account_poll_interval_seconds`（默认 300s）。单飞不叠加请求；收到 429/503 按 `Retry-After` 退避，**且只退避出问题的那条路由** —— 日志被限流时金额照旧每轮更新（旧实现一次失败就丢整轮回包，表现为「数字半天不动」）。右键「立即刷新」会强制带一次日志窗口。

> 金额换算说明：new-api 的额度是整数计分，默认 `500000 = $1`（`QuotaPerUnit`）。`currency` 可选 **`auto`（默认，跟随站点）** / `CNY` / `USD` / `TOKENS`：站点在「系统设置 → 计费与支付 → 货币与展示」里选的是哪种展示口径，桌宠就出哪种（站点显示 `$` 就不会被擅自换算成 `¥`）；跟随模式下连 `quota_per_unit` 与汇率都取站点自己的值（来自公开的 `/api/status`）。显式写 `CNY` / `USD` 时才用本地 `quota_per_unit` / `cny_rate`。「今日已用」按本机时区零点起算：金额取远程终身累计值的零点差值（本令牌与全账户各一个，见上），次数与 Token 取消费日志（`type=2`）；累计差值与日志窗口合计互为下限，所以超过 1000 次/天也不会「越用越少」，仅在观测有洞时以 `≥`（偏低）或 `≈`（含零点前尾段）标注。

## 配置 providers.json

可选中转预置列表。`name` 是说明名称，其余字段对应写入 `config.toml`：

```json
{
  "presets": [
    {
      "name": "https://api.example.com",
      "baseUrl": "https://api.example.com/v1",
      "provider": "relay",
      "wireApi": "responses",
      "model": "gpt-5.5"
    }
  ]
}
```

## 目录结构

```
configpilot/
├── main.py                  入口:注册后端 / svg 图标 provider
├── pet_main.py              独立桌宠入口(不打开主窗口)
├── backend/
│   ├── codex_config.py      配置读写 + 获取模型(后台线程)
│   ├── claude_desktop_config.py  Developer Mode + 第三方推理配置
│   ├── model_profiles.py    模型规则加载与校验
│   ├── newapi_pet.py        余额桌宠控制器(轮询 new-api 只读接口)
│   ├── pet_config.py        桌宠配置加载/保存/校验
│   ├── pet_manager.py       桌宠开关与悬浮窗生命周期
│   ├── pet_sources.py       复用 Codex/Claude 已配置的接口与 Key
│   └── quota_math.py        额度换算与今日用量统计
├── qml/
│   ├── main.qml             窗口 + 导航 + 启动屏 + 图标
│   ├── pet/
│   │   ├── PetWindow.qml    余额桌宠悬浮窗(生命周期 / 位置 / 数据注入)
│   │   ├── PetPanel.qml     悬浮面板本体(明细卡片 / 气泡 / 桌宠 / 右键菜单)
│   │   ├── PetSprite.qml    桌宠本体(自定义图片或内置矢量形象)
│   │   ├── PetStatCard.qml  明细卡里的额度小卡
│   │   ├── PetLogRow.qml    最近调用行(时间 / 模型 / Token / 金额)
│   │   ├── PetChipButton.qml 明细卡头部的胶囊按钮
│   │   └── PetSettingsDialog.qml  桌宠设置窗口
│   └── views/
│       ├── CodexView.qml    Codex 配置页
│       ├── ClaudeDesktopView.qml  Claude Desktop Subpage
│       ├── AboutView.qml    帮助页
│       └── ReasoningEffortSelector.qml  思考等级选择器
├── resources/               程序图标 (svg/ico)
├── providers.json           中转预置列表
├── model_profiles.json      模型思考等级与上下文预设
├── requirements.txt         运行依赖
├── build_nuitka.cmd         Nuitka 打包脚本
├── ConfigPilot.iss          Inno Setup 安装脚本
└── run.cmd                  开发期快速启动
```

## 许可证

[MIT](LICENSE) © 2026 aki-riko

基于 [PrismQML](https://pypi.org/project/prismqml/)（MIT）构建。
