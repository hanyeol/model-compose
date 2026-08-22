# 音频采集示例

本示例演示 `audio-capture` 组件：采集本地麦克风或系统音频（回环），并将编码后的音频作为 AAC 流**直接返回在 HTTP 响应中**——没有文件存储，也没有中间缓冲。

## 概述

两个工作流共享一个 `audio-capture` 组件:

1. **Capture Microphone** — 采集默认麦克风。仅需麦克风权限,是对管道进行冒烟测试的最快方法。
2. **Capture System Audio** — 采集操作系统正在播放的音频（回环）。macOS 需要 [`audiotee`](https://github.com/makeusabrew/audiotee) 辅助工具；Windows 使用 DirectShow 的 `virtual-audio-capturer`；Linux 使用默认 sink 的 PulseAudio monitor。

两个工作流都编码为 AAC（ADTS），字节一旦可用就以流式返回响应，因此下游消费者无需等待采集结束即可开始解码。

## 准备工作

### 前置条件

- model-compose 已安装并在 PATH 中
- 系统已安装 `ffmpeg`
- **仅 macOS 系统音频需要**: 系统 PATH 中有 [`audiotee`](https://github.com/makeusabrew/audiotee) CLI。用 `brew install audiotee` 安装。麦克风采集不需要。

### 平台权限

首次运行各工作流时:

- **macOS 麦克风** 会请求"麦克风"权限。
- **macOS 系统音频** 还会额外请求一次 `audiotee` 的 Core Audio process-tap 权限。
- **Windows / Linux** 依赖当前用户会话的权限，不会弹出提示。

### 查找音频设备

平台默认值可覆盖常见场景。若有多个输入设备或想指定特定设备，请先列出设备:

```bash
# macOS
ffmpeg -f avfoundation -list_devices true -i ""

# Windows
ffmpeg -f dshow -list_devices true -i dummy

# Linux
pactl list sources short
```

在动作中通过 `device` 指定（见下文[自定义](#自定义)）。

### 设置

```bash
cd examples/media-processing/audio-capture
```

## 运行方式

1. **启动服务:**
   ```bash
   model-compose up
   ```

   - API 端点: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **运行工作流:**

   **使用 CLI（将流式 AAC 保存到本地文件）:**
   ```bash
   # 10 秒麦克风片段 → mic.aac
   model-compose run capture-microphone \
     --input '{"duration": "10s"}' \
     --output mic.aac

   # 10 秒系统音频片段 → system.aac
   model-compose run capture-system-audio \
     --input '{"duration": "10s"}' \
     --output system.aac
   ```

   **使用 API (curl):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow": "capture-microphone", "input": {"duration": "5s"}}' \
     --output mic.aac
   ```

   **播放结果:**
   ```bash
   open mic.aac         # macOS
   xdg-open mic.aac     # Linux
   start mic.aac        # Windows
   ```

   或打开 http://localhost:8081 的 Web UI，编码后的音频将直接在浏览器中播放。

## 组件详情

### Audio Capture 组件

- **类型**: `audio-capture`
- **用途**: 本地麦克风或系统音频回环的实时采集
- **驱动**: `ffmpeg` — 自动选择 `avfoundation`（macOS）/ `dshow`（Windows）/ `pulse`（Linux）。macOS 系统音频还会启动 `audiotee` sidecar。
- **默认编解码器/容器**: 用 ADTS 封装的 `aac`

## 工作流详情

### 1. Capture Microphone

**ID**: `capture-microphone`
**说明**: 采集默认麦克风并以 AAC 流式返回响应。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|-----|------|------|--------|-----|
| `duration` | string | 否 | `10s` | 采集时长（如 `10s`、`30s`、`2m`）|

#### 输出

响应体本身就是 AAC（ADTS）流。通过 `model-compose run --output` 调用时，将字节保存为 `.aac` 文件后用任意媒体播放器或浏览器播放即可。

---

### 2. Capture System Audio

**ID**: `capture-system-audio`
**说明**: 采集操作系统正在播放的音频（回环）并以 AAC 流式返回响应。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|-----|------|------|--------|-----|
| `duration` | string | 否 | `10s` | 采集时长 |

#### 输出

与麦克风相同的结构: 响应体中的 AAC 字节。

#### 平台说明

- **macOS** 需要 PATH 中有 `audiotee`。首个系统音频块可能需要约 4~5 秒才能到达，这是 Core Audio process-tap 的启动特性，并非驱动问题。
- **Windows** 依赖 `virtual-audio-capturer` DirectShow 设备。若尚未安装，请安装 [screen-capture-recorder](https://github.com/rdp/screen-capture-recorder-to-video-windows-free)。
- **Linux** 读取默认 sink 的 PulseAudio monitor（`default.monitor`）。PipeWire 的 PulseAudio 兼容层同样有效。

## 自定义

### 选择特定设备

在动作中添加 `device` 以按索引或名称指定输入设备:

```yaml
- id: microphone
  source: microphone
  device: 1                          # macOS avfoundation 索引（见上文 `-list_devices`）
  # device: "Microphone (USB Audio)"  # Windows: 名称需完全匹配
  # device: "alsa_input.usb-...-mono" # Linux（来自 `pactl list sources short`）
  duration: ${input.duration}
```

### 修改采样率或声道数

语音识别管道通常需要 16 kHz 单声道；默认值由设备自行选择。在源端下采样和下混以节省带宽:

```yaml
- id: microphone
  source: microphone
  sample_rate: 16000
  channels: 1
  duration: ${input.duration}
```

### 覆盖编解码器或比特率

在动作上显式设置 `encoding`:

```yaml
- id: microphone
  source: microphone
  ...
  encoding:
    format: m4a          # 或 ogg、mp3、wav 等
    audio:
      codec: aac         # ogg 用 libopus
      bitrate: 192k
```

以视频为主的容器（`mp4`、`webm`）会自动映射到对应的仅音频容器（`m4a`、`ogg`），确保下游工具始终能拿到可解码的音频流。

### 无限时长采集

从输入中去掉 `duration`（或设为 null），采集会一直进行,直到客户端关闭连接。适合由消费者决定何时停止的场景；对于上文"保存到文件"的演示意义不大，因为响应只在采集停止后才完成。
