# Video Clipper 示例

本示例展示了 `video-clipper` 组件的使用方法，该组件通过 ffmpeg 从视频文件中裁剪一个或多个时间段。支持两种裁剪模式：`fast`（默认，stream copy，关键帧对齐）和 `accurate`（重新编码，帧级精度）。

## 概述

该示例基于同一个 `video-clipper` 组件提供三个工作流：

1. **单段裁剪**：提取一个时间段并返回视频文件
2. **多段裁剪**：提取多个时间段并以视频列表返回
3. **裁剪并合并**：提取多个时间段并拼接为单个视频文件

## 准备工作

### 前置要求

- 已安装并在 PATH 中的 model-compose
- 已安装并在 PATH 中的 [ffmpeg](https://ffmpeg.org/)

### 设置

进入示例目录：
```bash
cd examples/media-processing/video-clipper
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
   - 上传视频文件并输入时间段
   - 点击 "Run Workflow"

   **使用 CLI：**
   ```bash
   # 单段（10s..25s），fast（关键帧对齐）裁剪
   model-compose run clip-single --input '{
     "video": "/path/to/input.mp4",
     "start_time": "10s",
     "end_time": "25s"
   }'

   # 同一段，以帧级精度裁剪（重新编码）
   model-compose run clip-single --input '{
     "video": "/path/to/input.mp4",
     "start_time": "10s",
     "end_time": "25s",
     "precision": "accurate"
   }'

   # 多段以列表返回
   model-compose run clip-multiple --input '{
     "video": "/path/to/input.mp4",
     "spans": [
       {"start_time": 0, "end_time": 5},
       {"start_time": 30, "end_time": 45}
     ]
   }'

   # 多段合并为一个片段
   model-compose run clip-and-merge --input '{
     "video": "/path/to/input.mp4",
     "spans": [
       {"start_time": "00:00:10", "end_time": "00:00:20"},
       {"start_time": "00:01:00", "end_time": "00:01:15"}
     ]
   }'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=clip-single" \
     -F "video=@/path/to/input.mp4" \
     -F "start_time=10s" \
     -F "end_time=25s"
   ```

## 组件详情

### Video Clipper 组件

- **类型**：`video-clipper`
- **驱动**：`ffmpeg`
- **用途**：使用 ffmpeg 从视频文件中裁剪一个或多个时间段 —— `fast` 模式（默认）为 stream copy，`accurate` 模式为重新编码。

#### 主要字段

| 字段 | 类型 | 必需 | 默认值 | 说明 |
|-------|------|----------|---------|-------------|
| `video` | 视频源 | 是 | - | 要裁剪的视频文件 |
| `span` | 对象或对象列表 | 是 | - | 一个或多个 `{start_time, end_time}` 条目。单个对象会自动提升为单元素列表 |
| `merge` | boolean | 否 | `false` | 为 `true` 时将所有片段拼接为单个视频文件 |
| `precision` | `fast` \| `accurate` | 否 | `fast` | `fast` 通过 stream copy 对齐到 `start_time` 及之前最近的关键帧；`accurate` 重新编码使切分点落在请求的帧上 |
| `batch_size` | integer | 否 | `1` | 当输入是列表/流时每批处理的视频数量 |

`start_time` 和 `end_time` 支持以下格式：
- 数字（秒）：`10`、`10.5`
- 时长字符串：`"10s"`、`"1m"`、`"250ms"`
- 时间码：`"00:00:10"`、`"01:23:45"`

输出格式从输入容器保留（依次通过 `video.format`、输入文件扩展名，最后回退到 ffprobe 探测），以确保 `-c copy` 的有效性。

## 工作流详情

### 1. 单段裁剪

**说明**：从输入视频中提取一个 `[start_time, end_time]` 段。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `video` | file | 是 | - | 源视频文件 |
| `start_time` | 字符串/数字 | 否 | `0s` | 片段起点 |
| `end_time` | 字符串/数字 | 否 | `10s` | 片段终点 |
| `precision` | `fast` \| `accurate` | 否 | `fast` | 裁剪精度（参见[组件详情](#video-clipper-组件)） |

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `video` | video | 提取的片段 |

### 2. 多段裁剪

**说明**：提取多个时间段并作为视频文件列表返回。

#### 输入参数

| 参数 | 类型 | 必需 | 说明 |
|-----------|------|----------|-------------|
| `video` | file | 是 | 源视频文件 |
| `spans` | json | 是 | `{start_time, end_time}` 对象的 JSON 数组 |
| `precision` | `fast` \| `accurate` | 否 | 裁剪精度（参见[组件详情](#video-clipper-组件)） |

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `videos` | 视频列表 | 每个 span 一个，按输入顺序 |

### 3. 裁剪并合并

**说明**：提取多个段然后使用 ffmpeg concat demuxer 拼接为单个输出视频。

#### 输入参数

| 参数 | 类型 | 必需 | 说明 |
|-----------|------|----------|-------------|
| `video` | file | 是 | 源视频文件 |
| `spans` | json | 是 | `{start_time, end_time}` 对象的 JSON 数组 |
| `precision` | `fast` \| `accurate` | 否 | 裁剪精度（参见[组件详情](#video-clipper-组件)） |

#### 输出

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `video` | video | 合并后的片段 |

## 提示

- **fast 与 accurate**：`precision: fast`（默认）使用 `-c copy`，无损且几乎即时，但切分点会对齐到 `start_time` 及之前最近的关键帧，因此 GOP 较长的源可能比请求的时间稍早开始。`precision: accurate` 重新编码使切分点落在请求的帧上；输出不再是 bit-exact，编码耗时也显著增加，因此仅在下游处理需要精确帧边界时使用。
- **返回的切分区间**：当 `return_timestamp: true` 时，每个片段携带的 `start_time`/`end_time` 反映实际切分的位置 —— 在 `precision: fast` 下，这是对齐后的关键帧时间戳，而不是原始请求值。
- **流式输入**：非文件视频源（bytes、HTTP 上传）会被 spool 到临时文件恰好一次，以便每个 span 可以独立 seek。
- **流式 spans**：`spans` 列表也可以是由前置组件生成的流式迭代器 —— 每个 span 到达时立即处理（`merge=true` 除外，它必须等待所有 span 到达才能拼接）。
- **merge 时的格式一致性**：`merge=true` 使用 ffmpeg `concat` demuxer + `-c copy`；由于所有片段都来自同一源，编解码器/容器的一致性得到保证。

## 故障排查

### 常见问题

1. **ffmpeg not found**：确保 ffmpeg（以及 ffprobe）已安装并在 `PATH` 中可用。
2. **`end_time must be greater than start_time`**：每个 span 的 end 必须严格大于 start。
3. **Unknown format**：如果视频源既没有 format 提示也没有文件扩展名，将使用 ffprobe 探测容器。非常特殊或损坏的输入可能在此步骤失败 —— 请提供正确的文件扩展名，或在上游用带显式 format 的 `MediaSource` 包装。
4. **片段起始时间比预期早**：在 `precision: fast` 下，切分点会对齐到 `start_time` 及之前最近的关键帧。这是无损/快速路径的取舍 —— 使用较长 GOP 编码的源，漂移会更明显。若需要帧级精度，请切换到 `precision: accurate`（需要重新编码时间）。
