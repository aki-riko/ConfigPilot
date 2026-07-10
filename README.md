# ConfigPilot

**AI 工具配置与自动化中心。**

ConfigPilot 是一个用 [PrismQML](https://pypi.org/project/prismqml/) 构建的桌面工具。当前版本首先适配 OpenAI Codex CLI，用来管理 `~/.codex/config.toml`：在多个 API 中转之间切换、填写 API key、获取模型列表，免去手动编辑 TOML/JSON。

![ConfigPilot 主界面](docs/images/configpilot-main.png)

- **下载**：[GitHub Releases](../../releases)
- **适合**：需要频繁切换 Codex CLI provider、模型和高级配置，但不想手动编辑 TOML/JSON 的用户。

## 功能

- **API 连接配置**：直接填写任意 `base_url`、provider、wire API 和模型
- **高级选项**（都是 Codex 原生 `config.toml` 字段）：
  - `requires_openai_auth` —— 供应商用 Chat Completions 协议或非 GPT 模型时开启
  - `model_reasoning_effort` —— 选择模型时默认使用其支持的最高档；GPT-5.6 显示六档中文等级
  - `disable_response_storage` —— 禁用响应存储
- **模型上下文预设**：GPT-5.5 使用 `258400 / 245000`，GPT-5.6 使用 `372000 / 353000`
- **响应式界面**：连接、模型、上下文和兼容性分区展示，窄窗口自动切换为单列
- **获取模型**：请求中转的 `/v1/models`，结果填入 model 下拉（后台线程，不卡界面）
- **API key**：写入 `~/.codex/auth.json`
- **安全**：每次写入前自动备份 `config.toml.bak` / `auth.json.bak`，保留 `notify` 等其它原有配置不动
- **常驻操作栏**：随时查看未应用状态，并可重新读取或应用配置

## 安装使用（终端用户）

下载 [Releases](../../releases) 里的 `ConfigPilot_Setup_x.x.x.exe`，双击安装即可。无需 Python，VC++ 运行库已内置。

## 从源码运行（开发者）

需要 Python 3.11+（用到 `tomllib`）。

```bash
git clone https://github.com/aki-riko/configpilot.git
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

## 配置 providers.json

默认中转列表，供“重置为默认”使用。`name` 是说明名称，其余字段对应写入 `config.toml`：

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
├── backend/
│   ├── codex_config.py      配置读写 + 获取模型(后台线程)
│   └── model_profiles.py    模型规则加载与校验
├── qml/
│   ├── main.qml             窗口 + 导航 + 启动屏 + 图标
│   └── views/
│       ├── CodexView.qml    配置页
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
