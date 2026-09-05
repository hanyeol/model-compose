# 姿态骨架叠加示例

本示例展示了一个工作流：用 YOLOv8-pose 检测并跟踪视频中的每个人，为每帧中的每个姿态渲染骨架，再将叠加后的帧连同原音频轨重新组装为 mp4。整个流水线端到端以流式模式运行，因此内存占用与片长无关，始终保持有界。

> **许可证提示**：本示例会自动下载 Ultralytics 的 YOLOv8-pose 权重，该权重以 **AGPL-3.0** 发布。个人使用、研究、开源演示都没问题。商业使用需要遵守 AGPL-3.0（开源整个系统）或获取 Ultralytics Enterprise License — 详见 [ultralytics.com/license](https://www.ultralytics.com/license)。

## 概览

给定一段输入视频,工作流返回同一视频的新版本 — 在每帧检测到的每个人的姿态上方绘制彩色骨架。

策略:

1. **将上传流用 `fan-out` 作业分流** 到两个独立分支,一个给音频提取器,一个给帧提取器,让二者能并行消耗这一次性上传流,同时不把视频落到磁盘。
2. **分离音频轨** — 用 `audio-extractor` 从视频中分离出音频(原样保留)。
3. **流式提取每一帧** — 用 `video-frame-extractor`(`streaming: true` — 不做整段视频缓冲)。
4. **在帧流上运行姿态跟踪** — `streaming: true`,配置为发出每帧一个的分块流,每个分块携带源图像和每个检测到的姿态的一张全帧骨架 PNG。轨段、聚合的轨元数据、最后的元数据分块全部抑制 — 叠加步骤只需要帧。
5. **对每帧分块**,`merge` 将源帧与每个姿态的骨架图像一次性合成。`for-each` 作业的输出同样是流,叠加后的帧因此惰性流向编码器。
6. **将叠加后的帧流编码回 mp4** — 用 `video-encoder`,并把提取出的音频复用进输出。ffmpeg 按需从上游流拉取帧,该阶段也不做整段视频缓冲。

### 为什么流式很重要

朴素的设计会把每一帧都实体化到内存,在整个列表上跑检测,再把叠加后的列表交给编码器。这在短片上能用,但在长视频上会把内存吃爆(1080p 30 fps 10 分钟片段 = 18,000 帧 × 解码后 ~6 MB = 约 110 GB 的 PIL 图像)。

端到端流式下,叠加步骤中任一时刻最多只有 `batch_size` 帧在途,编码器随到随消。内存占用与片长无关,始终保持有界。

### 为什么用姿态跟踪(而不是纯检测)

这里的姿态跟踪纯粹被当作逐帧检测器兼渲染器 — 叠加不需要轨迹身份,相关的分块类型全部关闭。之所以仍然用跟踪器,是因为它的逐帧分块已经把源图像(`return_frame_image: true`)和每个检测姿态的全帧骨架 PNG(`return_skeleton_image: true`)打包在一起了。每个骨架 PNG 都是按源帧原分辨率、透明背景渲染的,所以合并步骤只需把整摞图像做 alpha 合成 — 无需按姿态做 x/y 计算。纯检测器只会输出关键点,那样工作流就必须自己画骨架。

## 准备

### 要求

- 已在 PATH 中安装 model-compose
- 已在 PATH 中安装 FFmpeg
- YOLO 姿态检测的 Python 依赖:
  ```bash
  pip install ultralytics lap
  ```
- YOLOv8n-pose 权重在首次运行时自动下载到 model-compose 的模型缓存。

### 设置

1. 进入示例目录:
   ```bash
   cd examples/media-processing/pose-skeleton-overlay
   ```

2. 准备一段要叠加的视频文件。

## 如何运行

1. **启动服务:**
   ```bash
   model-compose up
   ```

2. **运行工作流:**

   **使用 Web UI:**
   - 打开 Web UI: http://localhost:8081
   - 上传视频,可选择覆盖 `frame_rate` / `min_confidence` / `skeleton_format`
   - 点击 "Run Workflow"

   **使用 API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"frame_rate": 30, "min_confidence": 0.4, "skeleton_format": "natural"};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **使用 CLI:**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "frame_rate": 30,
     "min_confidence": 0.4,
     "skeleton_format": "natural"
   }'
   ```

## 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | video (file) | 是 | - | 用于叠加的输入视频 |
| `min_confidence` | number | 否 | `0.4` | 姿态检测最小置信度 (0.0 – 1.0)。若仍有人被漏检,可降低(例如 `0.25`) |
| `skeleton_format` | string | 否 | `natural` | 骨架布局:`natural`(COCO-17 关键点,与 YOLO 原生输出一致)或 `openpose`(BODY_18) |
| `frame_rate` | number | 否 | `30` | 输出帧率。为避免音画漂移,请设为源视频的真实 fps |

## 组件详情

### 音频提取器 (`audio-extractor`)
- **类型**:`audio-extractor`
- **驱动**:`ffmpeg`
- **功能**:读取视频流并将音频轨分离为 mp3。由上游 `fan-out` 作业的一个分支供给,与帧提取器并行消费上传流。稍后由编码器用于把音频复用回叠加后的视频。

### 帧提取器 (`frame-extractor`)
- **类型**:`video-frame-extractor`
- **驱动**:`ffmpeg`
- **功能**:随 ffmpeg 解码流式发出每一帧(`frame_interval: 1`)。`streaming: true` 表示提取器从不缓冲整段视频 — 每一帧直接流向下方的跟踪器。

### 姿态跟踪器 (`pose-tracker`)
- **类型**:`model` — `pose-tracking` 任务
- **驱动**:`custom`(YOLO 系列,`yolov8n-pose.pt` 权重)
- **功能**:消费帧流,发出形如 `{type: "detection", number, timestamp, poses: [{track_id, bounding_box, skeleton_image}], image}` 的逐帧检测分块流。`return_frame_image: true` 把源图像随每个检测分块一起打包,`return_skeleton_image: true` 为每个检测到的姿态按源分辨率渲染一张透明背景的骨架 PNG。跟踪器的其他分块类型被抑制:`return_tracks: false` 丢弃逐段和逐轨分块,`return_metadata: false` 丢弃末尾的 `metadata` 分块。

### 骨架合并器 (`skeleton-merger`)
- **类型**:`image-processor`(`merge` 方法)
- **驱动**:`native`
- **功能**:将输入列表中的每张图像 alpha 合成到一张按最大输入尺寸生成的共享画布上。由于骨架渲染与源帧同尺寸,一切按 1:1 对齐 — 源帧作为底层先入,再一次性把每个姿态的骨架 PNG 叠上去。

### 编码器 (`encoder`)
- **类型**:`video-encoder`
- **驱动**:`ffmpeg`
- **功能**:把叠加后的帧流编码为 mp4(`libx264 @ 8M`),并复用提取出的音频(`aac @ 192k`)。接受流输入,ffmpeg 按需拉取帧。

## 备注与调优

- **成本**:姿态检测按帧执行,每帧每个检测到的姿态渲染一张骨架 PNG。10 秒 30 fps 的片段 = 300 次检测器调用;墙钟时间随帧数线性增长。YOLOv8n-pose 是最小最快的权重 — 若精度比时延更重要,换成 `yolov8s/m/l/x-pose.pt`(更大、更准)。
- **并发**:`for-each` 作业上的 `batch_size: 8` 让最多 8 条合并流水线并发运行。提高它可以用内存换吞吐;若合并组件在争用下成为瓶颈则调低。
- **帧率**:源与输出帧率不同则会音画漂移。将源视频的真实 fps 传给 `frame_rate`。
- **漏检姿态**:若仍有人被漏检,降低 `min_confidence`(例如 `0.25`)。非常小/远的人可能仍被底层检测器丢掉 — 想提升召回,换更大的 YOLO 权重。
- **骨架样式**:`skeleton_format: natural` 使用 COCO-17 关键点(与 YOLO 原生输出一致);`openpose` 转换为 ControlNet 等下游姿态编辑工具常用的 BODY_18 布局。若打算把输出喂给 OpenPose 条件化的扩散流水线,请选 `openpose`。
- **插值帧**:当检测器在某一帧漏掉某个姿态、又在附近帧(`merge_gap` 以内)重新捕获时,跟踪器会用插值出的边界框和骨架填补空缺,让叠加在短暂的检测掉线区间视觉上保持顺滑。插值出的姿态在分块上被标记 `interpolated: true`,但叠加流水线对它们的处理与其他姿态无异。
