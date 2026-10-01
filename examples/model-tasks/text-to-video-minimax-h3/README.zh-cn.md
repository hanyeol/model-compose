# 文本到视频模型任务示例 (MiniMax-H3)

本示例演示如何使用 MiniMax-H3 的 Omni-Transformer 从文本提示生成一段带原生立体声音频的短片。它通过 model-compose 内置的 text-to-video 任务暴露。

## 概览

MiniMax-H3 将文本条件、音频轨和目标视频帧打包进一个序列，并在该序列上运行完整的 self-attention，在一次管线调用中联合生成 **视频 + 音频**。本示例将其组织为本地声明式工作流：

1. **本地扩散管线**：端到端运行 HuggingFace diffusers `MiniMaxH3ModularPipeline`——无外部 API。
2. **视频 + 音频联合生成**：每次生成返回 24 fps 视频轨和 32 kHz 立体声音频轨，两条轨道合并到同一个 mp4。
3. **可选 Sol-Attn 加速**：在 NVIDIA Blackwell 消费级 GPU (SM120) 上启用 `sol_attn` 时，主变换器块会走 Sol-Attn 编译后的 `flex_attention` 核，在长打包序列上比 SDPA 更快，同时保持最后几步去噪 dense 以保证质量。

## 准备

### 前置条件

- 已安装 model-compose 并位于 PATH。
- CUDA 支持的 GPU。Omni-Transformer 约 33B 参数——单张消费级 GPU 需要示例中设置的 `cpu_offload: true` 才能装下。H100 级硬件可无需 offload。
- 足够的磁盘空间存储检查点（基础 transformer、Qwen3-VL 文本编码器、VAE、音频 VAE 合计约 70 GB）。
- 可安装 `torch`、`diffusers (>= 0.36)`、`transformers (>= 4.45)`、`av` 的 Python 环境——首次运行自动安装。
- （可选）使用 Sol-Attn 需 compute capability 12.0 的 NVIDIA Blackwell 消费级 GPU（RTX 5090 / RTX PRO 6000）。启用 `sol_attn` 时示例自动安装 `mindor-sol-attn-blackwell` 核包；其他 GPU 透明回退至 dense attention。

### 模型访问

MiniMax-H3 权重位于 Hugging Face 的 `MiniMaxAI/MiniMax-H3`，受 MiniMax H3 Community License 门控。在模型的 Hugging Face 页面接受许可后，启动服务前运行 `hf auth login`（或导出 `HF_TOKEN`）。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次启动将从 Hugging Face 下载检查点（约 70 GB）。初次准备耗时较长；后续运行复用缓存分片。

2. **运行工作流：**
   ```bash
   # 最小调用——以默认值生成一段电影化短片。
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "a quiet alleyway at dusk, warm neon reflections on wet pavement, slow dolly in"}}'

   # 固定种子并请求更长的片段。
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "waves crashing on a rocky coast, overcast sky, slow-motion spray", "num_frames": 240, "seed": 42}}'
   ```

3. **打开 Web UI：**
   `http://localhost:8081` 提供 Gradio 表单来驱动同一工作流。

## 切换注意力后端

示例默认在 component 上使用 `backend: torch`，走 diffusers 的标准 SDPA / FlashAttention 调度。要在受支持的 Blackwell 主机启用 Sol-Attn，请在 component 指定后端：

```yaml
component:
  # ...
  family: minimax-h3
  backend: sol
```

Sol-Attn 可选调优位于 `action.params.sol_attn`：

```yaml
params:
  sol_attn:
    tau: 1.0
    thresh_type: diag
    dense_steps: 1
```

行为说明：

- `tau` 控制路由阈值尺度。更高则跳过更多 KV 块（更快，精度下降）；更低则接近 dense attention。
- `thresh_type: diag` 是更快的估计器；`exact` 更精确，开销稍大。
- `dense_steps` 让最后 N 步去噪走全量 dense attention。最后几步噪声最弱，稀疏近似误差最易被察觉，保留 1 步 dense 是一个廉价的质量保险。
- 在非 SM120 硬件上，processor 会记录警告并在每次 attention 调用时回退至 dense——无需改码即可可移植运行。
- 在 `backend: sol` 下省略 `sol_attn` 块也是有效的；上述默认值已经应用。

## 停止

```bash
model-compose down
```
