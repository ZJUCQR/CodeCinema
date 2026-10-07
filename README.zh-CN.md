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
  <a href="#framework">框架概览</a>
</p>

---

CodeCinema 是一个可扩展的开源影片制作框架，将画面、配乐和声音组合成完整影片。在本地 Studio 中选择场景、修改内容并生成 MP4，也可以用 Blender 或自己的渲染器创作。

## ✨ 亮点

- 🪄 **从场景到成片**：八种动态风格，可调整文字、配色、时长与镜头。
- 🎨 **自由选择画幅**：支持横屏、竖屏和方形视频。
- 🎼 **画面与声音一起制作**：生成配乐和音效，也可加入配音与录音。
- 🧩 **扩展你的创作**：接入 Blender、2D 绘图或自己的渲染器。
- 💻 **本地运行**：支持 macOS、Linux 和 Windows，基础出片无需 API Key。

<a id="quick-start"></a>

## 🚀 快速开始

需要 **Python 3.12+、Git 和 FFmpeg**。先克隆仓库，然后展开对应系统的安装命令：

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
<summary>Linux</summary>

```bash
sudo apt-get install python3-venv ffmpeg fonts-dejavu-core libgl1 libegl1 libfontconfig1
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

</details>

<details>
<summary>Windows</summary>

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
2. **改内容**：填写影片 ID、标题和字幕，选择时长与画幅。
3. **生成影片**：点击“生成我的影片”，完成后直接观看或下载 MP4。

![Eight starter looks](assets/images/starters.jpg)

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

在 Studio 的 “逐个定制分镜”中增删、排序镜头，修改文字、时长、配色和镜头运动。作品保存后可以继续编辑和重新生成。

模板适合制作动态风景短片。自定义人物、动作和故事表演可通过自己的渲染器实现。

<a id="framework"></a>

## 🧩 框架概览

每部影片拥有自己的故事、渲染器和素材，框架提供声音制作与成片合成等共用工具。可以从[示例源码](films/)开始开发自己的制作流程，影片配置统一放在根目录 [pyproject.toml](pyproject.toml)。

<a id="blender"></a>

## 🎬 Blender

创作 3D 影片需安装 [Blender 5.2 或更新版本](https://www.blender.org/download/)。[《守灯人》制作指南](films/beacon/README.zh-CN.md)提供渲染和个性化修改的方法。Studio 的基础模板不需要 Blender。

<a id="speech"></a>

## 🎙️ 配音与口型

在 Studio 的分镜卡片中展开 “添加配音”，填写台词、选择声音并描述情绪。台词留空时生成配乐版。

Apple Silicon Mac 可在仓库根目录安装本地情绪语音包，然后重启 Studio：

```bash
.venv/bin/python -m pip install -e ".[speech]"
```

首次配音会下载语音模型，无需 API Key。其他平台可使用录音。[《我不是戏神》制作指南](films/xishen/README.zh-CN.md)展示了配音与角色口型的完整制作流程。

## 🗂 项目结构

```text
CodeCinema/
├── codecinema/       # 框架与 Studio
├── films/            # 示例与自己的影片
├── assets/images/    # 共用展示图片
├── site/             # 项目主页
└── pyproject.toml    # 安装依赖与影片配置
```

## 🧭 工作原理

![CodeCinema 影片制作流程](assets/images/pipeline.svg)

从故事和镜头出发，生成画面、配乐与声音，再将它们同步组合成完整影片。

## 参与贡献

欢迎改进场景、Studio 和渲染器。开发环境与提交方式见[贡献指南](CONTRIBUTING.md)。

## 📜 许可

本项目以 [MIT 许可证](LICENSE) 发布 © 2026 ZJUCQR。
