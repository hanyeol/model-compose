# 视频精修示例

本示例展示了一个工作流：用 Silero VAD 检测视频音轨中的语音区域，将这些区域从原始视频中切出，并拼接为一个"仅语音"的 mp4。Silero VAD 以流式模式运行，因此每个确认的语音片段一出现就流向 clipper — 不必等待整段音频分析完成。

## 概览

给定一个输入视频，工作流返回一个精修版本，仅包含有人说话的部分。

策略：

1. **将上传流 fan-out** — 使用 `fan-out` 作业的 `spool: true` 模式。上传是一次性的，clipper 要等 VAD 发出至少一个片段才开始消费 — 普通的内存 fan-out 队列需要在 VAD 遍历音频期间缓存整段上传。spool 模式把上传落到 tempfile 一次，并给两个分支各自一个基于文件的 StreamResource，两者可以在没有队列反压的情况下以不同速度 seek/read。两个分支都关闭后 tempfile 被删除。
2. **分离音轨** — 使用 `audio-extractor` 从视频中抽取音频（`format: wav` — 未压缩；Silero 内部会 downmix/resample 为 16 kHz mono）。
3. **检测语音区域** — 以 `streaming: true` 运行 Silero VAD。每个确认片段一确认就立即以 `{start_time, end_time, confidence}` 发出，clipper 无需等待整段音频分析完成即可开始工作。
4. **切分并拼接** — `video-clipper`（`merge: true`）消费 VAD 片段流，用 `ffmpeg -c copy` 从 spool 的视频中提取每个 `[start_time, end_time]` 片段（不重编码），再通过 ffmpeg 的 `concat` demuxer 将所有片段拼接为一个 mp4。

### 为什么用 spool fan-out

上传流是一次性的 — `audio-extractor` 和 `video-clipper` 都需要读取同一份原始字节。普通 fan-out 将上传 tee 为两个内存分支，代价有界，但仅当两个分支消费速度大致相同时才成立。这里 clipper 被 VAD 门控（VAD 在发出最后一个片段前会先遍历整段音频，之后也持续处理），因此 clipper 分支会任意落后于音频分支，fan-out 队列必须缓存整段上传。`spool: true` 用 tempfile 取代内存队列：上传到达时一次写入磁盘，两个分支各自打开该文件，最后一个分支关闭后文件删除。工作流保持端到端流式且内存有界，无需单独的 `file-store` 组件。

### 为什么用流式 VAD

Silero 的非流式模式要在整段音频处理完成后才返回片段列表，因此 VAD 结束前 clipper 无法开始。`streaming: true` 让 clipper 在第一个片段一确认就开始切分，ffmpeg concat 步骤边到边拼接 — 流水线让 VAD 与 clipping 重叠执行，而不是串行。

## 准备

### 要求

- 已在 PATH 中安装 model-compose
- 已在 PATH 中安装 FFmpeg（及 `ffprobe`）— `audio-extractor` 与 `video-clipper` 都会用到
- Silero VAD 的 Python 依赖（首次运行时自动安装）：
  - `silero-vad`、`torch`、`torchaudio`、`numpy`

### 设置

1. 进入示例目录：
   ```bash
   cd examples/media-processing/video-refiner
   ```

2. 准备一个待精修的视频文件。spool tempfile 写入 OS 默认临时目录，工作流结束后自动清理 — 示例目录下不会创建单独的存储文件夹。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传视频，按需覆盖 `threshold` / `min_speech_duration` / `min_silence_duration` / `speech_padding_time`
   - 点击 "Run Workflow" 并下载精修后的视频

   **API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"threshold": 0.5, "min_speech_duration": "250ms"};type=application/json' \
     -F 'video=@./recording.mp4'
   ```

   **CLI：**
   ```bash
   model-compose run --input '{
     "video": "./recording.mp4",
     "threshold": 0.5,
     "min_speech_duration": "250ms",
     "min_silence_duration": "500ms",
     "speech_padding_time": "100ms"
   }'
   ```

## 输入参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `video` | video (file) | Yes | - | 待精修的输入视频 |
| `threshold` | number | No | `0.5` | Silero 语音概率阈值（0.0 – 1.0）。越高越严 — 想丢掉更多边缘语音就调高，想捕捉更多不确定时刻就调低 |
| `min_speech_duration` | duration | No | `250ms` | 丢弃短于该值的已确认语音 chunk |
| `min_silence_duration` | duration | No | `500ms` | 相邻语音 chunk 之间需要该长度的静音才会被视为独立片段 |
| `speech_padding_time` | duration | No | `100ms` | 每个检测片段两侧添加的 padding。防止因 Silero 帧级阈值造成的词首辅音被切掉 |

duration 字段支持 `"250ms"`、`"0.5s"`，或纯数字（秒）。

## 作业详情

### Fan-Out (`fanout-video`)
- **类型**：`fan-out`（`spool: true`）
- **作用**：将一次性上传流 tee 为两个独立分支 — `for-audio`（流向 `extract` → VAD）和 `for-clip`（流向 clipper）。`spool: true` 让上传一次性写入 tempfile，每个分支各自打开该文件；两个分支都关闭后 tempfile 被删除。clipper 分支只在 VAD 处理大部分音频后才开始消费，普通 fan-out 路径会触发队列反压 — spool 规避了这一问题。

## 组件详情

### Audio Extractor (`extractor`)
- **类型**：`audio-extractor`
- **驱动**：`ffmpeg`
- **作用**：以未压缩 WAV 读取输入。由上游 spool fan-out 的 `for-audio` 分支喂入，与 clipper 并行消费上传（无需将视频落到共享存储）。Silero 内部会 downmix/resample 到 16 kHz mono，WAV 是自然选择。

### VAD (`vad`)
- **类型**：`model` — `voice-activity-detection` 任务
- **驱动**：`custom`（Silero family）
- **作用**：以 `streaming: true` 在抽取的音频上运行 Silero VAD，每个确认的语音片段以 `{start_time, end_time, confidence}` 形式立即发出。模型打包在 `silero-vad` pip 包里，无需额外下载。`max_concurrent_count: 1` 串行化对模型实例的访问。

### Clipper (`clipper`)
- **类型**：`video-clipper`
- **驱动**：`ffmpeg`
- **作用**：消费 VAD 片段流，用 `ffmpeg -c copy` 从 spool 的视频中切出每个 `[start_time, end_time]` 片段（不重编码）。`merge: true` 让 clipper 通过 ffmpeg 的 `concat` demuxer 将所有片段拼接为单个 mp4，因此工作流输出是一个即用的精修视频，而非独立片段流。VAD 附带的 `confidence` 字段直接透传 — clipper 只读取 `start_time` / `end_time`。

## 说明与调优

- **阈值**：如果没有生成任何片段，`threshold` 可能过严 — 调低（如 `0.3`）或减小 `min_speech_duration`。若误报过多，调高 `threshold`（如 `0.6`）。
- **Padding**：`speech_padding_time` 100–200 ms 通常能防止因 Silero 帧级阈值造成的词首辅音被切掉。若首字辅音仍被切，继续调大。
- **无损切分**：clipper 使用 `-c copy`，切点会捕捉到最近的先前关键帧。对于 h.264 / hevc 内容，单个切点可能偏差几十毫秒。若需要帧精度，在 clipper 之后接入 `video-encoder` — 会失去"不重编码"的属性，但获得精确边界。
- **流式 VAD、拼接输出**：VAD 以流式模式运行使片段检测与切分重叠执行，但 clipper 的 `merge: true` 会等待整个片段流完成后再拼接。若想每完成一个片段就单独 yield，改为 `merge: false` 并将工作流输出改为流式形状。
- **Spool tempfile 位置**：spool 写入 `tempfile.NamedTemporaryFile` 返回的 OS 临时目录。若系统 `TMPDIR` 指向的分区较小，需要覆盖（如 `TMPDIR=/data/tmp model-compose up`）— 否则上传可能超出分区容量。
- **何时选择 spool**：`spool: true` 适合任何一个 fan-out 分支比其他分支消费显著慢（或需要等待下游信号后才开始消费）的场景。若所有分支速度相近，默认内存 fan-out 更便宜。spool 用磁盘换 RAM，并为每次运行增加一次 tempfile 写入。

## 故障排查

### 常见问题

1. **没有片段生成 / 输出为空**：`threshold` 过严。调低（如 `0.3`）或减小 `min_speech_duration`。
2. **片段边界处词被切**：调大 `speech_padding_time`（如 `200ms`）。
3. **未找到 `ffmpeg`**：安装 FFmpeg 与 `ffprobe`，确保两者都在 `PATH` 上。
4. **Spool tempfile 写入失败 / "No space left on device"**：OS 临时目录空间不足。将 `TMPDIR` 设置到能容纳上传的分区，或用大磁盘上的 `file-store` 替代 `spool: true`。
5. **"Upload stream already consumed" 错误**：上传流是一次性的。本工作流正是为此在 fan-out 上使用 `spool: true`。如果自定义时跳过 `fanout-video` 作业，`${input.video}` 的第二次读取者会失败 — 保留 spool fan-out，或在向多个消费者 fan-out 之前通过 `file-store`（或其他能提供可重读路径的机制）落盘。
