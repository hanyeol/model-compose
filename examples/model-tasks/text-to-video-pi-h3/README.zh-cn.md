# 文本到视频模型任务示例 (pi-H3)

本示例运行 **pi-H3**——LakonLab 发布的 MiniMax-H3 2/4 步蒸馏模型。它将 pi-Flow v2 少步采样与 DWD（Decoding Without a Decoder）结合，让最后一步直接预测像素，跳过视频 VAE。它通过 model-compose 内置的 text-to-video 任务暴露。

## 概览

MiniMax-H3 的公开权重已经过 CFG 蒸馏，因此社区压缩步数的路径通常是蒸馏适配器。LightX2V Turbo LoRA 把基模从 50 步压到 4–8 步，而 pi-H3 更进一步：

1. **2 或 4 调度器步数**（步数烘焙进适配器）。
2. **DWD**：最后一步去噪直接预测像素，视频 VAE 解码器从管线中移除。
3. **修剪过的基模**：在 `multimodalart/MiniMax-H3-Pruned` 上运行，而非完整 70 GB 版本。

驱动通过 diffusers 的 `ModularPipeline` 加载修剪基模，然后调用 LakonLab 的 adapter 加载器注入 DWD 头和蒸馏权重。推理使用标准管线调用，`num_inference_steps` 固定为 `step_count`。

## 准备

### 前置条件

- PATH 中的 `model-compose`
- 支持 CUDA 的 GPU。消费级（24 GB）保持 `cpu_offload: true`（已设置）；Blackwell 级（B200 / H200）可关闭并启用 `quantization: {type: fp8}`。
- 修剪基模检查点约 ~45 GB 磁盘 + pi-H3 适配器约 ~1 GB。
- 可安装 `torch`、`diffusers (>= 0.36)`、`transformers (>= 4.45)`、`lakonlab (>= 0.3)`、`av` 的 Python 环境。驱动将其列入 setup requirements，首次运行时 model-compose 会安装到 `.venv/pi-h3`。

### 模型访问

- **基础模型**：Hugging Face 的 `multimodalart/MiniMax-H3-Pruned`。受 MiniMax H3 Community License 门控——在启动服务前接受许可并运行 `hf auth login`（或导出 `HF_TOKEN`）。
- **pi-H3 适配器**：Hugging Face 的 `Lakonik/pi-H3`。作为 "Model Derivatives of MiniMax H3" 分发，适用同一社区许可。

## 适配器变体

驱动根据 `step_count` 和 `dwd` 自动选择子文件夹：

| `step_count` | `dwd`   | 加载子文件夹                   | 输出路径                       |
| :----------- | :------ | :---------------------------- | :----------------------------- |
| `2`          | `true`  | `pi_h3_2step_dwd_adapter`     | 最后一步直接输出像素            |
| `4`          | `true`  | `pi_h3_4step_dwd_adapter`     | 最后一步直接输出像素            |
| `2`          | `false` | `pi_h3_2step_adapter`         | 标准视频 VAE 解码              |
| `4`          | `false` | `pi_h3_4step_adapter`         | 标准视频 VAE 解码              |

**4 步 DWD** 变体是推荐默认——在 B200 上几秒内完成 5 秒片段，同时运动与纹理保真度最接近 50 步基模。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会下载修剪基模（~45 GB）与 pi-H3 适配器。后续运行复用已缓存的分片。

2. **运行工作流：**
   ```bash
   # 最小调用——step_count、DWD 与 scheduler shift 已在示例中配好。
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "a quiet alleyway at dusk, warm neon reflections on wet pavement, slow dolly in"}}'

   # 固定种子并请求更长片段。
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "waves crashing on a rocky coast, overcast sky, slow-motion spray", "num_frames": 192, "seed": 42}}'
   ```

3. **打开 Web UI：**
   `http://localhost:8081` 打开 Gradio 表单，驱动同一工作流。

## 调优说明

- **不存在 `guidance_scale` 与 `negative_prompt`。** pi-H3 是少步蒸馏适配器，每步单向前传，不应用 CFG。Schema 有意省略这两个字段。
- **不要在 `peft_adapter` 下叠加用户 LoRA。** 蒸馏适配器已占用 LoRA 槽；再叠加会破坏其调过的少步轨迹。Schema 拒绝该字段。
- **`quantization: {type: fp8}` 需要 Blackwell 级硬件**（B200 / H200）。在 SM89 及以下 LakonLab FP8 内核会回退到慢速路径或加载失败——未验证主机时请不要设置 `quantization`。
- **不设置 `video_shift` / `audio_shift` 时保持调度器默认值**（12 / 3）。DWD 适配器针对这些默认值调过；仅在匹配 LakonLab 发布的特定配方时覆盖。
- **`num_frames` 会向上吸附到视频 VAE 可解码的最近 `17*n + 5` 值**（124–345）。低于 124 的请求会上舍入，高于 345 的请求会报错。

## 关闭

```bash
model-compose down
```
