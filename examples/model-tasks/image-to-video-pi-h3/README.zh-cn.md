# 图像到视频模型任务示例 (pi-H3)

本示例使用 **pi-H3**（LakonLab 发布的 MiniMax-H3 2/4 步蒸馏模型）将静态图像动画化为带原生立体声的短片。提供首帧图像、可选的末帧图像（fl2va 关键帧插值），以及描述运动的提示词。它通过 model-compose 内置的 image-to-video 任务暴露。

## 概览

pi-H3 将 pi-Flow v2 少步采样与 DWD（Decoding Without a Decoder）结合，让最后一步去噪直接预测像素。image-to-video 模式下，驱动把管线工作流固定为 `fl2va`，仅拉取关键帧 transformer 分区，并接受两类输入：

- `image` —— 首帧条件（必需）
- `last_image` —— 末帧关键帧（可选）；指定时在两帧之间进行平滑插值

其余与 text-to-video 示例相同：修剪基模 + LakonLab 适配器 + 可选 FP8，`num_inference_steps` 固定为 `step_count`，`num_frames` 吸附到最近的 `17*n + 5`。

## 准备

### 前置条件

- PATH 中的 `model-compose`
- 支持 CUDA 的 GPU。消费级（24 GB）保持 `cpu_offload: true`（已设置）；Blackwell 级（B200 / H200）可关闭并启用 `quantization: {type: fp8}`。
- 修剪基模检查点约 ~45 GB + pi-H3 适配器约 ~1 GB 磁盘空间。
- 可安装 `torch`、`diffusers==0.40.0`、`peft==0.20.0`、`transformers (>= 4.45)`、`mmcv==1.6.1`、`av` 的 Python 环境。驱动在首次运行时会把它们装入 `.venv/pi-h3`；LakonLab（`v0.3.0`）本身因未发布到 PyPI，由驱动从 GitHub 拉取。
- 用于构建 `mmcv==1.6.1` 的 C/C++ 工具链（Debian/Ubuntu 使用 `build-essential`，macOS 使用 Xcode CLT）。mmcv 1.x 属 PEP 517 之前的包，驱动以 `--no-build-isolation` 方式构建，复用 venv 里的 torch。

### 模型访问

- **基础模型**：Hugging Face 的 `multimodalart/MiniMax-H3-Pruned`。受 MiniMax H3 Community License 门控——在启动服务前接受许可并运行 `hf auth login`（或导出 `HF_TOKEN`）。
- **Distillation 适配器**：Hugging Face 的 `Lakonik/pi-H3`。作为 "Model Derivatives of MiniMax H3" 分发，适用同一社区许可。可通过 `distillation` 字段固定 revision 或指向本地快照路径。

## 适配器变体

与 text-to-video 示例使用同一矩阵——驱动根据 `step_count` 和 `dwd` 自动选择子文件夹：

| `step_count` | `dwd`   | 加载子文件夹                   | 输出路径                       |
| :----------- | :------ | :---------------------------- | :----------------------------- |
| `2`          | `true`  | `pi_h3_2step_dwd_adapter`     | 最后一步直接输出像素            |
| `4`          | `true`  | `pi_h3_4step_dwd_adapter`     | 最后一步直接输出像素            |
| `2`          | `false` | `pi_h3_2step_adapter`         | 标准视频 VAE 解码              |
| `4`          | `false` | `pi_h3_4step_adapter`         | 标准视频 VAE 解码              |

**4 步 DWD** 变体是推荐默认。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动会下载修剪基模（~45 GB）与 pi-H3 适配器。后续运行复用已缓存的分片。

2. **运行工作流 —— 仅首帧：**
   ```bash
   # 以提示词驱动运动的静帧动画化。
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"image": "https://example.com/first.jpg", "prompt": "camera slowly dollies in, leaves rustle in the wind"}}'
   ```

3. **运行工作流 —— 首帧 + 末帧（关键帧插值）：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"image": "https://example.com/first.jpg", "last_image": "https://example.com/last.jpg", "prompt": "smooth transition, locked-off camera"}}'
   ```

4. **打开 Web UI：**
   `http://localhost:8081` 打开 Gradio 表单，驱动同一工作流。

## 调优说明

- **不存在 `guidance_scale` 与 `negative_prompt`。** pi-H3 为少步蒸馏，无 CFG。
- **不要在 `peft_adapter` 下叠加用户 LoRA。** 蒸馏适配器已占用 LoRA 槽；Schema 会拒绝。
- **`width`/`height` 未设置时默认取输入图像的尺寸。** 若需上/下采样而无需重作图，才需显式设定。
- **`quantization: {type: fp8}` 需要 Blackwell 级硬件**（B200 / H200）。否则请不要设置 `quantization`。
- **`num_frames` 会向上吸附到视频 VAE 可解码的最近 `17*n + 5`（124–345）。**

## 关闭

```bash
model-compose down
```
