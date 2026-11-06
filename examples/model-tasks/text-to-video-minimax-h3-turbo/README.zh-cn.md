# 文本到视频模型任务示例 (MiniMax-H3 + LightX2V Turbo LoRA)

本示例与 text-to-video-minimax-h3 工作流相同，但在基础 MiniMax-H3 Omni-Transformer 之上叠加 LightX2V/ModelTC Turbo LoRA，以少量步数完成生成。它通过 model-compose 内置的 text-to-video 任务暴露。

## 概览

MiniMax-H3 不发布 few-step 检查点，其公开权重已为 CFG-distilled，因此 `guidance_scale` 实际上无影响。LightX2V Turbo LoRA 是社区最广泛使用的 step-distilled 方案——无需重新训练基模，即可将默认 50 调度器步数降至 4 或 8 次模型评估。本示例以声明式方式组织这一配置：

1. **复用基础管线**：加载与原示例相同的 `MiniMaxH3ModularPipeline`，仅 LoRA 和 step/shift 设置不同。
2. **附加 Turbo LoRA**：示例通过 `peft_adapter` 声明 LoRA，驱动在加载阶段从 Hugging Face 下载并将其附加到基础 transformer 之上——无需额外的转换步骤。
3. **匹配 LoRA 的 Scheduler Shift**：768p Turbo 文件以 **video shift 6** 训练，不是调度器默认的 12。示例设置 `video_shift: 6`，使调度落在 LoRA 期望的 sigma 上。

## 准备

### 前置条件

与基础 MiniMax-H3 示例一致：PATH 中的 model-compose、支持 CUDA 的 GPU（消费级需 `cpu_offload: true`，已设置）、约 70 GB 磁盘空间用于基础检查点加数百 MB 用于 LoRA，以及可安装 `torch`、`diffusers (>= 0.36)`、`transformers (>= 4.45)`、`av` 的 Python 环境。

### 模型访问

- **基础模型**：Hugging Face 的 `MiniMaxAI/MiniMax-H3` 受 MiniMax H3 Community License 门控。在模型的 Hugging Face 页面接受许可后，启动服务前运行 `hf auth login`（或导出 `HF_TOKEN`）。
- **Turbo LoRA**：Hugging Face 的 `lightx2v/Minimax-h3-Turbo`。该仓库将多个变体打包在一起——参见下表。

## LoRA 变体

上游仓库包含五个 LoRA 文件。将文件与正确的 `video_shift` 和 `inference_steps` 配对非常关键：把 768p 文件与默认调度器 shift 搭配会使调度错位，运动质量明显下降。参考 [ModelTC/Minimax-H3-Turbo 模型规格](https://github.com/ModelTC/Minimax-H3-Turbo#1-model-specs)：

| 文件名                                                   | 任务        | 训练 video_shift | NFE | `inference_steps` |
| ------------------------------------------------------- | ---------- | ---------------: | --: | ----------------: |
| `minimax_h3_fl2v_turbo_4step_v0.1.safetensors`          | T2VA/FL2VA |               12 |   4 |                 5 |
| `minimax_h3_fl2v_turbo_8step_v1.0_bf16.safetensors`     | T2VA/FL2VA |               12 |   8 |                 9 |
| `minimax_h3_fl2v_turbo_4step_v1.0_768p_bf16.safetensors`| T2VA/FL2VA |                6 |   4 |                 5 |
| `minimax_h3_fl2v_turbo_8step_v1.0_768p_bf16.safetensors`| T2VA/FL2VA |                6 |   8 |                 9 |
| `minimax_h3_ref2v_turbo_4step_v0.1_bf16.safetensors`    | Ref2VA     |               12 |   4 |                 5 |

说明：

- 示例选用 **8-step 768p** 文件（`minimax_h3_fl2v_turbo_8step_v1.0_768p_bf16.safetensors`）作为均衡的默认。切换时请同时修改 `peft_adapter[0].model.filename`、`inference_steps` 和 `video_shift`——上表每一行是一个整体包。
- **`inference_steps` 为 NFE + 1**，因为 MiniMax-H3 调度器按包含终点 0 的 sigma 网格点数来计数。将 "8-step" 文件以 `inference_steps: 8` 传入会得到 7 次评估，而非 8 次。
- `audio_shift: 3` 对上表所有行通用——音频调度器在所有 Turbo 变体中均以 shift 3 训练。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动将下载基础检查点（约 70 GB）加 LoRA（数百 MB）。后续运行复用缓存分片。

2. **运行工作流：**
   ```bash
   # 最小调用——Turbo LoRA + shift 已在示例中接线完毕。
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "a quiet alleyway at dusk, warm neon reflections on wet pavement, slow dolly in"}}'

   # 固定种子并请求更长的片段。
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "waves crashing on a rocky coast, overcast sky, slow-motion spray", "num_frames": 192, "seed": 42}}'
   ```

3. **打开 Web UI：**
   `http://localhost:8081` 提供 Gradio 表单来驱动同一工作流。

## 调优说明

- **不要把 `guidance_scale` 调到 1.0 以上。** MiniMax-H3 权重是 CFG-distilled 的；更高的值不会改善提示贴合度，反而会破坏 Turbo LoRA 期望的 single-forward 调度。
- **让 `inference_steps` 匹配文件。** 4-step 文件需要 `inference_steps: 5`，8-step 文件需要 `inference_steps: 9`。超过训练预算增加步数并不会提升质量——LoRA 是按固定 NFE 蒸馏的。
- **不设置 `video_shift` / `audio_shift` 则保持调度器默认值（12 / 3）。** 不使用 Turbo LoRA 跑基础模型时，省略这些键（或设为 `null`）即可；默认值是面向未蒸馏的 50 步配方。

## 停止

```bash
model-compose down
```
