# Video Processor 示例

本示例展示了 `video-processor` 组件，该组件使用 ffmpeg 对视频应用逐帧变换（resize、crop、pad、flip、rotate）。由于每个方法都会安装一个 ffmpeg 视频滤镜，视频轨道始终会被重新编码；音频轨道默认使用 stream copy，因此保持无损。

## 概述

该示例基于同一个 `video-processor` 组件提供五个工作流：

1. **Resize Video**：使用 `fit`、`fill` 或 `stretch` 方式重新缩放视频
2. **Crop Video**：从每一帧中裁剪矩形区域
3. **Pad Video**：在视频周围添加纯色边框
4. **Flip Video**：水平或垂直翻转视频
5. **Rotate Video**：以任意角度旋转视频，可选择扩展画布

## 准备工作

### 前置要求

- 已安装并在 PATH 中的 model-compose
- 已安装并在 PATH 中的 [ffmpeg](https://ffmpeg.org/)

### 设置

进入示例目录：
```bash
cd examples/media-processing/video-processor
```

验证 ffmpeg 安装：
```bash
ffmpeg -version
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

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 从下拉菜单选择工作流
   - 上传视频文件并填写参数
   - 点击 "Run Workflow"

   **使用 CLI：**
   ```bash
   # 在指定框内保持宽高比缩放到 960x540
   model-compose run resize --input '{
     "video": "/path/to/input.mp4",
     "width": 960,
     "height": 540,
     "scale_mode": "fit"
   }'

   # 从 (100, 50) 开始裁剪 640x360 区域
   model-compose run crop --input '{
     "video": "/path/to/input.mp4",
     "x": 100,
     "y": 50,
     "width": 640,
     "height": 360
   }'

   # 四周添加 20px 的红色边框
   model-compose run pad --input '{
     "video": "/path/to/input.mp4",
     "left": 20, "right": 20, "top": 20, "bottom": 20,
     "color": "red"
   }'

   # 垂直翻转
   model-compose run flip --input '{
     "video": "/path/to/input.mp4",
     "direction": "vertical"
   }'

   # 逆时针旋转 90 度并扩展画布
   model-compose run rotate --input '{
     "video": "/path/to/input.mp4",
     "angle": 90,
     "expand": true
   }'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=resize" \
     -F "video=@/path/to/input.mp4" \
     -F "width=960" \
     -F "height=540" \
     -F "scale_mode=fit"
   ```

## 组件详情

### Video Processor 组件

- **类型**：`video-processor`
- **驱动**：`ffmpeg`
- **用途**：通过 ffmpeg 视频滤镜对视频应用逐帧变换（resize、crop、pad、flip、rotate）。视频轨道会被重新编码；音频轨道默认使用 stream copy。

#### 通用字段

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|-------|------|----------|---------|-------------|
| `method` | string | 是 | - | `resize`、`crop`、`pad`、`flip`、`rotate` 之一 |
| `video` | 视频源 | 是 | - | 输入视频（文件路径、上传或上游视频引用） |
| `encoding` | 对象 | 否 | - | 输出编码覆盖（`format`、`video.codec`、`video.bitrate` 等）。未设置时容器沿用输入格式，音频轨道使用 stream copy |
| `batch_size` | integer | 否 | `1` | 当输入是列表/流时每批处理的视频数量。批次内并发执行 |

未提供 `encoding` 时，容器沿用输入格式（否则回退到 `mp4`），视频编解码器从容器默认值中选择（例如 `mp4` 使用 `libx264`，`webm` 使用 `libvpx-vp9`），音频轨道逐字节复制。

## 工作流详情

### 1. Resize Video

**说明**：使用可配置的缩放行为将视频缩放到目标 `(width, height)` 框。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `video` | file | 是 | - | 源视频文件 |
| `width` | integer | 是 | - | 目标宽度（像素） |
| `height` | integer | 是 | - | 目标高度（像素） |
| `scale_mode` | select | 否 | `fit` | `fit`（信箱模式适配内部）、`fill`（填满并居中裁剪）或 `stretch`（忽略宽高比） |

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `video` | video | 缩放后的视频 |

### 2. Crop Video

**说明**：从每一帧中提取矩形区域。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `video` | file | 是 | - | 源视频文件 |
| `x` | integer | 否 | `0` | 裁剪左上角的 X 坐标 |
| `y` | integer | 否 | `0` | 裁剪左上角的 Y 坐标 |
| `width` | integer | 是 | - | 裁剪宽度（像素） |
| `height` | integer | 是 | - | 裁剪高度（像素） |

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `video` | video | 裁剪后的视频 |

### 3. Pad Video

**说明**：在不改变帧内容的情况下为视频添加纯色边框。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `video` | file | 是 | - | 源视频文件 |
| `left` | integer | 否 | `0` | 左侧填充（像素） |
| `right` | integer | 否 | `0` | 右侧填充（像素） |
| `top` | integer | 否 | `0` | 上方填充（像素） |
| `bottom` | integer | 否 | `0` | 下方填充（像素） |
| `color` | string | 否 | `black` | 边框颜色。支持 ffmpeg 颜色名称（`black`、`red`、`white`）、hex 字符串（`#ff0000`、`#00ff00ff`）或 RGBA 元组 |

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `video` | video | 添加填充后的视频 |

### 4. Flip Video

**说明**：沿指定轴翻转视频。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `video` | file | 是 | - | 源视频文件 |
| `direction` | select | 否 | `horizontal` | 翻转轴：`horizontal` 或 `vertical` |

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `video` | video | 翻转后的视频 |

### 5. Rotate Video

**说明**：将每一帧逆时针旋转 `angle` 度。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `video` | file | 是 | - | 源视频文件 |
| `angle` | number | 是 | - | 旋转角度（度，逆时针） |
| `expand` | boolean | 否 | `true` | 为 `true` 时扩展画布使旋转后的帧完整放在透明背景中；为 `false` 时保持原始帧尺寸并裁剪溢出部分 |

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `video` | video | 旋转后的视频 |

## 提示

- **视频重新编码，音频不变**：滤镜图会解码帧，因此 `-c:v copy` 不可行；视频轨道始终会重新编码。除非通过 `encoding.audio.codec` 覆盖，否则音频轨道使用 `-c:a copy`。
- **输出容器**：如果没有显式的 `encoding.format`，输出容器会沿用输入格式（否则回退到 `mp4`）。提供 `encoding` 可以一次性切换容器（`mp4` → `webm`）、编解码器（`libx264` → `libvpx-vp9`）、比特率、分辨率或帧率。
- **旋转方向**：`angle` 与 `image-processor` 的 `rotate` 一致，为逆时针度数。内部会将 ffmpeg 的 `rotate` 滤镜（顺时针弧度）取反后传入。
- **仅指定单轴的等比缩放**：将 `width` 或 `height` 之一留空，缺失的维度会根据源宽高比自动推导。
- **批次并行**：当输入是视频列表时，批次内的 ffmpeg 子进程并发运行。使用 `batch_size` 限制同时处理的视频数量。

## 故障排查

### 常见问题

1. **ffmpeg not found**：确保 ffmpeg（以及 ffprobe）已安装并在 `PATH` 中可用。
2. **不支持的编解码器/容器组合**：覆盖 `encoding` 时可能出现 ffmpeg 无法 mux 的组合（例如 `avi` 中的 `vp9`）。请选择与目标容器兼容的编解码器，或不设置 `encoding` 以接受容器默认编解码器。
3. **旋转裁掉了角落**：`expand: false` 时输出尺寸与输入相同，旋转帧的角落会被裁剪。若要保留全部内容，设置 `expand: true`。
4. **fit / fill 与 stretch**：`fit` 是信箱模式（添加透明填充以保持宽高比），`fill` 是填满并居中裁剪溢出，`stretch` 忽略宽高比按指定尺寸拉伸。
