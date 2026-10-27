# 活跃说话人检测模型任务示例

本示例演示如何通过 model-compose 的内置 `active-speaker-detection` 任务使用 Light-ASD 来判断**画面中哪个人正在说话**。以固定间隔从上传的视频中采样帧，经过 InsightFace 人脸追踪，然后由 Light-ASD 结合配对的音频对每条轨迹进行评分——产出每条轨迹的说话片段以及一条"此刻谁在说话"的扁平时间线。

## 概述

此工作流提供本地活跃说话人检测功能：

1. **本地活跃说话人模型**：在本地运行 Light-ASD 模型，无需外部 API
2. **复用人脸轨迹**：使用配对的 `face-tracking` 组件产出的检测结果，而不是运行自己的人脸检测器，使边界框与共享帧序列按帧对齐
3. **音频-视觉评分**：将 25 fps 的 112x112 灰度人脸裁剪与 16 kHz 单声道音频提取的 100 Hz MFCC 特征配对
4. **说话片段**：将逐帧的说话 logit 流合并为每条轨迹的 `start_time / end_time / duration` 区间
5. **自动源码安装**：首次运行时将 Light-ASD 上游仓库克隆到 mindor 安装根目录（作为 `lightasd/`），并将 Light-ASD 检查点下载到 `~/.cache/models/light_asd/`

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 已安装 ffmpeg 并在 PATH 中可用（用于帧和音频提取）
- 已安装 `git` 并在 PATH 中可用（首次运行时用于克隆 Light-ASD 上游源码）
- 运行小型 torch 模型所需的充足系统资源（推荐：4GB+ RAM）
- 带有 `torch`、`torchaudio`、`python_speech_features`、`insightface`、`opencv-python` 和 `onnxruntime` 的 Python 环境（首次运行时自动安装）
- `antelopev2` 模型包放置在 `./models/antelopev2`（face-tracking 使用；下载布局参见 face-tracking 示例）

### 模型设置

- Light-ASD 检查点在首次运行时从上游 GitHub 仓库自动获取，并缓存到 `~/.cache/models/light_asd/`。
- Light-ASD 上游源码会克隆到临时缓存（按 git 版本号作为 key），并在首次运行时安装为运行中 `mindor` 包旁边的 `lightasd` 包。后续运行复用已安装的副本。
- `antelopev2` 人脸追踪包**不会**自动下载——如何将其放置到 `./models/antelopev2` 下请参见 face-tracking 示例的 README。

### 环境配置

1. 进入本示例目录：
   ```bash
   cd examples/model-tasks/active-speaker-detection
   ```

2. 按与 face-tracking 示例相同的布局将 `antelopev2` 包放置到 `./models/antelopev2` 下。

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
     -F 'input={"video": "@clip", "frame_interval": 2, "sampled_frame_rate": 25.0}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `video` 文件
   - 根据需要调整 `frame_interval` / `sampled_frame_rate`
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 2, "sampled_frame_rate": 25.0}'
   ```

## 组件详情

### Frame Extractor 组件
- **Type**：`video-frame-extractor`
- **Driver**：`ffmpeg`
- **用途**：按固定节奏采样帧并将其 materialize 为列表，以便 tracker 和 speaker detector 消费相同的序列
- **关键 knob**：`frame_interval`（1 = 每帧，2 = 每隔一帧，依此类推）。选择一个值，使采样 fps 与模型组件上设置的 `sampled_frame_rate` 匹配（例如 50 fps 源 + `frame_interval: 2` = 25 fps，这是 Light-ASD 训练时使用的）
- **Streaming**：关闭。detector 需要 tracker 看到的同一份 materialize 后的帧列表，这样边界框才能对齐——如果流式输出 extractor 的结果，detector 读取之前 tracker 会先消耗掉。

### Face Tracking 模型组件
- **Type**：带 `face-tracking` 任务的 Model 组件
- **Family**：`insightface`
- **Model**：本地 `./models/antelopev2` 包
- **在本工作流中的角色**：产出 speaker detector 所消费的逐帧 `detections` 列表。因为下游只需要帧级的边界框，所以禁用 `return_tracks` 并启用 `return_detections`。

### Active-Speaker Detection 模型组件
- **Type**：带 `active-speaker-detection` 任务的 Model 组件
- **Family**：`light-asd`
- **Preset**：`finetuning-talkset`（默认）或 `pretrain-ava-cvpr`
- **功能**：
  - 接收与 tracker 相同的 materialize 后的帧，将每条人脸轨迹重新裁剪为 112x112 灰度图，并与输入视频音频提取的 100 Hz MFCC 特征配对
  - 在应用阈值之前，用可配置的窗口对逐帧说话 logit 进行平滑，使单帧闪烁不会碎片化说话段
  - 产出按轨迹的说话片段以及跨轨迹的 `active_timeline`
  - 串行执行（`max_concurrent_count: 1`）以限制 GPU 显存

### 模型信息：Light-ASD
- **上游**：[Junhua-Liao/Light-ASD](https://github.com/Junhua-Liao/Light-ASD)（CVPR 2023）
- **架构**：带双向 GRU 后端的轻量级音频-视觉双流编码器（~1M 参数）
- **训练**：AVA-ActiveSpeaker（pretrain）与 TalkSet（finetune）
- **期望输入**：25 fps 灰度人脸裁剪（112x112，以嘴部为中心）与 16 kHz 单声道 MFCC（100 Hz，13 系数）
- **许可证**：MIT

## 工作流详情

### 默认工作流

**说明**：从上传的视频中采样帧，运行人脸追踪，用 Light-ASD 对每条轨迹评分，并返回按轨迹的说话片段。

#### Job 流程

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[image, image, ...]| J1

    J1 --> J2((track<br/>job))
    J1 --> J3((detect<br/>job))
    J2 -.-> C2[Face Tracker<br/>insightface]
    C2 -.-> |detections| J2
    J2 --> J3

    Input --> |audio| J3
    J3 -.-> C3[Speaker Detector<br/>light-asd]
    C3 -.-> |speakers, active_timeline| J3

    J3 --> Output((Output<br/>report))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | 是 | - | 输入视频文件；同时也是提供给 Light-ASD 的音频源 |
| `frame_interval` | number | 否 | 2 | 在抽取时每 N 帧采样一次。选取一个值使得 `source_fps / frame_interval` ≈ 25（Light-ASD 以 25 fps 训练） |
| `sampled_frame_rate` | number | 否 | 25.0 | *采样后*序列的每秒帧数，用于推导每帧时间戳。设置为 `source_fps / frame_interval` |

#### 输出格式

`report` 是包含以下字段的 JSON 对象：

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `speakers` | array | 每条产生过说话帧的人脸轨迹各一个条目。详见下方。 |
| `active_timeline` | array | 跨所有轨迹按时间排序的扁平说话片段列表。不同轨迹的重叠条目保持独立。 |
| `frame_count` | integer | 分析的采样帧总数 |
| `track_count` | integer | detector 评分的人脸轨迹总数 |

每个 `speakers[i]` 条目：

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `track_id` | integer | 人脸追踪聚类 ID；与 face-tracking 组件返回的 `track_id` 匹配，便于两份输出的 join |
| `segments` | array | `{start_time, end_time, duration, score}` 列表。详见下方。 |

每个 `segments[j]` 条目：

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `start_time` | string | 以 `H:MM:SS.mmm` 时码表示的片段起始 |
| `end_time` | string | 以 `H:MM:SS.mmm` 时码表示的片段结束 |
| `duration` | string | 以 `H:MM:SS.mmm` 时码表示的 `end_time - start_time` |
| `score` | number | 该片段所有帧中平滑后 Light-ASD logit 的最大值 |

每个 `active_timeline[k]` 条目：

| 字段 | 类型 | 说明 |
|-------|------|-------------|
| `start_time` | string | 以 `H:MM:SS.mmm` 时码表示的片段起始 |
| `end_time` | string | 以 `H:MM:SS.mmm` 时码表示的片段结束 |
| `track_id` | integer | 该条目期间哪条人脸轨迹在说话 |
| `score` | number | 此片段的平滑后 logit |

示例：

```json
{
  "report": {
    "speakers": [
      {
        "track_id": 1,
        "segments": [
          { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "duration": "0:00:06.500", "score": 1.42 }
        ]
      },
      {
        "track_id": 2,
        "segments": [
          { "start_time": "0:00:09.200", "end_time": "0:00:12.800", "duration": "0:00:03.600", "score": 1.08 }
        ]
      }
    ],
    "active_timeline": [
      { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "track_id": 1, "score": 1.42 },
      { "start_time": "0:00:09.200", "end_time": "0:00:12.800", "track_id": 2, "score": 1.08 }
    ],
    "frame_count": 450,
    "track_count": 2
  }
}
```

## 系统要求

### 最低要求
- **RAM**：4GB（推荐 8GB+）
- **磁盘空间**：`antelopev2` 包和 Light-ASD 源码合计 ~1GB
- **CPU**：任何现代 x86_64 或 ARM64 处理器
- **互联网**：一次性的上游源码克隆与 Light-ASD 检查点下载需要

### 性能说明
- Light-ASD 是小型模型（~1M 参数）——对于短片段，CPU 通常足够。较长输入上，GPU（CUDA / MPS）仍然更快。
- 长视频上的主要开销是人脸追踪而非 Light-ASD 评分。

## 自定义

### 切换到 AVA 检查点

默认 preset 使用 `finetuning-talkset` 权重（在真实场景的语音上效果更好）。将 active-speaker-detector 组件的 `preset` 设置为 `pretrain-ava-cvpr` 以匹配素材的训练分布：

```yaml
- id: active-speaker-detector
  type: model
  task: active-speaker-detection
  driver: custom
  family: light-asd
  preset: pretrain-ava-cvpr
```

### 修剪或填充说话片段

组件的 `params` 块暴露了片段 shaping 的 knob：

```yaml
params:
  smoothing_window: 0.4s       # 窗口越长抑制闪烁越多
  threshold: 0.0               # 调高变得更严格；调低可捕捉更安静的说话
  min_segment_duration: 0.3s   # 合并后短于此长度的片段将被丢弃
  merge_gap: 0.2s              # 同一轨迹中相距最多此间隔的片段将被合并
```

### 仅时间线，无按轨迹拆分

设置 `return_speakers: false` 和 `return_timeline: true` 以放弃按轨迹的拆分，仅返回按时间排序的扁平列表。detector 内部仍会按轨迹进行评分——这只是隐藏了拆分结果。

## 故障排除

### 常见问题

1. **未返回说话片段**：确认 `audio` 输入确实包含语音——Light-ASD 无论人脸是否在动都会将静音判为非说话。另外确认 `sampled_frame_rate` ≈ 25；偏差较大会将人脸裁剪推到 MFCC 窗口未对齐的帧上，使 logit 变平。
2. **多个说话人被合并到同一条轨迹**：join 基于 face-tracking 的 `track_id`——如果两个不同的人共享一条轨迹，speaker detector 会把他们的说话都归属到该单一轨迹上。此时请调节 face-tracker 的 `similarity_threshold`。
3. **找不到模型文件**：Light-ASD 检查点和上游源码会自动 provisioning。如果首次运行失败，请确认 `git` 在 `PATH` 中，并且机器可以访问 `github.com` / `raw.githubusercontent.com`。
4. **`frame_rate` 不匹配警告**：确认 `sampled_frame_rate` 与 `source_fps / frame_interval` 一致。

### 性能优化

- **GPU**：安装启用了 CUDA 的 `torch`（以及可选的 `onnxruntime-gpu` 用于人脸追踪）以加快推理。
- **更短的帧序列**：按比例降低 `sampled_frame_rate` 和 `frame_interval`——Light-ASD 以 25 fps 训练，因此保持在该附近对评分质量很重要。
