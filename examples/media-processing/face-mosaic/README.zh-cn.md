# 人脸马赛克示例

本示例展示了一个工作流：对视频中每张检测到的人脸按 bounding box 进行像素化（或模糊），并在保留原音轨的前提下重新封装为 mp4。整个流水线以 end-to-end 流式方式运行，因此内存占用与片段长度无关，始终保持有界。

> **许可证提示**：本示例会自动下载 InsightFace 的 `antelopev2` 模型包，其训练数据许可**仅限非商业研究用途**。个人使用、研究、开源演示、自托管工具都没问题。**请勿**将该包内嵌到商业产品或付费服务中 — 此类场景请改用允许商用的检测器（`family: blazeface`）或自训练模型。

## 概览

给定一个输入视频，工作流返回一个每张人脸都被马赛克遮蔽的同版本视频。

策略：

1. **暂存上传视频** — 使用本地 `file-store` 保存视频，让音频分支和帧提取器能各自独立地重新读取（原始上传流是一次性的）。
2. **分离音轨** — 使用 `audio-extractor` 从暂存的视频中抽取音频（保持不变）。
3. **流式提取所有帧** — 使用 `video-frame-extractor` 生成帧流（`streaming: true`，不缓存整段视频）。
4. **逐帧检测 + 马赛克** — 使用 `face-detection`（InsightFace `antelopev2`）获取每张脸的 bbox，然后将该列表一次性传入 `image-processor mosaic`，一趟遮蔽一帧内所有人脸。extractor 输出流，因此 `for-each` 的输出也是流 — 遮蔽后的帧惰性流向 encoder。
5. **将遮蔽后的帧流重新编码** — 使用 `video-encoder` 编码为 mp4，并 mux 前面抽取的音频。ffmpeg 需要时才从上游流拉取帧，因此此阶段同样无需缓存整段视频。

逐帧的 detect+mosaic 组合封装在私有子工作流 `mosaic-faces-in-frame` 中，让主工作流的 `for-each` 保持清晰。

### 为什么需要流式

朴素设计会把每一帧都放进内存，对整个列表跑检测，再把遮蔽后的列表交给 encoder。对短片段没问题，但长视频会爆内存（1080p 30fps 10 分钟片段 = 18,000 帧 × 解码后 ~6 MB = ~110 GB PIL 图像）。

end-to-end 流式则最多让 `batch_size` 帧同时通过检测流水线，encoder 一到手就消费遮蔽帧。内存占用与片段长度无关，始终保持有界。

## 准备

### 要求

- 已在 PATH 中安装 model-compose
- 已在 PATH 中安装 FFmpeg
- InsightFace 检测的 Python 依赖：
  ```bash
  pip install insightface opencv-python onnxruntime
  ```
- `antelopev2` InsightFace 模型包在首次运行时自动下载到 `~/.cache/models/insightface/`。

### 设置

1. 进入示例目录：
   ```bash
   cd examples/media-processing/face-mosaic
   ```

2. 准备一个待遮蔽的视频文件。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传视频，按需覆盖 `mode` / `block_scale` / `blur_radius` / `frame_rate` / `min_confidence`
   - 点击 "Run Workflow"

   **API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"mode": "pixelate", "block_scale": 0.08, "frame_rate": 30};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **CLI：**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "mode": "pixelate",
     "block_scale": 0.08,
     "frame_rate": 30
   }'
   ```

## 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `video` | video (file) | 是 | - | 待处理的输入视频 |
| `mode` | string | 否 | `pixelate` | 马赛克算法：`pixelate` 或 `blur` |
| `block_scale` | number | 否 | `0.1` | 相对于每张人脸短边的像素块大小比例（0.0 – 1.0）。会自动适应 region 大小 — 远处的小脸和近处的大脸会得到视觉上一致的遮蔽强度。`mode: pixelate` 时使用 |
| `blur_radius` | number | 否 | `8.0` | 模糊半径（像素）。`mode: blur` 时使用 |
| `min_confidence` | number | 否 | `0.5` | 最小人脸检测置信度（0.0 – 1.0）。传给 InsightFace 的 `det_thresh`。若仍有漏检，请降低（例如 `0.3`）— 遮蔽场景下多几个假阳性优于漏检 |
| `frame_rate` | number | 否 | `30` | 输出帧率。设为源视频真实 fps，否则音视频会漂移 |

## 组件详情

### Storage (`storage`)
- **类型**：`file-store`
- **驱动**：`local`
- **作用**：将上传的视频保存到 `./storage/uploads/<task_id>`，使音频分支和帧提取器可以独立打开该文件。原始上传流是一次性的，如果没有这一步，先读的 job 会消耗掉整个流。

### Audio Extractor (`audio-extractor`)
- **类型**：`audio-extractor`
- **驱动**：`ffmpeg`
- **作用**：读取暂存的视频，将音轨分离为 mp3。供后续 encoder 将音频 mux 回遮蔽后的视频。

### Frame Extractor (`frame-extractor`)
- **类型**：`video-frame-extractor`
- **驱动**：`ffmpeg`
- **作用**：ffmpeg 每解码一帧就作为流 emit（`frame_interval: 1`）。`streaming: true`，因此 extractor 从不缓存整段视频，每个 `{image, timestamp}` chunk 直接流入下方的 `for-each`。

### Face Detector (`face-detector`)
- **类型**：`model` — `face-detection` 任务
- **驱动**：`custom`（InsightFace 家族，`antelopev2` 包）
- **作用**：为每帧返回 `{faces: [{bounding_box: {x, y, width, height}, score, ...}], width, height}`。下游只使用 `bounding_box`。相比 BlazeFace 对侧脸/小人脸/非正面人脸更稳健 — 这正是遮蔽工作流最关心的特性。

### Mosaic (`mosaic`)
- **类型**：`image-processor`（`mosaic` 方法）
- **驱动**：`native`
- **作用**：一次性对多个 region 应用马赛克。`region` 接受单个 `{x, y, width, height}` dict 或它们的列表，`${jobs.detect.output.faces[*].bounding_box}` 将检测结果直接投影为这种形状。

### Per-Frame Wrapper (`mosaic-faces-in-frame`)
- **类型**：`workflow`（调用私有子工作流 `mosaic-faces-in-frame`）
- **作用**：让主工作流的 `for-each` 能像调用单个组件一样调用两步（detect + mosaic）流水线。

### Encoder (`encoder`)
- **类型**：`video-encoder`
- **驱动**：`ffmpeg`
- **作用**：将遮蔽后的帧流编码为 mp4（`libx264 @ 8M`）并 mux 音频（`aac @ 192k`）。接受流输入，因此 ffmpeg 在准备好时才拉取帧。

## 说明与调优

- **成本**：人脸检测每帧运行。10 秒 30fps 剪辑 = 300 次调用。InsightFace 的 SCRFD 检测器比 BlazeFace 重，但仍然很快（CPU 上每帧数十毫秒，CoreML/CUDA 上更快）。总耗时与帧数线性相关。
- **并发**：`for-each` 上的 `batch_size: 4` 会并发执行最多 4 条 detect+mosaic 流水线。提高该值可用内存换吞吐；如果模型组件在竞争下成为瓶颈，则降低。
- **帧率**：源与输出 fps 不同会导致音视频漂移。将源的真实 fps 作为 `frame_rate` 传入。
- **漏检人脸**：若仍有漏检，降低 `min_confidence`（例如 `0.3`）— 假阳性也会被马赛克，但遮蔽场景下这是正确的权衡。对非常小的人脸，请提高 `face-detector` 的 `params.detection_size`（例如 `[960, 960]` 或 `[1280, 1280]`）— 检测器在该输入分辨率下运行，加大尺寸可以捕获更多小人脸，代价是吞吐量下降。
- **遮蔽强度**：`pixelate` 用更大的 `block_scale` 遮得更狠（典型 `0.05`–`0.2`）。块大小按每个 region 的短边计算，因此相同的 `block_scale` 在远近不同的人脸上呈现视觉上一致的强度。计算出的块会被 `min_block_size`（默认 `8`）从下方兜底、`max_block_size`（默认 `32`）从上方封顶 — 小脸不会生成 1–2 像素的几乎无效块，占满画面的近景大脸也不会变成像素艺术般的几块超大瓷砖。若某一端仍显得不理想，请调整对应的上/下限。若需要固定绝对像素大小（不随 region 变化），改用 mosaic 组件配置中的 `block_size`。`blur` 提高 `blur_radius`（典型 8–20）。半径较低时模糊仍可能留下轮廓，若需完全不可辨认，优先使用 `pixelate`。
- **重叠人脸**：当框重叠时，后处理的 region 会在前一 region 已马赛克的像素之上再次应用，因此重叠的人脸也保持被遮蔽。
- **框的边距**：检测器有时会紧贴眼鼻裁剪而留下头发/下巴。在 `face-detector` 上设置 `bounding_box_padding`（例如 `0.2`）可在每个返回框每一侧扩展 20% 后再送入 mosaic。
