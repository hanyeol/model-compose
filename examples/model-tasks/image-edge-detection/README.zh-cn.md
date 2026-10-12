# 图像边缘检测模型任务示例

此示例演示 model-compose 中基于模型的边缘检测器：HED、PiDiNet 和 Lineart。三者都生成单通道边缘图，适用于图像或视频生成的 ControlNet 条件输入。

## 概述

三个模型作为独立的工作流暴露：

1. **HED**（Holistically-Nested Edge Detection）— 经典软边缘，ControlNet HED/softedge 广泛使用
2. **PiDiNet**（Pixel Difference Network）— 紧凑的软边缘，权重比 HED 更轻
3. **Lineart** — 动漫风格线条提取，两个变体（realistic / coarse）

所有权重位于公开的 `lllyasviel/Annotators` HuggingFace repo，首次使用时自动下载。

## 准备工作

### 前置条件

- 已安装 model-compose 并在 PATH 中可用
- 具有 torch、numpy、PIL 的 Python 环境（自动管理）
- 首次运行需要互联网访问（模型下载）

### 模型权重

| Family              | 权重文件               | 大小    |
|---------------------|------------------------|---------|
| HED                 | `ControlNetHED.pth`    | ~56 MB  |
| PiDiNet             | `table5_pidinet.pth`   | ~2 MB   |
| Lineart (realistic) | `sk_model.pth`         | ~17 MB  |
| Lineart (coarse)    | `sk_model2.pth`        | ~17 MB  |

所有检查点都来自 `lllyasviel/Annotators`，缓存到标准 HuggingFace 缓存目录。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/hed/runs \
     -F "image=@/path/to/your/input-image.jpg"
   ```

   将 `hed` 替换为 `pidinet` 或 `lineart` 来调用其他预处理器。

   **使用 Web UI：**
   - 打开 http://localhost:8081
   - 选择工作流并上传图像
   - 点击 "Run Workflow"

   **使用 CLI：**
   ```bash
   model-compose run hed --input '{"image": "/path/to/your/input-image.jpg"}'
   ```

## 组件详情

### HED 组件
- **架构**：带有侧输出 score layer 的 VGG16 风格五阶段编码器（Xie & Tu, 2015），融合为单个边缘图
- **输入预处理**：BGR、ImageNet 均值减法、[0, 255]
- **输出**：灰度边缘图，亮像素 = 边缘

### PiDiNet 组件
- **架构**：Pixel-difference convolution network（Su et al., ICCV 2021），`lllyasviel/Annotators` 使用的 Table 5 变体
- **输入预处理**：RGB，归一化到 [0, 1]
- **输出**：灰度边缘图

### Lineart 组件
- **架构**：ResNet-9 U-Net generator（Anime2Sketch / Mukosame），ControlNet 1.1 lineart 使用
- **变体**：
  - `realistic` — `sk_model.pth`，详细线条提取
  - `coarse` — `sk_model2.pth`，简化线条
- **输入预处理**：RGB in `[-1, 1]`
- **输出**：灰度线条图（输出已反转使边缘在深色背景上明亮，与 ControlNet 约定一致）

## 自定义

### 反转输出

ControlNet lineart 变体有时期望深色背景上亮线条的默认约定之外的相反情况（亮色背景上暗线条）。翻转输出：

```yaml
action:
  image: ${input.image as image}
  invert: true
```

### 更改输入分辨率

默认输入大小为 512（模型原生）。提高以获得更清晰的细节，降低以加快速度：

```yaml
action:
  image: ${input.image as image}
  params:
    image_size: 768
```

### 安全模式（HED / PiDiNet）

抑制在 ControlNet 下常常成为伪造背景纹理的弱边缘：

```yaml
action:
  image: ${input.image as image}
  params:
    use_safe_mode: true
```

### 接入 ControlNet 工作流

将 edge 预处理器链接到基于 ControlNet 的图像或视频生成器之前：

```yaml
workflow:
  jobs:
    - id: edges
      component: hed
      input:
        image: ${input.image}
    - id: generate
      component: controlnet-generator
      input:
        prompt: ${input.prompt}
        control_image: ${edges.output}
```

### 批处理和流式处理

传递图像列表或帧提取器流以生成视频管道的逐帧边缘图：

```yaml
action:
  image: ${input.frames}
  batch_size: 4
```

## 故障排除

### 常见问题

1. **内存不足**：减小 `params.image_size` 或 `batch_size`；切换到 PiDiNet（最轻量）
2. **模型下载失败**：检查互联网连接和 HuggingFace 缓存目录权限
3. **平坦/噪点输出**：尝试 `use_safe_mode: true`（HED/PiDiNet）或提高 `image_size`
4. **约定错误**：如果 ControlNet 期望亮色背景上暗边缘，添加 `invert: true`

## 基于模型 vs 算法化边缘检测

对于不需要模型权重的纯算法边缘检测，请参见 `image-processor` 组件的 OpenCV driver 的 `canny` method。两种方法相互补充：

- **Canny** — 快速、无权重、确定性。最适合光线充足、边界清晰的主体。
- **HED / PiDiNet / Lineart** — 基于模型，更擅长经典算法所遗漏的语义边缘（头发、柔和的渐变、衣物褶皱）。大多数 ControlNet 1.1 edge/line 条件所必需。
