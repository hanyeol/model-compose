# Image Processor (OpenCV) 示例

此示例演示 model-compose `image-processor` 组件的 OpenCV driver。它使用 PIL 之外的经典计算机视觉算法 — 从 Canny 边缘检测开始，这是常见的 ControlNet 条件输入。

## 概述

`opencv` driver 使用 OpenCV 专用算法补充默认的 `native`（PIL）driver：

1. **Canny 边缘检测**：从输入图像生成单通道边缘图
2. **无头模式**：纯算法，无需下载模型权重
3. **ControlNet 就绪**：灰度输出直接馈入 ControlNet canny

## 准备工作

### 前置条件

- 已安装 model-compose 并在 PATH 中可用
- 具有 `opencv-python` 和 `numpy` 的 Python 环境（自动管理）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/media-processing/image-processor-opencv
   ```

2. 无需额外配置。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/input-image.jpg" \
     -F "low_threshold=100" \
     -F "high_threshold=200"
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传图像并调整阈值
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   model-compose run image-processor-opencv --input '{"image": "/path/to/your/input-image.jpg", "low_threshold": 100, "high_threshold": 200}'
   ```

## 工作流详情

### "Detect Image Edges (Canny)" 工作流

**描述**：从输入图像生成 Canny 边缘图。

#### 输入参数

| 参数              | 类型     | 必需 | 默认值 | 描述                                 |
|-------------------|----------|------|--------|--------------------------------------|
| `image`           | image    | 是   | -      | 输入图像文件（JPEG、PNG 等）         |
| `low_threshold`   | integer  | 否   | 100    | 梯度幅度的下限滞后阈值               |
| `high_threshold`  | integer  | 否   | 200    | 梯度幅度的上限滞后阈值               |

#### 输出格式

| 字段 | 类型   | 描述                                              |
|------|--------|---------------------------------------------------|
| -    | image  | 单通道灰度边缘图（L 模式），0 或 255              |

## 自定义

### 调整阈值

Canny 的两个阈值控制灵敏度：

- 两者都降低会得到更多边缘（更嘈杂但能捕捉较弱的梯度）
- 两者都提高会得到更少、更清晰的边缘
- ControlNet 约定为 2:1 比例（例如 100/200、50/100）

### 接入 ControlNet 工作流

将此组件链接到基于 ControlNet 的图像或视频生成器之前，将其输出传递到 ControlNet 的条件输入：

```yaml
workflow:
  jobs:
    - id: edges
      component: image-processor
      action: canny
      input:
        image: ${input.image}
    - id: generate
      component: controlnet-generator
      input:
        prompt: ${input.prompt}
        control_image: ${edges.output}
```

### 批处理和流式处理

传递图像列表或上游帧提取器流以生成视频管道的逐帧边缘图：

```yaml
component:
  type: image-processor
  driver: opencv
  action:
    method: canny
    image: ${input.frames}
    batch_size: 8
```

## 设计原则：无模型

OpenCV driver 仅承载不需要学习权重的算法。基于模型的 edge/line 预处理器（HED、PiDiNet、lineart）属于 model 组件家族。
