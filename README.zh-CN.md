<div align="center">

# CodeCinema

<p><b>用代码制作一部完整的短片：画面、音乐、音效、字幕和最终母带，一条命令全部重新生成。</b></p>

[![Homepage](https://img.shields.io/badge/%E4%B8%BB%E9%A1%B5-%E8%A7%82%E7%9C%8B%E5%BD%B1%E7%89%87-e0a948?logo=githubpages&logoColor=white)](https://zjucqr.github.io/CodeCinema/zh/)
[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![Blender (optional)](https://img.shields.io/badge/Blender-optional-ea7600?logo=blender&logoColor=white)](https://www.blender.org/)

[English](README.md) · **简体中文**

<img src="assets/images/banner.jpg" width="92%" alt="两部示例影片的画面">

</div>

---

CodeCinema 是一个小型框架，用来制作完全由代码构成的影片。一部影片就是一个文件夹，里面有一个 `film.toml` 和它自己的制作流程。框架提供每部影片都需要的部分：
- **设置**：每部影片一套分层设置，支持本地覆盖和环境变量，并能自动查找工具和字体。
- **声音**：共享的音频工具包，包括合成、物理建模、混响、真峰值限制和响度处理。
- **合成**：ffmpeg 辅助工具，负责探测、编码、拼接和混流。
- **命令行**：一个 CLI，可以列出影片、运行影片的步骤，以及创建新影片。

框架自带三部完整的影片项目、八种可定制的起步场景，以及本地可视化编辑器。

## ✨ 亮点

- 🪄 **选模板、改内容、点一下出片**：本地 Studio 提供八种动态场景、可编辑分镜、标题、字幕、颜色、横竖屏与方形画幅，一次点击生成 MP4，无需 API Key。
- 🎬 **三部完整影片项目**：160 秒的 Blender 武士决斗、128 秒的活体猫咪长卷，以及人物贯穿三集、含中文配音的 11 分钟开篇改编。
- 🧩 **约定很小，渲染器随意**：影片在 `film.toml` 里声明自己的步骤，`codecinema run <影片> <步骤>` 会用这部影片的设置来运行它。Blender、2D 矢量绘图、着色器，任何能输出画面帧的方式都可以。
- 🎼 **共享的声音工具包**：影片配乐背后的 DSP 库就是框架的一部分，包括振荡器、拨弦和模态物理模型、卷积混响、真峰值限制器和响度工具。
- ♻️ **可复现，可配置**：渲染结果确定，并行任务可断点续跑；分层设置无需改动受版本管理的文件；辅助工具支持 macOS、Linux 和 Windows。

## 🚀 快速开始

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git && cd CodeCinema
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m pip install -e .                             # 安装 `codecinema` 命令

codecinema studio                    # 自动打开本地可视化编辑器
```

制作前需安装 **FFmpeg**。**[三步出片教程](docs/GETTING_STARTED.zh-CN.md)** 提供 Mac、Linux、Windows 的具体安装命令。进入 Studio 后选场景、填文字、点击 **“生成我的影片”** 即可；成片输出到对应影片的 `assets/film/` 文件夹。也可以使用 `python -m codecinema …`。

<p align="center"><img src="assets/images/starters.jpg" width="100%" alt="八种真实模板画面：月夜、落日、极光、霓虹、海浪、水墨、宇宙和萤火森林"></p>

喜欢命令行？一条命令创建并制作：

```bash
codecinema new myfilm --preset aurora --title "我的影片" --render --open
```

## 🎞 示例影片

<div align="center">

| <a href="films/silvergrass/README.zh-CN.md"><img src="films/silvergrass/assets/images/still_190.jpg" width="360" alt="芒原决战"></a> | <a href="films/nightrevels/README.zh-CN.md"><img src="films/nightrevels/assets/images/still_1300.jpg" width="360" alt="韩熙载夜宴图 · 猫"></a> | <a href="films/xishen/README.zh-CN.md"><img src="films/xishen/assets/images/still-rain.jpg" width="360" alt="我不是戏神 · 开篇三集"></a> |
|:---:|:---:|:---:|
| **[《芒原决战》](films/silvergrass/README.zh-CN.md)** | **[《韩熙载夜宴图 · 猫》](films/nightrevels/README.zh-CN.md)** | **[《我不是戏神 · 开篇三集》](films/xishen/README.zh-CN.md)** |
| 落日芒草原上，无主之忍对决年迈的剑豪，分为剑、焰、雷三幕。 | 一场画在绢上的夜宴，每位宾客都是猫，还有一只小猫画师在偷偷作画。 | 按原著开篇六章的顺序，从陈伶雨夜归家、剧院噩梦到第一次编导演练，人物与时间线贯穿三集。 |
| Blender 3D · 160 秒 · 30 个镜头 | Skia 2D 绘画 · 128 秒 · 13 个猫品种 | Skia 动态漫画 · 11 分钟 · 三集 · 中文配音 |
| [观看](https://zjucqr.github.io/CodeCinema/zh/#silvergrass) · [下载](https://github.com/ZJUCQR/CodeCinema/releases/tag/film) | [观看](https://zjucqr.github.io/CodeCinema/zh/#nightrevels) · [下载](https://github.com/ZJUCQR/CodeCinema/releases/tag/nightrevels) | [观看](https://zjucqr.github.io/CodeCinema/xishen/watch.html) · [下载](https://github.com/ZJUCQR/CodeCinema/releases/tag/xishen) |
| `codecinema run silvergrass all` | `codecinema run nightrevels all` | `codecinema run xishen all --narration required` |

</div>

三部影片都可在[主页](https://zjucqr.github.io/CodeCinema/zh/#films)观看，点击对应 Release 下载 MP4；`codecinema list` 会列出各自的制作步骤。《芒原决战》需要 Blender 5.2+ 和较长渲染时间。《我不是戏神》使用 Mac 离线中文语音或自备录音，也可用 `--narration off` 生成字幕和配乐版本。各影片说明提供详细环境要求和定制方法。

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

在影片代码里，`from codecinema import settings, media` 和 `from codecinema.audio import dsp` 分别提供设置、ffmpeg 工具和声音工具包。完整说明见 **[docs/FRAMEWORK.md](docs/FRAMEWORK.md)**（英文）。

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
│   ├── procutil.py         # 跨平台的锁、进程、内存工具
│   ├── audio/dsp.py        # 共享的声音工具包
│   └── template/           # `codecinema new` 使用的起步影片
├── films/
│   ├── silvergrass/        # 示例：《芒原决战》（Blender 3D）
│   ├── nightrevels/        # 示例：《韩熙载夜宴图 · 猫》（2D）
│   └── xishen/             # 《我不是戏神》开篇三集（2D 动态漫画，11 分钟）
├── docs/                   # 框架说明
├── site/                   # 主页
└── pyproject.toml          # 包和依赖
```

## 🧭 工作原理

<div align="center">
<img src="assets/images/pipeline.svg" width="100%" alt="CodeCinema 影片的制作流程：数据规格、场景合成、渲染、声音、后期">
</div>

<p align="center"><sub><b>图 1.</b> 一部 CodeCinema 影片是怎样制作出来的。<b>(a)</b> 影片先写成数据：<code>film.toml</code> 声明步骤和设置，一份 config 存放整个故事（时间轴、节拍、角色、写成音符的乐谱）。<b>(b)</b> 影片把这些数据变成场景：角色、动作编排、镜头、环境和特效，全部按同一个影片时钟打关键帧，每个动作都会发出带时间的声音事件。<b>(c)</b> 渲染器以并行、可续渲的分块绘制画面：一部示例用 Blender 3D，另一部用 skia 2D 绘画。<b>(d)</b> 配乐、音效和环境声根据音符和事件合成，再混音和母带处理。<b>(e)</b> 字幕、画面和声音按采样精度合成并通过质检。框架用影片自己的设置运行每一步，并提供共享的设置、声音工具包和 ffmpeg 工具。</sub></p>

## 📜 许可

本项目以 [MIT 许可证](LICENSE) 发布 © 2026 ZJUCQR。
