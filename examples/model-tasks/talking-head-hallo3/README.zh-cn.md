# Talking Head 模型任务示例 (Hallo3)

本示例演示如何通过 model-compose 内置的 talking-head 任务运行 Hallo3（基于 CogVideoX-5B），从一张静态人像、驱动音频和可选的文本提示生成基于 DiT 的 talking-head 视频。

## 概述

此工作流提供本地 talking-head 生成功能：

1. **本地 Hallo3 DiT 流水线**：无需任何外部 API，在本地端到端运行 Hallo3 基于 CogVideoX 的 `SATVideoDiffusionEngine`
2. **文本引导的运动**：可选的 `prompt` 与驱动音频一同进入 T5-xxl 文本编码器，让你引导场景、风格或运动（例如 "cinematic close-up, warm lighting"）
3. **滑动窗口长视频**：Hallo3 在内部拼接 DiT 窗口，使超过单个窗口的音频渲染为连贯的单一输出
4. **自动模型管理**：首次运行时从 Hugging Face 下载 Hallo3 检查点包；流水线从安装的 repo 根目录解析 config 相对路径

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 强烈推荐**至少 24 GB VRAM** 的 CUDA GPU；CogVideoX-5B 是本合集中最重的 talking-head 骨干
- 可安装 torch/torchvision 和 Hallo3 依赖链（`diffusers`、`transformers`、`sat`、`sentencepiece`、`librosa`、`audio-separator`、`insightface`、`moviepy`、`av`……）的 Python 环境 — 首次运行时自动安装到沙箱 venv 中

### 为什么选择本地 talking-head

与云端 talking-head 服务不同，在本地运行 Hallo3 提供：

**本地处理的优势：**
- **隐私**：人像和语音录音永远不会离开本机
- **成本**：无按秒或按渲染的 API 费用
- **离线**：初始检查点下载后无需互联网连接
- **管道友好**：与其他 model-compose 任务无缝组合，可构建端到端的头像流水线

**权衡：**
- **硬件要求**：默认分辨率下需要约 24 GB VRAM；首次运行还会下载约 15 GB 的 CogVideoX 权重
- **非实时**：基于 CogVideoX-5B 的 50 步 DiT 循环意味着即使在 H100 级硬件上，每秒延迟也非常高
- **许可证**：Hallo3 权重仅**用于非商业研究**

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/talking-head-hallo3
   ```

2. 无需额外的环境配置 — Hallo3 检查点包（`fudan-generative-ai/hallo3`）在首次运行时从 Hugging Face 自动下载并缓存。

3. 本示例在专用的 **virtualenv**（`.venv/hallo3`）中运行模型工作进程，以隔离 Hallo3 的 CogVideoX SAT 工具包和 transformers 版本锁定，避免与控制器自身的 site-packages 冲突。venv 在首次运行时创建，之后重复使用。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会获取 Hallo3 源码、安装其 Python 依赖并下载 CogVideoX-5B 检查点包。请预留 20 分钟以上时间和约 15 GB 的下载量，控制器才会报告就绪。

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 最小调用 — 仅音频驱动
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 用文本提示引导场景
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "prompt": "cinematic close-up, warm evening lighting, subtle head movement"}'

   # 使用更少的 DiT 步骤进行快速预览
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "inference_steps": 25}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `image`（正面人像效果最佳）和 `audio` 剪辑（WAV/MP3）
   - 可选地添加 `prompt`，或调整 `inference_steps`、`guidance_scale`、`audio_guidance_scale`、`resolution`
   - 点击 "Run Workflow" 按钮以接收 MP4

## 配置参考

### 组件字段

| 字段     | 说明                                                                                                | 默认值  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | 必须为 `talking-head`。                                                                             | —       |
| `driver` | 必须为 `custom`。                                                                                   | —       |
| `family` | Talking-head 模型系列。设为 `hallo3`。                                                              | —       |
| `model`  | 检查点包。Hugging Face repo id（例如 `fudan-generative-ai/hallo3`）或本地目录。                     | —       |

### 动作字段

| 字段                            | 说明                                                                                                          | 默认值  |
|---------------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                         | 提供待动画化身份的源人像（或人像的列表/流）。                                                                 | —       |
| `audio`                         | 口型跟随的驱动音频剪辑（或剪辑列表）。                                                                        | —       |
| `params.prompt`                 | 通过 T5-xxl 文本编码器引导场景、风格或运动的可选文本提示。                                                    | （空）  |
| `params.negative_prompt`        | 描述要避免内容的文本。                                                                                        | （无）  |
| `params.inference_steps`        | DiT 推理步骤数。                                                                                              | `50`    |
| `params.guidance_scale`         | 文本条件化的 classifier-free guidance 缩放。                                                                  | `6.0`   |
| `params.audio_guidance_scale`   | 应用于音频条件化分支的 guidance 缩放。                                                                        | `3.0`   |
| `params.resolution`             | 输出帧分辨率（短边长度，像素）。                                                                              | `480`   |
| `params.num_frames`             | 每个 DiT 窗口生成的帧数。                                                                                     | `97`    |
| `params.shift`                  | 应用于调度器的 Flow-matching timestep shift。                                                                 | `5.0`   |
| `params.long_video`             | 为超过一个 DiT 窗口的音频启用长视频模式（窗口与混合）。                                                       | `true`  |
| `params.fps`                    | 输出视频帧率。                                                                                                | `25`    |
| `batch_size`                    | 当两个输入都是列表或流时，每批处理的 `(image, audio)` 对的数量。                                              | `1`     |
| `seed`                          | 用于可复现性的随机种子。留空则每次调用产生新样本。                                                            | （无）  |

## 备注

- **首次运行较慢**：控制器必须获取 Hallo3 源码、安装其依赖并下载 CogVideoX-5B 检查点。后续运行会重用缓存的安装和模型文件。
- **长音频**：生成时间随音频长度线性增长；单张 24 GB GPU 上大约每秒输出音频需要 3–5 分钟。
- **提示调优**：T5-xxl 文本编码器强大但敏感 — 从简短的电影风格描述符（"cinematic portrait, soft key light"）开始迭代。非常长的提示（>226 个 token）会被截断。
- **`long_video`**：任何长于一个 DiT 窗口（默认设置下约 4 秒）的输入都要保持开启。关闭它会将音频裁剪到单个窗口。
- **`resolution`**：提升到 720 会显著增加 VRAM 和延迟；默认 `480` 在 24 GB GPU 上是良好的预览/生产平衡。
- **管道搭配**：上游搭配 `text-to-speech`（将生成的语音作为 `audio` 传入），下游搭配 `image-upscale`，即可构建完全本地的文本到头像流水线。
