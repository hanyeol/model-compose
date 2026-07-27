# 屏幕采集示例

本示例演示 `screen-capture` 组件：将本地屏幕、屏幕区域或麦克风作为连续编码流采集，并通过 `file-store` 写入本地文件。

## 概述

三个工作流展示 MVP 的三种采集模式：

1. **采集桌面片段** — 按指定帧率采集整个显示器，保存为 MPEG-TS 片段
2. **采集屏幕区域** — 采集显示器的矩形区域（Windows/Linux 使用原生区域参数，macOS 通过解码后的裁剪滤镜实现）
3. **采集麦克风音频** — 仅从默认麦克风采集音频，保存为 AAC（无需屏幕录制权限）

## 准备工作

### 前置条件

- model-compose 已安装并在 PATH 中
- 系统已安装 `ffmpeg`
- 本示例不使用 macOS 系统音频采集；若需要，则还需 [`audiotee`](https://github.com/makeusabrew/audiotee) CLI。仅麦克风采集无需 audiotee。

### 平台权限

首次运行视频采集时：

- **macOS** 会请求屏幕录制权限。拒绝时不会抛异常，只会得到空流。
- **Linux Wayland** 每次会话都需要通过 PipeWire 门户批准。

麦克风采集使用独立的 OS 权限（麦克风），因此在 macOS 上无需授予屏幕录制权限即可冒烟测试。

### macOS 显示器索引

在 macOS 上，`display` 字段实际上是 avfoundation 设备索引，它排在视频摄像头之后。运行以下命令查看：

```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

查找 `[4] Capture screen 0` 之类的行，并通过 `--input '{"display": 4}'` 传入。在 Windows 和 Linux 上，默认 `0` 通常可用。

### 环境设置

```bash
cd examples/media-processing/screen-capture
```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081
   - 采集的片段写入本目录下的 `./output/`。

2. **运行工作流：**

   **使用 CLI：**
   ```bash
   # 15 fps 的 5 秒桌面片段（macOS：调整 display 索引）
   model-compose run capture-desktop-clip --input '{"duration": "5s", "framerate": 15, "display": 0}'

   # 从左上角偏移 100px 的 720p 区域，3 秒
   model-compose run capture-region-clip --input '{
     "duration": "3s",
     "x": 100,
     "y": 100,
     "width": 1280,
     "height": 720
   }'

   # 3 秒麦克风片段
   model-compose run capture-microphone-clip --input '{"duration": "3s"}'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow": "capture-desktop-clip", "input": {"duration": "5s"}}'
   ```

3. **查看输出：**

   ```bash
   ls -lh output/
   ffprobe output/desktop-*.ts
   ```

## 组件详情

### 屏幕采集组件

- **类型**：`screen-capture`
- **用途**：本地显示器与系统/麦克风音频的实时采集
- **驱动**：`ffmpeg`（自动识别 OS：视频用 avfoundation / gdigrab / x11grab，麦克风用 avfoundation / dshow / pulse）

### 文件存储组件

- **类型**：`file-store`
- **用途**：将编码后的流分块随到随写入本地文件

## 工作流详情

### 1. 采集桌面片段

**ID**：`capture-desktop-clip`
**描述**：在限定时长内采集整个显示器，保存为 MPEG-TS。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `duration` | string | 否 | `5s` | 采集时长（如 `5s`、`30s`、`2m`） |
| `framerate` | number | 否 | `15` | 视频帧率 |
| `display` | integer | 否 | `0` | 显示器 / avfoundation 设备索引（参考上文 macOS 说明） |
| `filename` | string | 否 | 时间戳 | 可选的文件名词干（不含扩展名） |

#### 输出

```json
{ "file": "output/desktop-1730000000.ts" }
```

---

### 2. 采集屏幕区域

**ID**：`capture-region-clip`
**描述**：仅采集矩形区域。Windows `gdigrab` 和 Linux `x11grab` 原生支持区域参数，macOS 通过解码后的 `-vf crop` 滤镜实现。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `duration` | string | 否 | `5s` | 采集时长 |
| `framerate` | number | 否 | `15` | 视频帧率 |
| `display` | integer | 否 | `0` | 显示器 / avfoundation 设备索引 |
| `x` | integer | 否 | `0` | 区域左边界（像素） |
| `y` | integer | 否 | `0` | 区域上边界（像素） |
| `width` | integer | 否 | `640` | 区域宽度（像素） |
| `height` | integer | 否 | `480` | 区域高度（像素） |
| `filename` | string | 否 | 时间戳 | 可选的文件名词干 |

#### 输出

```json
{ "file": "output/region-1730000000.ts" }
```

---

### 3. 采集麦克风音频

**ID**：`capture-microphone-clip`
**描述**：仅音频采集。绕过屏幕录制权限，是最方便的冒烟测试方式。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `duration` | string | 否 | `3s` | 采集时长 |
| `filename` | string | 否 | 时间戳 | 可选的文件名词干 |

#### 输出

```json
{ "file": "output/mic-1730000000.aac" }
```

## 自定义

### 更改容器格式

默认选择 MPEG-TS 是因为首字节延迟低且对中断具备容错。若要输出 MP4 或 WebM，在动作上设置 `encoding.format`：

```yaml
- id: desktop
  video_source: display
  encoding:
    format: mp4         # 管道输出所需的 fragmented mp4 标志会自动追加
    video:
      codec: libx264
      bitrate: 6M
```

记得同步修改 `save` job 中的 `path` 扩展名。

### 无界采集

删除 `duration` 即可持续流式采集，直到消费方（本示例中的 `file-store`）关闭。适用于下游决定停止时机的场景；但本示例的文件写入演示必须等采集停止才能完成工作流，因此实用性有限。

### 系统音频（macOS）

macOS 禁止 ffmpeg 直接回放系统音频。要采集扬声器正在播放的声音，需要安装 [`audiotee`](https://github.com/makeusabrew/audiotee)，然后在动作上设置 `audio_source: system`。由于 Core Audio process-tap API 的特性，从启动到首个块到达约有 4–5 秒的延迟。
