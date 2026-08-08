# Media Inspector 示例

本示例展示了 `media-inspector` 组件的使用方法，该组件可以在不解码内容的情况下读取媒体文件（音频、视频或图像）的元数据。它封装了 `ffprobe`（FFmpeg 自带）和 `exiftool`，同时返回规范化字段与工具的原始输出。

## 概述

该示例提供三个工作流：

1. **检查媒体 (ffprobe)**：返回音频或视频文件的完整元数据负载
2. **AV 摘要**：返回简洁摘要 —— 容器格式、时长、大小和主要的视频/音频流
3. **检查图像 (exiftool)**：返回图像的 EXIF/XMP/GPS 元数据

## 准备工作

### 前置要求

- 已安装并在 PATH 中的 model-compose
- `ffmpeg` 驱动：已安装并在 PATH 中的 [FFmpeg](https://ffmpeg.org/)（`ffprobe` 二进制文件）
- `exiftool` 驱动：已安装并在 PATH 中的 [ExifTool](https://exiftool.org/)

### 设置

进入示例目录：
```bash
cd examples/media-processing/media-inspector
```

验证工具已安装：
```bash
ffprobe -version
exiftool -ver
```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

   服务将在以下地址启动：
   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081

2. **运行工作流：**

   **使用 CLI：**
   ```bash
   # 音频/视频文件的完整元数据
   model-compose run inspect --input '{
     "media": "/path/to/input.mp4"
   }'

   # 格式/时长/大小 + 主要流的摘要
   model-compose run summary --input '{
     "media": "/path/to/input.mp4"
   }'

   # 图像的 EXIF/XMP/GPS
   model-compose run inspect-image --input '{
     "image": "/path/to/photo.jpg"
   }'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=summary" \
     -F "media=@/path/to/input.mp4"
   ```

## 组件详情

### Media Inspector 组件

- **类型**：`media-inspector`
- **驱动**：`ffmpeg`（使用 `ffprobe`）、`exiftool`
- **用途**：从媒体文件中读取容器/流/EXIF 元数据，无需解码。

#### 主要字段

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|-------|------|----------|---------|-------------|
| `media` | 媒体源 | 是 | - | 文件路径、URL 或插值变量 |
| `return_raw` | boolean | 否 | `true` | 是否在 `raw` 字段中包含驱动的原始输出 |

## 工作流详情

### 1. 检查媒体 (ffprobe)

**说明**：完整的 ffprobe 负载 —— 容器格式、每条流的编解码器/比特率/时长/分辨率/fps 及原始 JSON。

#### 输入参数

| 参数 | 类型 | 必需 | 说明 |
|-----------|------|----------|-------------|
| `media` | file | 是 | 源音频/视频文件 |

#### 输出（主要字段）

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `format` | string | 容器格式（例如 `mp4`、`mkv`、`wav`） |
| `duration` | float | 时长（秒） |
| `bitrate` | integer | 总比特率（bit/s） |
| `video_streams` | list | 每条视频流一项（codec、width、height、fps 等） |
| `audio_streams` | list | 每条音频流一项（codec、sample_rate、channels 等） |
| `raw` | object | 原始 ffprobe JSON |

### 2. AV 摘要

**说明**：将 ffprobe 负载精简为简短摘要 —— 适用于日志、快速 UI 展示或路由决策。

#### 输入参数

| 参数 | 类型 | 必需 | 说明 |
|-----------|------|----------|-------------|
| `media` | file | 是 | 源音频/视频文件 |

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `format` | string | 容器格式 |
| `duration` | float | 时长（秒） |
| `size` | integer | 文件大小（字节） |
| `video` | object \| null | 主视频流，若无则为 `null` |
| `audio` | object \| null | 主音频流，若无则为 `null` |

### 3. 检查图像 (exiftool)

**说明**：图像文件的 EXIF/XMP/GPS 元数据。若嵌入了相机设置（ISO、光圈、焦距）和 GPS 坐标也会一并返回。

#### 输入参数

| 参数 | 类型 | 必需 | 说明 |
|-----------|------|----------|-------------|
| `image` | file | 是 | 源图像文件（JPEG、PNG、HEIC 等） |

#### 输出（主要字段）

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `width`、`height` | integer | 图像尺寸 |
| `camera` | object | 制造商/型号/镜头 + 曝光设置 |
| `gps` | object \| null | 纬度/经度/海拔，若未嵌入则为 `null` |
| `metadata.exif` | object | EXIF 标签块 |
| `metadata.xmp` | object | XMP 标签块 |

## 提示

- **按用途选择驱动**：需要流级别的细节（编解码器、采样率、fps）时使用 `ffmpeg`；需要嵌入元数据（EXIF、XMP、GPS）时使用 `exiftool`。若两者都需要，可在同一 compose 文件中针对同一或不同组件运行两个 inspector 组件。
- **生产环境请设置 `return_raw: false`**：`raw` 负载冗长，仅在探索字段/调试时有用。
- **流式输入会被 spool**：非文件源（上传、HTTP 流）会先写入临时文件再进行探测，因为两种工具都需要可 seek 的输入。

## 故障排查

### 常见问题

1. **`ffprobe` / `exiftool` not found**：安装缺失的工具，并确保其在 `PATH` 中可用。
2. **`raw` 负载过大**：在 action 上设置 `return_raw: false`，或通过工作流的 `output:` 仅映射所需字段。
3. **某些输入的 `fps: null`**：ffprobe 对未知帧率会返回 `0/0`，驱动将其规范化为 `null`，以便调用方区分"无 fps 信息"与"零 fps"。
