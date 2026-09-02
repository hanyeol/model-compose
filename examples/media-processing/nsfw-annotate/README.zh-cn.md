# NSFW Annotate 示例

本示例演示一个工作流：在输入图像中检测 NSFW 区域，并返回同一张图像，在每个检测框周围绘制带标签的彩色 bounding box——**`*_EXPOSED` 类别用红色**、**`*_COVERED` 类别用黄色**、**其余（`FACE_*` 等）用灰色**。

与 [nsfw-mosaic](../nsfw-mosaic/) 配对的示例：检测器相同，但不像素化区域，而是把它们绘制出来，方便您可视化查看模型看到了什么、以什么置信度。

> **自备模型**：本示例不会自动下载任何 NSFW 权重。您需要在 `./models/nsfw_detector.pt` 提供一个基于 NSFW 类别训练的 YOLO 格式检测器——与 `nsfw-mosaic` 示例使用的文件相同。下载命令见 [nsfw-mosaic/README.md](../nsfw-mosaic/README.md#preparing-the-detector-model)。

## 概述

对输入图像，工作流返回两个字段：`annotated_image`（原图之上按检测绘制彩色框和标签）与 `objects`（原始检测记录——标签、分数、bounding box——供下游处理）。

策略：

1. **将上传 spool 到三个分支** —— 使用 `fan-out` 任务，`spool: true` 模式。上传是一次性的，而有三个任务需要读取它：`measure` 立即消费其分支，`brighten` 等待 `factor`，`annotate` 等待 `detect`——存在显著时差。Spool 把上传落到临时文件一次，让每个分支按自己的节奏打开该文件；所有分支关闭后临时文件被删除。
2. **测量原图平均亮度** —— 用 `image-analyzer analyze-brightness`，返回 0–255 ITU-R BT.601 尺度的 `mean_brightness`。
3. **计算亮度系数**（`target_luma / mean_brightness`）—— 一行 Python `shell` 步骤。当输入全黑或传入 `target_luma: 0`（opt-out）时回退为 `1.0`。
4. **对原图进行亮度调整** —— 用 `image-processor adjust-brightness`。PIL 的线性亮度乘数。极端偏移会被裁剪，因此把非常暗的原图归一化到 luma 200 会落在略低于目标处；作为检测器输入没有问题。
5. **在提亮后的图像上运行 NSFW 检测** —— Ultralytics YOLO 模型，返回 `{objects: [{label, label_id, confidence, bounding_box: {x, y, width, height}}], width, height}`。
6. **将每个检测折叠为一个带标签的框，绘制到未改动的原图上** —— 使用一个内联 `accumulate` 任务。每次迭代运行两步内部 pipeline：先画出轮廓矩形，再在框上方画标签文本。轮廓和文本颜色按检测的标签后缀通过条件判断选择：`*_EXPOSED` → 红，`*_COVERED` → 黄，其他 → 灰。

### 为什么在检测前归一化亮度

NudeNet（以及公开训练的其他所有 NSFW YOLO）都是在正常曝光范围的照片上训练的。非常暗或非常亮的输入落在该分布之外，置信度分数会整体下降——有时会低于 `min_confidence`，导致"本应显而易见"的区域被漏掉。归一化到一个绝对目标 luma（而不是 `1.5×` 这样的相对乘数）意味着无论原始曝光如何，每张输入都会收敛到同一个亮度带，从而让检测器看到与其训练分布相似的输入。

亮度调整仅应用于检测器的输入。标注绘制在未改动的原图上，因此返回的图像与调用方上传的一致——您在自己发送的像素上看到检测框。

### 为什么绘制在原图上而不是提亮图上

两个原因：

1. **输出应是调用方文件的带标签版本** —— 如果调用方只想知道"检测在哪里"，却收到提亮后的像素，会让人意外。
2. **扫描式对比更干净** —— 您可以用不同的 `target_luma` 值多次运行，diff 返回的 `objects` 数组，而返回图像的形态不应同时变化。

如果您想*看*到检测器所看到的（提亮后的帧上带框），把 annotate 任务的 accumulator 从 `${jobs.fanout-image.output.for-annotate}` 改为 `${jobs.brighten.output as image}`。

### 为什么内部 pipeline 是两步

`image-drawing` 每次动作调用只暴露一个绘制操作（矩形、文本、线……），因此"矩形 + 标签"组合需要两次调用。`accumulate` 每次迭代只运行一个 `do:`，把两次绘制调用按每次迭代自然串起来的方式是内联 `pipeline`——步骤 1 在运行中的 accumulator 上画矩形，步骤 2 在其之上画标签。pipeline 的输出回流回 `accumulate`，成为下一迭代的 accumulator。

### 为什么用后缀匹配决定颜色

NudeNet 的 18 个类别全部以 `_EXPOSED`、`_COVERED` 结尾，或者是 `FACE_MALE` / `FACE_FEMALE`。与其在颜色条件里枚举所有类别（18 个分支），工作流用 `ends-with` 运算符按后缀匹配——两个分支（`_EXPOSED`、`_COVERED`）加一个灰色兜底就覆盖全部，并且保持可读。

## 准备

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- Ultralytics YOLO 的 Python 依赖：
  ```bash
  pip install ultralytics
  ```

### 准备检测模型

与 [nsfw-mosaic](../nsfw-mosaic/README.md#preparing-the-detector-model) 相同。推荐：通过 Hugging Face 镜像获取 NudeNet v3.4 640m：

```bash
mkdir -p models
curl -fL -o models/nsfw_detector.pt \
  https://huggingface.co/vladmandic/nudenet/resolve/main/nudenet-v34-640m.pt
```

请确认文件大小约为 52 MB（`file models/nsfw_detector.pt` 应报告 `Zip archive data`）。如果同级 `nsfw-mosaic/models/` 目录里已有该文件，也可以用符号链接：

```bash
mkdir -p models
ln -s ../../nsfw-mosaic/models/nsfw_detector.pt models/nsfw_detector.pt
```

### 设置

1. 进入本示例目录：
   ```bash
   cd examples/media-processing/nsfw-annotate
   ```

2. 将检测器权重放到 `./models/nsfw_detector.pt`。

3. 准备一张要标注的图像。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传图像，可选覆盖 `min_confidence` / `line_width` / `bounding_box_padding`
   - 点击 "Run Workflow"
   - 响应中包含 `annotated_image`（带彩色标签框的输入）和 `objects`（原始检测记录）。

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"min_confidence": 0.35};type=application/json' \
     -F 'image=@./photo.jpg'
   ```

   **使用 CLI：**
   ```bash
   model-compose run --input '{
     "image": "./photo.jpg",
     "min_confidence": 0.35
   }'
   ```

## 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `image` | image (文件) | 是 | - | 要检测和标注 NSFW 区域的输入图像 |
| `target_luma` | number | 否 | `130` | 目标平均 luma（0–255，BT.601）。检测器输入会被缩放到平均 luma 匹配该值。设为 `0` 跳过归一化，直接在原始像素上检测。典型带宽：照片内容 `100`–`160`；低于 `40` 会压碎阴影，高于 `215` 会烧掉高光 |
| `min_confidence` | number | 否 | `0.35` | 最低检测置信度（0.0 – 1.0）。降低（例如 `0.2`）以在模型检查时暴露边缘检测 |
| `bounding_box_padding` | number | 否 | `0.0` | 绘制前每个检测框向外扩展的比例。这里保持 `0.0`（与 `nsfw-mosaic` 不同），使绘制的框与检测器原始输出完全一致——便于可视化调试 |
| `line_width` | number | 否 | `3` | 矩形轮廓粗细（像素） |
| `text_stroke_width` | number | 否 | `2` | 文本描边宽度（像素）——标签周围的黑色描边，使其在任何背景上都可读 |

## 输出结构

```json
{
  "annotated_image": "<image PNG>",
  "objects": [
    {
      "label": "FEMALE_BREAST_EXPOSED",
      "label_id": 3,
      "confidence": 0.87,
      "bounding_box": { "x": 412, "y": 180, "width": 220, "height": 260 }
    },
    {
      "label": "FACE_FEMALE",
      "label_id": 16,
      "confidence": 0.94,
      "bounding_box": { "x": 380, "y": 40, "width": 160, "height": 200 }
    }
  ]
}
```

- `annotated_image` —— 原始图像，每个检测绘制一个 bounding box + 标签。
- `objects[].label` —— NSFW 类名（依模型而定；NudeNet v3.4 使用 `FEMALE_BREAST_EXPOSED`、`MALE_GENITALIA_EXPOSED`、`BUTTOCKS_COVERED`、`FACE_MALE` 等名称）。
- `objects[].confidence` —— 检测器置信度，0.0 – 1.0。
- `objects[].bounding_box` —— 原图坐标系下的 `{x, y, width, height}`，像素。

## 任务详情

### Fan-Out (`fanout-image`)
- **Type**：`fan-out`（`spool: true`）
- **功能**：把一次性图像上传分流到三个独立分支——`for-measure`（供给亮度分析器）、`for-brighten`（`factor` 完成后供给检测器输入）、`for-annotate`（`detect` 完成后作为 accumulate 任务的初始 accumulator）。开启 `spool: true` 后，上传被一次性写入临时文件，每个分支按自己的节奏打开该文件；所有分支关闭后临时文件被删除。因为三个分支中有两个要等 `measure` 完成之后才开始消费，Spool 避免了普通 fan-out 路径本会遇到的队列 backpressure。

## 组件详情

### Image Analyzer (`image-analyzer`)
- **Type**：`image-analyzer`（`analyze-brightness` 动作）
- **Driver**：`native`
- **功能**：返回 0–255 BT.601 luma 尺度的 `mean_brightness`。`factor-calc` 任务把 `target_luma` 除以该值，得到 `adjust-brightness` 需要的乘数。也返回 `min_brightness` / `max_brightness` / `std_brightness`；工作流未暴露它们，如果您想按对比度决策也可以使用。

### Factor Calc (`factor-calc`)
- **Type**：`shell`
- **功能**：一行 Python 打印 `target / original`（当任一为零时回退为 `1.0`）。DSL 不做算术，因此这是最小的绕路。输出以 `as number` 解码，让提亮组件消费真正的 float。

### Image Processor (`image-processor`, `adjust-brightness` 动作)
- **Type**：`image-processor`
- **Driver**：`native`
- **功能**：通过 PIL 的 `ImageEnhance.Brightness` 将像素值乘以计算得出的系数。系数为 `1.0` 是空操作，所以 `target_luma: 0`（使 `factor-calc` 返回 `1.0`）无需任何特殊布线即可完全短路归一化。

### NSFW Detector (`nsfw-detector`)
- **Type**：`model` —— `object-detection` 任务
- **Driver**：`custom`（Ultralytics YOLO family）
- **功能**：在输入图像上运行用户提供的 NSFW YOLO 权重，返回标准 object-detection 响应形态。`max_concurrent_count: 1` 串行化 GPU 侧工作。暴露了 `bounding_box_padding`，让调用方无需重跑检测即可为视觉清晰度加宽绘制的框。

### Box Drawer (`box-drawer`)
- **Type**：`image-drawing`（`rectangle` 方法）
- **Driver**：`native`
- **功能**：在运行中的 accumulator 上绘制一个带轮廓的矩形。轮廓颜色由针对标签后缀的条件按检测选择。

### Text Drawer (`text-drawer`)
- **Type**：`image-drawing`（`text` 方法）
- **Driver**：`native`
- **功能**：在矩形上方绘制标签字符串。`anchor: ld`（left / descender）使文本基线正好落在矩形顶边上，让标签紧贴框上方。带黑色描边的 `stroke_width: 2` 使文本在任何背景上都保持可读。

## 说明与调优

- **成本**：每张图像 1 次 `analyze-brightness`、1 次 `adjust-brightness`、1 次 YOLO 前向传播，加上每个检测 2 次 `image-drawing` 调用。前处理是纯 NumPy / PIL，相对于检测几乎免费。
- **何时改变 `target_luma`**：默认 `130`（中间调）与大多数 YOLO 检测器的训练集曝光带匹配。如果输入持续偏暗且检测器漏掉区域，提高（`150`–`180`）；如果输入持续偏亮并且裁剪开始吞掉高光，降低（`100`–`120`）。传入 `target_luma: 0` 会完全跳过归一化——用于与原始基线做 A/B 对比。
- **何时归一化反而有害**：曝光良好的输入不会从再归一化中获益，反而可能因 PIL 的线性裁剪失去一些肤色渐变。如果确定输入已在正常曝光范围，请传入 `target_luma: 0`。
- **漏掉的检测**：降低 `min_confidence`（例如 `0.2`）以查看默认阈值隐藏的边缘检测。用于调试某个特定区域为什么没有被标记。
- **文字重叠**：如果两个检测在垂直方向靠得近，因为都锚定到框的左上角，标签可能重叠。这是"检查模型"用途下的有意设计——为避免碰撞而对标签重新排序或重新定位需要对完整检测列表再走一遍，作为调试工具而言不值得这份复杂度。
- **颜色方案**：调色板由两个条件编码（一个用于矩形，一个用于文本）。内联修改 RGB 十六进制码即可重映射；如果两级分组不够细，可添加分支（例如为 `FACE_*` 类别单独上色）。
- **与 `nsfw-mosaic` 的对比**：两个示例使用同一检测器和同一 `bounding_box` 字段。如果您在为 mosaic 工作流迭代 `min_confidence` / `iou_threshold` / 类别标签过滤，先用这个工作流跑一遍——在静态图像上视觉验证检测集，远比重新编码整段视频再检查 mosaic 结果快。
- **Spool 临时文件**：fan-out spool 写入 `tempfile.NamedTemporaryFile` 返回的操作系统临时目录（尊重 `TMPDIR`）。所有分支关闭后文件被删除，无需手动清理。如果临时分区较小而输入很大，将 `TMPDIR` 指向更大的磁盘。
