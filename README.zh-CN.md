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

框架自带两部完整的示例影片，分别用两种不同的技术制作。

## ✨ 亮点

- 🤖 **由 coding agent 创作的影片**：两部示例影片都是用自然语言导演，由 coding agent 从头到尾完成的，包括故事、角色、动画、镜头、配乐、音效和母带。
- 🎬 **两部完整的示例影片**：《芒原决战》是一部 160 秒的武士决斗，用 Blender 3D 渲染；《韩熙载夜宴图 · 猫》是一幅 128 秒的“活”长卷，用 skia 以 2D 绘制。
- 🧩 **约定很小，渲染器随意**：影片在 `film.toml` 里声明自己的步骤，`codecinema run <影片> <步骤>` 会用这部影片的设置来运行它。Blender、2D 矢量绘图、着色器，任何能输出画面帧的方式都可以。
- 🎼 **共享的声音工具包**：两部影片配乐背后的 DSP 库就是框架的一部分，包括振荡器、拨弦和模态物理模型、卷积混响、真峰值限制器和响度工具。
- ♻️ **可复现，可配置**：渲染结果确定，并行任务可断点续跑；分层设置无需改动受版本管理的文件；辅助工具支持 macOS、Linux 和 Windows。

## 🚀 快速开始

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git && cd CodeCinema
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install .                                          # 安装 `codecinema` 命令

codecinema check                      # 检查 Python 依赖、ffmpeg，以及 3D 示例需要的 Blender
codecinema list                       # 列出 films/ 里的影片和它们的步骤
codecinema run nightrevels all        # 2D 示例：几分钟生成整部影片
codecinema run silvergrass all        # 3D 示例：需要 Blender 5.2+，渲染时间较长
codecinema new myfilm                 # 从模板开始制作你自己的影片
```

每部影片把成片输出到它自己的 `assets/film/` 文件夹。不安装命令也可以用 `python -m codecinema …`。

## 🎞 示例影片

<div align="center">

| <a href="films/silvergrass/README.zh-CN.md"><img src="films/silvergrass/assets/images/still_190.jpg" alt="芒原决战"></a> | <a href="films/nightrevels/README.zh-CN.md"><img src="films/nightrevels/assets/images/still_1300.jpg" alt="韩熙载夜宴图 · 猫"></a> |
|:---:|:---:|
| **[《芒原决战》](films/silvergrass/README.zh-CN.md)** | **[《韩熙载夜宴图 · 猫》](films/nightrevels/README.zh-CN.md)** |
| 落日芒草原上，无主之忍对决年迈的剑豪，分为剑、焰、雷三幕。 | 一场画在绢上的夜宴，每位宾客都是猫，还有一只小猫画师在偷偷作画。 |
| Blender 3D · 160 秒 · 30 个镜头 | skia 2D 绘画 · 128 秒 · 13 个猫品种 |
| `codecinema run silvergrass all` | `codecinema run nightrevels all` |

</div>

两部影片都可以在[主页](https://zjucqr.github.io/CodeCinema/zh/)完整观看。

## 🎨 制作你自己的影片

```bash
codecinema new myfilm --title "My Film"     # 用模板创建 films/myfilm/
codecinema run myfilm all                    # 渲染一部 6 秒的起步影片
```

模板本身就是一部完整的小影片：`draw_frame()` 绘制每一帧，`score()` 生成声音，框架负责编码和混流。把这两个函数换成你自己的内容，随着影片变大再增加步骤，设置都放在 `film.toml` 里。

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
│   ├── cli.py              # codecinema list | run | new | check
│   ├── settings.py         # 每部影片的分层设置，工具和字体查找
│   ├── films.py            # 影片发现和步骤运行
│   ├── media.py            # ffmpeg：探测、编码、拼接、混流
│   ├── procutil.py         # 跨平台的锁、进程、内存工具
│   ├── audio/dsp.py        # 共享的声音工具包
│   └── template/           # `codecinema new` 使用的起步影片
├── films/
│   ├── silvergrass/        # 示例：《芒原决战》（Blender 3D）
│   └── nightrevels/        # 示例：《韩熙载夜宴图 · 猫》（2D）
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
