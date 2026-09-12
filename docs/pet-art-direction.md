# 桌宠立绘美术方向（Q版二次元）

## 目标

内置矢量"小飞宠"是一个圆角矩形 + 两根天线的抽象形体，缩到 120px 后没有角色辨识度。
目标换成 **DeepSeek Harness 桌宠那一档的 Q 版二次元人物**：二头身、粗等宽描线、平涂、
大眼高光、贴纸感轮廓。同时要求 **不与"鲸鱼娘"重复元素**。

## 鲸鱼娘元素排除清单（生成提示词里的 `strictly avoid`）

| 元素 | 说明 |
| --- | --- |
| 女仆头饰 / 荷叶边发带 / 猫耳发箍 | 鲸鱼娘头顶那圈白色褶边 |
| 蓝色系头发 | 蓝、长春花蓝、银蓝、淡紫都在禁用范围 |
| 鲸鱼 / 海豚 / 鱼 / 鳍 / 尾巴 / 鳃 / 海浪 / 船锚 | 海洋母题整体禁用 |
| 水手领 / 深蓝领结 / 领口菱形宝石 | 鲸鱼娘颈部三件套 |
| 半垂的困倦眼 | 鲸鱼娘的表情基调 |
| 蓝紫整体配色 | 避免与鲸鱼娘撞色 |

## 三个候选概念（`scripts/generate_pet_art.py --list-styles`）

| id | 名字 | 识别点 | 配色 |
| --- | --- | --- | --- |
| `navigator` | 小领航 · 阿诺 | 飞行帽 + 短斗篷 + 罗盘与钥匙挂件 + 抱一枚金币（呼应"余额"） | 杏橙 / 奶油白 / 水鸭蓝绿 / 黄铜金 |
| `barista` | 小焙 · 玛琪 | 贝雷帽 + 围裙 + 拿铁与币形饼干 + 小铜秤 | 焦糖 / 奶油 / 铁锈红 / 橄榄绿 |
| `archivist` | 小档 · 璃 | 圆框眼镜 +  oversized 毛衣 + 账本与火漆印 | 玫瑰粉 / 奶油 / 鼠尾草绿 / 金 |

三者都是暖色主导 + 一个冷色点缀，与鲸鱼娘的冷蓝单色系天然拉开距离；
`navigator` 与产品名 ConfigPilot 同义，优先推荐。

## 提示词组装

`scripts/generate_pet_art.py` 里分三段常量，改风格只动常量：

1. `STYLES[id]["brief"]`：角色形体与配色（英文，模型对英文响应更稳）。
2. `STYLE_CORE`：画风与出图约束 —— 二头身、粗描线、平涂、透明底、居中、
   无文字水印、轮廓在 120px 下仍可读。
3. `AVOID`：上面的排除清单（gpt-image 系没有独立 negative 参数，写进正文）。

## 出图后处理（同一脚本，只用项目已有的 PySide6，不新增依赖）

接口返回 → `QImage` 解码 → 判断"是否真有透明像素"（只看 `hasAlphaChannel()` 会被
"带 alpha 但全不透明"的 PNG 骗过，这里逐像素取 alpha 最小值）→ 纯色背景时四边洪水填充
抠底 + 贴边像素半透明羽化（缩到 120px 不留白边锯齿）→ alpha 包围盒裁边 → 补方留白 6% →
缩到 512×512 → 存 PNG，并额外叠一张浅底/深底对比预览图判断可读性。

参数兼容：不同中转站对 `background` / `output_format` / `quality` / `response_format`
支持不一，脚本按宽容度逐级降级重试；`data[0]` 同时支持 `b64_json` 与 `url`。

## 操作

```powershell
# 密钥与地址只走环境变量，不写进代码或仓库
$env:RELYX_API_BASE = "https://api.relyx.cc/v1"
$env:RELYX_API_KEY  = "<可用的 sk-...>"

.venv\Scripts\python.exe scripts\generate_pet_art.py --ping          # 先验密钥
.venv\Scripts\python.exe scripts\generate_pet_art.py --style all     # 三概念对比
.venv\Scripts\python.exe scripts\generate_pet_art.py --style navigator `
    --models gpt-image-2,gpt-image-2.5,gpt-image-2.5-flare,gpt-image-2.5-sunburst   # 四模型对比
.venv\Scripts\python.exe scripts\generate_pet_art.py --install .artifacts\pet\navigator__gpt-image-2.5__01.png --pet-name navigator
```

产物在 `.artifacts/pet/`：`<style>__<model>__NN.png`（定稿尺寸）+ `_preview.png`（深浅底对比）。
`--install` 把图放进 `resources/pet/<name>.png`，并把绝对路径写进
`%LOCALAPPDATA%\ConfigPilot\pet_config.json` 的 `pet_image`，桌宠下一次刷新即生效
（`PetSprite.qml` 的 `imagePath` 通道）。加 `--no-config` 只放文件不改配置。

离线自检（不联网、不需要密钥）：

```powershell
.venv\Scripts\python.exe scripts\generate_pet_art.py --self-test
```

## 后续（定稿形象选定后）

把 `resources/pet/` 里的立绘做成设置窗"桌宠外观"里的内置形象候选（Chips 选择 + 仍保留
自定义路径），替掉现在只能填绝对路径的单一输入框；这一步需要改
`qml/pet/PetSettingsDialog.qml` 与 `backend/newapi_pet.py`，等图定稿再做，避免返工。
