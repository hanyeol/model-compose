# 带 VAD 预分割的语音转文本

使用本地 Silero VAD 模型将长音频文件拆分为语音区间，剪出每个区间，并用 Whisper 进行转录 —— 全部在一条流式管道中完成。每个片段都带有相对于原始音频的绝对时间戳，因此输出可直接用于字幕或带时序的转录。

## 概述

工作流由三个作业组成，通过两个流式运算符（clipper 上的 `return_timestamp`，transcribe 作业上的 `+`）串联：

1. **`detect`** —— Silero VAD 以流式模式运行。语音区间一旦确认，即以 `{start_time, end_time, confidence}` dict 流的形式发出。
2. **`clip`** —— `audio-clipper`（ffmpeg 驱动）消费 VAD 流。设置 `return_timestamp: true` 后，每个输出 clip 被包装为 `{audio, start_time, end_time}`，源 span 信息随之传递到下游。
3. **`transcribe`** —— `for-each` 作业遍历 clip 流。对每个 clip，将该 clip 的 VAD `start_time` 作为 STT 的 `time_offset` 传入并运行 Whisper，返回的段因此已经带有原始音频中的绝对时间戳。作业的 `+` 运算符将 Whisper 每个 clip 的段流延迟展平为一条连续的段流。

工作流输出即为该展平后的流的 JSON 序列化，调用方无需等待整段音频即可看到 `{text, start_time, end_time}` dict 一个个到达。

典型用例：
- 从长音频录制（播客、讲座、访谈）生成具有准确段时序的字幕文件。
- 通过 VAD 预分割规避 Whisper 30 秒 chunking 限制处理长音频。
- 跳过长时间的静默，只把 Whisper 时间花在实际语音上。

## 准备工作

### 前置条件

- 已安装 model-compose 并在 `PATH` 中可用。
- `PATH` 中有 `ffmpeg`（供 clipper 使用）。
- Whisper 可运行于 **CPU**、**CUDA** 或 **MPS**（Apple Silicon）。默认配置使用 `device: mps`；在其他环境请切换为 `cpu` 或 `cuda`。
- Python 依赖在首次运行时自动安装：
  - `silero-vad`、`torch`、`torchaudio`、`soxr` —— VAD。
  - `transformers`、`torch` —— Whisper。

### 设置

进入本示例目录：

```bash
cd examples/media-processing/speech-to-text-with-vad
```

## 运行方式

1. **启动服务：**

   ```bash
   model-compose up
   ```

   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 http://localhost:8081。
   - 上传音频文件并选择语言。
   - 点击 **Run Workflow**。Whisper 每完成一个 clip，段就流式返回。

   **使用 CLI：**

   ```bash
   model-compose run --input '{
     "audio": "/path/to/lecture.mp3",
     "language": "en"
   }'
   ```

   **使用 API（SSE 流）：**

   ```bash
   curl -N -X POST http://localhost:8080/api/workflows/runs \
     -F "audio=@/path/to/lecture.mp3" \
     -F "language=en"
   ```

## 输入参数

| 参数 | 类型 | 必需 | 描述 |
|-----------|------|------|-------------|
| `audio` | file | 是 | 待转录的音频（wav、mp3、flac、m4a 等）。 |
| `language` | string | 否 | ISO 代码（`en`、`ko`、`ja`、`zh`）。默认为 `en`。 |

## 输出格式

JSON 流，每行一个段。时间戳是原始音频中的绝对位置（VAD clip 起始 + Whisper 的 clip 相对时间）。

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `text` | string | 该段的识别文本。 |
| `start_time` | number | 段起始时间（秒），绝对值。 |
| `end_time` | number | 段结束时间（秒），绝对值。 |

### 示例

```json
{"text": "Welcome back to the show.",        "start_time":   0.42, "end_time":   2.15}
{"text": "Today we're talking about VAD.",   "start_time":   2.60, "end_time":   5.30}
{"text": "It splits audio into speech runs.","start_time": 224.44, "end_time": 226.76}
```

## 组件详情

### `vad` —— 语音活动检测

- 类型：`model` (`task: voice-activity-detection`)
- 驱动：`custom`，family `silero`
- 设备：`cpu`（Silero 模型小，CPU 足够；不支持 MPS）。
- `sample_rate: 16000` —— 与 Whisper 的原生采样率一致，避免 clip → STT 路径上的额外重采样。Silero 也支持 8000 Hz。
- `streaming: true` —— 段一确认即发出，下游 clipper 和 STT 可立即开始工作。
- 关键 `params`：
  - `threshold: 0.5` —— 进入段所需的语音概率。
  - `min_speech_duration: 250ms`、`min_silence_duration: 500ms` —— hysteresis 边界。
  - `max_speech_duration: 30s` —— 限制单个突发以适配 Whisper 的 30 秒窗口。
  - `speech_padding_time: 100ms` —— 每个检测区间前后的额外音频，避免词边被切掉。

### `clipper` —— 音频剪辑器

- 类型：`audio-clipper`
- 驱动：`ffmpeg`
- `return_timestamp: true` —— 每个 clip 以 `{audio, start_time, end_time}` 形式发出，下游 for-each 可同时将音频和 span 传给 STT。

### `stt` —— 语音转文本

- 类型：`model` (`task: speech-to-text`)
- 驱动：`huggingface`，architecture `whisper`
- 模型：`openai/whisper-large-v3-turbo` —— 快速且准确；若需其他体积/速度权衡，可切换为 `openai/whisper-{tiny,base,small,medium,large-v3}`。
- 设备：`mps` —— Apple Silicon GPU。NVIDIA 用 `cuda`，其他环境用 `cpu`。
- `return_timestamps: true` —— 输出每段的 `start_time` / `end_time`。
- `streaming: true` —— Whisper 生成段的同时流式输出，与 `+` 运算符结合后让工作流输出一条平坦的段流。
- `time_offset: ${input.time_offset}` —— for-each 将每个 clip 的 VAD 起始时间作为该 offset 传入，STT 将其加到返回的每个段的 `start_time` / `end_time` 上，使结果带有原始音频中的绝对位置。

## 自定义

### 在 CPU 或 CUDA 上运行

```yaml
components:
  - id: stt
    ...
    device: cpu   # 或 NVIDIA 上的 'cuda'
```

### 更小 / 更快的 Whisper

```yaml
    model: openai/whisper-small       # 或 -base、-medium、-large-v3 等
```

### 调整 VAD 灵敏度

```yaml
  - id: vad
    ...
    action:
      params:
        threshold: 0.3               # 更宽松；可捕获较安静的语音
        min_speech_duration: 100ms   # 保留较短的突发
        min_silence_duration: 300ms  # 在更短的停顿处分割
```

### 保持时间戳为 clip 相对时间

从 STT 输入中去掉 `time_offset`，每个段将从其自身 clip 内的 0 开始：

```yaml
    - id: transcribe
      type: for-each
      input: ${jobs.clip.output}
      do:
        component: stt
        input:
          audio: ${item.audio}
          language: ${input.language}
      output:
        "+": ${output}
```
