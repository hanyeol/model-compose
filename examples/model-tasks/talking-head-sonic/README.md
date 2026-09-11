# Talking Head Model Task Example (Sonic)

This example demonstrates how to generate portrait talking-head videos from a still image and a driving audio clip using Sonic (Tencent), exposed through model-compose's built-in talking-head task.

## Overview

This workflow provides local talking-head generation that:

1. **Local Sonic SVD Pipeline**: Runs Sonic's `Sonic.process()` end-to-end without any external API — SVD-XT backbone, whisper-tiny audio encoder, audio2token / audio2bucket motion predictors, and RIFE frame interpolation
2. **Global Audio Perception**: Sonic conditions on the whole audio clip up front, giving smoother multi-second motion than window-only baselines
3. **Fast Inference**: Only 25 diffusion steps by default; renders roughly 2–3× faster than heavier DiT-based baselines at comparable identity fidelity
4. **Automatic Model Management**: Downloads the Sonic checkpoint bundle (Sonic + SVD-XT + whisper-tiny + RIFE + yoloface) from Hugging Face on first run; upstream's `src/` layout is renamed in place so it can't collide with model-compose's own source tree

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A CUDA-capable GPU with **at least 16 GB VRAM** is recommended (SVD-XT is the memory floor)
- A Python environment where torch/torchvision and the Sonic dependency chain (`diffusers`, `transformers`, `librosa`, `moviepy`, `insightface`, `av`, ...) can be installed — the first run installs them automatically into the sandbox venv

### Why Local Talking-Head

Unlike cloud talking-head services, running Sonic locally provides:

**Benefits of Local Processing:**
- **Privacy**: Portraits and voice recordings never leave the machine
- **Cost**: No per-second or per-render API fees
- **Offline**: Works without an internet connection after the initial checkpoint download
- **Pipeline Friendly**: Composes cleanly with other model-compose tasks for end-to-end avatar pipelines

**Trade-offs:**
- **Hardware Requirements**: Needs ~16 GB VRAM; the first run also downloads several GB of checkpoints
- **Not Real-Time**: Faster than most competitors, but still ~0.5–1s of GPU time per second of output audio
- **License**: Sonic weights are released for **non-commercial research use only**

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/talking-head-sonic
   ```

2. No additional environment configuration required — the Sonic checkpoint bundle (`LeonJoe13/Sonic`) is downloaded from Hugging Face and cached automatically on first run.

3. This example runs the model worker in a dedicated **virtualenv** (`.venv/sonic`) so Sonic's SVD/diffusers pins don't clash with the controller's own site-packages. The venv is created on first run and reused afterwards.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will fetch the Sonic source, install its Python dependencies, and download the checkpoint bundle. Expect ten-plus minutes and multi-GB downloads before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — animate a portrait with a driving audio clip
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # More expressive motion via the dynamic scale multiplier
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "dynamic_scale": 1.5}'

   # Preserve the input's native resolution (skip the 512-min resize)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "keep_resolution": true}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an `image` (a front-facing portrait works best) and an `audio` clip (WAV/MP3)
   - Optionally tune `dynamic_scale`, `inference_steps`, `min_resolution`, or toggle `keep_resolution`
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field    | Description                                                                                          | Default |
|----------|------------------------------------------------------------------------------------------------------|---------|
| `task`   | Must be `talking-head`.                                                                              | —       |
| `driver` | Must be `custom`.                                                                                    | —       |
| `family` | Talking-head model family. Set to `sonic`.                                                           | —       |
| `model`  | Checkpoint bundle. A Hugging Face repo id (e.g. `LeonJoe13/Sonic`) or a local directory.             | —       |

### Action Fields

| Field                     | Description                                                                                                 | Default |
|---------------------------|-------------------------------------------------------------------------------------------------------------|---------|
| `image`                   | Source portrait (or list/stream of portraits) providing the identity to animate.                            | —       |
| `audio`                   | Driving audio clip (or list of clips) whose speech the mouth follows.                                       | —       |
| `params.dynamic_scale`    | Motion-dynamics scale; larger values produce more expressive head and facial motion.                        | `1.0`   |
| `params.inference_steps`  | Number of diffusion inference steps.                                                                        | `25`    |
| `params.min_resolution`   | Minimum short-side resolution the face crop is resized to before rendering.                                 | `512`   |
| `params.keep_resolution`  | Preserve the input portrait's original resolution instead of resizing to `min_resolution`.                  | `false` |
| `params.fps`              | Output video frame rate.                                                                                    | `25`    |
| `batch_size`              | Number of `(image, audio)` pairs processed per batch when both inputs are lists or streams.                 | `1`     |
| `seed`                    | Random seed for reproducibility. Leave unset for a fresh sample each call.                                  | (none)  |

## Notes

- **First run is slow**: The controller has to fetch the Sonic source, install its dependencies, and download the checkpoint bundle. Subsequent runs reuse the cached install and model files.
- **Long audio**: Sonic's global audio perception scales well past one-minute clips; expect roughly 0.5–1s of GPU time per second of output audio.
- **`dynamic_scale`**: Bumping above 1.0 makes head/facial motion more dramatic; excessive values (>1.7) can look uncanny.
- **`keep_resolution`**: Keeping the source resolution can improve fidelity for high-quality portraits at the cost of extra latency and VRAM.
- **Face detection failure**: If no face is detected in the source image, the workflow raises "Sonic failed to render the talking-head video". Use a clearer, larger, front-facing portrait.
- **Pipeline pairing**: Pair with `text-to-speech` upstream (feed generated speech as `audio`) and `image-upscale` downstream for a fully local text-to-avatar pipeline.
