# 视频配音流水线

本示例演示端到端的视频配音工作流：从视频中提取原始音频，用 Whisper 转录，将转录文本翻译为目标语言，用 Qwen3-TTS 合成新的配音，并使用 Wav2Lip 将原视频的口型对齐到新音频。

## 概述

流水线依次串联五个组件：

1. **audio-extractor (ffmpeg)** — 将输入视频的音轨提取为 16 kHz PCM WAV。
2. **speech-to-text (Whisper turbo)** — 将提取的音频转录为源语言的完整文本。
3. **text-to-text (SMaLL-100)** — 通过特殊 `forced_bos_token` 选择目标语言，将转录文本翻译。
4. **text-to-speech (Qwen3-TTS)** — 使用预设声音（默认 `vivian`）合成目标语言的配音。
5. **lip-sync (Wav2Lip)** — 接受原视频与新音频，逐帧改写口部区域使其对齐翻译后的语音。

每个阶段都是独立组件，因此可以在不改动其余工作流的情况下替换任何一步 —— 例如把 STT 换成 `crisper-whisper` 获得标点，插入语音克隆 TTS 以保留原说话人的音色，或把 Wav2Lip 换成 `musetalk` / `latentsync` 获得更高质量的对口型。

## 准备工作

### 前置条件

- 已安装 model-compose 并在 `PATH` 中可用。
- 系统路径中有 `ffmpeg`（供音频提取和 Wav2Lip 的音频合成步骤使用）。
- 强烈建议使用 CUDA GPU；STT + TTS + 对口型的整套栈可以在 CPU 上运行，但短片以外的场景速度不实用。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/media-processing/video-dubbing
   ```

2. 无需额外环境配置 —— 所有模型都在首次运行时从 Hugging Face 下载或由封装库自带。Wav2Lip 阶段会额外将上游的 `justinjohn0306/Wav2Lip` fork 安装到专用的 virtualenv (`.venv/wav2lip`)，避免其陈旧的 `librosa`/`numba` 依赖固定与控制器 site-packages 冲突。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会下载 Whisper large-v3-turbo、SMaLL-100、Qwen3-TTS 和 Wav2Lip 的检查点并安装 Wav2Lip 的 venv。控制器就绪前预计需要数分钟以及数 GB 下载。

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 将英文源视频配音为韩文
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "src=@/path/to/talking-head.mp4" \
     -F 'input={"video": "@src", "source_language": "en", "target_language": "ko"}'

   # 同一素材，目标日语
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "src=@/path/to/talking-head.mp4" \
     -F 'input={"video": "@src", "source_language": "en", "target_language": "ja"}'
   ```

   **使用 Web UI：**
   - 打开 Web UI: http://localhost:8081
   - 上传一段说话面部清晰可见的 `video`（正面单人主体效果最佳）
   - 从下拉菜单选择 `source_language` 与 `target_language`
   - 点击 “Run Workflow” 获取配音后的 MP4

## 配置参考

### 工作流输入

| 字段               | 说明                                                        | 选项                    | 默认值  |
|-------------------|------------------------------------------------------------|------------------------|---------|
| `video`           | 含说话人的源视频。ffmpeg 可读的任意容器格式。                  | `video/*`              | —       |
| `source_language` | 源视频语音的语言（ISO-639-1 代码）。                          | `en`, `ko`, `ja`, `zh` | `en`    |
| `target_language` | 配音的目标语言（ISO-639-1 代码）。                            | `en`, `ko`, `ja`, `zh` | `ko`    |

### Job 流程

| Job              | 组件               | 输入                                                   | 依赖              |
|------------------|-------------------|-------------------------------------------------------|------------------|
| `extract-audio`  | `audio-extractor` | `source = input.video`                                | —                |
| `transcribe`     | `stt`             | `audio = extract-audio.output`, `language`            | `extract-audio`  |
| `translate`      | `translator`      | `text = transcribe.output`, `target_language`         | `transcribe`     |
| `synthesize`     | `tts`             | `text = translate.output`                             | `translate`      |
| `lip-sync`       | `lip-syncer`      | `video = input.video`, `audio = synthesize.output`    | `synthesize`     |

### 组件

| 组件              | 后端                                             | 备注                                                                       |
|------------------|--------------------------------------------------|---------------------------------------------------------------------------|
| `audio-extractor`| `audio-extractor` (ffmpeg driver)                | 将轨道 0 提取为 16 kHz PCM WAV                                              |
| `stt`            | `model / speech-to-text` (Whisper turbo)         | `openai/whisper-large-v3-turbo`；每次输入返回单个字符串                        |
| `translator`     | `model / text-to-text` (SMaLL-100)               | `alirezamsh/small100`；通过 `forced_bos_token` 选择目标语言                   |
| `tts`            | `model / text-to-speech` (Qwen3-TTS)             | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`；预设声音 `vivian`                     |
| `lip-syncer`     | `model / lip-sync` (Wav2Lip)                     | `family: wav2lip`, `preset: wav2lip-gan`；在专用 virtualenv 中运行             |

## 注意事项

- **声音一致性**：默认 `tts` 组件使用预设声音，因此配音的音色与原说话人不匹配。若需保留音色，请将 TTS 组件替换为语音克隆示例（如 `text-to-speech-clone-cosyvoice`），并把原说话人的短参考片段作为额外输入。
- **分段配音**：本流水线把视频作为单条发言进行转录与翻译，适合短片（< 30 s）。对更长的素材，请添加 `voice-activity-detection` 组件把音频切分为语音区段，并用 `for-each` job 独立翻译每一段 —— 流式 / VAD / `for-each` 模式请参考 `examples/media-processing/speech-to-text-with-correction`。
- **语言代码**：SMaLL-100 支持 100+ 目标语言。这里的下拉菜单只暴露了小的默认集合 —— 编辑 `model-compose.yml` 里的 `select/...` 列表可暴露更多。切换到其他多语言模型（`NLLB`、`mBART`、`M2M100`）时，需根据各模型的特殊语言 token 格式调整 `forced_bos_token` 字符串。
- **对口型质量**：Wav2Lip 快但保真度低于 diffusion 类方案。若追求更清晰的效果，可把 `lip-syncer` 组件的 `family: wav2lip` 换成 `family: musetalk` (v1.5) 或 `family: latentsync` (1.6) —— 对应的参数面参见 `examples/model-tasks/lip-sync-musetalk` 和 `lip-sync-latentsync`。
- **音频长度不匹配**：生成的 TTS 片段时长与源视频不同。Wav2Lip 在音频超出视频时前向循环源帧填补；最终视频长度对齐 TTS 音频而非源视频。
- **人脸检测失败**：若 Wav2Lip 在某帧检测不到人脸，工作流会抛出 `"Face not detected in one of the frames"`。可在 `lip-syncer` 组件上提供 `params.face_bounding_box` 绕过检测，或改用面部更大、正对镜头且清晰的素材。
