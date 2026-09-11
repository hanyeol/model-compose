# Talking Head 模型任务示例 (EchoMimic)

本示例演示如何通过 model-compose 内置的 talking-head 任务运行 EchoMimic（阿里巴巴/蚂蚁集团的扩散管道），从一张静态图像和驱动音频剪辑生成人像（或半身）talking-head 视频。

## 概述

此工作流提供本地 talking-head 生成功能：

1. **本地 EchoMimic 扩散流水线**：无需任何外部 API，在本地端到端运行 EchoMimic 的 `Audio2VideoPipeline`（v1，人像）或 `EchoMimicV2Pipeline`（v2，半身）
2. **两个预设**：`v1` 用于基于音频派生的人脸遮罩的仅人像口型同步；`v2` 用于由额外的逐帧姿态序列（npy 文件）驱动的半身动画
3. **上下文窗口渲染**：`context_frames` / `context_overlap` 控制时间窗口大小和重叠，以在长音频中实现平滑运动
4. **自动模型管理**：首次运行时从 Hugging Face 下载相应的 EchoMimic 检查点包；上游的 `src/` 布局在原位被重命名，避免与 model-compose 自身源码树冲突

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 推荐使用**至少 16 GB VRAM**（v2 半身需 24 GB）的 CUDA GPU
- 可安装 torch/torchvision 和 EchoMimic 依赖链（`diffusers`、`transformers`、`librosa`、`moviepy`、`insightface`、`av`……）的 Python 环境 — 首次运行时自动安装到沙箱 venv 中

### 为什么选择本地 talking-head

与云端 talking-head 服务不同，在本地运行 EchoMimic 提供：

**本地处理的优势：**
- **隐私**：人像和语音录音永远不会离开本机
- **成本**：无按秒或按渲染的 API 费用
- **离线**：初始检查点下载后无需互联网连接
- **管道友好**：与其他 model-compose 任务无缝组合，可构建端到端的头像流水线

**权衡：**
- **硬件要求**：v1 需要约 16 GB VRAM，v2 需要约 24 GB；首次运行还会下载数 GB 的检查点
- **非实时**：30 步扩散循环意味着每秒输出音频需要数秒 GPU 时间
- **许可证**：EchoMimic 权重仅**用于非商业研究**

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/talking-head-echomimic
   ```

2. 无需额外的环境配置 — EchoMimic 检查点包（v1 为 `BadToBest/EchoMimic`，v2 为 `BadToBest/EchoMimicV2`）在首次运行时从 Hugging Face 自动下载并缓存。

3. 本示例在专用的 **virtualenv**（`.venv/echomimic`）中运行模型工作进程，以隔离 EchoMimic 的 SD/diffusers 版本锁定，避免与控制器自身的 site-packages 冲突。venv 在首次运行时创建，之后重复使用。

4. **仅 v2：** 半身动画需要一个逐帧姿态 `.npy` 文件目录（由 EchoMimic 的 `dwpose` 预处理器生成）。将 `params.pose` 指向该目录。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会获取 EchoMimic 源码、安装其 Python 依赖并下载检查点包。请预留十多分钟时间和数 GB 的下载量，控制器才会报告就绪。

2. **运行工作流：**

   **使用 API (v1 人像)：**
   ```bash
   # 最小调用 — 用驱动音频剪辑动画化一张人像
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 更高分辨率的渲染
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "width": 768, "height": 768}'
   ```

   **使用 API (v2 半身)：**
   ```bash
   # v2 需要逐帧姿态序列目录
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "pose": "/path/to/pose_frames_dir"}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `image`（正面人像效果最佳）和 `audio` 剪辑（WAV/MP3）
   - 可选地调整 `width` / `height`、`inference_steps`、`cfg_scale` 或上下文窗口
   - 点击 "Run Workflow" 按钮以接收 MP4

## 配置参考

### 组件字段

| 字段     | 说明                                                                                                | 默认值  |
|----------|-----------------------------------------------------------------------------------------------------|---------|
| `task`   | 必须为 `talking-head`。                                                                             | —       |
| `driver` | 必须为 `custom`。                                                                                   | —       |
| `family` | Talking-head 模型系列。设为 `echomimic`。                                                           | —       |
| `preset` | EchoMimic 版本：`v1`（人像）或 `v2`（半身）。                                                       | `v1`    |
| `model`  | 检查点包。Hugging Face repo id（例如 `BadToBest/EchoMimic`）或本地目录。                            | —       |

### 动作字段

| 字段                        | 说明                                                                                                          | 默认值  |
|-----------------------------|---------------------------------------------------------------------------------------------------------------|---------|
| `image`                     | 提供待动画化身份的源人像（或人像的列表/流）。                                                                 | —       |
| `audio`                     | 口型跟随的驱动音频剪辑（或剪辑列表）。                                                                        | —       |
| `params.pose`               | （仅 v2）驱动半身运动的逐帧 `.npy` 姿态文件目录。                                                             | （无）  |
| `params.width` / `height`   | 输出帧的宽/高，单位像素。                                                                                     | `512`   |
| `params.inference_steps`    | 扩散推理步骤数。                                                                                              | `30`    |
| `params.cfg_scale`          | Classifier-free guidance 缩放。                                                                               | `2.5`   |
| `params.context_frames`     | 每个时间上下文窗口处理的帧数。                                                                                | `12`    |
| `params.context_overlap`    | 连续时间窗口之间的帧重叠。                                                                                    | `3`     |
| `params.motion_sync`        | 启用从参考 `pose` 视频提取运动线索的 motion-sync 模式。                                                       | `false` |
| `params.sample_rate`        | 模型期望的音频采样率；输入不同时会自动重采样。                                                                | `16000` |
| `params.fps`                | 输出视频帧率。                                                                                                | `25`    |
| `batch_size`                | 当两个输入都是列表或流时，每批处理的 `(image, audio)` 对的数量。                                              | `1`     |
| `seed`                      | 用于可复现性的随机种子。留空则每次调用产生新样本。                                                            | （无）  |

## 备注

- **首次运行较慢**：控制器必须获取 EchoMimic 源码、安装其依赖并下载检查点包。后续运行会重用缓存的安装和模型文件。
- **v2 姿态序列**：v2 没有 `pose` 目录就拒绝渲染。上游 repo 在 `dwpose_util/` 下提供了从参考视频提取姿态的辅助脚本。
- **上下文窗口**：更大的 `context_frames` 提供更平滑的运动，但 VRAM 成本增加；`context_overlap` 约为 `context_frames` 的 25% 是不错的默认值。
- **预设切换**：将 `preset` 从 `v1` 改为 `v2` 时，还需要将 `model` repo id 改为 `BadToBest/EchoMimicV2`（或对应的本地快照）。
- **管道搭配**：上游搭配 `text-to-speech`（将生成的语音作为 `audio` 传入），下游搭配 `image-upscale`，即可构建完全本地的文本到头像流水线。
