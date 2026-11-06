# Image-to-Video on RunPod (MiniMax-H3)

Animate a still image into a short video with the ~33B-parameter MiniMax-H3 Omni-Transformer, running on a remote [RunPod](https://www.runpod.io/) GPU pod. Supply a first-frame image and a motion prompt; optionally pass a closing keyframe (`last_image`) and MiniMax-H3's `fl2va` workflow will interpolate smoothly between the two.

## Why remote

- The checkpoint is ~70 GB and the model is 33B parameters. A single consumer GPU needs `cpu_offload: true` and is slow; H100-class hardware runs it comfortably but is impractical to own.
- On RunPod the pod stops after `idle_timeout`, so you pay for GPU time only while generating. The ~70 GB weights persist on the network volume across stop/resume, so the one-time download is amortized.

## Prerequisites

1. A [RunPod](https://www.runpod.io/) account with billing set up.
2. A **network volume** in a data center that has H100 availability. 100 GB is the practical minimum: ~70 GB of weights plus the pip cache. Note the volume ID.
3. Your [RunPod API key](https://www.runpod.io/console/user/settings).
4. Hugging Face access to [`MiniMaxAI/MiniMax-H3`](https://huggingface.co/MiniMaxAI/MiniMax-H3). The weights are gated by the MiniMax H3 Community License — accept the license on the model page and set `HF_TOKEN` in your `.env` (see below).

## Setup

Create a `.env` file in this directory (or export the variables in your shell):

```bash
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_VOLUME_ID=your-volume-id
HF_TOKEN=your-huggingface-token
```

`HF_TOKEN` is resolved on the host via `${env.HF_TOKEN}` and passed into the pod through `component.model.token` in the compose file. The pod's model provisioner then uses it to download the gated weights into the network-volume cache. Host env vars are **not** auto-forwarded into the pod, so a bare `HF_TOKEN` on the host would not reach `huggingface_hub` inside the pod.

## Try it

```bash
model-compose up
model-compose run --input '{
  "image": "https://example.com/first-frame.jpg",
  "prompt": "a gentle breeze rustles the leaves, camera slowly pushes in"
}'
```

First/last-frame interpolation (fl2va):

```bash
model-compose run --input '{
  "image": "https://example.com/start.jpg",
  "last_image": "https://example.com/end.jpg",
  "prompt": "smooth transition from day to dusk"
}'
```

What `model-compose up` does on the very first launch:

1. Terminates any orphan pod from a previous session.
2. Creates a new H100 SXM pod in the data center that holds your network volume. Expect ~30–90 s to reach `RUNNING` on Secure cloud.
3. The pod installs model-compose into the volume's pip cache and starts a WebSocket worker.
4. model-compose connects over `wss://<pod_id>-8000.proxy.runpod.net` with a per-session bearer token.
5. On the first request, the Hugging Face shards (~70 GB) are downloaded onto the network volume (15–30 min on RunPod's network) and loaded into VRAM in bfloat16 (another 3–5 min). `start_timeout: 45m` in the compose file is sized to cover this whole chain — the host would otherwise give up partway and stop the pod. Later resumes reuse the cached shards and are measured in seconds.

Subsequent requests just reuse the running pod. Ten minutes after the last request the pod is stopped automatically, pausing GPU billing. The next request resumes it.

## Cost sketch

- H100 SXM Secure cloud: ~$3.99 / hour while running
- 100 GB network volume: ~$7 / month
- The first request includes a one-time ~70 GB download (minutes, not hours, on RunPod's network). Later requests pay only for the generation itself.

## Switching GPUs

The example defaults to H100 SXM because it fits the full model without offload. Two alternatives:

- **Cheaper H100.** Change `gpu_type` to `NVIDIA H100 PCIe` — same 80 GB, slightly lower throughput, lower hourly rate.
- **24 GB consumer GPU.** Change `gpu_type` to `NVIDIA GeForce RTX 4090`, set `cloud_type: ALL`, and set `cpu_offload: true` on the component. The pod will fit the model via offload but each generation is noticeably slower.

## Clean up

```bash
model-compose down
```

terminates the pod. The network volume (and the cached ~70 GB checkpoint) is never touched by model-compose; delete it manually from the dashboard when you no longer need it.

If you want to keep the pod across restarts, run `model-compose stop` instead of `down` — stop keeps the pod provisioned (just paused), so the next `start` resumes it in seconds.
