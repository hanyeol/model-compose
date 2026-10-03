# Image-Text Scoring 模型任务示例

本示例展示如何通过 model-compose 内置的 `image-text-scoring` 任务，使用本地 CLIP 模型为图像与文本的语义匹配打分。两个工作流覆盖了全部模式：单对的 CLIPScore，以及可兼作零样本分类的广播排序。

## 概述

`image-text-scoring` 任务运行 CLIP（或 SigLIP）模型的前向过程，返回密集分数——余弦相似度、可选的 softmax 前 logit、可选的 softmax 概率——而不是嵌入。评分模式会根据输入形状自动决定：

- `pairwise` — 1 张图像 × 1 条文本（或 N × N）。每对一个余弦。
- `texts_to_image` — 1 张图像 × N 条文本。每条文本一个余弦；softmax 对文本进行排序。
- `images_to_text` — N 张图像 × 1 条文本。每张图像一个余弦；softmax 对图像进行排序。

长度不匹配（例如 2 张图像 × 3 条文本）会抛出错误。

## 准备

### 前置条件

- model-compose 已安装并在 PATH 中可用
- 具备运行 CLIP 的足够系统资源（建议 8GB+ 内存，GPU 可选）
- 包含 `transformers` 和 `torch` 的 Python 环境（自动管理）

### 为何使用评分（而非嵌入）

双编码器嵌入任务（`image-embedding`、`text-embedding`）返回原始向量——相似度选择、阈值设置、两侧拼接都需在下游自己完成。`image-text-scoring` 把这些压缩进一次调用，直接返回你真正想要的数值：

- **CLIPScore 质量门控** — 根据生成图像与提示词的匹配程度决定接受或拒绝。
- **文本排序** — 对一张图像从若干候选文本中挑选最佳。
- **零样本分类** — 将标签当作文本，与图像一起打分，读取 softmax 作为类别概率。无需训练。

当需要持久化检索向量时，该任务并不替代嵌入；当最终结果就是一个分数时，它取代了"胶水代码"。

### 环境配置

1. 进入示例目录：
   ```bash
   cd examples/model-tasks/image-text-scoring
   ```

2. 无需额外环境配置——模型在首次运行时自动下载并缓存。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **工作流 1 — CLIPScore (pairwise)：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/clip-score/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "image": "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
         "text": "a photo of a cat"
       }
     }'
   ```

   **使用 CLI：**
   ```bash
   model-compose run clip-score --input '{
     "image": "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
     "text": "a photo of a cat"
   }'
   ```

   返回类似 `{"cosine": 0.28}` 的单个标量余弦。

3. **工作流 2 — 候选排序（broadcast）：**

   1 张图像 × 多条文本（文本排序）：
   ```bash
   model-compose run rank-candidates --input '{
     "image": "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
     "text": [
       "a photo of a cat",
       "a photo of a dog",
       "a photo of a car",
       "a photo of a bowl of fruit"
     ]
   }'
   ```

   返回每条文本的余弦列表以及文本轴的 softmax 概率。softmax 最高的文本就是模型的零样本标签。

   多张图像 × 1 条文本（图像排序）——同一工作流，只需翻转形状：
   ```bash
   model-compose run rank-candidates --input '{
     "image": [
       "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
       "https://images.unsplash.com/photo-1518717758536-85ae29035b6d",
       "https://images.unsplash.com/photo-1552053831-71594a27632d"
     ],
     "text": "a photo of a cat"
   }'
   ```

   返回每张图像一个余弦和图像轴 softmax。

   **使用 Web UI：** 打开 http://localhost:8081，选择工作流并填入输入。

## 组件详情

### Image-Text Scoring 模型组件

- **类型**：使用 `image-text-scoring` 任务的 Model 组件
- **驱动**：`huggingface`
- **架构**：`clip`（CLIP 的图像/文本联合投影，带 logit-scale softmax）
- **模型**：`openai/clip-vit-base-patch32`
- **共享模型，两种动作**：
  - `score` — pairwise 形状；返回标量 `cosine`
  - `rank` — broadcast 形状；返回列表 `cosine` 和 softmax 概率

### 模型信息：CLIP ViT-Base/32

- **开发方**：OpenAI
- **骨干**：ViT-Base/32 图像编码器 + 12 层文本 Transformer
- **投影**：带可学习 logit scale 的共享图像/文本嵌入空间
- **许可证**：MIT

## 工作流详情

### 工作流 1 — "CLIPScore (pairwise)"

1 张图像 + 1 条文本 → 标量余弦。经典的 CLIPScore 信号。

#### 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `image` | image | 是 | 单张图像（URL、路径或 base64） |
| `text` | text | 是 | 单条文本 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `cosine` | number | 图像与文本的余弦相似度（−1 ~ 1）。 |

### 工作流 2 — "候选排序（broadcast）"

一侧多项的评分。任务根据输入长度自动选择 `texts_to_image` 或 `images_to_text`。

#### 输入参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `image` | image \| image[] | 是 | 1 张图像或图像列表。 |
| `text` | text \| text[] | 是 | 1 条文本或文本列表。必须恰好一侧长度为 1 才触发广播；长度相等则为 pairwise。 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `cosine` | number[] | "多侧"每个候选一个余弦。 |
| `softmax` | number[] | "多侧"的 softmax 概率；概率最高的索引为排序第一。 |

#### 评分模式矩阵

| `image` 长度 | `text` 长度 | 模式 | 分数形状 |
|-------------|------------|------|---------|
| 1 | 1 | `pairwise` | 标量余弦 |
| N | N | `pairwise` | 每对一个余弦 |
| 1 | N (>1) | `texts_to_image` | 余弦列表 + 文本轴 softmax |
| N (>1) | 1 | `images_to_text` | 余弦列表 + 图像轴 softmax |
| N (>1) | M (>1), N ≠ M | 错误 | — |

## 系统要求

### 最低要求

- **内存**：8GB（建议 16GB+）
- **显存**：可选；4GB+ GPU 可显著加速批量评分
- **磁盘空间**：ViT-B/32 检查点约 600MB
- **CPU**：多核处理器（建议 4 核以上）
- **互联网**：首次下载模型时需要

### 性能说明

- 首次运行会下载模型（约 600MB）
- pairwise 工作流 CPU 推理即可满足；批量排序在 GPU 上收益更大
- 小尺寸图像在 CPU 上的延迟主要集中在图像预处理（224×224 缩放）

## 自定义

### 使用其他 CLIP / SigLIP 检查点

替换为更大的 CLIP 或 SigLIP 检查点：

```yaml
components:
  - id: scorer
    type: model
    task: image-text-scoring
    driver: huggingface
    architecture: clip
    model: openai/clip-vit-large-patch14   # 精度更高，速度更慢
```

```yaml
components:
  - id: scorer
    type: model
    task: image-text-scoring
    driver: huggingface
    architecture: siglip
    model: google/siglip-base-patch16-224  # SigLIP（sigmoid loss 变体）
```

### 零样本分类提示模板

当文本遵循 "a photo of a {label}" 模板时分数提升明显：

```json
{
  "image": "https://example.com/animal.jpg",
  "text": [
    "a photo of a cat",
    "a photo of a dog",
    "a photo of a horse"
  ]
}
```

单纯的裸标签（`"cat"`、`"dog"`）也可工作，但通常会得到对比度较低的 softmax 分布。

### 返回原始 logit

CLIP 的余弦范围较窄（自然图像约为 −0.1 ~ 0.4）；softmax 前的 logit（余弦 × logit_scale）会把信号扩展到约 [−3, 30]，更便于设阈值：

```yaml
params:
  return_logit: true
```

## 故障排查

### 常见问题

1. **长度不匹配错误** — 两个输入列表长度不同且都不为 1。要么对齐长度（pairwise），要么把一侧设为单元素。
2. **模型下载失败** — 检查网络连接和磁盘空间。
3. **余弦整体偏低** — 即便是正确对，CLIP 的余弦也接近 0。阈值应参考 softmax 概率或原始 logit，而非仅看余弦。
4. **Softmax 看起来很平** — 裸标签或非常相似的文本会压缩分布。改用 "a photo of a {label}" 模板，或切换到更大的检查点。

### 性能优化

- **GPU**：设置 `device: cuda:0`（Apple Silicon 上为 `mps`）可显著加快推理
- **批次大小**：huggingface 驱动自动批处理评分任务；把候选放在同一次调用，而不是拆成 N 次
- **模型大小**：延迟敏感的门控选 ViT-B/32，追求最高精度选 ViT-L/14

## 与 Image Embedding + 余弦的比较

| 特性 | `image-text-scoring` | `image-embedding` + `text-embedding` |
|------|----------------------|---------------------------------------|
| 返回 | 余弦（+ logit、softmax） | 独立的图像和文本向量 |
| 下游胶水代码 | 无 | 需手动计算余弦 / softmax |
| 向量缓存 | 否 | 是（持久化到 vector store） |
| 适用场景 | 一次性门控、排序、分类 | 检索、去重、聚类 |

需要即时判断就选 scoring；需要日后检索的向量就选 embedding。
