# 音频混合器示例

本示例演示 `audio-mixer` 组件，使用 ffmpeg 将多个音频源合并为一个
输出。涵盖两种混合方式：

- **concat**：将多个音频首尾拼接为一个更长的音频
- **overlay**：将一个或多个覆盖音频混入基础音频
  （旁白之下的背景音乐、多层音效等）

## 概览

本示例基于同一个 `audio-mixer` 组件暴露三个工作流：

1. **Concatenate Audios**：将一组音频拼接为单个输出
2. **Overlay Single Audio**：将一个覆盖层混入基础音频，可配置
   起始时间、增益和淡入淡出
3. **Overlay Multiple Audios**：将多个覆盖层叠加到基础音频，
   每个具有独立的时间、增益、声像和淡入淡出

## 准备

### 前置条件

- 已安装 model-compose 并加入 PATH
- 已安装 [ffmpeg](https://ffmpeg.org/) 并加入 PATH

### 设置

进入示例目录：
```bash
cd examples/media-processing/audio-mixer
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
   - 上传所需的音频文件并设置 placement 字段
   - 点击 "Run Workflow"

   **通过 CLI：**
   ```bash
   # 将两个片段拼接为一个音频
   model-compose run concat --input '{
     "first": "/path/to/intro.mp3",
     "second": "/path/to/main.mp3"
   }'

   # 在背景音轨之上混入旁白
   model-compose run overlay-single --input '{
     "base": "/path/to/background.mp3",
     "overlay": "/path/to/narration.mp3",
     "start_time": "2s",
     "gain": 0.8
   }'

   # 在基础音轨之上叠加旁白和音效
   model-compose run overlay-multiple --input '{
     "base": "/path/to/background.mp3",
     "narration": "/path/to/narration.mp3",
     "sfx": "/path/to/effect.mp3"
   }'
   ```

   **通过 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=overlay-single" \
     -F "base=@/path/to/background.mp3" \
     -F "overlay=@/path/to/narration.mp3" \
     -F "start_time=2s" \
     -F "gain=0.8"
   ```

## 组件详情

### Audio Mixer 组件

- **Type**：`audio-mixer`
- **Driver**：`ffmpeg`
- **用途**：使用 ffmpeg 滤镜（`concat` 用于拼接，`amix` 用于叠加）
  将多个音频合并为一个输出。

由于 ffmpeg 滤镜图无法在流复制（stream-copy）输入上工作，混合过程中
音频总是会被重新编码。`format` 字段设置输出容器（默认 `wav`）；
`encoding` 字段控制编解码器、比特率、采样率和声道数。省略 `encoding`
时，会为每种格式选择合理默认值（mp3 → libmp3lame，wav → pcm_s16le，
aac/m4a → aac，opus → libopus，...）。

### Concat 方式

使用 ffmpeg 的 `concat` 滤镜将音频首尾拼接。所有输入必须具有相同的
采样率和声道布局 —— 否则 concat 滤镜会以 `Input link ... parameters
do not match` 报错。请在上游（例如 `audio-converter` 组件）对输入
进行归一化后再送入 `concat`。

#### 关键字段

| 字段 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audios` | 音频源列表 | 是 | - | 需要拼接的音频，按顺序（至少 2 个）|
| `crossfade` | duration | 否 | - | 为将来预留，目前未实现 |
| `format` | string | 否 | `wav` | 输出容器格式 |
| `encoding` | object | 否 | 格式默认值 | 输出编解码器 / 比特率 / 采样率 / 声道 |
| `batch_size` | integer | 否 | `1` | 当 `audios` 为列表的列表或流时，每批处理的输入*集合*数量 |
| `streaming` | boolean | 否 | `false` | 将输出作为字节流发出，而非临时文件 |

### Overlay 方式

将一个或多个覆盖音频混入基础音频。所有覆盖层与基础同时播放 —— 时间
由每个覆盖层的 `start_time`/`end_time` 单独控制。每个覆盖层在经过
自己的预处理链（delay → trim → gain → pan → fade）后，通过 ffmpeg 的
`amix` 滤镜进行合并。

#### 关键字段

| 字段 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `audio` | 音频源或列表 | 是 | - | 基础音频（列表将启用批处理模式：每个 base 一个输出）|
| `overlay` | 字符串或字符串列表 | 是 | - | 覆盖音频。单个字符串会自动包装为一个元素的列表 |
| `placement` | object 或 object 列表 | 否 | 一个默认 placement | 每个覆盖层一个 placement。单个 object 广播到所有覆盖层；列表按位置匹配 |
| `duration_mode` | `base` \| `longest` \| `shortest` | 否 | `base` | 输出相对于 base 和覆盖层运行多久 |
| `format` | string | 否 | `wav` | 输出容器格式 |
| `encoding` | object | 否 | 格式默认值 | 输出编解码器 / 比特率 / 采样率 / 声道 |
| `batch_size` | integer | 否 | `1` | 当 `audio` 为列表/流时，每批处理的基础音频数量 |
| `streaming` | boolean | 否 | `false` | 将输出作为字节流发出，而非临时文件 |

#### Placement 字段

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `start_time` | duration | - | 覆盖层首次播放的时间（以 base 的时间轴为基准，默认 `0s`）|
| `end_time` | duration | - | 覆盖层停止播放的时间（默认运行到覆盖层的自然结束）|
| `gain` | float | `1.0` | 线性音量乘数（1.0 = 不变，0.5 = -6dB，2.0 = +6dB）|
| `pan` | float -1..1 | `0.0` | 立体声声像（-1.0 = 全左，0.0 = 中央，+1.0 = 全右）|
| `fade_in` | duration | - | 从 `start_time` 开始的淡入时长 |
| `fade_out` | duration | - | 在 `end_time` 结束的淡出时长（需要 `end_time`）|

`start_time`、`end_time`、`fade_in`、`fade_out` 接受：
- 数字（秒）：`10`、`10.5`
- Duration 字符串：`"10s"`、`"1m"`、`"250ms"`
- 时间码：`"00:00:10"`、`"01:23:45"`

#### 时长策略

- **base**（默认）：base 结束时输出停止。早于 base 结束的覆盖层
  会消失；超过 base 的覆盖层会被截断。
- **longest**：输出运行到最后一个流结束。适用于延迟的覆盖层需要在
  base 结束后继续播放的场景。
- **shortest**：任何输入（base 或 overlay）一结束，输出立即停止。
  适用于让覆盖层决定总时长的场景。

`base` 会对 base 运行一次 `ffprobe` 以限制输出长度；`longest`/
`shortest` 由 `amix` 的 `duration` 选项直接处理。

## 工作流详情

### 1. Concatenate Audios

**描述**：通过 ffmpeg 的 `concat` 滤镜重新编码并将两个音频拼接为
一个。

#### 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `first` | file | 是 | 输出中先出现的音频 |
| `second` | file | 是 | 输出中后出现的音频 |

#### 输出

| 字段 | 类型 | 描述 |
|------|------|------|
| `audio` | audio | 拼接后的结果 |

### 2. Overlay Single Audio

**描述**：将单个覆盖层（旁白、音效等）混入基础音频。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `base` | file | 是 | - | 基础音频 |
| `overlay` | file | 是 | - | 覆盖音频 |
| `start_time` | duration | 否 | `2s` | 覆盖层在 base 时间轴上首次播放的时间 |
| `gain` | float | 否 | `0.8` | 覆盖层的线性音量乘数 |

#### 输出

| 字段 | 类型 | 描述 |
|------|------|------|
| `audio` | audio | 混入了覆盖层的基础音频 |

### 3. Overlay Multiple Audios

**描述**：在基础音轨之上叠加旁白和音效，每个具有独立的时间和增益。

#### 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `base` | file | 是 | 基础音频 |
| `narration` | file | 是 | 旁白覆盖层，从 `1s` 开始播放 |
| `sfx` | file | 是 | 音效覆盖层，在 `5s` 至 `7s` 之间以右声像播放 |

#### 输出

| 字段 | 类型 | 描述 |
|------|------|------|
| `audio` | audio | 混入了两个覆盖层的基础音频 |

## 提示

- **重新编码不可避免**：混合操作通过 ffmpeg 滤镜图运行，无法在流复制
  输入上工作。如果默认值与目标输出不符，请提供 `encoding`。
- **Placement 广播**：单个 `placement` object 会应用到每个覆盖层。
  仅当覆盖层需要不同的时间、增益或声像时才使用列表。
- **覆盖层同时性**：与视频覆盖层不同，这里没有 z 顺序 —— 每个覆盖层
  同时播放并汇入 base。`overlay` 列表的顺序不影响结果。
- **时间语义**：`start_time` 以 base 的时间轴为基准，因此
  `start_time: 5s` 会将覆盖层延迟 5 秒。`end_time` 在延迟后的时间轴
  上按绝对时间截断覆盖层。
- **淡出需要 `end_time`**：由于淡出在 `end_time` 结束，省略
  `end_time` 会禁用 `fade_out`。要有尾部淡出时请同时设置两者。
- **批处理模式**：传入基础音频列表会为每个 base 执行一次 overlay
  操作，并返回输出列表。除非按 base 参数化，否则相同的覆盖层集合会
  广播到每个 base。
- **流式输入**：非文件的音频源（字节、HTTP 上传）会在混合前假脱机
  到临时文件，以便 ffmpeg 可以对其进行 seek。

## 故障排除

### 常见问题

1. **未找到 ffmpeg**：确保 ffmpeg 已安装并在 `PATH` 中。
2. **`'audios' must contain at least two entries for concat`**：concat
   至少需要两个输入。单音频操作请使用 `overlay` 或其他组件。
3. **concat 时 `Input link ... parameters do not match`**：ffmpeg
   concat 滤镜要求每个输入具有相同的采样率和声道布局。拼接前使用
   `audio-converter` 之类的组件对输入进行归一化。
4. **`overlay/placement cardinality mismatch`**：当 `placement` 为
   列表时，其长度必须等于覆盖层的数量。单个 placement object 会广播
   到每个覆盖层。
5. **混合后覆盖层过小声或过大声**：此处 `amix` 不做归一化地对输入
   求和（`normalize=0`），因此原始电平会被保留。请调整每个覆盖层的
   `gain` —— 或在上游降低 base —— 直到平衡合适为止。
6. **淡出无效**：`fade_out` 需要 `end_time` 来锚定淡出尾部。请同时
   设置两者。
7. **concat 后格式不匹配**：输出格式取自 action 的 `format` 字段
   （默认：`wav`）。当该格式的默认编解码器与目标不符时，请显式设置
   `encoding.codec`。
