# 基于参考文本校正的语音转文本

使用本地 Whisper 模型转录音频文件，并将 STT 段与已知参考脚本对齐。识别错字会被替换为参考脚本的措辞，同时保留 STT 得到的时间戳 —— 输出是适合作为字幕的、带时序的校正文本。

## 概述

工作流由两个作业组成：

1. **`transcribe`** — 通过 **faster-whisper** 在本地运行 `large-v3-turbo`，
   使用 `return_timestamps: segment`。产出 `{text, start_time, end_time}` 段列表。
   faster-whisper 是 Whisper 的 CTranslate2 移植版 —— 显著快于 HuggingFace transformers 后端，
   可在 CPU 或 CUDA 上运行。
2. **`correct`** — 将这些段以及参考脚本传入 `transcript-corrector` 组件。
   每个 STT 段被锚定到参考中最匹配的跨度；匹配的段文本会被替换为
   参考的措辞，同时保留 STT 的 `start_time` / `end_time`。

典型用例：
- 清理已知脚本的录音（播客、有声书、脚本化叙述）。
- 当参考脚本与音频分开编写时，产出准确的字幕。
- 对 STT 输出做后处理，去除同音字/错字漂移而不丢失时序。

## 准备工作

### 前置条件

- 已安装 model-compose 并在 `PATH` 中可用。
- faster-whisper 运行于 **CPU**（包括 Apple Silicon 的 macOS）或 **CUDA**。
  CTranslate2 无 Metal/MPS 后端；在 Apple Silicon 上模型运行于 CPU
  （在 `turbo` 模型上仍然很快）。
- Python 依赖在首次运行时自动安装：
  - `faster-whisper` — CTranslate2 Whisper 运行时。
  - `rapidfuzz`、`regex` — 对齐评分。

### 设置

进入本示例目录：

```bash
cd examples/media-processing/speech-to-text-with-correction
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
   - 上传音频文件，粘贴参考脚本，并（可选）设置语言代码。
   - 点击 **Run Workflow**。

   **使用 CLI：**

   ```bash
   model-compose run --input '{
     "audio": "/path/to/reading.wav",
     "reference": "The full text that the speaker was supposed to read...",
     "language": "en"
   }'
   ```

   **使用 API：**

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "audio=@/path/to/reading.wav" \
     -F 'reference=The full text that the speaker was supposed to read...' \
     -F "language=en"
   ```

## 输入参数

| 参数 | 类型 | 必需 | 描述 |
|-----------|------|----------|-------------|
| `audio` | file | 是 | 待转录的音频（wav、mp3、flac、m4a 等）。 |
| `reference` | string | 是 | 音频所依据的真实脚本。 |
| `language` | string | 否 | ISO 代码（`en`、`ko`、`ja` 等）。省略时自动检测。 |

## 输出格式

校正后段的扁平列表。每个段上会保留 STT 输出的其他键。

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `text` | string | 与 STT 段最匹配的参考脚本措辞。 |
| `start_time` | number | 段起始时间（秒），来自 STT。 |
| `end_time` | number | 段结束时间（秒），来自 STT。 |

最佳参考匹配低于 `match_threshold` 的段会被跳过，而不是以错误的文本输出。

### 示例

参考：

```
Alice was beginning to get very tired of sitting by her sister on the bank
and of having nothing to do. Once or twice she had peeped into the book her
sister was reading, but it had no pictures or conversations in it.
```

STT（错字加粗）：

```
Alis was begining to get very tired of siting by her sister on the bank
and of having nothing to do. Once or twise she had peeped into the book her
sister was reading, but it had no pictures or convertations in it.
```

校正后的输出：

```json
[
  { "text": "Alice was beginning to get very tired of sitting by her sister on the bank and of having nothing to do.", "start_time": 0.0,  "end_time": 6.2 },
  { "text": "Once or twice she had peeped into the book her sister was reading, but it had no pictures or conversations in it.", "start_time": 6.2, "end_time": 12.8 }
]
```

## 组件详情

### `stt` — 语音转文本

- 类型：`model` (`task: speech-to-text`)
- 驱动：`custom`，family `faster-whisper`
- 模型：`Systran/faster-whisper-base` —— HuggingFace 上预转换的 CTranslate2 权重，
  首次运行时自动下载（约 150 MB）。可切换为更大更准确的规格：
  `Systran/faster-whisper-{small,medium,large-v3}`。
- 设备：`cpu`（macOS 上 CTranslate2 无 Metal/MPS 后端）。在 NVIDIA 上切换到 `cuda`。
- `compute_type: int8` —— 在 CPU 上快约 2 倍，质量下降很小。
  其他选项：`int8_float16`、`float16`、`float32`、`default`。
- 需要 `return_timestamps: true` 和 `timestamp_level: segment` ——
  校正器需要每段的 `start_time` / `end_time`。

### `corrector` — 文本校正器

- 类型：`transcript-corrector`
- 驱动：`native`（默认）
- 对齐：针对参考的滑动窗口进行逐段锚点匹配，
  使用 `rapidfuzz` 的字符级 Levenshtein 相似度评分。
- 关键选项：
  - `granularity: word` 用于以空格分隔的脚本，`character` 用于无空格的 CJK / 脚本。
  - `match_threshold: 0.5` —— 相似度低于此值的段被跳过。
  - `case_sensitive: false`、`ignore_punctuation: true` 控制仅用于评分的规范化；
    可见输出保留参考的原始大小写与标点。

## 自定义

### 在 NVIDIA GPU 上运行

```yaml
components:
  - id: stt
    ...
    device: cuda
    compute_type: float16       # 或 'int8_float16' 以降低 VRAM
```

### 更小 / 更快的 Whisper

```yaml
    model: Systran/faster-whisper-tiny     # 或 -base、-small、-medium、-large-v3
```

### CJK 脚本（无词间空格的中文、日文）

```yaml
  - id: corrector
    type: transcript-corrector
    action:
      ...
      granularity: character
      min_window_tokens: 12
```

### 严格匹配（丢弃更多模糊段）

```yaml
      match_threshold: 0.7
```
