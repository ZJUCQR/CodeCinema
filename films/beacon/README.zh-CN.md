# 守灯人

一部无对白的 Blender 原创短片：云海上的机械守灯人唤醒古老星环，远方的一点光给出了回应。

[在线观看](https://zjucqr.github.io/CodeCinema/zh/#beacon) · [下载 MP4](https://github.com/ZJUCQR/CodeCinema/releases/tag/beacon) · [English](README.md)

![机械守灯人与天文台星环](assets/images/poster.jpg)

**48 秒 · 1920 × 1080 · 24 fps · 立体声 · Blender 5.2+**

角色采用原创瓷白与黄铜造型，包含分层护甲、独立手指、嵌入式发光双眼和随风摆动的围巾。六个镜头共用同一套模型与连续表演时间线，从独处、倾听、伸手触碰，到点亮、发送与回应。原创合成配乐结合钢琴音色、弓弦泛音与玻璃钟声。风声、伺服电机和接触音效按动作时间同步。

## 一条命令出片

按[安装教程](../../README.zh-CN.md#quick-start)安装框架，另外安装 [Blender 5.2 或更新版本](https://www.blender.org/download/)，然后在仓库根目录运行：

```bash
codecinema run beacon all
```

成片位于 `films/beacon/assets/film/TheLastBeacon.mp4`。不需要 API Key、外部模型、贴图包或 Blender 插件。程序会自动寻找 Blender 和 FFmpeg。自定义安装位置可通过 `BLENDER_BIN`、`FFMPEG`、`FFPROBE` 指定。整片需要渲染 1,152 张全分辨率 3D 画面，耗时取决于显卡。

显存充足时，可以使用 `codecinema run beacon all --jobs 2`，同时渲染两个互不重叠的帧段。小显卡建议保留默认单进程。制作命令带有互斥锁，避免重复运行时相互覆盖。

先快速检查造型：

```bash
codecinema run beacon check
codecinema run beacon still                 # 六张 960 × 540 关键帧
codecinema run beacon still 481 --full      # 触碰时刻的全分辨率画面
```

预览保存在 `films/beacon/out/stills/`，不会覆盖成片画面。

## 个性化修改

新建 `films/beacon/film.local.toml`，无需修改受版本管理的文件：

```toml
[render]
samples_final = 64           # 边缘更干净，渲染时间增加
exposure = -0.2              # 比发布版略亮

[art]
porcelain = [0.72, 0.79, 0.75]
brass = [0.52, 0.28, 0.085]
scarf = [0.06, 0.20, 0.30]  # 线性 RGB：蓝色围巾
```

再次运行 `codecinema run beacon all`。中断后可以继续渲染。修改场景代码、故事数据或受支持的视觉设置后，程序会自动清理旧帧缓存。需要强制重做时使用 `codecinema run beacon all --force`。

| 想修改什么 | 文件 |
| --- | --- |
| 分镜说明、动作与声音共用的时间节点 | [src/story.py](src/story.py) |
| 人物、相机、材质、灯光和表演 | [src/scene.py](src/scene.py) |
| 和声、旋律、乐器和音效 | [src/sound.py](src/sound.py) |
| 编码和成片检查 | [src/run.py](src/run.py) |

六镜头与 48 秒配乐是一起设计的。若要改变总时长，需要一起调整镜头、动作和音乐，不能只修改时长常量。

## 分步制作

```bash
codecinema run beacon render
codecinema run beacon audio
codecinema run beacon assemble
```

`out/audio/` 保存音乐、环境声、音效分轨、总混音和响度报告。`out/qc.json` 记录成片参数、完整解码结果、AAC 响度与真峰值。合成阶段检查所有画面，要求正好 1,152 帧、48 秒，并拒绝真峰值超过 −1 dBTP 的成片。混音目标为 −16 LUFS，给 AAC 编码留出余量。

![成片六镜头](assets/images/storyboard.jpg)

环境准备可参考 [Blender 安装说明](../../README.zh-CN.md#blender)。示例图片和影片均由仓库内的场景代码渲染，整体采用风格化动画美术。

唯一作者：**ZJUCQR**。代码与原创程序化资产采用 [MIT](../../LICENSE) 许可。
