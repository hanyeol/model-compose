# 在 RunPod 上运行的文本到视频 (MiniMax-H3)

与 [text-to-video-minimax-h3](../text-to-video-minimax-h3/) 相同的工作流，但约 33B 参数的 MiniMax-H3 Omni-Transformer 运行在远程 [RunPod](https://www.runpod.io/) GPU 容器上，而非本地。声明式配置保持一致——只有 `component.runtime` 发生变化。

## 为什么用远程

- 检查点约 70 GB，模型 33B 参数。单张消费级 GPU 需要 `cpu_offload: true` 且速度较慢；H100 级硬件可从容运行，但自持并不现实。
- 在 RunPod 上，Pod 会在 `idle_timeout` 后停止，所以只在生成时付 GPU 费用。约 70 GB 的权重在停止/恢复期间会保留在网络卷上，因此一次性下载成本被摊销。

## 前置条件

1. 已设置计费的 [RunPod](https://www.runpod.io/) 账户。
2. 位于具备 H100 可用性的数据中心的 **网络卷**。100 GB 是实用的最小值：约 70 GB 权重加 pip 缓存。记录卷 ID。
3. [RunPod API 密钥](https://www.runpod.io/console/user/settings)。
4. [`MiniMaxAI/MiniMax-H3`](https://huggingface.co/MiniMaxAI/MiniMax-H3) 的 Hugging Face 访问权限。权重受 MiniMax H3 Community License 门控——在模型页面接受许可，并在 `.env` 中设置 `HF_TOKEN`（见下文）。

## 配置

在本目录创建 `.env` 文件（或在 shell 中导出变量）：

```bash
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_VOLUME_ID=your-volume-id
HF_TOKEN=your-huggingface-token
```

`HF_TOKEN` 由宿主机通过 `${env.HF_TOKEN}` 解析，并通过 compose 文件中的 `component.model.token` 传入 Pod。Pod 的模型 provisioner 使用它将受门控的权重下载到网络卷缓存中。宿主机环境变量 **不会** 自动转发进 Pod，因此宿主机上单独的 `HF_TOKEN` 不会到达 Pod 内部的 `huggingface_hub`。

## 试运行

```bash
model-compose up
model-compose run --input '{"prompt": "a quiet alleyway at dusk, warm neon reflections on wet pavement, slow dolly in"}'
```

首次 `model-compose up` 的流程：

1. 终止上一次会话的任何孤立 Pod。
2. 在持有你的网络卷的数据中心创建新的 H100 SXM Pod。在 Secure cloud 上通常需要 ~30–90 秒达到 `RUNNING`。
3. Pod 将 model-compose 安装到卷的 pip 缓存，并启动 WebSocket worker。
4. model-compose 使用每会话的 bearer token，通过 `wss://<pod_id>-8000.proxy.runpod.net` 建立连接。
5. 首次请求时，Hugging Face 分片（约 70 GB）会下载到网络卷（在 RunPod 网络上 15–30 分钟）并以 bfloat16 载入 VRAM（另 3–5 分钟）。compose 文件中的 `start_timeout: 60m` 是为覆盖整条链路而设——否则宿主机会半途放弃并停止 Pod。之后的恢复复用缓存分片，按秒计。

后续请求复用正在运行的 Pod。在最后一次请求 10 分钟后，Pod 会自动停止以暂停 GPU 计费。下一次请求会将其恢复。

## 成本概览

- H100 SXM Secure cloud：运行时约 $3.99/小时
- 100 GB 网络卷：约 $7/月
- 首次请求包含一次性约 70 GB 下载（在 RunPod 网络上按分钟计，不是小时）。后续请求只为生成本身付费。

## 更换 GPU

示例默认使用 H100 SXM，因为它可以在无 offload 情况下装下完整模型。两种替代方案：

- **更便宜的 H100.** 将 `gpu_type` 改为 `NVIDIA H100 PCIe` — 同为 80 GB，吞吐略低，时费更低。
- **24 GB 消费级 GPU.** 将 `gpu_type` 改为 `NVIDIA GeForce RTX 4090`，设置 `cloud_type: ALL`，并在 component 上设置 `cpu_offload: true`。Pod 通过 offload 装下模型，但每次生成会明显变慢。

## 清理

```bash
model-compose down
```

会终止 Pod。网络卷（以及缓存的约 70 GB 检查点）不受 model-compose 影响；不再需要时请在控制台手动删除。

如果希望跨重启保留 Pod，使用 `model-compose stop` 而不是 `down` — stop 保留 Pod 的 provisioned（仅暂停）状态，下一次 `start` 会在数秒内恢复。
