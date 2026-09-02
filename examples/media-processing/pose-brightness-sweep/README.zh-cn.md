# 姿态检测 × 亮度扫描示例

本示例展示了一个工作流：接收一张输入图像，将其归一化到 0–255 ITU-R BT.601 luma 尺度上的 5 个绝对亮度目标，对每个变体运行 YOLOv8-pose，并并排返回 5 张姿态叠加图像 — 让你能直观判断检测器在这张特定输入上偏好哪个亮度带。

> **许可证提示**：本示例会自动下载 Ultralytics 的 YOLOv8-pose 权重，该权重以 **AGPL-3.0** 发布。个人使用、研究、开源演示都没问题。商业使用需要遵守 AGPL-3.0（开源整个系统）或获取 Ultralytics Enterprise License — 详见 [ultralytics.com/license](https://www.ultralytics.com/license)。

## 概览

给定一张输入图像，工作流按每个目标 luma 带返回一张姿态叠加图像（默认 `50`、`90`、`130`、`170`、`210`）。每个字段都是完全渲染的图像（亮度调整 + 骨架叠加），可按名称寻址（`luma_050` … `luma_210`）。

策略：

1. **将上传缓存并分两阶段 fan-out。** 第一个 `fan-out` 作业以 `spool: true` 模式运行 — 将一次性上传落到临时文件一次，并向两个分支（`for-measure` 和 `for-sweep`）各交出一份基于文件的图像资源。由于这些资源可复制，第二个 `fan-out` 通过廉价的 `copy(N)` 拆分其输入（不再生成第二个临时文件），为每个扫描目标产生一个独立句柄。分两阶段是为了分离关注点：分析器可以立即消费自己的分支，而扫描流水线可以等待 `measure` 完成而不会让分析器阻塞（那时缓存文件已经完全写入）。
2. **一次性测量源 luma** — 使用 `image-analyzer`（`analyze-brightness` 度量）。返回 0–255 BT.601 luma 尺度上的 `mean_brightness`，即每次扫描迭代用来推导目标乘数的除数。
3. **Fan out** — 顶层 `for-each` 作业遍历目标 luma 列表，将每个目标与其第二阶段 fan-out 分支配对为 `{luma, image}` 项。每次迭代独立运行一个内联 `pipeline`，`batch_size: 5` 让 CPU 侧步骤能重叠执行。
4. **每次迭代内部** — 用一个小的 Python shell 作业计算 `factor = target / original`，通过 `image-processor adjust-brightness` 应用它，运行 YOLOv8-pose（`return_skeleton_image: true` 为每个姿态生成源分辨率的透明背景骨架 PNG），然后用 `image-processor merge` 将所有骨架 alpha 合成到亮度调整后的图像上。
5. **投影结果** — 顶层工作流的 `output:` 块按位置索引（`jobs.sweep.output[0]` … `[4]`）选取每次迭代，将其 `pose_overlay_image` 暴露为顶层 `luma_NNN` 字段，Web UI 因此按带渲染一张图像卡。`for-each` 保留输入顺序，所以索引 `N` 始终对应扫描输入列表的第 N 项。

### 为什么用绝对 luma（而不是原始乘数）

原始乘数扫描（`0.5×`、`1.0×`、`2.0×` …）会因输入原始亮度不同而落到不同的绝对亮度带 — 对暗照片的 2× 位移与对亮照片的 2× 位移落到完全不同的位置。以绝对 luma 为目标可归一化源曝光，所以 5 个带（`50, 90, 130, 170, 210`）对任何输入都是同样的 5 个带，跨不同照片的结果比较才有意义。

代价：亮度调整仍使用 PIL 的 `ImageEnhance.Brightness`，这是一个在 0 和 255 处裁剪的线性乘数。所以把一个非常暗的源推到目标 210 时，考虑到高光裁剪后可能会略低于 210。作为"检测器喜欢哪个带"的实验足够了，但作为光度归一化不够。

### 为什么在前端一次性测量（而不是每次迭代内）

源 luma 在 5 次迭代中不变，所以对相同像素重复分析 5 次只会浪费 CPU。在外层工作流的 `measure` 作业里测量意味着它在 fan-out 之前发生一次，导出的值作为标量 `original_luma` 输入传给每次迭代的流水线。

### 为什么用内联 pipeline（而不是子工作流）

每目标的工作是 4 个顺序步骤（factor 计算 → 变亮 → 检测 → 叠加）。`for-each` 可以运行任意内联作业作为其 `do:` 主体，`pipeline` 作业以隐式的 `${output}` → 下一个 `${input}` 连接链式串联步骤 — 所以整个四步序列直接住在 `for-each` 内部，无需单独的工作流定义。代价是作用域：pipeline 步骤只能看到 pipeline 自己的 `${input}` 和上一步的 `${output}`，外层作用域（如包围它的 `${item}`）不可达。所以 pipeline 顶层的 `input:` 块把所有步骤需要的东西（目标 luma、源图像分支、源 luma、阈值）一次性打包进一个 dict，每个步骤的 `output:` 映射再将运行时状态（factor、亮度调整后的图像、姿态）重新打包给下一步。

### 为什么用 Python shell 作业算 factor

model-compose 的变量绑定 DSL 渲染值并做类型转换，但不做算术运算。计算 `target / original_luma` 需要走 shell；把两个值作为 `argv` 的一行 `python3 -c` 命令是最小的绕路。Shell 步骤的 stdout 是一个普通的 float 字符串，pipeline 的 `output:` 映射通过 `${output as number}` 强制转换后交给变亮步骤。

## 准备

### 要求

- 已在 PATH 中安装 model-compose
- YOLO 姿态检测和图像分析的 Python 依赖：
  ```bash
  pip install ultralytics numpy
  ```
- YOLOv8n-pose 权重在首次运行时自动下载到 model-compose 的模型缓存。

### 设置

1. 进入示例目录：
   ```bash
   cd examples/media-processing/pose-brightness-sweep
   ```

2. 准备一张至少有一个可见人物的图像。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传图像，可选择覆盖 `min_confidence` / `max_pose_count`
   - 点击 "Run Workflow"
   - 响应包含 5 个图像字段（`luma_050` … `luma_210`）— 每个亮度带一张卡片，展示亮度调整后的图像叠加检测到的骨架。

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"min_confidence": 0.4, "max_pose_count": 5};type=application/json' \
     -F 'image=@./person.jpg'
   ```

   **使用 CLI：**
   ```bash
   model-compose run --input '{
     "image": "./person.jpg",
     "min_confidence": 0.4,
     "max_pose_count": 5
   }'
   ```

## 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `image` | image (file) | 是 | - | 用于亮度扫描的输入图像 |
| `min_confidence` | number | 否 | `0.4` | 姿态检测最小置信度 (0.0 – 1.0)。若在所有亮度层级都漏检某人，可降低（例如 `0.25`） |
| `max_pose_count` | integer | 否 | `5` | 每张图像返回的最大姿态数 |

## 输出形状

每个目标亮度带被投影为独立的顶层图像字段 `luma_NNN`（`NNN` 为 0–255 尺度上的目标平均 luma，前补零）。这种扁平形状让 Web UI 按带并排渲染一张图像卡。

```json
{
  "luma_050": "<image PNG>",
  "luma_090": "<image PNG>",
  "luma_130": "<image PNG>",
  "luma_170": "<image PNG>",
  "luma_210": "<image PNG>"
}
```

骨架与图像中人物对齐最干净的那个带就是该输入下检测器的曝光甜点。如果需要底层姿态数据（分数、bounding box）或叠加前的亮度调整图像，从 pipeline 输出提升它们 — 每次迭代返回完整记录 `{target_luma, applied_factor, poses, brightened_image, pose_overlay_image}`；顶层工作流的 `output:` 块目前只投影 `pose_overlay_image` 以保持 UI 简洁，但你可以在那里增加更多字段而不用动 pipeline 步骤。

> **注意**：如果修改了 `sweep` 作业上的目标 luma 列表，工作流 `output:` 块中的字段名也要相应重命名 — 字段名是静态 YAML，不是运行时从扫描值派生的。

## 组件详情

### 图像分析器 (`image-analyzer`)
- **类型**：`image-analyzer`
- **驱动**：`native`
- **功能**：对源图像运行 `analyze-brightness`。与扫描迭代并行消费上游 `fan-out` 作业的 `for-measure` 分支。返回 `mean_brightness`（BT.601 luma 的算术平均，0–255）以及 `min/max/std_brightness` 和尺寸。这里只用 `mean_brightness` — 作为每目标 factor 的除数。

### Factor 计算器 (`factor-calc`)
- **类型**：`shell`
- **功能**：运行一行 Python 脚本，打印 `target / original`（若源全黑则为 `1.0`）。stdout 由变亮步骤通过 `as number` 消费。这是流水线中唯一发生算术的地方 — 其余都是纯变量绑定。

### 图像处理器 (`image-processor`)
- **类型**：`image-processor`
- **驱动**：`native`
- **功能**：暴露两个 action。`adjust-brightness` 把像素强度乘以 `factor`（PIL `ImageEnhance.Brightness`，在 0/255 处裁剪的线性乘数）。`merge` 将同尺寸图像列表 alpha 合成到一个画布上 — 这里用于把骨架 PNG 叠在每张亮度调整后的图像上方。

### 姿态检测器 (`pose-detector`)
- **类型**：`model` — `pose-detection` 任务
- **驱动**：`custom`
- **系列**：`yolo` (`yolov8n-pose.pt` 权重)
- **功能**：在一张图像上检测最多 `max_pose_count` 个姿态，并为每个姿态渲染全分辨率透明背景骨架 PNG（`return_skeleton_image: true`）。关键点数组被抑制（`return_keypoints: false`），因为叠加流水线只需要预渲染的骨架图。`max_concurrent_count: 1` 序列化推理，让 GPU 显存保持有界，即便外层 `for-each` 一次 fan-out 5 个迭代。

## 备注与调优

- **成本**：每个目标带一次姿态检测。默认 5 带扫描下，墙钟时间约为单次姿态检测调用的 5 倍，减去并发 CPU 工作重叠的部分。换用 `yolov8s/m/l/x-pose.pt` 可换取更高精度，成本按比例增加。
- **扫描范围**：默认 `[50, 90, 130, 170, 210]` 覆盖 8-bit luma 尺度上的深阴影 → 中间 → 高光。`128` 为精确中点；`~40` 以下基本上是被压死的阴影，`~215` 以上则高光过曝。若默认对你的用例太粗糙，编辑 `sweep` 作业上的列表以聚焦更窄的带。
- **各带皆漏检姿态**：如果每个变体都看不到姿态，说明检测器根本就没看到人 — 在把责任归给亮度之前，降低 `min_confidence`（例如 `0.25`）或换用更大的 YOLO 权重。
- **叠加中的基础图像**：当某个目标下检测到 0 个姿态时，`pose_overlay_image` 与亮度调整后的图像相同（merge 只返回基础）。这是刻意为之 — 让 5 张输出卡在视觉上对齐，可以无空隙地翻阅。
- **绝对 luma 的局限**：亮度 action 是带裁剪的线性乘数，所以极端位移（非常暗的输入 → 高目标，或非常亮的输入 → 低目标）会偏离目标。若准确的光度归一化比扫描可视化更重要，改用基于 gamma 的色调映射 — `image-processor` 目前不暴露它，需要加到核心里。
