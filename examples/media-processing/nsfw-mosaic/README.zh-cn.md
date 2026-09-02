# NSFW Mosaic 示例

本示例演示一个工作流：将视频中每个检测到的 bounding box 内的 NSFW 区域进行像素化（或模糊）遮挡，再把处理后的帧重新组装成 mp4——同时保留原始音轨。用于内容审核：给定一段可能包含露骨内容的视频，产出可以安全显示或分享的版本。

整个管线端到端以流式方式运行，因此无论片段有多长，内存都保持有界。

> **自备模型**：本示例不会自动下载任何 NSFW 权重。您需要在 `./models/nsfw_detector.pt` 提供一个基于 NSFW 类别训练的 YOLO 格式检测器。见下方[准备检测模型](#准备检测模型)。

> **请负责任地使用**：本示例的目的是"对您已有权处理的视频（审核队列、法务审查、个人库）进行单向遮挡成人内容"。不要将其用于对人进行画像或监控，也不要用于您无权检查的内容。检测并不完美——请假设会有一些区域被漏掉，尤其是在低分辨率、运动模糊或不寻常角度下；如果下游用途涉及安全关键，请配合人工审核环节。

## 概述

对输入视频，工作流返回同一段视频的一个版本，其中每个 NSFW 区域都被 mosaic 效果遮挡。

策略：

1. **将上传流 fan-out** —— 用 `fan-out` 任务分为两个独立分支，一个供音频提取器、一个供帧提取器，让它们能并行消费一次性的上传流，而无需把视频落盘。
2. **拆出音轨** —— 用 `audio-extractor` 从视频中分离音频（保持不变）。
3. **流式抽取每一帧** —— 用 `video-frame-extractor`（`streaming: true` —— 不缓冲整段视频）。
4. **在帧流上运行 object-tracking** —— `streaming: true`，配置为发出每帧检测 chunk 流，每个 chunk 同时携带源图像和检测到的 NSFW bounding box。轨迹片段、轨迹级聚合、终止 metadata chunk 全部被抑制——mosaic 步骤只需要每帧检测。
5. **对每个每帧 chunk**，用一个内联 `accumulate` 步骤在一次遍历中对每个检测区域的 bounding box 应用 mosaic。如果某帧没有检测，accumulator 原样通过。
6. **将遮挡后的帧流重新编码回 mp4** —— 用 `video-encoder`，并将提取的音频复用到输出中。ffmpeg 会在需要时从上游流拉取帧，因此此阶段也不会整段缓冲。

### 为什么流式很重要

朴素的设计会把每一帧都物化到内存里，对整个列表运行检测，然后把遮挡后的列表交给编码器。这对短片可行，但对较长视频会撑爆内存（1080p 30 fps 10 分钟片段 = 18,000 帧 × 每帧解码 ~6 MB = ~110 GB 的 PIL 图像）。

端到端流式的情况下，一次最多只有 `batch_size` 帧在 mosaic 步骤中流动，编码器一到就消费遮挡后的帧。无论片段多长，内存都保持有界。

### 为什么使用 object-tracking（而不是纯 object-detection）

这里 object-tracking 只被当作"逐帧检测器 + 载体"来用——身份信息（`track_id`、片段）对遮挡无关紧要，相关 chunk 类型全部被禁用。之所以仍使用 tracker，有两个原因：

- **每帧 chunk 打包了源图像**。每个 `{type: "detection", ...}` chunk 已经在 `objects` 旁边携带该帧的 `image`，因此 mosaic 步骤只需要一个 `for-each`——每帧一次迭代——而不需要纯 `object-detection` 组件所强制的两步 detect-then-accumulate 管线（后者会把源图像留在另一条流上，然后需要按帧 zip 起来）。
- **间隙插值补上短暂漏检**。当底层检测器在两次命中之间的一两帧上失败，tracker 会把漏帧的 `objects` 列表填上一个插值的 bounding box，因此那些原本没被覆盖的帧也能被遮挡。间隙填补窗口为 `params.merge_gap` 秒（默认 `0.5`）。

检测 chunk 会被延迟 `merge_gap` 秒后再发出，让插值窗口有机会闭合——这会引入少量流式延迟，但正是这个机制让间隙填补生效。`params.min_frame_count` **不**应用于检测 chunk（只应用于非流式结果中的已确认轨迹），所以只出现一帧的检测也能到达 mosaic 步骤。对遮挡而言这是正确的权衡：误报同样会被 mosaic，比漏检安全得多。

## 准备

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 已安装 FFmpeg 并在 PATH 中可用
- Ultralytics YOLO tracking 的 Python 依赖：
  ```bash
  pip install ultralytics lap
  ```

### 准备检测模型

您需要一个 YOLO 格式（`.pt`）的检测器，训练用于定位 NSFW 区域。推荐默认是 **NudeNet v3.4 640m** —— 一个 YOLOv8m 检测器，包含 18 个解剖学类别（包括暴露与遮盖两种变体），由 [notAI-tech](https://github.com/notAI-tech/NudeNet) 训练，采用 AGPL-3.0 许可。

请从 [Hugging Face 镜像](https://huggingface.co/vladmandic/nudenet) 下载（使用镜像是因为该仓库的 GitHub release 下载可能会被重定向到登录页）：

```bash
curl -fL -o models/nsfw_detector.pt \
  https://huggingface.co/vladmandic/nudenet/resolve/main/nudenet-v34-640m.pt
```

请确认文件约为 52 MB，而不是几 KB 的 HTML —— 如果 `file models/nsfw_detector.pt` 报告 `Zip archive data`，就是下载成功。

任何 Ultralytics 兼容的 `.pt` 权重，只要其类别标签对应 NSFW 区域即可在此使用——通过修改 `model-compose.yml` 中的 `nsfw-tracker.model.path` 换成您自己的。一个更快（但准确度较低）的选择是同一仓库的 320n 变体（`nudenet-v34-320n.pt`，约 6 MB）。

**类别选择**。每个 YOLO 模型有自己的类名列表。示例 `nsfw-tracker` 组件下的 `labels:` 列表将检测限制为 `FEMALE_GENITALIA_EXPOSED` 与 `MALE_GENITALIA_EXPOSED`——编辑此列表以拓宽或收窄覆盖范围。未知的类名会在加载时抛出清晰的错误，同时列出可用列表。

### 设置

1. 进入本示例目录：
   ```bash
   cd examples/media-processing/nsfw-mosaic
   ```

2. 将检测器权重放到 `./models/nsfw_detector.pt`（见上方）。

3. 准备一段要遮挡的视频文件。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传视频，可选覆盖 `mode` / `block_scale` / `blur_radius` / `frame_rate` / `min_confidence`
   - 点击 "Run Workflow"

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"mode": "pixelate", "block_scale": 0.1, "frame_rate": 30};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **使用 CLI：**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "mode": "pixelate",
     "block_scale": 0.1,
     "frame_rate": 30
   }'
   ```

## 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | video (文件) | 是 | - | 要遮挡的输入视频 |
| `mode` | string | 否 | `pixelate` | Mosaic 算法：`pixelate` 或 `blur` |
| `block_scale` | number | 否 | `0.1` | 相对于每个区域较短边的像素化块大小（0.0 – 1.0）。自动适配——小区域获得比例更细的块。用于 `mode: pixelate` |
| `blur_radius` | number | 否 | `8.0` | 模糊半径（像素）。用于 `mode: blur` |
| `min_confidence` | number | 否 | `0.35` | 最低检测置信度（0.0 – 1.0）。降低（例如 `0.2`）以捕获更多边缘区域——对遮挡而言，多一些误报比漏检更安全 |
| `bounding_box_padding` | number | 否 | `0.1` | 在 mosaic 之前每个检测框向外扩展的比例。小的填充（例如 `0.1` = 10 %）可以隐藏紧贴裁剪的边缘，防止原始区域的一两个像素从框外泄漏 |
| `merge_gap` | number | 否 | `0.5` | tracker 会跨越进行插值的漏检秒数（也是检测 chunk 的流式延迟下限）。提高它可跨越更长的检测器空档，代价是更多缓冲；如果延迟比间隙填补更重要，则降低 |
| `frame_rate` | number | 否 | `30` | 输出帧率。设为源视频的真实 fps 以避免音频漂移 |

## 组件详情

### Audio Extractor (`audio-extractor`)
- **Type**：`audio-extractor`
- **Driver**：`ffmpeg`
- **功能**：读取视频流并把音轨拆分为 mp3。由上游 `fan-out` 任务的一个分支馈入，使其能与帧提取器并行消费上传流。后由编码器用于把音频复用回遮挡后的视频。

### Frame Extractor (`frame-extractor`)
- **Type**：`video-frame-extractor`
- **Driver**：`ffmpeg`
- **功能**：随 ffmpeg 解码流式产出每一帧（`frame_interval: 1`）。`streaming: true` 意味着提取器不会缓冲整段视频——每一帧直接流入下方的 tracker。

### NSFW Tracker (`nsfw-tracker`)
- **Type**：`model` —— `object-tracking` 任务
- **Driver**：`custom`（Ultralytics YOLO family）
- **功能**：消费帧流并发出形如 `{type: "detection", number, timestamp, objects: [{track_id, label, bounding_box}], image}` 的每帧检测 chunk 流。tracker 的其他 chunk 类型在此全部被抑制：`return_tracks: false` 丢弃每片段和每轨迹 chunk，`return_metadata: false` 丢弃终止 `metadata` chunk。`return_frame_image: true` 把源图像打包进每个检测 chunk，让 mosaic 步骤不需要一条独立的帧流去 zip。`max_concurrent_count: 1` 串行化 GPU 侧工作；外层 `for-each` 仍在 CPU 侧跨帧并行运行 mosaic 工作。

### Mosaic (`mosaic`)
- **Type**：`image-processor`（`mosaic` 方法）
- **Driver**：`native`
- **功能**：对一个 bounding box 应用 mosaic。由内联 `accumulate` 步骤在每个检测上调用一次。

### Encoder (`encoder`)
- **Type**：`video-encoder`
- **Driver**：`ffmpeg`
- **功能**：将遮挡后的帧流编码为 mp4（`libx264 @ 8M`）并复用提取到的音频（`aac @ 192k`）。接受流式输入，因此 ffmpeg 会在准备好时按需拉取帧。

## 说明与调优

- **成本**：NSFW 检测在每一帧上运行。10 秒 30 fps 片段 = 300 次检测调用。YOLO 很快（CPU 上每帧数十毫秒，CUDA / CoreML 更快），因此墙钟时间与帧数线性相关。
- **并发**：外层 `for-each` 的 `batch_size: 16` 最多并发运行 16 条每帧 mosaic 管线。提高以用内存换吞吐；如果 mosaic 在争用下成为瓶颈则降低。
- **帧率**：如果源和输出帧率不同，音视频会漂移。请把源视频的真实 fps 作为 `frame_rate` 传入。
- **漏掉的区域**：如果仍有区域被漏掉，降低 `min_confidence`（例如 `0.2`）——多出的误报也就是被 mosaic 一次，对遮挡是正确的权衡。如果在小尺度下持续漏检，重新训练或换更大的 YOLO 变体。
- **间隙填补窗口**：`merge_gap` 同时控制插值窗口（tracker 会桥接多少秒的漏检）和检测 chunk 的最小流式延迟（chunk 会被暂存这段时间以让插值完成）。默认 `0.5` 秒在 30 fps 下能桥接几帧的漏检——如果检测器经常连续掉更长的段，提高它（例如 `1.0`），但要注意所有下游帧都会被同样延迟。
- **类别选择**：编辑 `nsfw-tracker` 组件下的 `labels:` 列表以拓宽或收窄被 mosaic 的类别（默认为 `FEMALE_GENITALIA_EXPOSED` 与 `MALE_GENITALIA_EXPOSED`）。类名依赖您的权重——检查模型的标签列表；未知名称会在加载时抛出清晰错误。
- **遮挡强度**：对 `pixelate`，更大的 `block_scale` 遮挡更强（典型值 `0.05`–`0.2`）。块大小从每个区域的较短边计算，因此同一 `block_scale` 在小区域和大区域上给出视觉一致的强度。对 `blur`，提高 `blur_radius`（典型值 8–20）。模糊在低半径下可能留下模糊轮廓——如果区域必须完全无法辨认，优先使用 `pixelate`。
- **重叠区域**：当框重叠时，后续区域会在已被 mosaic 的像素上再次 mosaic，因此重叠的检测仍然会被遮挡。
- **填充框**：检测器的框可能贴得很紧，边缘会漏出原始区域的一两个像素。`bounding_box_padding` 参数（默认 `0.1` = 10 %）在每个返回的框流入 mosaic 之前向每一侧扩展——如果您仍看到边缘泄漏则提高它，如果填充侵入了无关内容则降低它。
- **无检测的帧**：干净的帧检测数为零，因此内联 `accumulate` 步骤的输入列表为空，accumulator 原样通过——原始帧直达编码器。工作流层面无需任何特例处理。
