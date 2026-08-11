# 图像分割模型任务示例

此示例演示了如何使用 model-compose 内置的 image-segmentation 任务，通过 Meta 的 Segment Anything Model (SAM) 从图像生成分割掩码。

## 概述

此工作流提供本地可提示分割：

1. **本地 SAM 模型**：在无需外部 API 的情况下本地运行 Meta 的 Segment Anything Model
2. **自动模式**：无需任何提示为图像中每个不同区域生成掩码
3. **框提示模式**：围绕用户提供的边界框（例如来自目标检测组件）精细化掩码
4. **SAM 1 与 SAM 2 支持**：可搭配任何 Ultralytics SAM 检查点 (`sam_b.pt`、`sam2_b.pt`、`sam2.1_l.pt`、`mobile_sam.pt` 等)
5. **自动模型管理**：首次使用时下载并缓存默认模型

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- 足够的系统资源运行 SAM（推荐：8GB+ RAM；自动模式下强烈建议 GPU）
- 带 `ultralytics` 的 Python 环境（首次运行时自动安装）

### 为何选择本地分割

与基于云的视觉 API 不同，本地运行 SAM 提供：

**本地处理的优点：**
- **隐私**：所有图像均在本地处理，不会发送到外部服务
- **成本**：无按图像或 API 使用费用
- **离线**：初次模型下载后无需互联网连接即可工作
- **延迟**：每次推理无网络往返
- **自定义模型**：可接入任何 Ultralytics SAM 检查点

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API — 自动模式：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image"}'
   ```

   **使用 API — 框提示模式：**
   ```bash
   # 单个框
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image", "box_prompt": {"x": 100, "y": 100, "width": 300, "height": 400}}'

   # 多个框
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image", "box_prompt": [{"x": 100, "y": 100, "width": 300, "height": 400}, {"x": 500, "y": 200, "width": 250, "height": 250}]}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传图像文件
   - 可选提供 `box_prompt`、`min_confidence`、`min_area`、`max_segment_count` 和 `return_mask`
   - 点击"运行工作流"按钮

## 结果格式

**自动模式：**
```json
{
  "segments": [
    {
      "score": 0.92,
      "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 460 },
      "area": 12345,
      "mask": "<PNG>"
    }
  ],
  "width": 1920,
  "height": 1080
}
```

**框提示模式**为每个分割添加 `prompt_index` 字段：
```json
{
  "segments": [
    {
      "score": 0.87,
      "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 460 },
      "area": 12345,
      "mask": "<PNG>",
      "prompt_index": 0
    }
  ],
  "width": 1920,
  "height": 1080
}
```

- `score` — 分割置信度（SAM 的稳定性估计）。
- `bounding_box` — 从掩码派生的 `{x, y, width, height}`，原点在左上角。
- `area` — 掩码面积（像素）。
- `mask` — 以 PNG 表示的二值掩码（`return_mask: false` 时省略）。
- `prompt_index` — 此分割对应的输入 `box_prompt` 索引（仅框提示模式）。

分割按 `score` 降序排列，并截断到 `max_segment_count`。

## 与目标检测结合

[object-detection](../object-detection/README.md) 组件的输出可直接作为 SAM 的框提示：

```yaml
jobs:
  - id: detect
    component: yolo-detector
    action:
      image: ${input.image as image}
  - id: segment
    component: sam-segmenter
    action:
      image: ${input.image as image}
      box_prompt: ${detect.output.objects[*].bounding_box}
```

## 使用自定义模型

替换 `model-compose.yml` 中的 `model` 块，指向任意 Ultralytics SAM 检查点。例如：

```yaml
model:
  provider: local
  path: /path/to/your/mobile_sam.pt
```

可用的 Ultralytics SAM 检查点：`sam_b.pt`、`sam_l.pt`、`sam2_t.pt`、`sam2_b.pt`、`sam2_l.pt`、`sam2.1_t.pt`、`sam2.1_b.pt`、`sam2.1_l.pt`、`mobile_sam.pt`。

## 动作参数

| 参数 | 类型 | 默认值 | 描述 |
|---|---|---|---|
| `image` | image | （必需） | 输入图像 |
| `box_prompt` | object 或 list | `null` | 框提示 — `{x, y, width, height}`（单个）或它们的列表。省略时以自动模式运行 |
| `max_segment_count` | int | `100` | 每张图像的最大分割数 |
| `return_mask` | bool | `true` | 以 PNG 返回每个分割的二值掩码 |
| `params.min_confidence` | float | `0.5` | 最小分割置信度 |
| `params.min_area` | int | `null` | 最小掩码面积（像素，用作噪声过滤） |
