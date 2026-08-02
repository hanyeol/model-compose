# 视频超分辨率示例

此示例演示了一个工作流：使用超分辨率模型对视频的每一帧进行放大并重新组装 —— 同时保留原始音频轨。

## 概述

给定输入视频，工作流返回一个超分辨率版本的同一视频，并将原始音频轨重新混入。

策略如下：

1. 使用 `audio-extractor` 从输入视频中**分离音频轨**（保持不变）。
2. 使用 `video-frame-extractor` 将**每一帧提取为静止图像**。
3. **对每一帧**通过 `for-each` 作业运行 `image-upscale`（Real-ESRGAN x4）。
4. 使用 `video-encoder` 将**放大后的帧重新编码**为视频，并将提取的音频混入输出。

## 准备工作

### 前置条件

- 已安装 model-compose 并在 PATH 中可用
- 已安装 FFmpeg 并在 PATH 中可用
- Real-ESRGAN 推理所需的 Python 依赖：
  ```bash
  pip install torch torchvision realesrgan
  ```
- Real-ESRGAN 权重（`RealESRGAN_x4.pth`）将在首次运行时从 Hugging Face 上的 `ai-forever/Real-ESRGAN` 自动下载。

### 设置

1. 进入本示例目录：
   ```bash
   cd examples/showcase/upscale-video
   ```

2. 准备要放大的视频文件。建议使用短片 —— 逐帧超分辨率成本较高。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 上传视频，并可选覆盖 `frame_rate`
   - 点击"运行工作流"

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: multipart/form-data" \
     -F 'input={"frame_rate": 30};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **使用 CLI：**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "frame_rate": 30
   }'
   ```

## 组件详情

### 音频提取器 (`audio-extractor`)
- **类型**：`audio-extractor`
- **驱动**：`ffmpeg`
- **功能**：将输入视频的音频轨分离为独立的 mp3 文件。之后编码器会将其重新混入放大后的视频。

### 帧提取器 (`frame-extractor`)
- **类型**：`video-frame-extractor`
- **驱动**：`ffmpeg`
- **功能**：将视频解码为每一帧的列表（`frame_interval: 1`，含时间戳）。`streaming: false`，以便 `for-each` 作业可迭代实体化列表。

### 放大器 (`upscaler`)
- **类型**：`model` —— `image-upscale` 任务
- **驱动**：`custom`（Real-ESRGAN family）
- **模型**：来自 Hugging Face `ai-forever/Real-ESRGAN` 的 `RealESRGAN_x4.pth`
- **缩放**：4x
- **切片**：`tile_size: 256`、`tile_pad_size: 24`、`tile_batch_size: 4` —— 在高分辨率帧下将 VRAM 使用限制在合理范围。

### 编码器 (`encoder`)
- **类型**：`video-encoder`
- **驱动**：`ffmpeg`
- **功能**：将放大后的帧重新编码为 mp4（`libx264 @ 8M`）并混入提取的音频（`aac @ 192k`）。`frame_rate` 控制输出时序。

## 注意事项与调优

- **成本**：对每一帧运行 Real-ESRGAN x4 非常耗时。10 秒 30 fps 的片段 = 300 次模型调用。建议从短片开始。
- **帧率**：如果源与输出帧率不同，音频与视频将不同步。将源真实 fps 作为 `frame_rate` 传入（默认 `30` 是回退值）。
- **选择其他放大器**：将 `family: real-esrgan` 和模型文件替换为其他支持的 family（`esrgan`、`swinir`、`ldsr`）。每种 family 暴露各自的切片参数 —— 请参见 `image-upscale` 文档。
- **批处理**：`for-each` 作业默认按顺序运行帧。在 `for-each` 作业上设置 `batch_size` 可并发处理帧（受 GPU 内存限制）。
