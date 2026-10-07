# 我不是戏神 · 开篇三集

以 CodeCinema 制作三九音域《我不是戏神》开篇第 1–6 章的三集动态漫画。三集统一使用 Skia 人物造型和画风，并保留随情节变化的室内乐配乐，区分雨夜、剧院、调查、奇观与喜剧场景。总长 **11 分钟**，1920×1080、24 fps、2.35:1 画面，含中文配音、字幕、环境声及道具音效。人物形象、服装状态与剧情时间线在三集间保持连贯。

**[在线观看](https://zjucqr.github.io/CodeCinema/xishen/watch.html)** · **[下载三集与合集](https://github.com/ZJUCQR/CodeCinema/releases/tag/xishen)** · [English](README.md)

![雨夜的陈伶、剧院观众和换上黑棉大衣后的同一人物](assets/images/banner.jpg)

| 集数 | 片名 | 原著范围 | 时长 |
| --- | --- | --- | --- |
| 01 | 戏鬼回家 | 第 1 章 | 3:30 |
| 02 | 我们在看着你 | 第 2–3 章 | 3:30 |
| 03 | 陈氏编导法则 | 第 4–6 章 | 4:00 |

打开 [观看页](watch.html) 选择剧集、跳转段落或连续播放。成片在 `assets/film/ep01.mp4`、`ep02.mp4`、`ep03.mp4`，合集在 `assets/film/xishen_complete.mp4`。视频包含已经绘制的字幕，以及可选择的中文字幕轨和章节标记。

## 重新生成

从项目根目录运行：

先按[安装教程](../../README.zh-CN.md#quick-start)配置框架和 FFmpeg：

```bash
python -m pip install -e ".[speech]"
python -m codecinema run xishen all --narration required --speech-engine local
```

发布版使用 Apple Silicon 本地 Qwen3-TTS 情绪配音与 Qwen3 ForcedAligner 逐字对齐。首次运行会下载模型，之后缓存每句声音，无需 API key。不同人物固定声线，按镜头的恐惧、犹疑、疲惫和思考调整表演。口型跟随最终配音的实际时间和音节；停顿、旁白和内心独白时闭嘴。

`--speech-engine local` 要求本地情绪引擎，不会自动换成基础声音。默认 `auto` 优先使用已安装的语音包，Mac 未安装时使用系统声音。Linux / Windows 可把录音放到 `assets/voices/<镜头 id>.wav`，使用 `--speech-engine recording --narration required`；没有本地对齐模型时，口型根据声音活动开合。`--narration off` 生成字幕与配乐版本。详见[框架语音教程](../../README.zh-CN.md#speech)。

需要可显示简体中文的字体。Mac 自动查找宋体；其他系统可安装 Noto Serif CJK 或将 `XISHEN_FONTS_SONG`、`XISHEN_FONTS_KAITI` 指向对应字体文件。不同系统的字体和语音引擎可能产生不同的字形与声线；固定素材、版本和设置后，帧与配乐确定。

```bash
# 分步制作或只处理某一集
.venv/bin/python -m codecinema run xishen plan
.venv/bin/python -m codecinema run xishen stills
.venv/bin/python -m codecinema run xishen audio --episode ep01 --narration required --speech-engine local
.venv/bin/python -m codecinema run xishen render --episode ep01 --jobs 3 --narration required --speech-engine local
.venv/bin/python -m codecinema run xishen assemble --episode ep01 --narration required --speech-engine local
.venv/bin/python -m codecinema run xishen qc --episode ep01 --narration required --speech-engine local

# 低分辨率预览；制作与合成须使用同一套设置和配音选项
XISHEN_VIDEO_WIDTH=960 XISHEN_VIDEO_HEIGHT=540 \
  .venv/bin/python -m codecinema run xishen all --episode ep01 --narration required --speech-engine local
```

`--narration` 和 `--speech-engine` 属于制作设置。分步运行时保持一致；音频会在画面渲染前准备，例如音频使用 `required`，画面与合成也使用 `required`。镜头分块和输入签名支持断点续渲，半成品不会被当作完成的镜头。

观看页可直接用浏览器打开。需要 HTTP 播放时，在项目根目录运行 `.venv/bin/python -m codecinema run xishen serve`，访问 `http://127.0.0.1:8000/watch.html`。内置服务器支持视频分段请求，段落跳转和拖动进度条都能正常工作。

## 人物与原著依据

[原著官方页面](https://fanqienovel.com/page/7276384138653862966)及逐章链接记录在 [canon.json](data/canon.json)。影片是压缩改编，旁白和对白重新创作。人物面部、建筑细节和镜头属于视觉设计；原文明确的服装、地点、道具和事件顺序作为连续性的依据。

- 陈伶开篇为红戏袍、赤脚、湿黑发、额角受伤；第二集清晨出门时才换黑棉大衣，第三集继续穿同一件衣服。
- 前世 28 岁、京城剧院实习编导；今生是少年，不擅自给这六章内未明确的年龄赋值。
- 韩蒙保持黑大衣、粗卷烟。灾厄指针爆炸后才出现脸颊伤痕。
- 林医生保持白大褂、黑框眼镜和当前的诊所医生身份。
- 陈宴只在对白里被提到，没有提前出场或揭示后续真相。
- 观众期待值严格沿 `29 → 30 → 27 → 29 → 32` 变化。第六章后半仅显示增量，不杜撰终值。
- 早餐铺的恋爱说法明确是陈伶制造的误会，不当作赵乙或小六的真实人物设定。

九名出场人物共用同一套绘制函数和服装表。每个镜头都标注原著来源；前一集的状态必须与后一集的起始状态相接。开篇不使用后期神道技能、武器或黄昏社身份。

## 文件与验证

```text
data/canon.json       原著来源、角色设定与连续性约束
data/episodes.json    三集脚本、分镜、时长、服装和事件
src/story.py         唯一的故事时钟及状态校验
src/art.py           同一套人物、场景与绘制工具
src/scenes.py        分镜表演、镜头运动与字幕
src/score.py         随场景变化的室内乐配乐
src/sound.py         情绪配音、定时音效、压低配乐的混音
src/run.py           分块渲染、合成、章节、字幕轨和质检
out/screenplay.md     生成的完整改编剧本
out/continuity.json   逐镜头解析后的服装、道具和原著来源
out/*.srt             每集及合集的字幕
out/qc.json           本地生成的成片与连续性质检报告
assets/images/        海报、人物形象表与展示配图
out/stills/           生成的分镜联系表
assets/film/          三集 MP4 与合集
```

质检核对剧情时序、跨集状态、期待值、字体、字幕宽度、67 个镜头的确定性和运动、帧数、画面尺寸、音画时长、字幕轨、章节、响度与真峰值，并完整解码成片检查错误。结果写入 `out/qc.json`。影片和中间音视频不提交 Git，可由上述命令重新生成。

本版使用共享的人物设计、独立脸型、发型和体态；画面不再叠加片名、集数与解释性文字，只保留底部字幕和剧情中的道具文字。
