# 视频采集示例

本示例演示 `video-capture` 组件：采集本地摄像头，并将编码后的视频作为 fragmented MP4 流**直接返回在 HTTP 响应中**——没有文件存储，也没有中间缓冲。

任何被操作系统暴露为摄像头的设备都可以使用：物理网络摄像头、USB 采集卡以及虚拟摄像头（OBS Virtual Camera、Snap Camera 等）在 ffmpeg 看来都是普通的视频设备。

## 概述

单个工作流 `capture-webcam` 打开默认摄像头，编码为 fragmented MP4 流并作为 HTTP 响应返回。第一个 fragment 到达时就可以开始播放,所以支持 MP4 over HTTP 的下游工具无需等待采集结束即可开始解码。

macOS 上编码器默认使用 `h264_videotoolbox`（硬件），使 1080p30 保持实时；Windows 和 Linux 上默认使用 `libx264`。

## 准备工作

### 前置条件

- model-compose 已安装并在 PATH 中
- 系统已安装 `ffmpeg`（macOS 的 Homebrew 版本已带硬件编码器支持）

### 平台权限

首次运行摄像头采集时：

- **macOS** 会请求"摄像头"权限。拒绝将得到空流，而非异常。
- **Windows** 和 **Linux** 依赖当前用户会话的设备权限，不会弹出提示。

### 查找摄像头

平台默认值可覆盖常见场景。若有多个摄像头或想指定虚拟摄像头,请先列出设备:

```bash
# macOS
ffmpeg -f avfoundation -list_devices true -i ""

# Windows
ffmpeg -f dshow -list_devices true -i dummy

# Linux
v4l2-ctl --list-devices
```

在动作中通过 `device` 指定（见下文[自定义](#自定义)）。

### 设置

```bash
cd examples/media-processing/video-capture
```

## 运行方式

1. **启动服务:**
   ```bash
   model-compose up
   ```

   - API 端点: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **运行工作流:**

   **使用 CLI（将流式 MP4 保存到本地文件）:**
   ```bash
   # 10 秒 720p 30fps 采集 → webcam.mp4
   model-compose run capture-webcam \
     --input '{"duration": "10s", "framerate": 30, "width": 1280, "height": 720}' \
     --output webcam.mp4
   ```

   **使用 API (curl):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow": "capture-webcam", "input": {"duration": "5s"}}' \
     --output webcam.mp4
   ```

   **播放结果:**
   ```bash
   open webcam.mp4         # macOS
   xdg-open webcam.mp4     # Linux
   start webcam.mp4        # Windows
   ```

   或打开 http://localhost:8081 的 Web UI，编码后的视频将直接在浏览器中播放。

## 组件详情

### Video Capture 组件

- **类型**: `video-capture`
- **用途**: 本地摄像头 / 采集卡 / 虚拟摄像头的实时采集
- **驱动**: `ffmpeg` — 自动选择 `avfoundation`（macOS）/ `dshow`（Windows）/ `v4l2`（Linux）
- **默认编码器**: macOS 上为 `h264_videotoolbox`，其他平台为 `libx264`

## 工作流详情

### Capture Webcam

**ID**: `capture-webcam`
**说明**: 将 fragmented MP4 直接流式返回到 HTTP 响应的摄像头采集。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|-----|------|------|--------|-----|
| `duration` | string | 否 | `10s` | 采集时长（如 `10s`、`30s`、`2m`）|
| `framerate` | number | 否 | `30` | 视频帧率 |
| `width` | integer | 否 | `1280` | 帧宽度（像素）|
| `height` | integer | 否 | `720` | 帧高度（像素）|

#### 输出

响应体本身就是 fragmented MP4 流。通过 `model-compose run --output` 调用时，将字节保存为 `.mp4` 文件后用任意媒体播放器或浏览器播放即可。

## 自定义

### 选择特定摄像头

在动作中添加 `device` 以按索引或名称指定摄像头:

```yaml
- id: webcam
  source: camera
  device: 1               # macOS avfoundation 索引（见上文 `-list_devices`）
  # device: "OBS Virtual Camera"      # macOS/Windows: 名称需完全匹配
  # device: /dev/video2               # Linux
  framerate: ${input.framerate}
  ...
```

Windows 上 `device` 是必填项——dshow 不支持数字索引，必须传入设备名称。

### 更高的分辨率或帧率

在请求中提高 `width`/`height`/`framerate`:

```bash
model-compose run capture-webcam \
  --input '{"width": 1920, "height": 1080, "framerate": 60, "duration": "5s"}' \
  --output webcam-1080p60.mp4
```

macOS 默认编码器（`h264_videotoolbox`）可轻松处理 1080p60。若 Windows/Linux 上的 `libx264` 无法实时跟上 1080p60，可提高 `encoding.video.bitrate`，或将编解码器覆盖为硬件编码器（NVIDIA 用 `h264_nvenc`，Intel Quick Sync 用 `h264_qsv`，Linux VA-API 用 `h264_vaapi`）。

### 覆盖编解码器或比特率

在动作上显式设置 `encoding`:

```yaml
- id: webcam
  source: camera
  ...
  encoding:
    format: mp4
    video:
      codec: h264_nvenc   # 或 libx264、h264_qsv、h264_vaapi 等
      bitrate: 8M
```

### 使用其他容器格式

将 `encoding.format` 改为 `ts`（MPEG-TS——首字节延迟低，即使采集中断也可播放）或 `webm`（VP9）。当格式为 `mp4` / `mov` / `m4v` 时，fragmented MP4 参数会自动加入,因此可直接通过 HTTP 流式传输，无需额外调整。

### 无限时长采集

从输入中去掉 `duration`（或设为 null），采集会一直进行，直到客户端关闭连接。适合由消费者决定何时停止的场景；对于上文"保存到文件"的演示意义不大，因为响应只在采集停止后才完成。
