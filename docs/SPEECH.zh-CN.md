# 给影片加配音

八种模板都支持逐镜头配音。台词留空时仍生成配乐版，不需要语音模型。

## 在 Studio 里操作

1. 运行 `codecinema studio`，展开“逐个定制分镜”。
2. 展开“添加配音”，填写短台词，选择声音和语言，描述情绪，例如“温柔而好奇”“紧张但克制”“一边观察一边思考”。
3. 给镜头留足时长，点击“生成我的影片”。也可先用“快速预览”试听。

Apple Silicon Mac 首次安装情绪语音包：

```bash
python -m pip install -e ".[speech]"
codecinema studio
```

第一次配音会下载 Qwen3-TTS CustomVoice，之后复用缓存。无需 API key。普通框架和无配音模板不会下载或载入模型。未安装语音包的 Mac 可使用系统声音，但系统声音不支持情绪提示。本地情绪模型目前要求 Apple Silicon。

中文声线可选 Serena、Vivian、Dylan、Uncle Fu 和 Eric；英文可选 Ryan、Aiden；日语、韩语可选 Ono Anna、Sohee。模型也支持跨语言配音；较长项目请先试听。

## 修改镜头数据

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

添加配音时，已识别的旧版原始模板会自动升级，并将原渲染器与镜头数据一同备份到 `out/edits/`。自定义代码会保留；若还不支持配音，会显示明确提示，避免台词被悄悄忽略。可以新建模板后复制镜头数据，或把新的配音功能合入自己的渲染器。

## 自定义人物口型

公共模块 `codecinema.audio.speech` 提供配音、录音转换与中文逐字对齐；`codecinema.audio.performance` 提供可保存为 JSON 的表演时间表。

先完成声音的剪裁和时间调整，再对最终波形做对齐，随后释放语音模型、开始画面渲染。人物嘴形由真实音节和音量共同驱动，停顿时闭嘴；旁白与内心独白不指定画面中的说话人物。其他语言可以提供相同 `{text, start, end}` 格式的外部对齐时间戳。没有逐字时间戳的录音也可使用音量开合，但语音形状精度较低。

完整接口示例见[英文指南](SPEECH.md)，完整制作示例见[开篇三集](../films/xishen/README.zh-CN.md)。
