# Talking Head 模型任务示例 (SadTalker)

本示例演示如何通过 model-compose 内置的 talking-head 任务运行 SadTalker，让一张静态人像与驱动音频进行口型同步（并带有自然的头部运动）。

## 概述

此工作流提供本地 talking-head 生成功能：

1. **本地 SadTalker 流水线**：无需任何外部 API，在本地端到端运行 SadTalker 的 Audio2Coeff + 人脸渲染器
2. **音频驱动口型同步**：直接从驱动音频预测头部姿态和表情系数，然后渲染出人像口部与面部跟随语音的视频
3. **自动人脸检测与裁剪**：检测并对齐源人像中的人脸；支持保留全画面背景或紧凑的人脸裁剪
4. **可选的人脸增强**：将 GFPGAN（或 RestoreFormer）作为逐帧人脸增强器运行，获得更清晰的面部
5. **自动模型管理**：首次运行时从 Hugging Face 下载 SadTalker 检查点包；流水线在原位被重命名并重写导入语句，避免上游 `src/` 布局与 model-compose 自身源码树冲突

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 强烈推荐支持 CUDA 的 GPU；对实际长度的音频而言，仅 CPU 运行速度慢到不切实际
- 可安装 torch/torchvision 和 SadTalker 依赖链（`librosa`、`numba`、`face-alignment`、`gfpgan`、`basicsr`、`facexlib`、`av`……）的 Python 环境 — 首次运行时自动安装

### 为什么选择本地 talking-head

与云端 talking-head 服务不同，在本地运行 SadTalker 提供：

**本地处理的优势：**
- **隐私**：人像和语音录音永远不会离开本机
- **成本**：无按秒或按渲染的 API 费用；同一张人像可以低成本地重新驱动
- **离线**：初始检查点下载后无需互联网连接
- **管道友好**：与其他 model-compose 任务（上游的 text-to-speech、下游的 image-upscale 等）无缝组合，可构建端到端的头像流水线

**权衡：**
- **硬件要求**：256 预设需要约 6 GB VRAM，512 预设需要约 12 GB VRAM。首次运行还会下载数 GB 的检查点
- **非实时**：SadTalker 需要消费整段音频以求解一致的头部姿态/表情序列 — 不支持流式输入
- **许可证**：SadTalker 权重仅**用于非商业研究**

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/talking-head-sadtalker
   ```

2. 无需额外的环境配置 — SadTalker 检查点包（`vinthony/SadTalker`）在首次运行时从 Hugging Face 自动下载并缓存。

3. 本示例在专用的 **virtualenv**（`.venv/sadtalker`）中运行模型工作进程，以隔离 SadTalker 陈旧的 numpy/numba/librosa 版本锁定，避免与控制器自身的 site-packages 冲突。venv 在首次运行时创建，之后重复使用。

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会获取 SadTalker 源码、安装其 Python 依赖并下载检查点包。请预留数分钟时间和数 GB 的下载量，控制器才会报告就绪。

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 最小调用 — 用驱动音频剪辑动画化一张人像
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # 全画面渲染，仅口部运动（推荐用于带身体/背景的照片）
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "preprocess": "full", "still": true}'

   # 更富表现力的面部动作，不使用 GFPGAN 增强器
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "expression_scale": 1.4, "enhancer": null}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传 `image`（正面人像效果最佳）和 `audio` 剪辑（WAV/MP3）
   - 可选地调整 `preprocess`、切换 `still`、选择 `enhancer`，或调节 `expression_scale` / `pose_style`
   - 点击 "Run Workflow" 按钮以接收 MP4

## 配置参考

### 组件字段

| 字段     | 说明                                                                                                | 默认值         |
|----------|-----------------------------------------------------------------------------------------------------|----------------|
| `task`   | 必须为 `talking-head`。                                                                             | —              |
| `driver` | 必须为 `custom`。                                                                                   | —              |
| `family` | Talking-head 模型系列。目前仅支持 `sadtalker`。                                                     | —              |
| `preset` | SadTalker 检查点变体：`v0.0.2-256`（256×256，更轻）或 `v0.0.2-512`（512×512，更清晰）。              | `v0.0.2-256`   |
| `model`  | 检查点包。Hugging Face repo id（例如 `vinthony/SadTalker`）或本地目录路径。                          | —              |

### 动作字段

| 字段                   | 说明                                                                                                          | 默认值        |
|------------------------|---------------------------------------------------------------------------------------------------------------|---------------|
| `image`                | 提供待动画化身份的源人像（或人像的列表/流）。                                                                 | —             |
| `audio`                | 口型跟随的驱动音频剪辑（或剪辑列表）。                                                                        | —             |
| `params.preprocess`    | 人脸预处理模式：`crop`、`extcrop`、`resize`、`full`、`extfull`。使用 `full` 保留整张照片。                    | `crop`        |
| `params.still`         | 保持头部静止（仅口部动）。`preprocess` 为 `full` 时推荐。                                                     | `false`       |
| `params.enhancer`      | 逐帧人脸增强器：`gfpgan` 或 `RestoreFormer`。留空则跳过增强器过程。                                           | （无）        |
| `params.background_enhancer` | 背景超分增强器：`realesrgan`。留空则跳过。                                                              | （无）        |
| `params.expression_scale`    | 应用于预测面部表情强度的乘数。较大的值看起来更夸张。                                                   | `1.0`         |
| `params.pose_style`    | `[0, 46]` 范围内的头部姿态样式索引。同一音频下不同值会采样不同的姿态模式。                                    | `0`           |
| `params.ref_eyeblink`  | 可选的参考视频，其眨眼动作将被转移到输出上。                                                                  | （无）        |
| `params.ref_pose`      | 可选的参考视频，其头部姿态动作将被转移到输出上。                                                              | （无）        |
| `params.input_yaw` / `input_pitch` / `input_roll` | 以度为单位的手动头部旋转关键帧（int 列表）。覆盖预测的旋转。                            | （无）        |
| `params.face3dvis`     | 除了输出外，另外渲染一个 3D 人脸调试视频。                                                                    | `false`       |
| `params.size`          | 人脸渲染器分辨率。应与加载的预设匹配（`v0.0.2-256` 对应 `256`，`v0.0.2-512` 对应 `512`）。                    | `256`         |
| `params.facerender_batch_size` | 人脸渲染器推理循环使用的批处理大小。                                                                   | `2`           |
| `params.fps`           | 输出视频帧率。SadTalker 渲染器内部目标为 25 fps。                                                             | `25`          |
| `batch_size`           | 当两个输入都是列表或流时，每批处理的 `(image, audio)` 对的数量。                                              | `1`           |
| `seed`                 | 用于可复现性的随机种子。留空则每次调用产生新样本。                                                            | （无）        |

## 备注

- **首次运行较慢**：控制器必须获取 SadTalker 源码、安装其依赖并下载检查点包。后续运行会重用缓存的安装和模型文件。
- **长音频**：生成时间随音频长度线性增长。考虑将长剪辑按段落切分，然后在下游拼接输出。
- **人脸检测失败**：如果源图像中未检测到人脸，工作流会抛出 "SadTalker failed to detect a face in the input image"。请使用更清晰、更大、正面朝向的人像。
- **全画面照片**：对于人物只占画面一部分的照片，使用 `preprocess: full` 配合 `still: true`，背景保持静止的同时口部在原位动画化。
- **增强器消耗时间**：GFPGAN 会显著增加每帧延迟。预览时关闭它，仅在最终渲染时启用。
- **管道搭配**：上游搭配 `text-to-speech`（将生成的语音作为 `audio` 传入），下游搭配 `image-upscale`，即可构建完全本地的文本到头像流水线。
