# 深度估计模型任务示例

此示例演示如何使用 model-compose 的内置 depth-estimation 任务通过 Depth Anything V2 从输入图像生成单目深度图，适用于作为 ControlNet 的条件输入或下游场景理解。

## 概述

此工作流生成逐像素深度图，具备以下特性：

1. **本地深度模型**：在本地运行 Depth Anything V2 估计相对深度
2. **灰度输出**：返回归一化到 0–255 的单通道深度图（默认近处像素更亮）
3. **ControlNet 就绪**：灰度输出可直接馈入 ControlNet depth 模型
4. **自动模型管理**：首次使用时自动下载和缓存模型
5. **无外部 API**：完全离线的深度估计

## 准备工作

### 前置条件

- 已安装 model-compose 并在 PATH 中可用
- 运行 Depth Anything V2 的足够资源（推荐：8GB+ RAM，首选 GPU）
- 具有 torch 和 transformers 的 Python 环境（自动管理）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/depth-estimation
   ```

2. 无需额外配置 — 模型和依赖项自动管理。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/input-image.jpg"
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 选择输入图像
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   model-compose run depth-estimation --input '{"image": "/path/to/your/input-image.jpg"}'
   ```

## 组件详情

### 深度估计模型组件（默认）
- **类型**：使用 depth-estimation 任务的模型组件
- **用途**：单目相对深度估计
- **模型**：depth-anything/Depth-Anything-V2-Small-hf
- **架构**：Depth Anything V2（DPT 风格 ViT）
- **特性**：
  - 对真实场景图像的强大零样本相对深度估计
  - 可直接用于 ControlNet depth 条件的灰度输出
  - GPU 加速支持

### 模型信息：Depth Anything V2

- **开发者**：DepthAnything（开源）
- **架构**：DINOv2 ViT 骨干网之上的 DPT head
- **训练**：大规模合成 + 真实相对深度数据
- **优势**：清晰的边界，跨场景的强泛化能力
- **输入/输出**：RGB 图像 → 单通道相对深度图

## 工作流详情

### "Estimate Image Depth" 工作流（默认）

**描述**：使用预训练的单目深度模型从输入图像生成深度图。

#### 输入参数

| 参数     | 类型   | 必需 | 默认值 | 描述                                |
|----------|--------|------|--------|-------------------------------------|
| `image`  | image  | 是   | -      | 输入图像文件（JPEG、PNG 等）        |

#### 输出格式

| 字段 | 类型   | 描述                                   |
|------|--------|----------------------------------------|
| -    | image  | 单通道灰度深度图（L 模式）              |

## 自定义

### 反转深度约定

某些 ControlNet depth 模型期望远处像素更亮而不是近处。翻转输出：

```yaml
component:
  type: model
  task: depth-estimation
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Small-hf
  action:
    image: ${input.image as image}
    invert: true
```

### 覆盖输入分辨率

默认输入大小遵循模型自己的 image processor。当需要更精细的细节或更快的推理时覆盖它：

```yaml
component:
  type: model
  task: depth-estimation
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Small-hf
  action:
    image: ${input.image as image}
    params:
      image_size: 518    # Depth Anything V2 原生尺寸
```

### 使用其他模型

任何暴露 `AutoModelForDepthEstimation` 的 HuggingFace 模型均可工作。DPT 和 Depth Anything 变体通过 `architecture` 字段获得一流支持：

```yaml
# Depth Anything V2 Base（更高质量，更慢）
component:
  type: model
  task: depth-estimation
  architecture: depth-anything
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Base-hf
  action:
    image: ${input.image as image}

# Intel DPT Large（经典 DPT 基线）
component:
  type: model
  task: depth-estimation
  architecture: dpt
  model:
    provider: huggingface
    repository: Intel/dpt-large
  action:
    image: ${input.image as image}
```

### 批处理和视频处理

传递图像列表或上游帧提取器流：

```yaml
component:
  type: model
  task: depth-estimation
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Small-hf
  action:
    image: ${input.frames}
    batch_size: 4
```

这使组件适合作为接收 `conditioning_frames` 的 ControlNet 基础 video-to-video 管道的上游预处理器。

## 故障排除

### 常见问题

1. **内存不足**：减小 `params.image_size` 或 `batch_size`，或切换到 Small 变体
2. **模型下载失败**：检查互联网连接和磁盘空间
3. **处理缓慢**：确保已启用 GPU 加速
4. **平坦/噪点深度**：尝试更大的变体（Base/Large）或增加 `params.image_size`

## 模型变体

- **depth-anything/Depth-Anything-V2-Small-hf**：默认。快速，~100MB
- **depth-anything/Depth-Anything-V2-Base-hf**：更好的质量，较慢
- **depth-anything/Depth-Anything-V2-Large-hf**：最高质量，最慢
- **Intel/dpt-large**：经典 DPT 基线
- **Intel/dpt-hybrid-midas**：DPT 混合变体
