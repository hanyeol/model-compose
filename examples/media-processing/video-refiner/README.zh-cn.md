# Video Refiner 示例

本示例串联 **file-store**、**`audio-extractor`**、**Silero VAD** 和 **`video-clipper`**，生成仅包含检测到的语音区域的视频。整个管道以流式方式端到端运行：VAD 一旦确认语音片段就立即发出，clipper 随之实时生成对应的视频片段。

## 概述

四个 job 组成一个流式管道：

1. **`store`** — 将上传的视频存入本地 `file-store`，以便音频分支和每个分段裁剪都能独立地重新读取。`StreamResource` 是一次性的，若无此步骤原始上传流会被最先读取的 job 消耗掉。
2. **`extract`** — 通过 `audio-extractor`（ffmpeg）从已存储的视频中提取音频轨道，音频流直接送入 VAD。
3. **`detect`** — 以**流式模式**（`streaming: true`）运行 Silero VAD：每个语音片段在确认的瞬间即以 `{start_time, end_time, confidence}` 形式发出，无需等待完整音频分析完成。
4. **`refine`** — 使用 `"|"` split 操作符将 VAD 分段流 fan-out 为 `(video, span)` 对，逐对送入 `video-clipper`。每收到一个分段，clipper 就重新打开已存储的视频，seek 到 `[start_time, end_time]`，并发出一个无损片段。片段完成一个就流式输出一个。

VAD 的分段模式（`start_time`、`end_time`）与 clipper 的 span 模式 1:1 匹配，无需形状映射 —— 分段上额外的 `confidence` 字段会被 clipper 直接忽略。

典型用例：
- 从原始录制视频中产生"纯语音"版本，供审阅或字幕制作
- 将采访/播客视频上传到转录服务前进行修剪 —— 节省成本且减少静音段的幻觉
- 接入只需要人声部分的场景分类或 ASR 管道

## 管道

```
input.video ── store ─┐
                      │
                      ├──► extract ──► detect (streaming) ──┐
                      │                                     │
                      │                    "|": vad output   ← fan-out
                      │                    video: 已存储路径
                      │                    span:  ${item}
                      │                                     │
                      └────────────────────────────────► refine ──► 片段流
```

`"|"` split 操作符（详见 [variable-binding 参考文档](../../../docs/user-guide/14-variable-binding.md)）以 VAD 分段流为源，产生两个并行的 per-item 流：一个始终解析为已存储视频的路径，另一个解析为当前分段。每个 `(video, span)` 对触发一次 ffmpeg stream-copy 裁剪。

## 准备工作

### 前置要求

- 已安装并在 PATH 中的 model-compose
- 已安装并在 PATH 中的 [ffmpeg](https://ffmpeg.org/)（`audio-extractor` 和 `video-clipper` 均使用）
- Python 依赖在首次运行时自动安装：
  - `silero-vad`、`torch`、`torchaudio`、`numpy` —— VAD 模型

### 设置

进入示例目录：

```bash
cd examples/media-processing/video-refiner
```

验证 ffmpeg 安装：

```bash
ffmpeg -version
```

本地 file-store 默认写入 `./storage/`（见 `model-compose.yml` 中的 `storage` 组件）。首次运行时会自动创建目录，无需额外设置。

## 运行方式

1. **启动服务：**

   ```bash
   model-compose up
   ```

   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 http://localhost:8081
   - 上传视频文件
   - 可选择覆盖 `threshold`、`min_speech_duration`、`min_silence_duration`、`speech_padding_time`
   - 点击 **Run Workflow**，随片段到达下载 refined 片段

   **使用 CLI：**

   ```bash
   # 默认参数
   model-compose run --input '{"video": "/path/to/recording.mp4"}'

   # 更严格的 VAD（丢弃更多边缘语音），并添加边界填充以避免词首被切
   model-compose run --input '{
     "video": "/path/to/recording.mp4",
     "threshold": 0.6,
     "min_speech_duration": "500ms",
     "speech_padding_time": "200ms"
   }'
   ```

   **使用 API：**

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "video=@/path/to/recording.mp4" \
     -F 'input={"video": "@video", "threshold": 0.6}'
   ```

## 组件详情

### `storage` — File Store

- **类型**：`file-store`
- **驱动**：`local`
- **用途**：持久化上传的视频，使 `extract` 和 `refine` 均可独立重新读取。若无此步骤，一次性的上传流会被最先读取的 job 消耗掉。
- **说明**：
  - `base_path: ./storage` 将所有存储保留在示例目录下。若需共享/云存储，将驱动替换为 `aws-s3` / `gcp-storage` / `azure-blob`
  - `${context.run_id}` 为每次 run 隔离存储键，避免并行运行冲突

### `extractor` — Audio Extractor

- **类型**：`audio-extractor`
- **驱动**：`ffmpeg`
- **用途**：从已存储的视频中提取音频轨道供 VAD 使用，输出 WAV

### `vad` — Voice Activity Detection

- **类型**：带 `voice-activity-detection` 任务的模型组件
- **驱动**：`custom`
- **家族**：`silero`
- **用途**：检测提取音频中的语音区域
- **说明**：
  - `streaming: true` 一旦确认分段就立即发出（不等待完整列表）
  - 模型内置于 `silero-vad` pip 包中，无需 HuggingFace 下载
  - 输入在内部重采样为 16 kHz 单声道

### `clipper` — Video Clipper

- **类型**：`video-clipper`
- **驱动**：`ffmpeg`
- **用途**：对每个到达的 `(video, span)` 对，使用 `ffmpeg -c copy`（不重新编码）从已存储视频中裁剪 span
- **说明**：
  - `merge` 保持默认（`false`），片段一到达就流式输出。若要拼接为单个文件，设置 `merge: true` —— 参见[自定义](#自定义)
  - 由于不重新编码，切分点会对齐到容器支持的最近之前关键帧。若需帧级精度，裁剪后用 `video-encoder` 重新编码

## 工作流详情

### "Video Refiner" 工作流

**说明**：使用 Silero VAD 检测语音区域，将 refined 视频片段按分段流式输出。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `video` | video | 是 | - | 源视频文件（MP4、MOV、MKV 等） |
| `threshold` | number | 否 | `0.5` | Silero 语音概率阈值（0.0-1.0），越高越严格 |
| `min_speech_duration` | duration | 否 | `250ms` | 短于此值的语音块被丢弃 |
| `min_silence_duration` | duration | 否 | `500ms` | 分离相邻语音块所需的静音长度 |
| `speech_padding_time` | duration | 否 | `100ms` | 在检测到的每个块两侧添加的填充 |

Duration 字段接受 `"250ms"`、`"0.5s"` 或裸的秒数数字。

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `video` | video (stream) | refined 视频片段流 —— 每个检测到的语音分段一段，完成时立即发出 |

## 自定义

### 将所有片段拼接为单个 refined 视频

在 clipper action 上设置 `merge: true`，并将工作流输出从流改为单个视频：

```yaml
components:
  - id: clipper
    type: video-clipper
    action:
      video: ${input.video}
      span: ${input.span}
      merge: true
```

`merge: true` 时 clipper 会等待整个 span 流到达后再运行 ffmpeg 的 `concat` demuxer，因此管道不再是逐块流式 —— 但输出是一个可直接播放的单一文件。

### 用云对象存储代替本地磁盘

将 `storage` 组件的驱动替换为 `aws-s3` / `gcp-storage` / `azure-blob`：

```yaml
components:
  - id: storage
    type: file-store
    driver: aws-s3
    bucket: ${env.S3_BUCKET}
    region: ${env.AWS_REGION | us-east-1}
    access_key_id: ${env.AWS_ACCESS_KEY_ID}
    secret_access_key: ${env.AWS_SECRET_ACCESS_KEY}
    base_path: video-refiner/
```

工作流其余部分无需修改 —— `put` 返回的逻辑路径由下游 job 直接使用。

### 将 refined 片段接入下游 ASR

添加一个 job，将每个流式片段送入 `speech-to-text` 模型组件。因为片段以流的形式到达，下游 job 每段一到就处理，无需等待整个视频完成。

## 提示

- **端到端流式**：管道的任何阶段都不会等待完结：VAD 一确认即发出分段，clipper 一到达即裁剪，每个片段一由 ffmpeg 完成就交付。
- **无损裁剪**：clipper 使用 `ffmpeg -c copy`，因此片段边界对齐到容器支持的最近关键帧。对于有损编解码（h.264、hevc）可能有几毫秒偏差，如需帧级精度，请在裁剪后用 `video-encoder` 重新编码。
- **填充的意义**：Silero 的 frame-level 阈值可能导致词首被切；`speech_padding_time` 设为 100-200ms 通常可避免此问题。
- **存储清理**：`storage` 组件将上传保留在 `./storage/uploads/` 下。若要大规模运行，请添加周期性清理 job 或按 run 隔离存储并在完成后删除。

## 故障排查

### 常见问题

1. **不生成片段 / 流立即结束**：阈值可能过于严格 —— 降低 `threshold`（如 `0.3`）或减小 `min_speech_duration`。
2. **片段边界处词被切**：增大 `speech_padding_time`（如 `200ms`）。
3. **`ffmpeg` not found**：安装 ffmpeg（及 ffprobe），并确保两者在 `PATH` 中。
4. **存储目录权限错误**：确保进程可写入 `./storage/`。若需不同位置，请修改 `model-compose.yml` 中的 `storage.base_path`。
5. **`StreamResource` already consumed 错误**：本示例通过先将上传写入 file-store 来避免此问题。若自定义省略 `store` job，请注意 `${input.video}` 只能消耗一次 —— 需先保存到磁盘（`save_to`）或通过 `file-store` 持久化后再 fan-out。
