# 第一次用 CodeCinema 出片

[English](GETTING_STARTED.md) · [框架说明](FRAMEWORK.md)

**安装一次，打开 Studio，点“生成我的影片”。** 模板会自动制作动态画面、片名、字幕、立体声配乐和经过检查的 MP4。起步模板无需账号、API Key、Blender 或外部素材。

![八种真实模板画面：月夜、落日、极光、霓虹、海浪、水墨、宇宙和萤火森林](../assets/images/starters.jpg)

## 1. 只需安装一次

需要 **Python 3.12 或更新版本**、Git 和 **FFmpeg**（包含 `ffprobe`）。先下载项目：

```bash
git clone https://github.com/ZJUCQR/CodeCinema.git
cd CodeCinema
```

**Mac：** 使用 [Homebrew](https://brew.sh/) 安装工具，然后执行：

```bash
brew install python@3.12 ffmpeg
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

**Linux：** 用系统包管理器安装 Python 3.12+、FFmpeg 和字体。Ubuntu 24.04 可以执行：

```bash
sudo apt-get install python3-venv ffmpeg fonts-dejavu-core libgl1 libfontconfig1
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m codecinema studio
```

**Windows（PowerShell）：** 先安装 [Python 3.12+](https://www.python.org/downloads/) 和 FFmpeg：

```powershell
winget install Gyan.FFmpeg
# 安装后重新打开 PowerShell，回到 CodeCinema 目录，再运行下面三行。
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m codecinema studio
```

不必手动激活虚拟环境。Windows 安装了更新的 Python 时，把 `-3.12` 换成对应版本即可。浏览器会自动打开 **http://127.0.0.1:8787/**；使用期间保留终端，按 `Ctrl+C` 关闭 Studio。

## 2. 三步出片

1. **选择场景：** 点击喜欢的模板缩略图。
2. **加入你的想法：** 填影片 ID、标题和开场字幕，选时长和横竖屏。首次保留 12 秒、720p 即可。
3. **生成我的影片：** 等进度完成，直接观看或下载 MP4。

默认模板通常几秒即可出片，实际取决于电脑性能。更长的时间线、更高的画质会增加制作时间。**快速预览** 单独输出 360p 文件，已经生成的正式成片会保留。项目和媒体都留在本机。

成片位置：**`films/<影片ID>/assets/film/<影片ID>.mp4`**。下次打开 Studio，在 **“我的影片”** 中选中作品，修改后再点生成即可；此前的设置自动保存在影片目录的 `out/edits/`。

## 3. 八种风格，随时混搭

| 模板 | 画面 | 适合的内容 |
| --- | --- | --- |
| `moonrise` 月夜山峦 | 星空、升月、层叠山峦 | 安静的片头、个人标题短片 |
| `sunset` 金色落日 | 暖光、岛屿、粼粼水面 | 旅行回忆、温暖的片尾 |
| `aurora` 极光之境 | 北极光、森林湖泊 | 梦幻或神秘氛围 |
| `neon` 霓虹城市 | 紫色天际线、发光窗户 | 城市故事、音乐片头 |
| `ocean` 碧海潮汐 | 碧蓝海浪、明亮天空 | 夏日寄语、放松的短片 |
| `ink` 水墨远山 | 纸上山水、薄雾、飞鸟 | 诗句、简洁的标题影片 |
| `cosmos` 漫游宇宙 | 星环行星、卫星、星空 | 科幻开场 |
| `ember` 萤火森林 | 暮色森林、点点萤火 | 温柔、温暖的夜景 |

展开 **“逐个定制分镜”**，每张卡片就是一个镜头：改标题和字幕、调整时长与镜头运动、添加或移除镜头、用上下箭头改变顺序，也可以让多个场景出现在同一部影片里。总时长随卡片变化。**画幅** 支持横屏、竖屏和方形；**自选点缀色** 可以调整高光与字幕的颜色。

起步模板制作的是带动态场景与配乐的标题短片。新人物、打斗动作或叙事场面需要扩展绘制代码；进阶时可看 [框架说明](FRAMEWORK.md) 和 [《我不是戏神》开篇三集](../films/xishen/README.zh-CN.md) 中的共享人物与剧情时间线。

## 喜欢一条命令？

使用同一虚拟环境运行下面的命令。将 `python` 换成 `.venv/bin/python`（Mac/Linux）或 `.\.venv\Scripts\python.exe`（Windows），无需激活环境：

```bash
python -m codecinema new myfilm --preset aurora --title "我的第一部影片" --render --open
python -m codecinema customize myfilm --preset ocean --title "夏日回忆" --duration 20 --render
python -m codecinema customize myfilm --format portrait --quality high --render
python -m codecinema run myfilm all --quality preview
```

`--open` 用默认播放器打开成片。新建默认 12 秒、三个镜头、720p；已有影片 ID 不会被覆盖，改作品用 `customize`。所有定制都会保存上一版设置。

想直接编辑数据，只改 `films/myfilm/scenes.json`，然后运行 `python -m codecinema run myfilm all`：

```json
{
  "version": 1,
  "title": "从星空到远方",
  "seed": 7,
  "scenes": [
    {"preset": "moonrise", "duration_s": 6, "camera": "wide", "title": "一个安静的夜晚", "subtitle": "再看一眼星空。"},
    {"preset": "sunset", "duration_s": 6, "camera": "drift", "title": "新的地平线", "subtitle": "还有更多故事等着发生。", "accent": "#ffdfb5"}
  ]
}
```

`camera` 可选 `wide`（全景）、`drift`（缓慢移动）、`close`（推进）；每个镜头至少 0.5 秒，总长 1.5–600 秒。文字自动适配画幅，字体缺字时会明确提示如何修复。音画使用同一条按帧计算的时间线，检查完整 MP4 后才报告制作成功。

## 遇到问题时

| 情况 | 解决方法 |
| --- | --- |
| 找不到 `codecinema` 命令 | 直接使用上面的虚拟环境 Python 路径，加 `-m codecinema` |
| 缺少 Python 包 | 用启动 Studio 的同一虚拟环境重新执行安装命令 |
| 找不到 FFmpeg / `ffprobe` | 安装 FFmpeg；Windows 重开终端后再检查 |
| Linux 无法加载 Skia 图形库 | 用包管理器安装 `libgl1` 和 `libfontconfig1`，Studio 会显示具体加载错误 |
| 中文无法显示 | 安装 Noto Sans CJK（Ubuntu 用 `fonts-noto-cjk`），或在影片 `film.local.toml` 写 `[fonts]` 和 `ui = "/字体文件路径/font.ttf"` |
| 影片 ID 已存在 | 换一个 ID；或从“我的影片”打开原作品，命令行用 `customize` |
| 端口被占用 | 启动时加 `studio --port 8788` |
| 合成提示设置不一致 | 直接运行 `all`；分步制作需使用相同的画质、画幅、时长和帧率 |
| 想撤回修改 | 把 `out/edits/<时间戳>/` 中的 `scenes.json` 和 `film.toml` 复制回影片目录，再生成一次 |

生成的视频、音频和中间文件默认不提交 Git。可以分享代码、镜头数据和文档；成片适合放在 GitHub Release 中。
