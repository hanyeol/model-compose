# Talking Head 模型任务示例 (Float)

本示例演示如何通过 model-compose 内置的 talking-head 任务运行 Float（DeepBrain AI 的 flow-matching 管道，支持显式情绪标签），从一张静态人像和驱动音频剪辑生成情绪条件化的 talking-head 视频。

## 概述

此工作流提供本地 talking-head 生成功能：

1. **本地 Float flow-matching 流水线**：无需任何外部 API，在本地端到端运行 Float 的 `InferenceAgent.run_inference()` — 对人像 + 音频 latent 进行 flow-matching，配合 wav2vec2 音频编码器
2. **显式情绪标签**：从 `happy`、`sad`、`angry`、`fear`、`disgust`、`surprise`、`neutral` 中选择，或保留 `S2E` 哨兵值让 Float 直接从音频推导情绪
3. **快速推理**：默认仅 10 flow-matching NFE；是本合集中最快的 talking-head 骨干之一
4. **自动模型管理**：首次运行时从 Hugging Face 下载 Float 检查点包（Float 权重 + wav2vec2-base-960h + 情绪识别头）；上游的扁平 repo 布局被包装成单一的 `float_talker/` 包，使 `models/`、`options/` 等顶层名称不会与 site-packages 中的其他项冲突

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 强烈推荐支持 CUDA 的 GPU；CPU 推理慢得多
- 可安装 torch/torchvision 和 Float 依赖链（`diffusers`、`transformers`、`librosa`、`face-alignment`、`torchdiffeq`、`moviepy`……）的 Python 环境 — 首次运行时自动安装到沙箱 venv 中

### 为什么选择本地 talking-head

与云端 talking-head 服务不同，在本地运行 Float 提供：

**本地处理的优势：**
- **隐私**：人像和语音录音永远不会离开本机
- **成本**：无按秒或按渲染的 API 费用
- **离线**：初始检查点下载后无需互联网连接
- **管道友好**：与其他 model-compose 任务无缝组合，可构建端到端的头像流水线

**权衡：**
- **硬件要求**：相对轻量（约 8 GB VRAM），但在高端显卡上仍更快
- **以英语为中心的情绪头**：捆绑的情绪识别器在英语语音上训练；对非英语音频，显式 `emotion` 标签是更安全的回退
- **许可证**：Float 权重仅**用于非商业研究**

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/talking-head-float
   ```

2. 无需额外的环境配置 — Float 检查点包（`yuvraj108c/float`）在首次运行时从 Hugging Face 自动下载并缓存。

3. 本示例在专用的 **virtualenv**（`.venv/float`）中运行模型工作进程，以便 Float 在安装时被重命名为 `float_talker.models` / `float_talker.options` 的 `models/` 和 `options/` 包不会与控制器自身的 site-packages 冲突。venv 在首次运行时创建，之后重复使用。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会获取 Float 源码、安装其 Python 依赖并下载检查点包。请预留数分钟时间和数 GB 的下载量，控制器才会报告就绪。

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 最小调用 — 情绪自动检测
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 强制指定显式情绪标签
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "emotion": "happy"}'

   # 跳过人脸裁剪以渲染完整画面（当人像已在上游被紧凑裁剪时有用）
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "crop": false}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `image`（正面人像效果最佳）和 `audio` 剪辑（WAV/MP3）
   - 可选地选择 `emotion`，或调整 `inference_steps`、`cfg_scale`、`a_cfg_scale`、`e_cfg_scale`
   - 点击 "Run Workflow" 按钮以接收 MP4

## 配置参考

### 组件字段

| 字段     | 说明                                                                                                | 默认值  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | 必须为 `talking-head`。                                                                             | —       |
| `driver` | 必须为 `custom`。                                                                                   | —       |
| `family` | Talking-head 模型系列。设为 `float`。                                                               | —       |
| `model`  | 检查点包。Hugging Face repo id（例如 `yuvraj108c/float`）或本地目录。                               | —       |

### 动作字段

| 字段                        | 说明                                                                                                          | 默认值  |
|-----------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                     | 提供待动画化身份的源人像（或人像的列表/流）。                                                                 | —       |
| `audio`                     | 口型跟随的驱动音频剪辑（或剪辑列表）。                                                                        | —       |
| `params.emotion`            | 情绪标签：`happy`、`sad`、`angry`、`fear`、`disgust`、`surprise`、`neutral`，或自动检测的 `S2E`。            | `S2E`   |
| `params.emotion_scale`      | 应用于情绪条件化强度的乘数。                                                                                  | `1.0`   |
| `params.inference_steps`    | Flow-matching 推理步骤数（NFE）。                                                                             | `10`    |
| `params.cfg_scale`          | 应用于参考分支的 classifier-free guidance 缩放。                                                              | `2.0`   |
| `params.a_cfg_scale`        | 应用于音频条件化分支的 guidance 缩放。                                                                        | `2.0`   |
| `params.e_cfg_scale`        | 应用于情绪条件化分支的 guidance 缩放。                                                                        | `1.0`   |
| `params.crop`               | 渲染前将源人像裁剪到检测到的人脸；禁用则渲染完整画面。                                                        | `true`  |
| `params.fps`                | 输出视频帧率。                                                                                                | `25`    |
| `batch_size`                | 当两个输入都是列表或流时，每批处理的 `(image, audio)` 对的数量。                                              | `1`     |
| `seed`                      | 用于可复现性的随机种子。留空则每次调用重用 Float 默认值（25）。                                               | `25`    |

## 备注

- **首次运行较慢**：控制器必须获取 Float 源码、安装其依赖并下载检查点包。后续运行会重用缓存的安装和模型文件。
- **`S2E` vs 显式情绪**：对英语语音，`S2E` 给出自然结果；对其他语言，显式标签（`happy`、`sad`……）可避免以英语为中心的情绪头的错误预测。
- **`e_cfg_scale`**：提高此值会让情绪条件化更直接地反映；结合显式 `emotion` 标签可获得强风格化输出。
- **`crop: false`**：如果输入人像已经紧凑裁剪（例如来自上游的 `image-upscale` 组件），跳过 Float 的人脸裁剪步骤可获得更整洁的画面。
- **人脸检测失败**：如果源图像中未检测到人脸，Float 的内置预处理器会抛出对齐错误。请使用更清晰、更大、正面朝向的人像。
- **管道搭配**：上游搭配 `text-to-speech`（将生成的语音作为 `audio` 传入），下游搭配 `image-upscale`，即可构建完全本地的文本到头像流水线。
