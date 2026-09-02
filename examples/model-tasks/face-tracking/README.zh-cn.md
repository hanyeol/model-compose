# 人脸追踪模型任务示例

本示例演示如何通过 model-compose 的内置 `face-tracking` 任务使用 InsightFace 在视频帧中追踪人脸。以固定间隔从上传的视频中采样帧，进行检测与嵌入，然后按余弦相似度聚类，使同一个人在帧之间被归为一条轨迹——最终输出一份按人物划分、带时间码片段的报告。

## 概述

此工作流提供本地人脸追踪功能：

1. **本地人脸追踪模型**：在本地运行 InsightFace 的 `antelopev2` 模型包，无需外部 API
2. **帧采样**：使用 ffmpeg 按用户指定的间隔从输入视频中抽取帧
3. **身份聚类**：按余弦相似度对每帧人脸嵌入进行在线聚类，使每个独立身份被归为一条轨迹
4. **片段聚合**：将每帧时间戳聚合为按人物划分的 `start_time / end_time / duration` 区间
5. **自动模型管理**：首次运行时从 InsightFace GitHub Release 拉取 `antelopev2` 包，解压到 `./models/antelopev2` 并在后续运行中复用

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 已安装 ffmpeg 并在 PATH 中可用（用于帧提取）
- 运行 onnxruntime 所需的充足系统资源（推荐：4GB+ RAM）
- 带有 `insightface`、`opencv-python` 和 `onnxruntime` 的 Python 环境（首次运行时自动安装）
- 互联网连接（首次运行时下载 antelopev2 包需要）

### antelopev2 模型包

无需手动准备。首次运行会根据 [model-compose.yml](model-compose.yml) 中的 `url` + `bundled: true` 配置自动下载归档，并解压到 `./models/antelopev2`。后续运行直接复用该目录。

解压后的结构：

```
models/
└── antelopev2/
    ├── 1k3d68.onnx
    ├── 2d106det.onnx
    ├── genderage.onnx
    ├── glintr100.onnx
    └── scrfd_10g_bnkps.onnx
```

### 环境配置

1. 进入本示例目录：
   ```bash
   cd examples/model-tasks/face-tracking
   ```

2. 无需额外的环境配置。首次运行会自动准备模型包。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "frame_interval": 15, "sampled_frame_rate": 2.0}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `video` 文件
   - 根据需要调整 `frame_interval` / `sampled_frame_rate` / `similarity_threshold`
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 15, "sampled_frame_rate": 2.0}'
   ```

## 组件详情

### Frame Extractor 组件
- **Type**：`video-frame-extractor`
- **Driver**：`ffmpeg`
- **用途**：以固定节奏从输入视频中采样帧，并以图像流形式发送给 tracker
- **关键参数**：`frame_interval`（1 = 每一帧，15 = 每 15 帧一次，依此类推）
- **流式处理**：开启。extractor 的原始分块形式为 `{image, timestamp, number, ...}`；`output: ${result[].image}` 将每个分块投影为仅保留 `image`，使下游消费者看到纯图像流。帧随着 ffmpeg 生成实时流向 face-tracking，因此长视频不会整体缓冲。

### Face Tracking Model 组件
- **Type**：`face-tracking` 任务的 Model 组件
- **Family**：`insightface`
- **Model**：本地 `./models/antelopev2` 包
- **功能**：
  - 逐帧检测人脸并提取 512 维身份嵌入
  - 按余弦相似度在线聚类嵌入，使每个身份被归为一条轨迹
  - 以 H:MM:SS.mmm 时间码形式生成每条轨迹的片段（start/end/duration）
  - 串行执行（`max_concurrent_count: 1`）以限制 GPU 内存

### 模型信息：antelopev2 (InsightFace)
- **提供者**：InsightFace
- **主干网络**：ResNet-100 (`glintr100.onnx`)
- **嵌入维度**：512
- **检测器**：SCRFD-10G (`scrfd_10g_bnkps.onnx`)
- **归一化**：L2 归一化嵌入——余弦相似度等价于点积
- **许可**：仅限非商业研究使用

## 工作流详情

### 默认工作流

**描述**：从上传的视频中采样帧，运行人脸追踪，并返回按人物划分的片段。

#### Job 流程

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[{image, timestamp, ...}]| J1

    J1 --> J2((track<br/>job))
    J2 -.-> C2[Face Tracker<br/>insightface]
    C2 -.-> |{tracks, frame_count}| J2

    J2 --> Output((Output<br/>report))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | video (file) | Yes | - | 输入视频文件 |
| `frame_interval` | number | No | 15 | 提取时每 N 帧采样一次 |
| `sampled_frame_rate` | number | No | 2.0 | *采样后*序列的每秒帧数，用于推导每帧时间戳。设为 `source_fps / frame_interval` |
| `similarity_threshold` | number | No | 0.4 | 两张人脸被归入同一轨迹的余弦相似度阈值 |
| `min_frame_count` | number | No | 2 | 出现帧数少于该值的轨迹被丢弃 |
| `merge_gap` | number | No | 1.0 | 相邻片段之间间隔小于该秒数则合并 |
| `return_track_image` | boolean | No | true | 为每个片段附加一张人脸裁剪。在原始帧分辨率下按检测到的 bounding box 直接裁切，适用于 UI 显示、缩放，或送入其他嵌入主干网络重新嵌入（见下方[使用其他模型重新嵌入](#使用其他模型重新嵌入)）。仅需时间码时设为 `false` 可减小载荷 |
| `return_gender_age` | boolean | No | false | 为每条轨迹附加 `gender`（`"male"` / `"female"`）与 `age`（整数），取自轨迹中得分最高的帧。需要模型包含 gender/age 子模型（`antelopev2`、`buffalo_l`） |
| `bounding_box_padding` | number | No | 0.2 | 将人脸裁剪的 bounding box 按此比例向每一侧扩展（例如 `0.2` = 上下左右各 +20%）。仅影响返回的裁剪图像；嵌入与聚类仍使用未扩展的框。适用于检测框过紧（头发/下巴/耳朵被切）或人脸在画面中较小导致裁剪显得模糊的情况 |

#### 输出格式

`report` 是包含以下字段的 JSON 对象：

| 字段 | 类型 | 描述 |
|------|------|------|
| `tracks` | array | 每个检测到的身份一个条目。见下方。 |
| `frame_count` | integer | 分析的采样帧总数 |

每个 `tracks[i]` 条目：

| 字段 | 类型 | 描述 |
|------|------|------|
| `embedding` | number[] | L2 归一化的身份 centroid（antelopev2 为 512 维）。适合与身份数据库直接进行余弦匹配，或用于合并被判定为同一人的轨迹。仅在启用 `return_embedding` 时存在 |
| `segments` | array | `{start_time, end_time, duration, score}` 列表（启用 `return_track_image` 时包含 `image`）。见下方 |
| `frame_count` | integer | 该轨迹出现的采样帧数 |
| `score` | number | 该轨迹所有帧中的最高检测置信度。可用于轨迹排序或过滤 |
| `gender` | string | `"male"` 或 `"female"`，取自该轨迹得分最高的帧。仅在启用 `return_gender_age` 且模型包含 gender 子模型时存在 |
| `age` | integer | 年龄估计值，取自该轨迹得分最高的帧。仅在启用 `return_gender_age` 且模型包含 age 子模型时存在 |

每个 `segments[j]` 条目：

| 字段 | 类型 | 描述 |
|------|------|------|
| `start_time` | string | 片段开始（`H:MM:SS.mmm` 时间码） |
| `end_time` | string | 片段结束（`H:MM:SS.mmm` 时间码） |
| `duration` | string | `end_time - start_time`（`H:MM:SS.mmm` 时间码） |
| `score` | number | 该片段代表帧（片段中得分最高的帧，即 `image` 的裁切来源帧）的检测置信度 |
| `image` | image | 该片段得分最高帧的人脸裁剪，在原始帧分辨率下按检测到的 bounding box 直接裁切（每张人脸尺寸不同）。仅在启用 `return_track_image` 时存在 |

示例（`return_track_image: false`，`return_embedding: false`）：

```json
{
  "report": {
    "tracks": [
      {
        "segments": [
          { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "duration": "0:00:06.500", "score": 0.94 },
          { "start_time": "0:00:14.000", "end_time": "0:00:17.000", "duration": "0:00:03.000", "score": 0.88 }
        ],
        "frame_count": 21,
        "score": 0.94
      }
    ],
    "frame_count": 40
  }
}
```

### 使用其他模型重新嵌入

启用 `return_track_image` 后，每个片段会附带一张人脸裁剪——该片段中得分最高帧，在原始分辨率下按检测到的 bounding box 直接裁切得到的图像。将这些裁剪送入另一个 `face-embedding` 组件（或您自己的视觉模型），即可复用本任务的检测与聚类结果，同时用不同的主干网络获取嵌入。下游组件会在裁剪上自行执行检测/对齐，从而两个嵌入模型之间保持松散耦合：

```yaml
- id: track
  component: face-tracker
  input:
    frames: ${jobs.frames.output}
    frame_rate: ${input.sampled_frame_rate}
    return_track_image: true

- id: reembed
  component: alt-face-embedder
  # 对每个轨迹的每个片段，重新嵌入其代表裁剪。
  input:
    face_image: ${jobs.track.output.tracks[*].segments[*].image}
```

每个轨迹上的 `embedding` 字段是 insightface 自身嵌入的 running centroid 且始终存在，因此下游代码也可以直接比较轨迹（例如合并因光照差异而被拆成两条的同一个人）。

## 系统要求

### 最低要求
- **RAM**：4GB（推荐 8GB+）
- **磁盘空间**：`antelopev2` 包约 1GB
- **CPU**：任何现代 x86_64 或 ARM64 处理器
- **互联网**：一次性模型包下载所需

### 性能说明
- 检测成本随采样帧数增长——选择 `frame_interval` 时应保证采样 fps 能覆盖您希望捕捉的最短出现（例如以 2 fps 采样以捕捉 ≥ 1 秒的出现）
- 通过 onnxruntime 使用 GPU（CUDA / CoreML / DirectML）能显著提升吞吐
- 首次运行会初始化 onnxruntime 与检测器——后续运行更快

## 自定义

### 更密集地采样

降低 `frame_interval` 并相应提高 `sampled_frame_rate`。对于 30 fps 的源视频，每 5 帧采样一次得到 6 fps：

```bash
model-compose run --input '{"video": "clip.mp4", "frame_interval": 5, "sampled_frame_rate": 6.0}'
```

### 收紧身份分组

提高 `similarity_threshold` 使聚类更保守（合并更少，轨迹更细）。典型范围：

- `0.30 – 0.40`：激进分组，可能合并长相相似的人
- `0.40 – 0.55`：平衡
- `> 0.55`：严格，可能将光照/角度变化大的同一人拆分

### 物化的帧列表（非流式）

本示例以流式模式运行 extractor。如果您想先物化完整的帧列表（例如在 `for-each` job 中检查或持久化到磁盘），请关闭 `streaming` 并将投影切换为 `[*]`：

```yaml
- id: frame-extractor
  type: video-frame-extractor
  driver: ffmpeg
  action:
    video: ${input.video}
    frame_interval: ${input.frame_interval}
    streaming: false
    output: ${result[*].image}
```

`face-tracking` 会透明地处理物化列表和 async iterator。

## 故障排查

### 常见问题

1. **`frame_rate` 不匹配**：如果时间码看起来不对，请确认 `sampled_frame_rate` 与 `source_fps / frame_interval` 一致。错误值不会破坏聚类，但会使所有报告的时间戳按比例偏移。
2. **未返回任何轨迹**：提高采样速率（降低 `frame_interval`）或降低 `min_frame_count`——该人可能只出现在单个采样帧中。
3. **同一人被拆分为多个轨迹**：降低 `similarity_threshold`（例如 0.35），或者如果拆分仅由相邻缺口引起，则提高 `merge_gap`。
4. **不同的人被合并到同一轨迹**：提高 `similarity_threshold`（例如 0.5）——默认值偏向召回率。
5. **找不到模型文件**：确认 `./models/antelopev2` 目录包含上方列出的所有 `.onnx` 文件。

### 性能优化

- **GPU**：安装 `onnxruntime-gpu`（CUDA）或 `onnxruntime-silicon`（Apple）以加速推理
- **检测尺寸**：更大的检测输入能提升小人脸的召回率，但会减慢推理——参见 InsightFace family 配置中的 `detection_size`
- **采样率**：最大的调节杠杆——将采样 fps 减半大致会使运行时间减半

## 相关示例

- `face-embedding`：从静态图像中提取单个身份嵌入
- `face-swap`：将源图像的人脸身份迁移到目标图像
- `find-person-scenes`（showcase）：给定目标人脸，找出视频中该人物出现的场景——使用 `face-embedding` + `vector-processor` 而非内置 tracker
