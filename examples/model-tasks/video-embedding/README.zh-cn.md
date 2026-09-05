# 视频嵌入模型任务示例

本示例演示如何使用 model-compose 内置的 `video-embedding` 任务，通过 X-CLIP 为上传的视频生成单一视频级嵌入。从视频中采样帧，输入 X-CLIP 的视觉编码器 + 多帧集成 transformer，并将其压缩为一个 512 维向量，该向量与 X-CLIP 文本编码器共享同一个视频-文本联合空间——从而可以对该向量进行自然语言检索，无需对每次查询重新编码视频。

## 概述

此工作流提供本地视频嵌入功能：

1. **本地视频编码器**：通过 HuggingFace transformers 在本地运行 X-CLIP，无需外部 API
2. **定长向量**：将任意长度的视频压缩为适合余弦相似度检索的 512 维 L2 归一化嵌入
3. **视频-文本联合空间**：该向量与 X-CLIP 的文本嵌入位于同一空间，因此文本查询可直接检索视频
4. **自动帧处理**：嵌入器将提取的帧重采样为 X-CLIP 训练时使用的帧数（`-patch16` 为 32，`-patch32` 为 8），因此无需精确匹配提取器的步长

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 已安装 ffmpeg 并在 PATH 中可用（用于帧提取）
- 运行 X-CLIP 所需的充足系统资源（推荐：8GB+ RAM，GPU 可选但可加速推理）
- 带有 `transformers`、`torch` 和 `accelerate` 的 Python 环境（首次运行时自动安装）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/video-embedding
   ```

2. 无需额外的环境配置 — X-CLIP 检查点将在首次运行时从 HuggingFace 下载。

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
     -F 'input={"video": "@clip", "frame_interval": 15}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `video` 文件
   - 按需调整 `frame_interval` / `max_frame_count`
   - 点击"Run Workflow"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 15}'
   ```

## 组件详情

### 帧提取器组件
- **类型**：`video-frame-extractor`
- **驱动**：`ffmpeg`
- **用途**：以固定节奏从输入视频中采样帧，并作为实体化列表传递给嵌入器
- **关键参数**：`frame_interval`（步长；1 = 每帧，15 = 每 15 帧）与 `max_frame_count`（提取列表的上限，适合长视频）
- **非流式**：X-CLIP 在一次前向传播中同时编码所有帧，因此嵌入器需要在运行前拿到完整列表。

### 视频嵌入模型组件
- **类型**：带 `video-embedding` 任务的模型组件
- **驱动**：`huggingface`
- **架构**：`xclip`
- **模型**：`microsoft/xclip-base-patch16-zero-shot`
- **功能**：
  - 在本地运行 X-CLIP 的视觉编码器 + 多帧集成 transformer（MIT）
  - 将提取的帧列表均匀重采样至 X-CLIP 期望的帧数（`-patch16` 为 32，`-patch32` 为 8）
  - 输出 512 维 L2 归一化的 float 向量 — 与 X-CLIP 文本嵌入的余弦相似度即为点积
  - 串行执行（`max_concurrent_count: 1`），以控制 GPU 内存占用

### 模型信息：X-CLIP base-patch16（零样本）
- **开发者**：Microsoft
- **架构**：CLIP ViT-B/16 视觉编码器 + 多帧集成 transformer + CLIP 文本编码器
- **训练帧**：32 帧 @ 224x224
- **嵌入维度**：512
- **训练数据集**：Kinetics-400
- **零样本准确率**：Kinetics-600 上 65.2%、UCF-101 上 72.0%、HMDB-51 上 44.6%
- **许可证**：MIT
- **模型卡片**：[microsoft/xclip-base-patch16-zero-shot](https://huggingface.co/microsoft/xclip-base-patch16-zero-shot)

## 工作流详情

### 默认工作流

**描述**：从上传的视频采样帧，运行 X-CLIP，并返回单个视频嵌入。

#### 作业流程

```mermaid
graph TD
    Input((输入<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[image, ...]| J1

    J1 --> J2((embed<br/>job))
    J2 -.-> C2[Video Embedder<br/>X-CLIP]
    C2 -.-> |[512 维向量]| J2

    J2 --> Output((输出<br/>embedding))
```

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----|------|------|--------|------|
| `video` | video（文件） | 是 | - | 输入视频文件 |
| `frame_interval` | number | 否 | 15 | 提取时每 N 帧采样一次。值越小对源覆盖越密，代价是提取成本更高。 |
| `max_frame_count` | number | 否 | 64 | 提取帧列表的上限。嵌入器会将其重采样到 X-CLIP 的训练帧数（32），因此 ≥ 该值均可 — 更大只会浪费提取时间。 |

#### 输出格式

| 字段 | 类型 | 描述 |
|-----|------|------|
| `embedding` | number[] | 512 个浮点数。已 L2 归一化，因此 `dot(a, b)` 等于余弦相似度。 |

示例：

```json
{
  "embedding": [0.023, -0.451, 0.187, ...]
}
```

## 系统要求

### 最低要求
- **RAM**：8GB（推荐 16GB+）
- **磁盘空间**：X-CLIP 检查点约 1GB
- **CPU**：任何现代 x86_64 或 ARM64 处理器
- **GPU**：可选（CUDA / MPS）— 可显著加速推理
- **互联网**：仅一次性模型下载需要

### 性能说明
- 首次运行下载 X-CLIP 检查点（约 400MB）并初始化 transformers — 后续运行明显更快
- 推理成本由 32 帧 ViT-B/16 前向传播主导 — 中端 GPU 上数百毫秒，CPU 上数秒
- 帧提取成本随 `frame_interval` 变化 — 降低它（更密集采样）仅在 `max_frame_count` 以内有效

## 自定义

### 更快的模型（更少的帧）

以少量精度损失换取约 4 倍推理提速，切换到 8 帧 `-patch32` 变体：

```yaml
- id: video-embedder
  type: model
  task: video-embedding
  driver: huggingface
  architecture: xclip
  model: microsoft/xclip-base-patch32
```

嵌入器会从模型的 config 读取期望帧数，因此无需其他更改。

### 自定义 X-CLIP 检查点

HuggingFace 上任何 X-CLIP 系列检查点都可以使用 — 只需替换 `model:` 字段。若加载非 X-CLIP 但也提供 `get_video_features` 的视频编码器，请设置 `architecture: auto`。

### 短视频的更密集采样

若视频短于 `frame_interval × 32`，请降低 `frame_interval`（或去掉 `max_frame_count`）使 ffmpeg 至少产生 32 帧 — 这样嵌入器就能为每个 X-CLIP 输入槽提供真实帧，而不是重复最后一帧。

## 集成示例

### 与向量存储集成（索引）

对每个视频嵌入一次，存储向量并稍后检索：

```yaml
workflows:
  - id: index-video
    jobs:
      - id: frames
        component: frame-extractor
        input:
          video: ${input.video as video}

      - id: embed
        component: video-embedder
        depends_on: [ frames ]
        input:
          frames: ${jobs.frames.output}

      - id: store
        component: vector-store
        depends_on: [ embed ]
        input:
          vector: ${jobs.embed.output}
          metadata:
            video_id: ${input.video_id}
            title: ${input.title}
```

### 与文本检索集成（检索）

以自然语言搜索已索引的视频。由于 X-CLIP 与其自身的文本编码器共享嵌入空间，文本侧也需要使用同一 X-CLIP 检查点：

```yaml
workflows:
  - id: search-videos
    jobs:
      - id: embed-query
        component: xclip-text-embedder
        input:
          text: ${input.query}

      - id: search
        component: vector-store
        depends_on: [ embed-query ]
        input:
          action: search
          vector: ${jobs.embed-query.output}
          top_k: 10
```

> **注意**：X-CLIP 的文本分支与视频分支联合训练，因此文本查询必须使用同一 X-CLIP 模型嵌入 — 通用的 sentence-transformers 嵌入无法与视频向量空间对齐。

## 故障排除

### 常见问题

1. **推理期间内存不足**：降到 `-patch32` 变体，或在模型组件上设置 `device: cpu` 转到 CPU。
2. **极短视频，嵌入全部重复**：若源共不足 32 帧，嵌入器会复制最后一帧填满输入张量。请降低 `frame_interval` 或接受降级的保真度。
3. **模型下载失败**：检查网络连通性与 HuggingFace 可用性；首次运行会拉取约 400MB。
4. **文本查询无法匹配**：你可能使用了非 X-CLIP 的文本编码器。仅当文本与视频嵌入均来自同一 X-CLIP 检查点时才对齐。

### 性能优化

- **GPU**：在模型组件上设置 `device: cuda`（NVIDIA）或 `device: mps`（Apple Silicon），相较 CPU 可获得数量级提速
- **更小的模型**：`-patch32`（8 帧）比 `-patch16`（32 帧）快约 4 倍，在通用动作识别上精度损失有限
- **批处理多个视频**：将 `frames:` 设为列表的列表以在一次前向传播中嵌入多个视频（`batch_size` 控制共享 GPU 流的数量）

## 相关示例

- `text-embedding`：从文本生成嵌入（配合匹配的 X-CLIP 检查点用于跨模态检索）
- `image-embedding`：使用 CLIP / SigLIP / DINOv2 的单图像变体
- `face-tracking`：视频中每个人物的时段 — 可与视频嵌入一起索引的正交信号
