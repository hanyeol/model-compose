# Face Gender Annotate 示例

在输入图像中检测所有人脸，使用同一检测器的 genderage 头将每张脸分类为男/女，并在原图上按预测性别的颜色画出 bounding box — **男性蓝色**，**女性红色**，检测器未能确定性别时用灰色。

## 概览

给定一张输入图像，工作流返回两个字段：`annotated_image`（原图上叠加了按性别着色的人脸框）和 `faces`（原始检测记录 — bounding box、score、gender、age — 供下游处理）。

策略：

1. **将上传流 spool 为两个分支** — 使用 `fan-out` 作业的 `spool: true` 模式。上传是一次性的，而两个读者在非常不同的时刻消费它：`detect` 立即消费自己的分支，而 `annotate` 只在 `detect` 结束后才打开自己的分支来作为 accumulator 的初始值。spool 将上传一次性落到 tempfile，两个分支各自按自己的节奏打开文件；两个分支都关闭后 tempfile 被删除。
2. **运行人脸检测** — 使用 InsightFace `antelopev2` pack。开启 `return_gender_age: true` 让 pack 内置的 genderage 头为每个检测填充 `face.gender`（`"male"` 或 `"female"`）与 `face.age`。无需单独的分类器。
3. **将每张脸的 bounding box 折叠到源图上** — 使用内联 `accumulate` 作业。每次迭代取运行中的图像（`${accumulator}`）并返回多画一个矩形后的同一图像。矩形颜色由针对 `item.gender` 的条件表达式按脸挑选。

### 为什么 gender 挂在 `face-detection`（而不是单独的分类器）

InsightFace 的 `antelopev2` pack 同时打包 SCRFD 检测器 *和* genderage 分类器 — 找到人脸的同一次 forward pass 也会为其分配 gender 与 age。将其暴露在 `face-detection`（通过 `return_gender_age: true`，与 `face-embedding` / `face-tracking` 同样的做法）可避免把每张脸切出来送入第二个模型只为回答"男或女"的往返。若换成不打包 genderage 的 pack，`gender` 与 `age` 字段会被简单省略而不是抛错。

### 为什么绘制步骤用内联 accumulate

`image-drawing` 每次 action 调用只暴露一个绘制操作（rectangle、text、line、…），因此画 N 个框需要 N 次调用。`accumulate` 每次迭代运行一次 `do:`，并把运行中的图像作为下一次迭代的 `${accumulator}` 传递 — 因此把 N 个框叠加到源图上的自然方式是用 `accumulate` 作业把每个检测折叠到 accumulator 上。若某张脸没有检测到 gender，条件表达式的 `if_false` 灰色兜底会生效 — 框仍会被画出。

## 准备

### 要求

- 已在 PATH 中安装 model-compose
- InsightFace 检测的 Python 依赖：
  ```bash
  pip install insightface opencv-python onnxruntime pillow
  ```
- InsightFace **antelopev2** pack 会在首次运行时自动下载到 model-compose 的模型缓存。无需手动下载。

### 设置

1. 进入示例目录：
   ```bash
   cd examples/media-processing/face-gender-annotate
   ```

2. 准备一张至少含有一张可见人脸的图像。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传图像，按需覆盖 `min_confidence` / `line_width`
   - 点击 "Run Workflow"
   - 响应包含 `annotated_image`（输入图像 + 按性别着色的人脸框）与 `faces`（原始检测记录）。

   **API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"min_confidence": 0.5};type=application/json' \
     -F 'image=@./people.jpg'
   ```

   **CLI：**
   ```bash
   model-compose run --input '{
     "image": "./people.jpg",
     "min_confidence": 0.5
   }'
   ```

## 输入参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `image` | image (file) | Yes | - | 待检测并标注人脸的输入图像 |
| `min_confidence` | number | No | `0.5` | 最小检测置信度（0.0 – 1.0）。调低（如 `0.35`）可捕捉更多边缘 / 部分遮挡的人脸，代价是可能出现少量误报 |
| `line_width` | number | No | `3` | 矩形描边线宽（像素） |

## 输出形状

```json
{
  "annotated_image": "<image PNG>",
  "faces": [
    {
      "bounding_box": { "x": 120, "y": 84, "width": 156, "height": 202 },
      "score": 0.94,
      "gender": "male",
      "age": 34
    },
    {
      "bounding_box": { "x": 380, "y": 96, "width": 148, "height": 194 },
      "score": 0.91,
      "gender": "female",
      "age": 28
    }
  ]
}
```

- `annotated_image` — 每张检测到的人脸都画有一个 bounding box 的源图。`"male"` 用蓝色（`#1E90FF`），`"female"` 用红色（`#DC143C`），pack 未返回 gender 的人脸用灰色（`#808080`）。
- `faces[].gender` — `"male"` 或 `"female"`；若检测器的 genderage 头未产出值，则缺失。
- `faces[].age` — 估计年龄的整数值（年）；若不可用，则缺失。
- `faces[].bounding_box` — 源图坐标系像素单位的 `{x, y, width, height}`。
- `faces[].score` — 检测器置信度（0.0 – 1.0）。

## 作业详情

### Fan-Out (`fanout-image`)
- **类型**：`fan-out`（`spool: true`）
- **作用**：将一次性图像上传 tee 为两个独立分支 — `for-detect`（喂给检测器）与 `for-annotate`（在 `detect` 完成后作为 `accumulate` 作业的初始 accumulator）。`spool: true` 让上传一次性写入 tempfile，每个分支各自打开该文件；两个分支都关闭后 tempfile 被删除。annotate 分支只在检测器完成后开始消费，普通 fan-out 路径会触发队列反压 — spool 规避了这一问题。

## 组件详情

### Face Detector (`face-detector`)
- **类型**：`model` — `face-detection` 任务
- **驱动**：`custom`（InsightFace family，`antelopev2` pack）
- **作用**：检测输入图像中的所有人脸，通过 `return_gender_age: true` 为每个检测附上 pack 的 genderage 预测（`"male"` / `"female"` 加整数年龄）。`max_concurrent_count: 1` 串行化推理，保持 ONNX Runtime 内存有界。将 `detection_size` 调至 `(960, 960)` 或 `(1280, 1280)` 可召回更小 / 更远的人脸，代价按每张图像成比例增长。

### Box Drawer (`box-drawer`)
- **类型**：`image-drawing`（`rectangle` 方法）
- **驱动**：`native`
- **作用**：在运行中的 accumulator 上画一个 outlined rectangle。描边颜色由针对 `item.gender` 的条件按每个检测挑选：male → dodger blue（`#1E90FF`），female → crimson（`#DC143C`），否则 gray（`#808080`）。`line_width` 设置描边线宽（像素）。

## 说明与调优

- **成本**：每张图像一次 InsightFace forward pass。仅 CPU 推理时以检测为主；genderage 头对每张检测到的脸只增加少量成本。在 Apple Silicon 上，若可用则优先选 CoreML 执行提供者，HD 输入通常每张图像延迟远低于 1 秒。
- **未返回 gender**：`gender` 字段仅当加载的 pack 打包了 genderage 模型时才会填充。`antelopev2`（本示例默认值）打包了。如果把 `model.url` 换成仅检测的 pack，框仍会画但全为灰色（fallback 颜色）— 这是标注器的信号：请求了 genderage 但 pack 无法回答。
- **漏检人脸**：默认 `min_confidence: 0.5` 下若漏掉某张脸，先降至 `0.35`；若任何阈值都漏掉，很可能对默认 `(640, 640)` 检测输入而言太小 — 调高 `face-detector` 组件的 `detection_size`。
- **误报**：非常高的 `min_confidence`（如 `0.85`）会在标注前丢掉被遮挡 / 侧面的脸。若默认阈值下出现杂框，通常以 `0.05` 递增就够了。
- **自定义颜色**：颜色调色板直接内联在 `annotate` 作业的 `outline` 条件里 — male 蓝 `#1E90FF`，female 红 `#DC143C`，unknown 灰 `#808080`。编辑 hex 字符串即可换配色；扩展 `"?"` 列表添加分支（如按年龄段）也可以。
- **Spool tempfile**：fan-out spool 写入 `tempfile.NamedTemporaryFile` 返回的 OS 临时目录（尊重 `TMPDIR`）。所有分支关闭后文件被删除，无需手动清理。若临时分区较小而输入较大，将 `TMPDIR` 指向更大的磁盘。
