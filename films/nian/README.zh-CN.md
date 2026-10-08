<div align="center">

# 年

<p><sub>用 <a href="../../README.zh-CN.md"><b>CodeCinema</b></a> 制作的示例影片</sub></p>

<p><b>一部关于年兽的三分半钟普通话 3D 动画短片，用一份剧本写成。</b></p>

[![主页](https://img.shields.io/badge/主页-在线观看-e0a948?logo=githubpages&logoColor=white)](https://zjucqr.github.io/CodeCinema/zh/#nian)
[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f.svg)](../../LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Blender 5.2+](https://img.shields.io/badge/Blender-5.2%2B-ea7600?logo=blender&logoColor=white)](https://www.blender.org/)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)

[English](README.md) · **简体中文**

<img src="../../assets/nian/images/poster.jpg" width="92%" alt="雪夜森林里的年兽">

</div>

---

**传说每到除夕，年兽就会从山里下来；它怕红色，也怕响声。** 奶奶一边包饺子一边讲这个老故事，小满却想不通：那它为什么每年还要来？她提着灯笼、端着饺子溜进雪夜，在森林里遇见了年兽：庞大、温柔、饿着肚子，脖子上围着一条褪了色的红围巾。

村民的鞭炮突然炸响，年兽捂住耳朵缩成一团，小满张开双臂挡在它前面。这时，奶奶认出了那条围巾。六十年前，还是小姑娘的她，把它围在一只冻得发抖的小兽脖子上。它从来就不怕红色，它怕的，是一个人过年。

- **画面：** 青瓦覆雪的山村、春联与灯笼、温暖的厨房、月光下的松林和泛黄的回忆，全部由场景库搭建，用 Blender 卡通渲染。
- **声音：** 古筝、二胡、笛子演奏的五声音阶主题，锣鼓与唢呐的年味，普通话对白，年兽无言的哼声和呜咽，鞭炮、烟花与落雪。

## ✨ 亮点

- 🤖 **由 coding agent 制作。** 用自然语言指挥：coding agent 写了故事、剧本、主题旋律和每一个镜头。
- 🧧 **反转的传说。** 怕红色的年兽，围着一条红围巾；伏笔从它第一次出场就在画面里。
- 🏮 **年味细节。** 倒贴的“福”字、春联、摇晃的灯笼、横跨巷子的彩灯串、鞭炮和烟花。
- 🎞 **泛黄的回忆。** 回忆段落是同一片森林换成暖色的回忆光，合成时再加上调色、胶片颗粒和暗角。
- 🗣 **各平台声音一致。** 普通话对白以小体积录音保存在 `assets/nian/voices/`，并附中英文字幕轨。

## 🚀 快速开始

按照[安装说明](../../README.zh-CN.md#quick-start)安装框架，再安装 [Blender 5.2 或更高版本](https://www.blender.org/download/)。在仓库根目录运行；Windows 请把 `.venv/bin/python` 换成 `.\.venv\Scripts\python.exe`。

```bash
.venv/bin/python -m codecinema run nian all
```

成片位于 `assets/nian/film/Nian.mp4`，带中文和英文字幕轨。春联和片名使用随仓库提供的站酷快乐体，中文在各个平台上显示一致。

## 🎬 改成你的故事

所有内容都在 [`screenplay.json`](screenplay.json)。角色的声音在演员表里设定一次，每句台词再写明情绪：

```json
"nainai": {"from": "grandma", "name": "奶奶",
           "voice": {"profile": "grandma", "speaker": "Serena", "pitch": -1.5,
                     "direction": "用七十多岁慈祥老奶奶的语气，声音温和，略带沙哑。"}}
```

```json
{"t": 0.6, "who": "nainai", "say": "它怕的，是一个人过年。", "mood": "tender",
 "en": "What it feared... was spending the New Year alone."}
```

修改台词后检查时间：`codecinema run nian plan` 会提示哪句台词压到了下一句。分步命令见[《小企鹅飞起来》说明](../pebble/README.zh-CN.md#-改成你的故事)。

## 📜 致谢

故事、剧本、调度与配乐由 coding agent 借助 CodeCinema 完成。乐器采样来自 S. Christian Collins 的 [GeneralUser GS](https://www.schristiancollins.com/generaluser.php)。中文字体为站酷快乐体（SIL 开源字体许可）。以 [MIT 许可](../../LICENSE)发布。
