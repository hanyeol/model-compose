# 目标检测模型任务示例

此示例演示如何通过 model-compose 内置的 object-detection 任务使用 Ultralytics YOLO 检测图像中的目标，提供离线检测能力。

## 概述

此工作流提供本地目标检测：

1. **本地 YOLO 模型**：无需外部 API，在本地运行 Ultralytics YOLO 检测模型
2. **边界框**：返回每个目标的轴对齐边界框，包含类别标签和置信度分数
3. **自定义权重**：支持任何 Ultralytics YOLO 检测或分割检查点（`.pt`）
4. **标签过滤**：通过 `labels` 动作参数可选择性地将检测限制为特定类别标签
5. **自动模型管理**：首次使用时自动下载并缓存默认模型

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 足够的系统资源来运行 YOLO（推荐：4GB+ RAM）
- 包含 `ultralytics` 的 Python 环境（首次运行时自动安装）

### 为何选择本地目标检测

与基于云的视觉 API 不同，在本地运行 YOLO 具有以下优势：

**本地处理的好处：**
- **隐私**：所有图像在本地处理，不向外部服务发送数据
- **成本**：无按图像或 API 使用费
- **离线**：初次模型下载后无需网络连接即可工作
- **延迟**：每次推理无需网络往返
- **自定义模型**：可插入任何 Ultralytics YOLO 检查点（`.pt`），包括领域专用模型

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 检测所有目标（默认 yolo11n.pt 的 COCO 80 个类别）
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image"}'

   # 仅检测特定标签
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image", "labels": ["person", "dog"], "min_confidence": 0.5}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传图像文件
   - 可选择调整 `labels`、`min_confidence`、`max_object_count`、`iou_threshold`、`agnostic_nms` 和 `bounding_box_padding`
   - 点击"运行工作流"按钮

## 结果格式

```json
{
  "objects": [
    {
      "label": "person",
      "label_id": 0,
      "score": 0.87,
      "bounding_box": [x, y, width, height]
    }
  ],
  "width": 1920,
  "height": 1080
}
```

- `label` — 来自 `model.names` 的人类可读类别名称。
- `label_id` — 模型报告的整数类别索引。
- `score` — `[0, 1]` 范围内的检测置信度。
- `bounding_box` — 以左上角为原点的像素单位 `[x, y, width, height]`。

## 使用自定义模型

替换 `model-compose.yml` 中的 `model` 块以指向任何 Ultralytics YOLO 检查点。例如，使用在您自己的数据集上训练的自定义检测器：

```yaml
component:
  type: model
  task: object-detection
  driver: custom
  family: yolo
  model:
    provider: local
    path: /path/to/your/model.pt
  action:
    image: ${input.image as image}
    labels: [ your_class_a, your_class_b ]
    min_confidence: 0.3
```

也支持分割检查点（`yolo11*-seg.pt` 等）— 仅读取边界框，掩码被忽略。

## 动作参数

| 参数 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| `image` | image | （必需） | 输入图像 |
| `labels` | list[str] | `null` | 将检测限制为这些类别标签。未知标签将快速失败 |
| `min_confidence` | float | `0.25` | 最小检测置信度 |
| `max_object_count` | int | `300` | 每张图像的最大检测数 |
| `iou_threshold` | float | `0.7` | 非极大值抑制的 IoU 阈值 |
| `agnostic_nms` | bool | `false` | 对所有标签执行类别无关的 NMS |
| `bounding_box_padding` | float | `0.0` | 按其宽度/高度的比例在每一侧扩展每个边界框（例如 `0.1` = 10%）。限制在图像边界内。当将框传递给裁剪或 SAM 框提示时非常有用 |
