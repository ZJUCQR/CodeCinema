<h1 align="center">CodeCinema</h1>

<p align="center">
  <a href="README.md">English</a> · <strong>简体中文</strong>
</p>

<p align="center">
  <a href="https://zjucqr.github.io/CodeCinema/zh/#films">
    <img src="assets/images/banner.jpg" width="100%" alt="CodeCinema 影片制作框架：让故事动起来，从画面与声音到最终成片">
  </a>
</p>

<p align="center">
  <a href="https://github.com/ZJUCQR/CodeCinema/actions/workflows/ci.yml"><img src="https://github.com/ZJUCQR/CodeCinema/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2ea44f.svg" alt="License: MIT"></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&amp;logoColor=white" alt="Python 3.12+"></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&amp;logoColor=white" alt="FFmpeg required"></a>
  <a href="#blender"><img src="https://img.shields.io/badge/Blender-optional-ea7600?logo=blender&amp;logoColor=white" alt="Blender optional"></a>
</p>

<p align="center">
  <a href="https://zjucqr.github.io/CodeCinema/zh/"><strong>项目主页</strong></a> ·
  <a href="#quick-start"><strong>快速开始</strong></a> ·
  <a href="#framework">框架指南</a>
</p>

---

CodeCinema 是可扩展的开源影片制作框架，用代码让故事动起来，将画面、配乐和音效组合成完整影片。可以在本地可视化编辑器中选模板并定制，也可以接入自己的渲染器与制作流程。每部影片在 `films/` 下有独立目录，配置统一放在根目录 `pyproject.toml`。框架提供：

- **设置**：每部影片一套分层设置，支持本地覆盖和环境变量，并能自动查找工具和字体。
- **声音**：共享的音频工具包，包括合成、物理建模、混响、真峰值限制和响度处理。
- **合成**：ffmpeg 辅助工具，负责探测、编码、拼接和混流。
- **命令行**：一个 CLI，可以列出影片、运行影片的步骤，以及创建新影片。

通过 Studio，可以从模板直接制作 MP4。示例影片展示了如何接入自定义渲染器、声音与后期流程。

## ✨ 亮点

- 🪄 **选模板、改内容、点一下出片**：本地 Studio 提供八种动态场景、可编辑分镜、标题、字幕、颜色、横竖屏与方形画幅，一次点击生成 MP4，无需 API Key。
- 🧩 **约定很小，渲染器随意**：影片在 `pyproject.toml` 里声明自己的步骤，`codecinema run <影片> <步骤>` 会用这部影片的设置来运行它。Blender、2D 矢量绘图、着色器，任何能输出画面帧的方式都可以。
- 🎼 **共享的声音工具包**：影片配乐背后的 DSP 库就是框架的一部分，包括振荡器、拨弦和模态物理模型、卷积混响、真峰值限制器和响度工具。
- 🎙️ **可选情绪配音**：在 Studio 逐镜头填写台词和表演提示，也可使用自己的录音。[语音教程](#speech)介绍本地语音包与可复用的口型时间接口。
- ♻️ **可复现，可配置**：渲染结果确定，并行任务可断点续跑。分层设置无需改动受版本管理的文件。辅助工具支持 macOS、Linux 和 Windows。


<a id="quick-start"></a>

## 🚀 快速开始

需要 **Python 3.12+、Git 和 FFmpeg**（含 `ffprobe`）。先克隆仓库，然后展开对应系统的安装命令：

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git
cd CodeCinema
```

<details>
<summary>macOS</summary>

使用 [Homebrew](https://brew.sh/) 安装工具并创建环境：

```bash
brew install python@3.12 ffmpeg
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

</details>

<details>
<summary>Linux · Ubuntu 24.04</summary>

```bash
sudo apt-get install python3-venv ffmpeg fonts-dejavu-core libgl1 libegl1 libfontconfig1
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

</details>

<details>
<summary>Windows · PowerShell</summary>

先安装 [Python 3.12+](https://www.python.org/downloads/)，然后运行：

```powershell
winget install Gyan.FFmpeg
# 安装后重新打开 PowerShell，再回到 CodeCinema 目录。
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m codecinema studio
```

</details>

这些命令直接使用虚拟环境，无需激活。Windows 使用更新的 Python 时，将 `-3.12` 替换为对应版本。Studio 自动打开 **http://127.0.0.1:8787/**。使用期间保持终端运行，按 `Ctrl+C` 退出。

1. **选场景**：点击喜欢的缩略图。
2. **改内容**：填写影片 ID、标题和字幕，选择时长与画幅。默认三个镜头、12 秒、720p。
3. **生成影片**：点击“生成我的影片”，完成后直接观看或下载 MP4。

成片：**`films/<id>/assets/film/<id>.mp4`**。

![Eight starter looks](assets/images/starters.jpg)

后续命令示例请先激活环境：macOS/Linux 使用 `source .venv/bin/activate`，Windows PowerShell 使用 `.\.venv\Scripts\Activate.ps1`。也可以继续使用上面的虚拟环境 Python 路径加 `-m codecinema`。

## 🎞 示例影片

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <a href="films/silvergrass/README.zh-CN.md"><img src="assets/images/examples/silvergrass.jpg" width="100%" alt="芒原决战"></a>
      <h3><a href="films/silvergrass/README.zh-CN.md">芒原决战</a></h3>
      <p>落日芒草原上，无主之忍对决年迈的剑豪，分为剑、焰、雷三幕。</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/zh/#silvergrass">观看</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/film">下载</a> · <a href="films/silvergrass/README.zh-CN.md">制作指南</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="films/nightrevels/README.zh-CN.md"><img src="assets/images/examples/nightrevels.jpg" width="100%" alt="韩熙载夜宴图 · 猫"></a>
      <h3><a href="films/nightrevels/README.zh-CN.md">韩熙载夜宴图 · 猫</a></h3>
      <p>一场画在绢上的夜宴，每位宾客都是猫，还有一只小猫画师在偷偷作画。</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/zh/#nightrevels">观看</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/nightrevels">下载</a> · <a href="films/nightrevels/README.zh-CN.md">制作指南</a></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="films/xishen/README.zh-CN.md"><img src="assets/images/examples/xishen.jpg" width="100%" alt="我不是戏神"></a>
      <h3><a href="films/xishen/README.zh-CN.md">我不是戏神</a></h3>
      <p>从陈伶雨夜归家、剧院噩梦到第一次编导演练。</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/zh/#xishen">观看</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/xishen">下载</a> · <a href="films/xishen/README.zh-CN.md">制作指南</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="films/beacon/README.zh-CN.md"><img src="assets/images/examples/beacon.jpg" width="100%" alt="守灯人"></a>
      <h3><a href="films/beacon/README.zh-CN.md">守灯人</a></h3>
      <p>云海上的瓷白机械守灯人唤醒古老星环，远方的一点光给出了回应。</p>
      <p><a href="https://zjucqr.github.io/CodeCinema/zh/#beacon">观看</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/beacon">下载</a> · <a href="films/beacon/README.zh-CN.md">制作指南</a></p>
    </td>
  </tr>
</table>


<a id="customization"></a>

## 🎨 制作自己的影片

```bash
codecinema new myfilm --preset aurora --title "My Film" --render --open
codecinema customize myfilm --preset neon --format portrait --render
codecinema run myfilm all --quality preview
```

在 Studio 的“逐镜头定制”中增删、排序镜头，修改文字、时长、配色和镜头运动。也可以直接编辑 `films/myfilm/scenes.json`。八种风格：`moonrise`、`sunset`、`aurora`、`neon`、`ocean`、`ink`、`cosmos`、`ember`，支持横屏、竖屏和方形画幅。

这些预设生成动态风景标题短片。新人物、动作和故事表演需要[自定义渲染器](#framework)。

<details>
<summary>手动编辑分镜 JSON</summary>

```json
{
  "version": 1,
  "title": "From Night to Morning",
  "seed": 7,
  "scenes": [
    {"preset": "moonrise", "duration_s": 6, "camera": "wide", "title": "A Quiet Night", "subtitle": "One last look at the stars."},
    {"preset": "sunset", "duration_s": 6, "camera": "drift", "title": "Another Horizon", "subtitle": "There is more to come.", "accent": "#ffdfb5"}
  ]
}
```

支持 `wide`、`drift`、`close` 镜头。每镜头至少 0.5 秒，总时长 1.5–600 秒。保存后运行 `codecinema run myfilm all`。文字自动换行，画面与声音使用相同的帧边界。成片通过完整解码检查后才报告成功。

</details>


<a id="framework"></a>

## 🧩 框架开发

<details>
<summary>影片接口、设置和共享模块</summary>

每部影片一个目录，包含入口脚本 `src/run.py`、素材 `assets/` 和自动生成的 `out/`。个人覆盖设置放在 Git 忽略的 `film.local.toml`。

影片配置统一放在根目录 `pyproject.toml` 的 `[tool.codecinema.films.<id>]` 表中，具体参数位于其 `settings` 子表。Studio 和 `codecinema new` 会根据 `[tool.codecinema.starter]` 默认值自动登记新影片。CLI 自动发现影片，设置 `CODECINEMA_FILM_DIR`，在影片目录执行入口脚本。`codecinema list` 查看影片与步骤，`presets` 查看预设，`check` 检查环境，`run <id> <step>` 运行步骤。

设置优先级由低到高：框架默认值 → 根目录 `pyproject.toml` 的 `[tool.codecinema.films.<id>.settings.*]` → 影片目录中的 `film.local.toml`（直接使用 `[video]`、`[audio]` 等表）→ 影片前缀或 `CODECINEMA_*` 环境变量。工具还支持 `BLENDER_BIN`、`FFMPEG`、`FFPROBE`。

| 模块 | 用途 |
| --- | --- |
| `codecinema.settings` | `get()` 取值、`path()` 解析影片相对路径、`tool()` 查找工具、`font()` 查找字体。`ROOT` 为影片根目录 |
| `codecinema.audio.dsp` | 合成、滤波、物理建模、混响、混音、真峰值限制与响度。`SR` 来自影片采样率设置 |
| `codecinema.media` | `probe()`、`encoder()`、`concat()`、`mux()` |
| `codecinema.procutil` | 文件锁、进程管理、内存与文件复制 |
| `codecinema.blender` | 后台启动 Blender、动作曲线与修改器工具 |
| `codecinema.audio.speech` / `performance` | 配音、录音、对齐与口型时间 |
| `codecinema.films` | `discover()` 发现影片，`Film.run()` 执行步骤 |

在生成的 `src/run.py` 中修改 `draw_frame(canvas, frame)` 和 `score()`，即可扩展画面与音乐。`plan`、`stills`、`render`、`audio`、`assemble`、`qc` 分别负责时间线、联系表、画面、声音、合成和质检。`all` 串起整个流程。

Studio 和 `customize` 接受标记为 `[tool.codecinema.films.<id>]` 下的 `template = "starter-v1"` 的项目。独立示例遵循各自的制作指南。预览单独写入 `out/preview/` 和 `<id>_preview.mp4`。分步运行时，画质、画幅、FPS、时长必须一致。签名检查阻止拼接过期素材。

开发时将故事、动作和音效放在同一时间线上，固定随机种子，用可续渲分块减少重复计算。完整接口示例见[英文参考](README.md#framework)。

</details>


<a id="blender"></a>

## 🎬 Blender

<details>
<summary>接入 Blender 渲染器</summary>

安装 [Blender 5.2+](https://www.blender.org/download/)。框架自动查找标准安装目录和 `PATH`。其他位置可设置 `BLENDER_BIN`。

```bash
codecinema run beacon still
codecinema run beacon all
codecinema run silvergrass check
codecinema run silvergrass build
```

[守灯人](films/beacon/README.zh-CN.md)以四个文件演示故事时间线、场景与动作、配乐、渲染和质检。[芒原决战](films/silvergrass/README.zh-CN.md)提供双人骨骼、打斗、布料与毛发参考，其动作模块依赖原影片骨骼和配置，不能直接套用到任意角色。

```python
from codecinema import blender
blender.run("src/build_scene.py", "--quality", "preview")
```

`run()` 在当前影片目录后台执行 Blender。`command()` 返回命令参数供自定义进程管理使用。`fcurves_of()`、`channelbag_of()` 支持 Blender 5 的动作槽。`muted_modifiers()` 临时关闭视口修改器，并在异常后恢复。`Performance.mouth()` 可驱动 Blender 角色口型。使用与最终声音一致的镜头时间和起始偏移。更多示例见[英文参考](README.md#blender)。

</details>


<a id="speech"></a>

## 🎙️ 配音与口型

<details>
<summary>情绪配音、录音与角色口型</summary>

八种模板都支持逐镜头配音。台词留空时仍生成配乐版，不需要语音模型。

### 在 Studio 里操作

1. 运行 `codecinema studio`，展开“逐个定制分镜”。
2. 展开“添加配音”，填写短台词，选择声音和语言，描述情绪，例如“温柔而好奇”“紧张但克制”“一边观察一边思考”。
3. 给镜头留足时长，点击“生成我的影片”。也可先用“快速预览”试听。

Apple Silicon Mac 首次安装情绪语音包：

```bash
python -m pip install -e ".[speech]"
codecinema studio
```

第一次配音会下载 Qwen3-TTS CustomVoice，之后复用缓存。无需 API key。普通框架和无配音模板不会下载或载入模型。未安装语音包的 Mac 可使用系统声音，但系统声音不支持情绪提示。本地情绪模型目前要求 Apple Silicon。

中文声线可选 Serena、Vivian、Dylan、Uncle Fu 和 Eric。英文可选 Ryan、Aiden。日语、韩语可选 Ono Anna、Sohee。模型也支持跨语言配音。较长项目请先试听。

### 修改镜头数据

在 `scenes.json` 的某个镜头里添加：

```json
"narration": {
  "text": "天空也有故事要讲。",
  "voice": "Serena",
  "language": "Chinese",
  "direction": "温柔、有好奇心，像在给朋友讲故事，避免播音腔。"
}
```

将该镜头的 `duration_s` 设为合适的时长，然后运行：

```bash
codecinema run myfilm all --speech-engine local
```

声音超出镜头时会提示所需时长，不会截断台词。说话期间会自动压低配乐。修改台词、声音、语言或情绪会生成新的配音缓存。

任何平台都可以使用自己的录音：把单声道 WAV 放进 `films/myfilm/assets/voices/arrival.wav`，在上述对象增加 `"recording": "arrival.wav"`，使用 `--speech-engine recording` 生成。每个有台词的镜头都要提供录音。`system` 指定 Mac 系统声音，`auto` 优先使用已安装的本地情绪模型。

添加配音时，已识别的旧版原始模板会自动升级，并将原渲染器与镜头数据一同备份到 `out/edits/`。自定义代码会保留。若还不支持配音，会显示明确提示，避免台词被悄悄忽略。可以新建模板后复制镜头数据，或把新的配音功能合入自己的渲染器。

### 自定义人物口型

公共模块 `codecinema.audio.speech` 提供配音、录音转换与中文逐字对齐。`codecinema.audio.performance` 提供可保存为 JSON 的表演时间表。

先完成声音的剪裁和时间调整，再对最终波形做对齐，随后释放语音模型、开始画面渲染。人物嘴形由真实音节和音量共同驱动，停顿时闭嘴。旁白与内心独白不指定画面中的说话人物。其他语言可以提供相同 `{text, start, end}` 格式的外部对齐时间戳。没有逐字时间戳的录音也可使用音量开合，但语音形状精度较低。

完整接口示例见[英文指南](README.md#speech)，完整制作示例见[开篇三集](films/xishen/README.zh-CN.md)。

</details>


<a id="troubleshooting"></a>

## 🔧 常见问题

<details>
<summary>展开查看解决方法</summary>

| 情况 | 解决方法 |
| --- | --- |
| 找不到 `codecinema` 命令 | 直接使用上面的虚拟环境 Python 路径，加 `-m codecinema` |
| 缺少 Python 包 | 用启动 Studio 的同一虚拟环境重新执行安装命令 |
| 找不到 FFmpeg / `ffprobe` | 安装 FFmpeg。Windows 重开终端后再检查 |
| Linux 无法加载 Skia 图形库 | 用包管理器安装 `libgl1`、`libegl1` 和 `libfontconfig1`，Studio 会显示具体加载错误 |
| 中文无法显示 | 安装 Noto Sans CJK（Ubuntu 用 `fonts-noto-cjk`），或在影片 `film.local.toml` 写 `[fonts]` 和 `ui = "/字体文件路径/font.ttf"` |
| 影片 ID 已存在 | 换一个 ID。或从“我的影片”打开原作品，命令行用 `customize` |
| 端口被占用 | 启动时加 `studio --port 8788` |
| 合成提示设置不一致 | 直接运行 `all`。分步制作需使用相同的画质、画幅、时长和帧率 |
| 想撤回修改 | 从 `out/edits/<时间戳>/` 恢复 `scenes.json`，将备份 `pyproject.toml` 中仅属于这部影片的配置表恢复到根配置，再生成一次 |

</details>


<a id="publishing"></a>

## 📦 发布

<details>
<summary>GitHub Release 与项目主页</summary>

每部示例对应一个平行 Release，只上传最终 MP4，不上传校验文件、预览、帧或诊断报告。保持文件名稳定。未变化的影片无需重新上传。发布标签应指向成片实际使用的源码版本。

| 标签 | 成片 |
| --- | --- |
| `film` | `SilverGrass.mp4` |
| `nightrevels` | `NightRevels.mp4` |
| `beacon` | `TheLastBeacon.mp4` |
| `xishen` | `ep01.mp4`、`ep02.mp4`、`ep03.mp4`、`xishen_complete.mp4` |

先完成渲染和影片质检，再推送源码、海报和页面。用 `gh release upload <tag> <MP4路径> --clobber` 更新有变化的成片。所有影片的发布说明统一在 GitHub Release 页面编辑。

素材上传完成后执行 `gh workflow run pages.yml --ref main`。替换附件不会触发新版本发布事件。网站构建器只下载声明的成片，验证大小和摘要，用附件 ID 更新缓存。素材不完整时保留线上旧站。

```bash
python3 site/build.py
python3 -m http.server 8080 --directory out/site
```

自定义输出目录必须为空或包含之前的网站构建标记。不允许覆盖仓库源文件夹。完整发布示例见[英文参考](README.md#publishing)。

</details>

## 🗂 项目结构

`codecinema/` 提供共享工具。`films/` 下每个文件夹是一部独立影片，包含自己的故事、渲染代码和制作素材。

```text
CodeCinema/
├── codecinema/             # 共享影片制作框架
│   ├── cli.py              # 命令入口与工具链检查
│   ├── studio.py           # 本地编辑器与制作任务
│   ├── studio_assets/      # 编辑器界面与预设缩略图
│   ├── projects.py         # 项目创建、修改与备份
│   ├── starters.py         # 预设选项与分镜数据校验
│   ├── template/           # 创建新影片时复制的模板源文件
│   ├── films.py            # 发现影片并执行制作步骤
│   ├── registry.py         # 工作区影片配置管理
│   ├── settings.py         # 配置、工具与字体查找
│   ├── blender.py          # Blender 启动与共享工具
│   ├── media.py            # FFmpeg 编码与成片合成
│   ├── audio/              # 音频合成、配音与口型时间
│   ├── procutil.py         # 进程、锁与内存工具
│   └── diagnostics.py      # 依赖检查与安装提示
├── films/                  # 各自独立的影片项目
│   ├── silvergrass/        # 《芒原决战》
│   ├── nightrevels/        # 《韩熙载夜宴图 · 猫》
│   ├── xishen/             # 《我不是戏神》
│   └── beacon/             # 《守灯人》
├── assets/images/          # 共用图标与 README 配图
├── site/                   # 双语项目主页与网站构建脚本
├── .github/workflows/      # CI 与 GitHub Pages 部署
└── pyproject.toml          # 包依赖与全部影片配置
```

## 🧭 工作原理

![CodeCinema 影片的制作流程：数据规格、场景合成、渲染、声音、后期](assets/images/pipeline.svg)

**图 1.** 一部 CodeCinema 影片是怎样制作出来的。**(a)** 影片先写成数据：`pyproject.toml` 声明步骤和设置，一份 config 存放整个故事（时间轴、节拍、角色、写成音符的乐谱）。**(b)** 影片把这些数据变成场景：角色、动作编排、镜头、环境和特效，全部按同一个影片时钟打关键帧，每个动作都会发出带时间的声音事件。**(c)** 渲染器以并行、可续渲的分块绘制画面：一部示例用 Blender 3D，另一部用 skia 2D 绘画。**(d)** 配乐、音效和环境声根据音符和事件合成，再混音和母带处理。**(e)** 字幕、画面和声音按采样精度合成并通过质检。框架用影片自己的设置运行每一步，并提供共享的设置、声音工具包和 ffmpeg 工具。

## 参与贡献

[贡献指南](CONTRIBUTING.md)介绍开发环境、验证命令及新增模板或渲染器的方法。[框架说明](#framework)介绍影片接口与共享工具。

## 📜 许可

本项目以 [MIT 许可证](LICENSE) 发布 © 2026 ZJUCQR。
