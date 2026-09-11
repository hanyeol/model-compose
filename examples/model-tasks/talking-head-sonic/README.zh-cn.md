# Talking Head 模型任务示例 (Sonic)

本示例演示如何通过 model-compose 内置的 talking-head 任务运行 Sonic（腾讯），从一张静态图像和驱动音频剪辑生成人像 talking-head 视频。

## 概述

此工作流提供本地 talking-head 生成功能：

1. **本地 Sonic SVD 流水线**：无需任何外部 API，在本地端到端运行 Sonic 的 `Sonic.process()` — SVD-XT 骨干、whisper-tiny 音频编码器、audio2token / audio2bucket 运动预测器和 RIFE 帧插值
2. **全局音频感知**：Sonic 预先在整段音频上进行条件化，比仅窗口的基线提供更平滑的多秒运动
3. **快速推理**：默认仅 25 个扩散步骤；在可比身份保真度下比更重的基于 DiT 的基线快约 2–3 倍
4. **自动模型管理**：首次运行时从 Hugging Face 下载 Sonic 检查点包（Sonic + SVD-XT + whisper-tiny + RIFE + yoloface）；上游的 `src/` 布局在原位被重命名，避免与 model-compose 自身源码树冲突

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 推荐使用**至少 16 GB VRAM** 的 CUDA GPU（SVD-XT 是内存下限）
- 可安装 torch/torchvision 和 Sonic 依赖链（`diffusers`、`transformers`、`librosa`、`moviepy`、`insightface`、`av`……）的 Python 环境 — 首次运行时自动安装到沙箱 venv 中

### 为什么选择本地 talking-head

与云端 talking-head 服务不同，在本地运行 Sonic 提供：

**本地处理的优势：**
- **隐私**：人像和语音录音永远不会离开本机
- **成本**：无按秒或按渲染的 API 费用
- **离线**：初始检查点下载后无需互联网连接
- **管道友好**：与其他 model-compose 任务无缝组合，可构建端到端的头像流水线

**权衡：**
- **硬件要求**：需要约 16 GB VRAM；首次运行还会下载数 GB 的检查点
- **非实时**：比大多数竞争模型快，但每秒输出音频仍需约 0.5–1 秒的 GPU 时间
- **许可证**：Sonic 权重仅**用于非商业研究**

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/talking-head-sonic
   ```

2. 无需额外的环境配置 — Sonic 检查点包（`LeonJoe13/Sonic`）在首次运行时从 Hugging Face 自动下载并缓存。

3. 本示例在专用的 **virtualenv**（`.venv/sonic`）中运行模型工作进程，以隔离 Sonic 的 SVD/diffusers 版本锁定，避免与控制器自身的 site-packages 冲突。venv 在首次运行时创建，之后重复使用。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会获取 Sonic 源码、安装其 Python 依赖并下载检查点包。请预留十多分钟时间和数 GB 的下载量，控制器才会报告就绪。

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 最小调用 — 用驱动音频剪辑动画化一张人像
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 通过 dynamic scale 乘数获得更富表现力的动作
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "dynamic_scale": 1.5}'

   # 保留输入的原始分辨率（跳过 512 最小值缩放）
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "keep_resolution": true}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `image`（正面人像效果最佳）和 `audio` 剪辑（WAV/MP3）
   - 可选地调整 `dynamic_scale`、`inference_steps`、`min_resolution` 或切换 `keep_resolution`
   - 点击 "Run Workflow" 按钮以接收 MP4

## 配置参考

### 组件字段

| 字段     | 说明                                                                                                | 默认值  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | 必须为 `talking-head`。                                                                             | —       |
| `driver` | 必须为 `custom`。                                                                                   | —       |
| `family` | Talking-head 模型系列。设为 `sonic`。                                                               | —       |
| `model`  | 检查点包。Hugging Face repo id（例如 `LeonJoe13/Sonic`）或本地目录。                                | —       |

### 动作字段

| 字段                        | 说明                                                                                                          | 默认值  |
|-----------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                     | 提供待动画化身份的源人像（或人像的列表/流）。                                                                 | —       |
| `audio`                     | 口型跟随的驱动音频剪辑（或剪辑列表）。                                                                        | —       |
| `params.dynamic_scale`      | 运动动态缩放；较大的值会产生更富表现力的头部和面部动作。                                                      | `1.0`   |
| `params.inference_steps`    | 扩散推理步骤数。                                                                                              | `25`    |
| `params.min_resolution`     | 渲染前人脸裁剪缩放到的最小短边分辨率。                                                                        | `512`   |
| `params.keep_resolution`    | 保留输入人像的原始分辨率，而不是缩放到 `min_resolution`。                                                     | `false` |
| `params.fps`                | 输出视频帧率。                                                                                                | `25`    |
| `batch_size`                | 当两个输入都是列表或流时，每批处理的 `(image, audio)` 对的数量。                                              | `1`     |
| `seed`                      | 用于可复现性的随机种子。留空则每次调用产生新样本。                                                            | （无）  |

## 备注

- **首次运行较慢**：控制器必须获取 Sonic 源码、安装其依赖并下载检查点包。后续运行会重用缓存的安装和模型文件。
- **长音频**：Sonic 的全局音频感知在超过一分钟的剪辑上依然良好扩展；每秒输出音频约需 0.5–1 秒 GPU 时间。
- **`dynamic_scale`**：提升到 1.0 以上会让头部/面部动作更戏剧化；过高的值（>1.7）可能看起来诡异。
- **`keep_resolution`**：保留源分辨率对高质量人像可以提高保真度，但会带来额外的延迟和 VRAM 消耗。
- **人脸检测失败**：如果源图像中未检测到人脸，工作流会抛出 "Sonic failed to render the talking-head video"。请使用更清晰、更大、正面朝向的人像。
- **管道搭配**：上游搭配 `text-to-speech`（将生成的语音作为 `audio` 传入），下游搭配 `image-upscale`，即可构建完全本地的文本到头像流水线。
