<h1 align="center">CodeCinema</h1>

<p align="center">
  <strong>让你的故事动起来。</strong><br>
  用代码创作完整影片的开源框架：画面、配乐、音效与最终成片。
</p>

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
  <a href="docs/GETTING_STARTED.zh-CN.md"><img src="https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&amp;logoColor=white" alt="Python 3.12+"></a>
  <a href="docs/GETTING_STARTED.zh-CN.md"><img src="https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&amp;logoColor=white" alt="FFmpeg required"></a>
  <a href="docs/BLENDER.md"><img src="https://img.shields.io/badge/Blender-optional-ea7600?logo=blender&amp;logoColor=white" alt="Blender optional"></a>
</p>

<p align="center">
  <a href="https://zjucqr.github.io/CodeCinema/zh/"><strong>项目主页</strong></a> ·
  <a href="docs/GETTING_STARTED.zh-CN.md"><strong>快速开始</strong></a> ·
  <a href="docs/FRAMEWORK.md">框架指南</a>
</p>

---

CodeCinema 是可扩展的通用影片制作框架。可以在本地可视化编辑器中选模板并定制，也可以接入自己的渲染器与制作流程。每部影片是一个包含 `film.toml` 的文件夹；框架提供：

- **设置**：每部影片一套分层设置，支持本地覆盖和环境变量，并能自动查找工具和字体。
- **声音**：共享的音频工具包，包括合成、物理建模、混响、真峰值限制和响度处理。
- **合成**：ffmpeg 辅助工具，负责探测、编码、拼接和混流。
- **命令行**：一个 CLI，可以列出影片、运行影片的步骤，以及创建新影片。

通过 Studio，可以从模板直接制作 MP4；示例影片展示了如何接入自定义渲染器、声音与后期流程。

## ✨ 亮点

- 🪄 **选模板、改内容、点一下出片**：本地 Studio 提供八种动态场景、可编辑分镜、标题、字幕、颜色、横竖屏与方形画幅，一次点击生成 MP4，无需 API Key。
- 🧩 **约定很小，渲染器随意**：影片在 `film.toml` 里声明自己的步骤，`codecinema run <影片> <步骤>` 会用这部影片的设置来运行它。Blender、2D 矢量绘图、着色器，任何能输出画面帧的方式都可以。
- 🎼 **共享的声音工具包**：影片配乐背后的 DSP 库就是框架的一部分，包括振荡器、拨弦和模态物理模型、卷积混响、真峰值限制器和响度工具。
- 🎙️ **可选情绪配音**：在 Studio 逐镜头填写台词和表演提示，也可使用自己的录音。[语音教程](docs/SPEECH.zh-CN.md)介绍本地语音包与可复用的口型时间接口。
- ♻️ **可复现，可配置**：渲染结果确定，并行任务可断点续跑；分层设置无需改动受版本管理的文件；辅助工具支持 macOS、Linux 和 Windows。

## 🚀 快速开始

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git && cd CodeCinema
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m pip install -e .                             # 安装 `codecinema` 命令

codecinema studio                    # 自动打开本地可视化编辑器
```

制作前需安装 **FFmpeg**。**[三步出片教程](docs/GETTING_STARTED.zh-CN.md)** 提供 Mac、Linux、Windows 的具体安装命令。进入 Studio 后选场景、填文字、点击 **“生成我的影片”** 即可；成片输出到对应影片的 `assets/film/` 文件夹。也可以使用 `python -m codecinema …`。

![八种真实模板画面：月夜、落日、极光、霓虹、海浪、水墨、宇宙和萤火森林](assets/images/starters.jpg)

喜欢命令行？一条命令创建并制作：

```bash
codecinema new myfilm --preset aurora --title "我的影片" --render --open
```

## 🎞 示例影片

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <a href="films/silvergrass/README.zh-CN.md"><img src="assets/images/examples/silvergrass.jpg" width="100%" alt="芒原决战"></a>
      <h3><a href="films/silvergrass/README.zh-CN.md">芒原决战</a></h3>
      <p>落日芒草原上，无主之忍对决年迈的剑豪，分为剑、焰、雷三幕。</p>
      <p><strong>Blender 3D · 160 秒 · 30 个镜头</strong></p>
      <p><a href="https://zjucqr.github.io/CodeCinema/zh/#silvergrass">观看</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/film">下载</a> · <a href="films/silvergrass/README.zh-CN.md">制作指南</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="films/nightrevels/README.zh-CN.md"><img src="assets/images/examples/nightrevels.jpg" width="100%" alt="韩熙载夜宴图 · 猫"></a>
      <h3><a href="films/nightrevels/README.zh-CN.md">韩熙载夜宴图 · 猫</a></h3>
      <p>一场画在绢上的夜宴，每位宾客都是猫，还有一只小猫画师在偷偷作画。</p>
      <p><strong>Skia 2D · 128 秒 · 13 个猫品种</strong></p>
      <p><a href="https://zjucqr.github.io/CodeCinema/zh/#nightrevels">观看</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/nightrevels">下载</a> · <a href="films/nightrevels/README.zh-CN.md">制作指南</a></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="films/xishen/README.zh-CN.md"><img src="assets/images/examples/xishen.jpg" width="100%" alt="我不是戏神 · 开篇三集"></a>
      <h3><a href="films/xishen/README.zh-CN.md">我不是戏神 · 开篇三集</a></h3>
      <p>按原著开篇顺序，从陈伶雨夜归家、剧院噩梦到第一次编导演练，人物与时间线贯穿三集。</p>
      <p><strong>Skia 2D · 11 分钟 · 三集 · 中文配音</strong></p>
      <p><a href="https://zjucqr.github.io/CodeCinema/xishen/watch.html">观看</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/xishen">下载</a> · <a href="films/xishen/README.zh-CN.md">制作指南</a></p>
    </td>
    <td width="50%" valign="top">
      <a href="films/beacon/README.zh-CN.md"><img src="assets/images/examples/beacon.jpg" width="100%" alt="守灯人"></a>
      <h3><a href="films/beacon/README.zh-CN.md">守灯人</a></h3>
      <p>云海上的瓷白机械守灯人唤醒古老星环，远方的一点光给出了回应。</p>
      <p><strong>Blender 3D · 48 秒 · 6 个镜头 · 原创配乐</strong></p>
      <p><a href="https://zjucqr.github.io/CodeCinema/zh/#beacon">观看</a> · <a href="https://github.com/ZJUCQR/CodeCinema/releases/tag/beacon">下载</a> · <a href="films/beacon/README.zh-CN.md">制作指南</a></p>
    </td>
  </tr>
</table>

示例影片均可在[主页](https://zjucqr.github.io/CodeCinema/zh/#films)观看，点击对应 Release 下载 MP4；`codecinema list` 会列出各自的制作步骤。《芒原决战》与《守灯人》需要 Blender 5.2+，3D 渲染比 2D 示例耗时更长。《我不是戏神》三集全程共用同一套 Skia 2D 人物造型，配有随场景变化的配乐和情绪中文对白。发布版配音使用 Apple Silicon 上的可选本地语音包；其他平台可以提供录音。`--narration off` 可生成字幕与配乐版本。各影片指南提供安装要求和定制方法。

## 🎨 制作你自己的影片

```bash
codecinema new myfilm --preset sunset --title "我的影片" --duration 15 --render
codecinema customize myfilm --preset neon --title "城市灯火" --format portrait --render
codecinema run myfilm all --quality preview   # 另存快速预览，保留正式成片
```

模板默认 **三个镜头、12 秒、720p**。通过 Studio 或 `scenes.json`，可以逐镜头改风格、时长、文字和镜头运动；八种场景均支持横屏、竖屏、方形画幅与原创合成配乐。每次定制都会自动保存上一版设置。

需要新的动画表现时，再修改生成项目 `src/run.py` 中的 `draw_frame()` 和 `score()`。个性化操作看 [简单教程](docs/GETTING_STARTED.zh-CN.md)，渲染器开发看 [框架说明](docs/FRAMEWORK.md)。

```toml
# films/myfilm/film.toml
[film]
id = "myfilm"
title = "My Film"
entry = "src/run.py"                    # 运行影片各步骤的脚本
steps = ["render", "audio", "assemble", "all"]

[settings.video]
width = 1920
height = 1080
fps = 24
```

在影片代码里，`from codecinema import settings, media` 和 `from codecinema.audio import dsp` 分别提供设置、ffmpeg 工具和声音工具包。完整说明见 **[docs/FRAMEWORK.md](docs/FRAMEWORK.md)**（英文）。[Blender 指南](docs/BLENDER.md)与[语音教程](docs/SPEECH.zh-CN.md)介绍共享渲染工具、配音和口型接口的复用方式。

## 🗂 项目结构

```
CodeCinema/
├── codecinema/             # 框架
│   ├── cli.py              # studio | presets | new | customize | list | run | check
│   ├── studio.py           # 本地可视化编辑器与制作任务
│   ├── studio_assets/      # 编辑器界面与真实场景缩略图
│   ├── settings.py         # 每部影片的分层设置，工具和字体查找
│   ├── films.py            # 影片发现和步骤运行
│   ├── media.py            # ffmpeg：探测、编码、拼接、混流
│   ├── blender.py          # 后台启动与共享 Blender 工具
│   ├── procutil.py         # 跨平台的锁、进程、内存工具
│   ├── audio/
│   │   ├── dsp.py          # 合成、效果、混音与母带处理
│   │   ├── speech.py       # 可选配音、录音和对齐
│   │   └── performance.py  # 可复用的对白与口型时间表
│   └── template/           # `codecinema new` 使用的起步影片
├── films/
│   ├── silvergrass/        # 示例：《芒原决战》（Blender 3D）
│   ├── nightrevels/        # 示例：《韩熙载夜宴图 · 猫》（2D）
│   ├── xishen/             # 《我不是戏神》开篇三集（2D 动态漫画，11 分钟）
│   └── beacon/             # 示例：《守灯人》（Blender 3D）
├── docs/                   # 框架说明
├── site/                   # 主页
└── pyproject.toml          # 包和依赖
```

## 🧭 工作原理

![CodeCinema 影片的制作流程：数据规格、场景合成、渲染、声音、后期](assets/images/pipeline.svg)

**图 1.** 一部 CodeCinema 影片是怎样制作出来的。**(a)** 影片先写成数据：`film.toml` 声明步骤和设置，一份 config 存放整个故事（时间轴、节拍、角色、写成音符的乐谱）。**(b)** 影片把这些数据变成场景：角色、动作编排、镜头、环境和特效，全部按同一个影片时钟打关键帧，每个动作都会发出带时间的声音事件。**(c)** 渲染器以并行、可续渲的分块绘制画面：一部示例用 Blender 3D，另一部用 skia 2D 绘画。**(d)** 配乐、音效和环境声根据音符和事件合成，再混音和母带处理。**(e)** 字幕、画面和声音按采样精度合成并通过质检。框架用影片自己的设置运行每一步，并提供共享的设置、声音工具包和 ffmpeg 工具。

## 参与贡献

[贡献指南](CONTRIBUTING.md)介绍开发环境、验证命令及新增模板或渲染器的方法；[框架说明](docs/FRAMEWORK.md)介绍影片接口与共享工具。

## 📜 许可

本项目以 [MIT 许可证](LICENSE) 发布 © 2026 ZJUCQR。
