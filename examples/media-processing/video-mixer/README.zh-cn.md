# 视频混合器示例

本示例演示 `video-mixer` 组件，使用 ffmpeg 将多个视频合成为一个输出。
涵盖两种混合方式：

- **concat**：将多个视频首尾拼接为一个更长的视频
- **overlay**：将一个或多个视频叠加到基础视频之上
  （水印、画中画、并排布局等）

## 概览

本示例基于同一个 `video-mixer` 组件暴露三个工作流：

1. **Concatenate Videos**：将一组视频拼接为单个输出
2. **Overlay Single Video**：在基础视频上叠加一个覆盖层
   （水印 / 画中画）
3. **Overlay Multiple Videos**：在基础视频上叠加多个覆盖层，
   每个都有独立的位置

## 准备

### 前置条件

- 已安装 model-compose 并加入 PATH
- 已安装 [ffmpeg](https://ffmpeg.org/) 并加入 PATH

### 设置

进入示例目录：
```bash
cd examples/media-processing/video-mixer
```

确认 ffmpeg 已安装：
```bash
ffmpeg -version
```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

   服务将启动：
   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081

2. **运行工作流：**

   **通过 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 从下拉菜单选择工作流
   - 上传所需的视频文件并设置位置字段
   - 点击 "Run Workflow"

   **通过 CLI：**
   ```bash
   # 将两个片段拼接为一个视频
   model-compose run concat --input '{
     "first": "/path/to/intro.mp4",
     "second": "/path/to/main.mp4"
   }'

   # 在基础视频上合成画中画
   model-compose run overlay-single --input '{
     "base": "/path/to/lecture.mp4",
     "overlay": "/path/to/webcam.mp4",
     "x": 20,
     "y": 20,
     "width": 320
   }'

   # 在基础视频上叠加两个覆盖层，各自使用不同位置
   model-compose run overlay-multiple --input '{
     "base": "/path/to/main.mp4",
     "overlay_a": "/path/to/left.mp4",
     "overlay_b": "/path/to/right.mp4"
   }'
   ```

   **通过 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=overlay-single" \
     -F "base=@/path/to/lecture.mp4" \
     -F "overlay=@/path/to/webcam.mp4" \
     -F "x=20" \
     -F "y=20" \
     -F "width=320"
   ```

## 组件详情

### Video Mixer 组件

- **Type**：`video-mixer`
- **Driver**：`ffmpeg`
- **用途**：使用 ffmpeg 滤镜（`concat` 用于拼接，`overlay` 用于合成）
  将多个视频合并为一个输出。

由于 ffmpeg 滤镜图无法在流复制（stream-copy）输入上工作，混合过程中
视频总是会被重新编码。`encoding` 字段控制输出容器/编解码器；
若未指定，则会为每种格式选择合理默认值（mp4 → libx264 + aac，
webm → libvpx-vp9 + libopus，...）。

### Concat 方式

使用 ffmpeg 的 `concat` 滤镜将视频首尾拼接。所有输入必须具有相同的
分辨率、SAR、像素格式、帧率、音频采样率和声道布局 —— 否则 concat
滤镜会以 `Input link ... parameters do not match` 报错。请在上游
(例如 `video-converter` 组件) 对输入进行归一化后再送入 `concat`。

通过 `encoding` 字段的重新编码只控制输出流；它不会协调不匹配的输入。
视频和音频轨都会被拼接；没有音频的输入会以静音填充。

#### 关键字段

| 字段 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `videos` | 视频源列表 | 是 | - | 需要拼接的视频，按顺序（至少 2 个）|
| `crossfade` | duration | 否 | - | 为将来预留，目前未实现 |
| `encoding` | object | 否 | mp4 默认值 | 输出容器/编解码器 |
| `batch_size` | integer | 否 | `1` | 当 `videos` 为列表的列表或流时，每批处理的输入*集合*数量 |
| `streaming` | boolean | 否 | `false` | 将输出作为字节流发出，而非临时文件 |

### Overlay 方式

在基础视频之上合成一个或多个覆盖层。覆盖层按列表顺序堆叠 —— 第一个
落在基础上，第二个落在其结果上，依此类推 —— 因此索引越靠后的
覆盖层显示得越靠上。

#### 关键字段

| 字段 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | 视频源或列表 | 是 | - | 基础视频（列表将启用批处理模式：每个 base 一个输出）|
| `overlay` | 字符串或字符串列表 | 是 | - | 覆盖视频。单个字符串会自动包装为一个元素的列表 |
| `placement` | object 或 object 列表 | 否 | 一个默认 placement | 每个覆盖层一个 placement。单个 object 广播到所有覆盖层；列表按位置匹配 |
| `audio_mode` | `base` \| `overlay` \| `mix` \| `none` | 否 | `base` | 输出携带哪些音频轨 |
| `duration_mode` | `base` \| `longest` \| `shortest` | 否 | `base` | 输出相对于 base 和覆盖层运行多久 |
| `encoding` | object | 否 | mp4 默认值 | 输出容器/编解码器 |
| `batch_size` | integer | 否 | `1` | 当 `video` 为列表/流时，每批处理的基础视频数量 |
| `streaming` | boolean | 否 | `false` | 将输出作为字节流发出，而非临时文件 |

#### Placement 字段

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `x` | integer | `0` | 覆盖层在基础视频上放置的 X 坐标 |
| `y` | integer | `0` | 覆盖层在基础视频上放置的 Y 坐标 |
| `width` | integer | - | 将覆盖层缩放到指定宽度（仅设置一个维度时保持宽高比）|
| `height` | integer | - | 将覆盖层缩放到指定高度 |
| `anchor` | `top-left` \| `top-center` \| `top-right` \| `center-left` \| `center` \| `center-right` \| `bottom-left` \| `bottom-center` \| `bottom-right` | `top-left` | 覆盖层与 `(x, y)` 对齐的锚点 |
| `opacity` | float 0..1 | `1.0` | Alpha 乘数 |
| `start` | duration | - | 覆盖层出现的时间（默认 `0s`）|
| `end` | duration | - | 覆盖层消失的时间（默认运行到 base 结束）|

`start`/`end` 接受：
- 数字（秒）：`10`、`10.5`
- Duration 字符串：`"10s"`、`"1m"`、`"250ms"`
- 时间码：`"00:00:10"`、`"01:23:45"`

#### 音频策略

- **base**：仅保留基础视频的音频轨（水印 / 画中画 常用）
- **overlay**：仅保留覆盖层的音频轨；多个覆盖层的音频会被混合
- **mix**：将基础和所有覆盖层的音频轨混合
- **none**：去除输出中的音频

#### 时长策略

- **base**（默认）：base 结束时输出停止。早于 base 结束的覆盖层会
  消失；超过 base 的覆盖层会被截断。
- **longest**：输出运行到最后一个流结束。通过克隆 base 的最后一帧
  (`tpad`) 将其延长到自身结束之后，使 overlay 滤镜能继续合成。
- **shortest**：任何输入（base 或 overlay）一结束，输出立即停止。
  适用于让覆盖层决定总时长的场景。

`base` 会对 base 运行一次 `ffprobe` 以限制输出长度；`longest` 会 probe
每个输入以计算填充长度；`shortest` 不做 probe。

## 工作流详情

### 1. Concatenate Videos

**描述**：通过 ffmpeg 的 `concat` 滤镜重新编码并将两个视频拼接为
一个。

#### 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `first` | file | 是 | 输出中先出现的视频 |
| `second` | file | 是 | 输出中后出现的视频 |

#### 输出

| 字段 | 类型 | 描述 |
|------|------|------|
| `video` | video | 拼接后的结果 |

### 2. Overlay Single Video

**描述**：在基础视频上放置一个覆盖层（水印、画中画等）。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `base` | file | 是 | - | 基础视频 |
| `overlay` | file | 是 | - | 覆盖视频 |
| `x` | integer | 否 | `20` | 基础视频上的 X 坐标 |
| `y` | integer | 否 | `20` | 基础视频上的 Y 坐标 |
| `width` | integer | 否 | `320` | 将覆盖层缩放到指定宽度 |

#### 输出

| 字段 | 类型 | 描述 |
|------|------|------|
| `video` | video | 顶部合成了覆盖层的基础视频 |

### 3. Overlay Multiple Videos

**描述**：在基础视频上合成两个覆盖层，各自具有独立位置。覆盖层按
列表顺序堆叠。

#### 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `base` | file | 是 | 基础视频 |
| `overlay_a` | file | 是 | 第一个覆盖层（若与 `overlay_b` 重叠则位于其下方）|
| `overlay_b` | file | 是 | 第二个覆盖层（若与 `overlay_a` 重叠则位于其上方）|

#### 输出

| 字段 | 类型 | 描述 |
|------|------|------|
| `video` | video | 顶部合成了两个覆盖层的基础视频 |

## 提示

- **重新编码不可避免**：混合操作通过 ffmpeg 滤镜图运行，无法在流复制
  输入上工作。如果默认值与目标容器不符，请提供 `encoding`。
- **Placement 广播**：单个 `placement` object 会应用到每个覆盖层。
  仅当覆盖层需要不同的坐标、尺寸或时间时才使用列表。
- **覆盖层堆叠**：列表中的第一个覆盖层先被合成，因此当区域重叠时，
  靠后的覆盖层显示在上方。请按从底到顶的顺序排列列表。
- **Anchor 语义**：`anchor` 相对于 `(x, y)` 移动覆盖层。例如
  `anchor: center` 将覆盖层的*中心*而非左上角对齐到 `(x, y)`。
- **时间限定的覆盖层**：`start`/`end` 让覆盖层仅在某个时间窗口内可见
  —— 适用于只出现几秒的字幕条或稍后淡入的水印。
- **批处理模式**：传入基础视频列表会为每个 base 执行一次 overlay
  操作，并返回输出列表。除非按 base 参数化，否则相同的覆盖层集合会
  广播到每个 base。
- **流式输入**：非文件的视频源（字节、HTTP 上传）会在混合前假脱机到
  临时文件，以便 ffmpeg 可以对其进行 seek。

## 故障排除

### 常见问题

1. **未找到 ffmpeg**：确保 ffmpeg 已安装并在 `PATH` 中。
2. **`'videos' must contain at least two entries for concat`**：concat
   至少需要两个输入。单视频操作请使用 `overlay` 或其他组件。
3. **concat 时 `Input link ... parameters do not match`**：ffmpeg
   concat 滤镜要求每个输入具有相同的分辨率、SAR、像素格式、帧率、
   音频采样率和声道布局。拼接前使用 `video-converter` 之类的组件对
   输入进行归一化。
4. **`overlay/placement cardinality mismatch`**：当 `placement` 为
   列表时，其长度必须等于覆盖层的数量。单个 placement object 会广播到
   每个覆盖层。
5. **overlay-multiple 中 z 顺序错误**：覆盖层按列表顺序堆叠（第一个
   先绘制，最后一个显示在上方）。重新排列列表以更改堆叠顺序。
6. **使用 `audio_mode: overlay` 时输出静音**：覆盖视频可能没有音频轨。
   如果要保留 base 的音频，请切换到 `audio_mode: base` 或
   `audio_mode: mix`。
7. **concat 后格式不匹配**：输出格式取自 `encoding.format`（默认：
   `mp4`）。如果输入使用了非常规编解码器，请显式设置
   `encoding.video.codec` / `encoding.audio.codec`。
