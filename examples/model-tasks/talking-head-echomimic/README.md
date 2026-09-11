# Talking Head Model Task Example (EchoMimic)

This example demonstrates how to generate portrait (or half-body) talking-head videos from a still image and a driving audio clip using EchoMimic — Alibaba/Ant Group's diffusion-based pipeline — exposed through model-compose's built-in talking-head task.

## Overview

This workflow provides local talking-head generation that:

1. **Local EchoMimic Diffusion Pipeline**: Runs EchoMimic's `Audio2VideoPipeline` (v1, portrait) or `EchoMimicV2Pipeline` (v2, half-body) end-to-end without any external API
2. **Two Presets**: `v1` for portrait-only lip-sync with an audio-derived face mask; `v2` for half-body animation driven by an additional per-frame pose sequence (npy files)
3. **Context-Windowed Rendering**: `context_frames` / `context_overlap` control temporal window size and overlap for smooth motion across long audio
4. **Automatic Model Management**: Downloads the appropriate EchoMimic checkpoint bundle from Hugging Face on first run; upstream's `src/` layout is renamed in place so it can't collide with model-compose's own source tree

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A CUDA-capable GPU with **at least 16 GB VRAM** is recommended (24 GB for v2 half-body)
- A Python environment where torch/torchvision and the EchoMimic dependency chain (`diffusers`, `transformers`, `librosa`, `moviepy`, `insightface`, `av`, ...) can be installed — the first run installs them automatically into the sandbox venv

### Why Local Talking-Head

Unlike cloud talking-head services, running EchoMimic locally provides:

**Benefits of Local Processing:**
- **Privacy**: Portraits and voice recordings never leave the machine
- **Cost**: No per-second or per-render API fees
- **Offline**: Works without an internet connection after the initial checkpoint download
- **Pipeline Friendly**: Composes cleanly with other model-compose tasks for end-to-end avatar pipelines

**Trade-offs:**
- **Hardware Requirements**: Needs ~16 GB VRAM for v1, ~24 GB for v2; first run also downloads several GB of checkpoints
- **Not Real-Time**: 30-step diffusion loop means seconds of GPU time per second of output audio
- **License**: EchoMimic weights are released for **non-commercial research use only**

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/talking-head-echomimic
   ```

2. No additional environment configuration required — the EchoMimic checkpoint bundle (`BadToBest/EchoMimic` for v1, `BadToBest/EchoMimicV2` for v2) is downloaded from Hugging Face and cached automatically on first run.

3. This example runs the model worker in a dedicated **virtualenv** (`.venv/echomimic`) so EchoMimic's SD/diffusers pins don't clash with the controller's own site-packages. The venv is created on first run and reused afterwards.

4. **v2 only:** Half-body animation requires a directory of per-frame pose `.npy` files (produced by EchoMimic's `dwpose` preprocessor). Point `params.pose` at that directory.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will fetch the EchoMimic source, install its Python dependencies, and download the checkpoint bundle. Expect ten-plus minutes and multi-GB downloads before the controller reports ready.

2. **Run the workflow:**

   **Using API (v1 portrait):**
   ```bash
   # Minimal call — animate a portrait with a driving audio clip
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # Higher-resolution render
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "width": 768, "height": 768}'
   ```

   **Using API (v2 half-body):**
   ```bash
   # v2 requires a per-frame pose sequence directory
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "pose": "/path/to/pose_frames_dir"}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an `image` (a front-facing portrait works best) and an `audio` clip (WAV/MP3)
   - Optionally tune `width` / `height`, `inference_steps`, `cfg_scale`, or the context window
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field    | Description                                                                                             | Default |
|----------|---------------------------------------------------------------------------------------------------------|---------|
| `task`   | Must be `talking-head`.                                                                                 | —       |
| `driver` | Must be `custom`.                                                                                       | —       |
| `family` | Talking-head model family. Set to `echomimic`.                                                          | —       |
| `preset` | EchoMimic release: `v1` (portrait) or `v2` (half-body).                                                 | `v1`    |
| `model`  | Checkpoint bundle. A Hugging Face repo id (e.g. `BadToBest/EchoMimic`) or a local directory.            | —       |

### Action Fields

| Field                       | Description                                                                                                    | Default |
|-----------------------------|----------------------------------------------------------------------------------------------------------------|---------|
| `image`                     | Source portrait (or list/stream of portraits) providing the identity to animate.                               | —       |
| `audio`                     | Driving audio clip (or list of clips) whose speech the mouth follows.                                          | —       |
| `params.pose`               | (v2 only) Directory of per-frame `.npy` pose files driving half-body motion.                                   | (none)  |
| `params.width` / `height`   | Output frame width/height in pixels.                                                                           | `512`   |
| `params.inference_steps`    | Number of diffusion inference steps.                                                                           | `30`    |
| `params.cfg_scale`          | Classifier-free guidance scale.                                                                                | `2.5`   |
| `params.context_frames`     | Number of frames processed per temporal context window.                                                        | `12`    |
| `params.context_overlap`    | Frame overlap between consecutive temporal windows.                                                            | `3`     |
| `params.motion_sync`        | Enable motion-sync mode which extracts motion cues from the reference `pose` video.                            | `false` |
| `params.sample_rate`        | Audio sample rate the model expects; resampling is applied if the input differs.                               | `16000` |
| `params.fps`                | Output video frame rate.                                                                                       | `25`    |
| `batch_size`                | Number of `(image, audio)` pairs processed per batch when both inputs are lists or streams.                    | `1`     |
| `seed`                      | Random seed for reproducibility. Leave unset for a fresh sample each call.                                     | (none)  |

## Notes

- **First run is slow**: The controller has to fetch the EchoMimic source, install its dependencies, and download the checkpoint bundle. Subsequent runs reuse the cached install and model files.
- **v2 pose sequence**: v2 refuses to render without a `pose` directory. The upstream repo ships helper scripts under `dwpose_util/` to extract poses from a reference video.
- **Context window**: Larger `context_frames` gives smoother motion at higher VRAM cost; `context_overlap` around 25% of `context_frames` is a good default.
- **Preset switch**: Changing `preset` from `v1` to `v2` also requires changing the `model` repo id to `BadToBest/EchoMimicV2` (or the corresponding local snapshot).
- **Pipeline pairing**: Pair with `text-to-speech` upstream (feed generated speech as `audio`) and `image-upscale` downstream for a fully local text-to-avatar pipeline.
