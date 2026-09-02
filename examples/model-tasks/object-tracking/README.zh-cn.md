# 对象追踪模型任务示例

本示例演示如何通过 model-compose 的内置 `object-tracking` 任务使用 Ultralytics YOLO 在视频帧中追踪对象。以固定间隔从上传的视频中采样帧，经过 YOLO 检测和内置追踪器（ByteTrack / BoT-SORT），使同一对象在帧之间保持稳定的身份——最终输出一份按对象划分、带时间码片段的报告，每个片段包含标签和最佳帧的 bounding box。

## 概述

此工作流提供本地对象追踪功能：

1. **本地 YOLO 模型**：在本地运行 Ultralytics YOLO 检测检查点，无需外部 API
2. **帧采样**：使用 ffmpeg 按用户指定的间隔从输入视频中抽取帧
3. **身份追踪**：将帧送入 YOLO 内置追踪器（ByteTrack 或 BoT-SORT），使每个对象在帧之间保持稳定的 `track_id`
4. **片段聚合**：将每帧时间戳聚合为按对象划分的 `start_time / end_time / duration` 区间
5. **流式摄入**：extractor 按 ffmpeg 生成速度将帧流向追踪器，因此长视频不会整体缓冲
6. **自动模型管理**：首次运行时自动下载并缓存 `yolov8n.pt` 默认检查点

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 已安装 ffmpeg 并在 PATH 中可用（用于帧提取）
- 运行 YOLO 所需的充足系统资源（推荐：4GB+ RAM）
- 带有 `ultralytics` 和 `lap` 的 Python 环境（首次运行时自动安装）

### YOLO 模型权重

无需手动准备。[model-compose.yml](model-compose.yml) 中的 `model.path` 指向 `./models/yolov8n.pt`；首次运行会根据文件名从对应的 Ultralytics 发布版本自动下载，并缓存到 `./models/`。后续运行直接复用该文件。

如需使用其他检查点（例如更大的模型或微调后的模型），可以将您的 `.pt` 文件放入 `./models/` 并让 `model.path` 指向它，或将 `model.path` 设为任意 Ultralytics 预设名（`yolov8n.pt`、`yolo11n.pt`、`yolo11s.pt` …）。

### 环境配置

1. 进入本示例目录：
   ```bash
   cd examples/model-tasks/object-tracking
   ```

2. 无需额外的环境配置。首次运行会自动下载检查点。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 使用默认 yolov8n.pt 追踪所有 COCO 类别
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "frame_interval": 5, "sampled_frame_rate": 6.0}'

   # 限制为特定标签
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "labels": ["person", "car"], "min_confidence": 0.35}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `video` 文件
   - 根据需要调整 `frame_interval` / `sampled_frame_rate` / `labels` / `tracker`
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 5, "sampled_frame_rate": 6.0}'
   ```

## 组件详情

### Frame Extractor 组件
- **Type**：`video-frame-extractor`
- **Driver**：`ffmpeg`
- **用途**：以固定节奏从输入视频中采样帧，并以图像流形式发送给追踪器
- **关键参数**：`frame_interval`（1 = 每一帧，5 = 每 5 帧一次，依此类推）
- **流式处理**：开启。extractor 的原始分块形式为 `{image, timestamp, number, ...}`；`output: ${result[].image}` 将每个分块投影为仅保留 `image`，使下游消费者看到纯图像流。帧随着 ffmpeg 生成实时流向 object-tracking，因此长视频不会整体缓冲。

### Object Tracking Model 组件
- **Type**：`object-tracking` 任务的 Model 组件
- **Family**：`yolo`
- **Model**：本地 `./models/yolov8n.pt`（首次使用时自动下载）
- **功能**：
  - 逐帧运行 YOLO 检测，再将检测结果送入 ByteTrack 或 BoT-SORT，使 `track_id` 在帧之间保持稳定
  - 惰性消费帧流——不缓冲整段视频
  - 将每帧检测聚合为每条轨迹的片段（`start_time / end_time / duration`），以 H:MM:SS.mmm 时间码形式生成；每个片段附带最佳帧的标签与 bounding box
  - 串行执行（`max_concurrent_count: 1`）以限制 GPU 内存

### 模型信息：yolov8n (Ultralytics)
- **提供者**：Ultralytics
- **任务**：对象检测（默认 80 类 COCO）
- **规模**：Nano——YOLOv8 中最小、最快的版本
- **可用追踪器**：ByteTrack（默认）、BoT-SORT
- **许可**：AGPL-3.0（Ultralytics）

## 工作流详情

### 默认工作流

**描述**：从上传的视频中采样帧，运行对象追踪，并返回按对象划分的片段。

#### Job 流程

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[{image, timestamp, ...}]| J1

    J1 --> J2((track<br/>job))
    J2 -.-> C2[Object Tracker<br/>yolo]
    C2 -.-> |{tracks, detections}| J2

    J2 --> Output((Output<br/>report))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | video (file) | Yes | - | 输入视频文件 |
| `frame_interval` | number | No | 5 | 提取时每 N 帧采样一次 |
| `sampled_frame_rate` | number | No | 6.0 | *采样后*序列的每秒帧数，用于推导每帧时间戳。设为 `source_fps / frame_interval` |
| `labels` | list[string] | No | - | 将检测限制为这些类标签（例如 `["person", "car"]`）。未知标签会立即报错。未设置则返回模型已知的所有类 |
| `min_confidence` | number | No | 0.25 | 检测最低置信度 `[0, 1]` |
| `min_frame_count` | number | No | 3 | 出现帧数少于该值的轨迹被丢弃 |
| `merge_gap` | number | No | 0.5 | 允许对象未被检测到的额外秒数，超出则拆分片段。相邻帧始终合并 |
| `tracker` | string | No | `bytetrack` | 使用的 Ultralytics 追踪器——`bytetrack` 或 `botsort` |
| `return_detections` | boolean | No | true | 是否在 `tracks` 之外包含帧中心的检测视图（每个采样帧一个条目，按 `track_id` 标注） |
| `return_frame_image` | boolean | No | false | 为每个 detection 条目附加完整源帧。需要 `return_detections: true` |

#### 输出格式

`report` 是包含以下字段的 JSON 对象：

| 字段 | 类型 | 描述 |
|------|------|------|
| `tracks` | array | 每个检测到的对象身份一个条目（见下方） |
| `detections` | array | 帧中心的 detection 视图——每个采样帧一个条目，其中的检测对象按 `track_id` 标注。仅在启用 `return_detections` 时存在 |

每个 `tracks[i]` 条目：

| 字段 | 类型 | 描述 |
|------|------|------|
| `track_id` | integer | 追踪器分配的身份，在整个视频中保持稳定 |
| `label` | string | 得分最高帧的类标签（例如 `"person"`、`"car"`） |
| `label_id` | integer | 模型报告的整数类索引 |
| `segments` | array | 该轨迹出现的片段列表。见下方 |
| `frame_count` | integer | 该轨迹出现的采样帧总数 |
| `score` | number | 该轨迹所有帧中的最高检测置信度 |

每个 `segments[j]` 条目：

| 字段 | 类型 | 描述 |
|------|------|------|
| `start_time` | string | 片段开始（`H:MM:SS.mmm` 时间码） |
| `end_time` | string | 片段结束（`H:MM:SS.mmm` 时间码） |
| `duration` | string | `end_time - start_time`（`H:MM:SS.mmm` 时间码） |
| `label` | string | 该片段得分最高帧的类标签 |
| `label_id` | integer | 该片段得分最高帧的整数类索引 |
| `score` | number | 该片段得分最高帧的检测置信度 |
| `bounding_box` | object | 该片段得分最高帧的 `{x, y, width, height}`（像素，左上原点） |

每个 `detections[k]` 条目（启用 `return_detections` 时）：

| 字段 | 类型 | 描述 |
|------|------|------|
| `number` | integer | 该采样帧的从 1 开始的索引 |
| `timestamp` | string | 帧时间戳（`H:MM:SS.mmm` 时间码） |
| `objects` | array | 此帧的检测对象，每个对象包含 `track_id`、`label`、`label_id`、`bounding_box`、`score`；当框由缺失检测的间隙线性插值得到时会附带 `interpolated: true` |
| `image` | image | 完整采样帧。仅在启用 `return_frame_image` 时存在 |

示例（`return_detections: false`）：

```json
{
  "report": {
    "tracks": [
      {
        "track_id": 1,
        "label": "person",
        "label_id": 0,
        "segments": [
          {
            "start_time": "0:00:00.500", "end_time": "0:00:04.833", "duration": "0:00:04.333",
            "label": "person", "label_id": 0, "score": 0.91,
            "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 460 }
          }
        ],
        "frame_count": 26,
        "score": 0.91
      }
    ]
  }
}
```

## 系统要求

### 最低要求
- **RAM**：4GB（推荐 8GB+）
- **磁盘空间**：`yolov8n.pt` 约 10MB（更大版本：`yolov8s.pt` 约 22MB、`yolov8m.pt` 约 52MB、`yolov8l.pt` 约 87MB、`yolov8x.pt` 约 136MB）
- **CPU**：任何现代 x86_64 或 ARM64 处理器
- **互联网**：一次性权重下载所需

### 性能说明
- 检测成本随采样帧数增长——选择 `frame_interval` 时应保证采样 fps 能覆盖您希望捕捉的最短片段（例如以 6 fps 采样以捕捉 ≥ 约 0.5 秒的连续出现）
- 使用 GPU（CUDA）能显著提升吞吐；Apple Silicon 在可用时会自动使用 MPS 后端
- 首次运行会初始化 YOLO 与追踪器——后续运行更快
- 追踪器从 extractor 的流中惰性消费帧，因此峰值内存不会随视频长度线性增长

## 自定义

### 更密集地采样

降低 `frame_interval` 并相应提高 `sampled_frame_rate`。对于 30 fps 的源视频，每 2 帧采样一次得到 15 fps：

```bash
model-compose run --input '{"video": "clip.mp4", "frame_interval": 2, "sampled_frame_rate": 15.0}'
```

### 切换追踪器

`bytetrack` 更快，适合大多数场景；`botsort` 增加了外观特征（ReID），对短暂遮挡通常更鲁棒：

```bash
model-compose run --input '{"video": "clip.mp4", "tracker": "botsort"}'
```

### 限制为特定类别

传入 `labels` 列表以仅保留您关心的类别。列表之外的检测会在追踪之前被丢弃，从而也加快处理速度：

```bash
model-compose run --input '{"video": "clip.mp4", "labels": ["person"], "min_confidence": 0.4}'
```

### 使用自定义模型

将 `model-compose.yml` 中的 `model` 块替换为任意 Ultralytics YOLO 检查点。例如，指向使用自有数据集微调的检测器：

```yaml
- id: object-tracker
  type: model
  task: object-tracking
  driver: custom
  family: yolo
  model:
    provider: local
    path: /path/to/your/model.pt
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    labels: [ your_class_a, your_class_b ]
    params:
      tracker: bytetrack
      min_confidence: 0.3
```

同样支持分割检查点（`yolo11*-seg.pt` 等）——只读取 bounding box。

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

`object-tracking` 会透明地处理物化列表和 async iterator。

## 故障排查

### 常见问题

1. **`frame_rate` 不匹配**：如果时间码看起来不对，请确认 `sampled_frame_rate` 与 `source_fps / frame_interval` 一致。错误值不会破坏追踪，但会使所有报告的时间戳按比例偏移。
2. **未返回任何轨迹**：提高采样速率（降低 `frame_interval`）或降低 `min_frame_count`——该对象可能只出现在少数采样帧中。
3. **同一对象被拆分为多个轨迹**：如果拆分由短暂遮挡引起，请提高 `merge_gap`；或尝试基于外观再识别的 `tracker: botsort`。
4. **不同对象被合并到同一轨迹**：降低 `merge_gap`、提高 `min_confidence`，或收窄 `labels`——同一类别中非常接近的 bounding box 可能会干扰 ID 分配。
5. **找不到模型文件**：确认 `./models/yolov8n.pt` 存在（或 `model.path` 指向可由首次运行下载解析的有效 Ultralytics 预设名）。

### 性能优化

- **GPU**：安装带 CUDA 支持的 PyTorch 可获得大幅加速；Apple Silicon 会自动使用 MPS
- **采样率**：最大的调节杠杆——将采样 fps 减半大致会使运行时间减半
- **标签过滤**：传入 `labels` 会在追踪之前丢弃不关心的类别，减少 associator 需要管理的轨迹数量
- **模型规模**：`yolov8n.pt` 最快；如需更高召回，可换成 `yolov8s/m/l/x`，代价是吞吐下降

## 相关示例

- `object-detection`：使用同一 YOLO family 在单张图像上检测对象（无追踪）
- `pose-tracking`：在视频中追踪人物姿态（关键点），采用相同的流式/片段形态
- `face-tracking`：使用 InsightFace 在视频中追踪人脸，基于嵌入的身份聚类
