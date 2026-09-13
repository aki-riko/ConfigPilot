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
`--install` 把图放进 `resources/pet/<name>.png`；默认还会把该绝对路径写进本机
`%LOCALAPPDATA%\ConfigPilot\pet_config.json` 的 `pet_image`，桌宠立刻换装。
**发布内置形象时加 `--no-config`**：留空配置就走清单 `default`，不该把某台机器的绝对路径
写进用户配置。新增内置形象要在 `resources/pet/presets.json` 补一条 `{id, label, file}`。

离线自检（不联网、不需要密钥）：

```powershell
.venv\Scripts\python.exe scripts\generate_pet_art.py --self-test
```

## 姿势帧与动画

静态立绘哪怕再好看，放在桌面上也只是"贴纸"。所以定稿形象另外出了一组姿势帧，
由 `qml/pet/PetSprite.qml` 的状态机驱动：

| 角色 | 触发条件 | 表现 |
| --- | --- | --- |
| `idle` | 基准 | 抱金币站立 |
| `blink` | 空闲时每 3.2~5.8s 随机插播 220ms | 闭眼，把"贴纸"变成活的 |
| `wave` | 左键点击 / 从打瞌睡里被叫醒 | 抬手挥动 |
| `cheer` | 余额变动（`usageBumped` → `bounce()`） | 双手举金币 + 闪光 |
| `sleepy` | 90s 无任何交互 | 闭眼歪头 + zzz |
| `alert` | 余额耗尽 / 请求失败（优先级最高） | 抱一个空钱袋 + 担忧脸 + 红色角标 |

配套的程序化补间（不依赖素材，单图形象同样生效）：上下浮动、±2.2° 缓慢左右摇摆、
以脚底为原点的挤压拉伸（压扁 → 拉长 → 回弹）、拖动时按横向速度前倾、松手回正。
姿势之间用**两层交叉淡入 100ms** 而不是硬切：生图各帧不可能逐像素对齐，硬切会看到"跳"。

### 姿势帧怎么来的

不重新描述角色，而是拿定稿立绘走 `/images/edits`（multipart，`image=<定稿图>`）：
同一张参考图只改动作，五官/发色/服饰/线宽/上色才不逐帧漂移。
实测六个角色的帽徽、辫子、斗篷青边、腰带罗盘与钥匙、靴子全部一致。

```powershell
$env:RELYX_API_BASE = "https://api.relyx.cc/v1"; $env:RELYX_API_KEY = "<sk-...>"
# 出一整套姿势帧(以 resources/pet/navigator/idle.png 为参考)
.venv\Scripts\python.exe scripts\generate_pet_art.py --poses all --style navigator `
    --models gpt-image-2.5-flare --keep-raw
# 只调对齐参数时用已存的 __raw.png 重排,不花额度
.venv\Scripts\python.exe scripts\generate_pet_art.py --poses all --align-only --keep-raw `
    --from-file .artifacts\pet\frames\navigator\idle__raw.png `
    --frames-out .artifacts\pet\frames\navigator
```

### 对齐规则（两个真实的坑）

1. **每帧各自按 alpha 包围盒高度归一**，不能共用同一个缩放系数：idle 参考图可能是上一轮
   已缩到 512 的成品，姿势帧是 1024 原图，跨分辨率比包围盒绝对值没有意义。第一版按
   anchor 帧算统一比例再夹 ±12%，结果后 5 帧被放大到裁切（只剩躯干）。实测同一参考图
   出来的各帧"角色占画面比例"都在 90% 上下，各自归一后彼此不跳。
2. **横向按脚部像素质心对齐**，不是包围盒中心：挥手 / 举金币会让包围盒朝一侧偏，
   按中心对齐角色会左右抖，脚才是站立的支点。脚底则统一压到同一基线。

`--self-test` 里有对应断言：三张不同分辨率、不同包围盒高度（含头顶多一截道具）的合成帧，
输出必须身高一致且压在同一基线上。

## 已落地的接线

立绘随程序发布在 `resources/pet/`（Nuitka 的 `--include-data-dir=resources=resources`
与 Inno 的 `main.dist\*` 递归拷贝都会带上），用户配置里只存一个短令牌：

| `pet_image` 取值 | 生效形象 |
| --- | --- |
| `""`（留空） | `resources/pet/presets.json` 里 `default` 指向的立绘，当前是 `preset:navigator`（带六帧动画） |
| `preset:<id>` | 指定某个内置立绘（`navigator` 带动画；`barista` / `archivist` 目前是单图） |
| `vector` | 老的自绘矢量小飞宠，仍然保留、仍然可选 |
| `D:\pics\pet.png` | 用户自备图片（原行为，完全兼容） |

姿势帧在清单里是 `frames: {角色: 相对路径}`；**不写 frames 也能动** —— 约定
`resources/pet/<id>/<角色名>.png` 会自动发现，缺某个角色或整个 frames 为空时
桌宠逐级退回 `idle` → 主立绘 → 自绘形体，不会出现空白隐身。

- `backend/pet_art.py`：令牌 ↔ 绝对路径的唯一解析处（清单缺失时退化为扫描目录；
  id 过白名单正则，`file` 字段过 `basename`，不能穿越出立绘目录）。
- `backend/newapi_pet.py`：新增 `petImageSource` / `petImagePresets` /
  `defaultPetImageToken` 三个只读属性与 `resolvePetImage(token)` 槽。
- `qml/pet/PetPanel.qml`：`PetSprite.imagePath` 改吃 `petImageSource`，并且不再挂
  `panel.ready` —— 立绘与凭证就绪无关，挂上会让桌宠启动瞬间先闪一下自绘形体。
- `qml/pet/PetSettingsDialog.qml`：「桌宠外观」卡片加了 64px 实时预览 + 内置形象芯片行，
  点芯片只是把令牌写回原来的路径框，路径框仍是唯一提交值。

验证：`tests/test_pet_art.py`（令牌与姿势帧解析 13 例）与 `tests/test_pet_ui.py`
（`test_built_in_pet_art_reaches_sprite_and_chips` 串起"配置 → 解析 → QML 绑定"整条链；
`test_pose_state_machine_priority_and_fallback` 锁住姿势优先级与降级路径），
另外离屏抓真实 `PetWindow` 窗口确认立绘与每种姿势都真的画进了悬浮窗。

## 定稿记录

- 主形象 `navigator`（小领航 · 阿诺）：杏橙发 / 金青瞳 / 奶油飞行帽 / 抱一枚刻星金币，
  腰上挂罗盘与钥匙 —— 与 ConfigPilot 的"领航 + 余额"语义对齐。
- 四个模型都出过同一概念：`gpt-image-2.5-flare` 头身比最夸张、轮廓最干净，120px 下最耐看，
  定为发布版本；`gpt-image-2` 描线最精致但靴带、皮带扣这类细节在 120px 会糊。
- `barista`、`archivist` 也各出一版并作为可选内置形象一起发布，风格统一走 flare。

