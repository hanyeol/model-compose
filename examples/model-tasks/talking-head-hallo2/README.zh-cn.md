# Talking Head 模型任务示例 (Hallo2)

本示例演示如何通过 model-compose 内置的 talking-head 任务运行 Hallo2，从一张静态人像和驱动音频剪辑生成高分辨率、长时长的 talking-head 视频。

## 概述

此工作流提供本地 talking-head 生成功能：

1. **本地 Hallo2 扩散流水线**：无需任何外部 API，在本地端到端运行 Hallo2 的 `FaceAnimatePipeline`（reference UNet + denoising UNet + face locator + motion module）
2. **长音频支持**：Hallo2 将长音频切分为 60 秒段，对每段进行动画化后通过内置的 `merge_videos` 步骤拼接为单一输出 — 可用于数分钟的剪辑
3. **运动加权条件**：独立的 `pose_weight` / `face_weight` / `lip_weight` 缩放让你调节驱动音频暗示的运动多大程度上覆盖源人像的静态姿态
4. **自动模型管理**：首次运行时从 Hugging Face 下载 Hallo2 检查点包；Hallo2 本身已经提供干净的 `hallo/` 包布局，无需 SadTalker 风格的重写

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 强烈推荐支持 CUDA 的 GPU；40 步扩散循环在 CPU 上速度慢到不切实际
- 可安装 torch/torchvision 和 Hallo2 依赖链（`diffusers`、`transformers`、`librosa`、`audio-separator`、`insightface`、`moviepy`、`av`……）的 Python 环境 — 首次运行时自动安装到沙箱 venv 中

### 为什么选择本地 talking-head

与云端 talking-head 服务不同，在本地运行 Hallo2 提供：

**本地处理的优势：**
- **隐私**：人像和语音录音永远不会离开本机
- **成本**：无按秒或按渲染的 API 费用；同一张人像可以低成本地重新驱动
- **离线**：初始检查点下载后无需互联网连接
- **管道友好**：与其他 model-compose 任务（上游的 text-to-speech、下游的 image-upscale 等）无缝组合，可构建端到端的头像流水线

**权衡：**
- **硬件要求**：默认分辨率下需要约 12 GB VRAM；首次运行还会下载数 GB 的检查点
- **非实时**：扩散循环加段落拼接意味着即使在高端 GPU 上，每秒输出音频也有数秒延迟
- **许可证**：Hallo2 权重仅**用于非商业研究**

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/talking-head-hallo2
   ```

2. 无需额外的环境配置 — Hallo2 检查点包（`fudan-generative-ai/hallo2`）在首次运行时从 Hugging Face 自动下载并缓存。

3. 本示例在专用的 **virtualenv**（`.venv/hallo2`）中运行模型工作进程，以隔离 Hallo2 的 diffusers/transformers 版本锁定，避免与控制器自身的 site-packages 冲突。venv 在首次运行时创建，之后重复使用。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会获取 Hallo2 源码、安装其 Python 依赖并下载检查点包。请预留十多分钟时间和数 GB 的下载量，控制器才会报告就绪。

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 最小调用 — 用驱动音频剪辑动画化一张人像
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 提高口部/面部权重，让音频驱动的动作更强烈
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "lip_weight": 1.4, "face_weight": 1.3}'

   # 使用更少的扩散步骤进行快速预览
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "inference_steps": 20}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `image`（正面人像效果最佳）和 `audio` 剪辑（WAV/MP3）
   - 可选地调整运动权重、`face_expand_ratio`、`inference_steps` 或 `cfg_scale`
   - 点击 "Run Workflow" 按钮以接收 MP4

## 配置参考

### 组件字段

| 字段     | 说明                                                                                                | 默认值  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | 必须为 `talking-head`。                                                                             | —       |
| `driver` | 必须为 `custom`。                                                                                   | —       |
| `family` | Talking-head 模型系列。设为 `hallo2`。                                                              | —       |
| `model`  | 检查点包。Hugging Face repo id（例如 `fudan-generative-ai/hallo2`）或本地目录。                     | —       |

### 动作字段

| 字段                          | 说明                                                                                                          | 默认值  |
|-------------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                       | 提供待动画化身份的源人像（或人像的列表/流）。                                                                 | —       |
| `audio`                       | 口型跟随的驱动音频剪辑（或剪辑列表）。                                                                        | —       |
| `params.pose_weight`          | Motion module 条件化时应用于驱动姿态信号的权重。                                                              | `1.1`   |
| `params.face_weight`          | Motion module 条件化时应用于驱动面部信号的权重。                                                              | `1.1`   |
| `params.lip_weight`           | Motion module 条件化时应用于驱动唇部信号的权重。                                                              | `1.1`   |
| `params.face_expand_ratio`    | 检测到的人脸框周围的人脸裁剪扩展比例。                                                                        | `1.2`   |
| `params.inference_steps`      | 每个去噪循环的扩散推理步骤数。                                                                                | `40`    |
| `params.cfg_scale`            | Classifier-free guidance 缩放。                                                                               | `3.5`   |
| `params.motion_module_frames` | Motion module 每个窗口处理的帧数。                                                                            | `16`    |
| `params.long_video`           | 为超过一个窗口的音频启用 Hallo2 的长视频模式（分块与混合）。                                                  | `true`  |
| `params.high_resolution`      | 运行内置超分过程以生成更高分辨率的输出。                                                                      | `false` |
| `params.fps`                  | 输出视频帧率。                                                                                                | `25`    |
| `batch_size`                  | 当两个输入都是列表或流时，每批处理的 `(image, audio)` 对的数量。                                              | `1`     |
| `seed`                        | 用于可复现性的随机种子。留空则每次调用产生新样本。                                                            | （无）  |

## 备注

- **首次运行较慢**：控制器必须获取 Hallo2 源码、安装其依赖并下载检查点包。后续运行会重用缓存的安装和模型文件。
- **长音频**：生成时间随音频长度线性增长。原生支持数分钟输入；运行时间也成比例增加。
- **运动权重**：将 `lip_weight` 和 `face_weight` 提高到 1.0 以上会让语音驱动的运动更明显，但可能牺牲身份保真度。`pose_weight` 控制模型愿意引入多少头部运动。
- **`long_video`**：任何长于默认运动窗口的输入都要保持开启 — Hallo2 的段落/拼接流水线正是数分钟输出得以实现的关键。
- **`high_resolution`**：上采样器是独立的扩散过程；启用后大约会使延迟和 VRAM 翻倍。
- **管道搭配**：上游搭配 `text-to-speech`（将生成的语音作为 `audio` 传入），下游搭配 `image-upscale`，即可构建完全本地的文本到头像流水线。
