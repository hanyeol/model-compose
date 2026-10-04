# Video-Text Scoring 模型任务示例

本示例展示如何通过 model-compose 内置的 `video-text-scoring` 任务，使用本地 X-CLIP 模型为视频与文本的语义匹配打分。两个工作流覆盖了核心场景：用于文本到视频输出的 CLIPScore 风格标量门控，以及对候选文本进行排序的零样本视频分类器。

## 概述

X-CLIP 的 forward 会根据正在打分的视频对文本嵌入进行条件化调整，因此通过 `video-embedding` + `text-embedding` 分别嵌入两侧**无法复现**分数。`video-text-scoring` 任务直接调用完整的 X-CLIP forward，返回密集分数——余弦相似度、可选的 softmax 前 logit、可选的 softmax 概率。

评分模式根据输入形状自动决定：

- `pairwise` — N 个视频 × N 条文本。每对一个余弦。
- `texts_to_video` — 1 个视频 × K 条文本。沿文本轴返回余弦列表；softmax 对文本进行排序。
- `videos_to_text` — N 个视频 × 1 条文本。沿视频轴返回余弦列表；softmax 对视频进行排序。

长度不匹配会抛出错误。

## 准备

### 前置条件

- model-compose 已安装并在 PATH 中可用
- `ffmpeg` 在 PATH 中（帧提取器使用）
- 具备运行 X-CLIP 的足够系统资源（建议 12GB+ 内存；延迟敏感的门控建议使用 GPU）
- 包含 `transformers` 和 `torch` 的 Python 环境（自动管理）

### 为何使用评分（而非嵌入）

对 CLIP（图像-文本）而言，两侧分别嵌入后取余弦可以精确复现 CLIPScore。但对 X-CLIP **则不行**——文本嵌入依赖于被打分的视频。因此 `video-text-scoring` 是**获取真实 X-CLIP 分数的唯一途径**：

- **文本到视频的质量门控** — 根据生成的片段与提示词的匹配度决定接受或拒绝。
- **零样本视频分类** — 将标签当作文本，对视频与所有标签打分，读取 softmax 作为类别概率。无需训练。
- **视频检索排序** — 针对单个文本查询对 N 个候选片段排序。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/video-text-scoring
   ```

2. 无需额外环境配置——模型在首次运行时自动下载并缓存。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **工作流 1 — 视频 × 提示词评分（pairwise）：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/score-video/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "video": "https://example.com/clip.mp4",
         "text": "a chef chopping vegetables in a kitchen"
       }
     }'
   ```

   **使用 CLI：**
   ```bash
   model-compose run score-video --input '{
     "video": "https://example.com/clip.mp4",
     "text": "a chef chopping vegetables in a kitchen"
   }'
   ```

   返回类似 `{"cosine": 0.26}` 的单个标量余弦。

3. **工作流 2 — 零样本视频分类：**

   ```bash
   model-compose run classify-video --input '{
     "video": "https://example.com/clip.mp4",
     "text": [
       "a cooking video",
       "a sports highlight",
       "an animated short",
       "a dance performance"
     ]
   }'
   ```

   返回每条文本的余弦列表以及文本轴的 softmax 概率。softmax 最高的文本就是模型的零样本标签。

   **使用 Web UI：** 打开 http://localhost:8081，选择工作流并填入输入。

## 组件详情

### Video-Text Scoring 模型组件

- **类型**：使用 `video-text-scoring` 任务的 Model 组件
- **驱动**：`huggingface`
- **架构**：`xclip`（视频条件化文本嵌入）
- **模型**：`microsoft/xclip-base-patch32`
- **共享模型，两种动作**：
  - `score` — pairwise 形状；返回标量 `cosine`
  - `rank` — texts_to_video 形状；返回列表 `cosine` 和 softmax 概率

### 帧采样器（Video Frame Extractor）

- **类型**：`video-frame-extractor`
- **驱动**：`ffmpeg`
- 每秒约 2 帧，每个片段最多 32 帧。X-CLIP 内部会重新采样到自身期望的帧数（8 帧），因此超采样是安全的。

### 模型信息：X-CLIP ViT-Base/32

- **开发方**：Microsoft
- **骨干**：ViT-Base/32 图像编码器 + 多帧集成 Transformer（MIT）+ 带视频条件化提示的 CLIP 文本 Transformer
- **投影**：带可学习 logit scale 的共享视频/文本嵌入空间
- **训练数据**：Kinetics-400 / 600
- **许可证**：MIT

## 工作流详情

### 工作流 1 — "视频 × 提示词评分（pairwise）"

1 个视频 + 1 条文本 → 标量余弦。典型的文本到视频质量门控。

#### 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `video` | video | 是 | 1 个视频（URL、路径或 data URI） |
| `text` | text | 是 | 1 条文本 / 提示词 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `cosine` | number | 视频与文本的余弦相似度。 |

### 工作流 2 — "零样本视频分类"

1 个视频 + 候选文本列表 → 排序分布。

#### 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `video` | video | 是 | 1 个视频。 |
| `text` | text[] | 是 | 候选文本（当作类别标签使用）。 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `cosine` | number[] | 每个候选文本一个余弦。 |
| `softmax` | number[] | 候选文本轴的 softmax 概率；概率最高的索引为排序第一的标签。 |

#### 评分模式矩阵

| `videos` 长度 | `texts` 长度 | 模式 | 分数形状 |
|-------------|------------|------|---------|
| 1 | 1 | `pairwise` | 标量余弦 |
| N | N | `pairwise` | 每对一个余弦 |
| 1 | K (>1) | `texts_to_video` | 余弦列表 + 文本轴 softmax |
| N (>1) | 1 | `videos_to_text` | 余弦列表 + 视频轴 softmax |
| N (>1) | M (>1), N ≠ M | 错误 | — |

## 系统要求

### 最低要求

- **内存**：12GB（建议 16GB+）
- **显存**：强烈建议 4GB+ GPU；CPU 推理比 CLIP 慢 10–20 倍（因多帧集成 Transformer）
- **磁盘空间**：ViT-B/32 X-CLIP 检查点约 600MB
- **CPU**：多核处理器（建议 4 核以上）
- **互联网**：首次下载模型时需要

### 性能说明

- 首次运行会下载模型（约 600MB）
- 短片段的 CPU 处理中帧提取主导延迟；用 `fps` 设置上限
- X-CLIP 的 MIT 执行跨帧注意力——更长的片段的成本高于单纯帧数所暗示的

## 自定义

### 对多个视频使用同一文本评分

将若干视频以嵌套帧列表的形式放在一次调用里，评分器会用一次 forward 计算 `videos_to_text` 完整交叉矩阵：

```yaml
jobs:
  - id: score
    component: scorer
    action: rank
    input:
      frames:
        - ${jobs.extract-a.output}
        - ${jobs.extract-b.output}
        - ${jobs.extract-c.output}
      text: "a cooking video"
```

结果的 `cosine` 与 `softmax` 为视频轴列表——softmax 最高的索引为排序第一的视频。

### 零样本分类的提示模板

与 CLIP 一样，使用模板会提升分数质量：

```json
{
  "video": "https://example.com/clip.mp4",
  "text": [
    "a video of cooking",
    "a video of a sports game",
    "a video of a dance performance"
  ]
}
```

### 返回原始 logit

X-CLIP 的余弦范围较窄；softmax 前的 logit（余弦 × logit_scale）会把信号扩展到更宽的范围，便于设阈值：

```yaml
params:
  return_logit: true
```

## 故障排查

### 常见问题

1. **长度不匹配错误** — 视频和文本都超过 1 个且长度不同。要么对齐长度（pairwise），要么把一侧设为单元素。
2. **模型下载失败** — 检查网络连接和磁盘空间。
3. **Softmax 看起来很平** — 文本之间过于相似，或片段超出 X-CLIP 的 Kinetics 预训练分布。使用 "a video of {label}" 模板，或添加更有区分度的候选。
4. **分数总是接近 0** — 即便正确对，原始余弦也接近 0。阈值应参考 softmax 概率或原始 logit，而非仅看余弦。
5. **找不到 ffmpeg** — 安装 `ffmpeg` 并确保在 PATH 中。

### 性能优化

- **GPU**：设置 `device: cuda:0`（Apple Silicon 上为 `mps`）可显著加速
- **帧预算**：短片段上降低提取器的 `fps` 和 `max_frame_count`；模型本就会内部重采样
- **批次**：把多视频任务（嵌套帧）放入一次调用中，比运行 N 个独立工作流更高效

## 与 video-embedding + 余弦的比较

| 特性 | `video-text-scoring` | `video-embedding` + `text-embedding` |
|------|----------------------|---------------------------------------|
| 返回 | 余弦（+ logit、softmax） | 独立的视频和文本向量 |
| 复现模型自身的分数 | 可以 | **不可以**（X-CLIP 根据视频对文本嵌入做条件化） |
| 向量缓存 | 否 | 是（持久化到 vector store） |
| 适用场景 | 一次性门控、排序、零样本分类 | 检索、去重、聚类 |

需要 X-CLIP 分数本身就选 scoring；仅在需要把视频向量存到磁盘以供后续检索时才选 embedding——缓存的向量无法再次复现 X-CLIP 所报告的余弦。
