# Lip Sync Model Task Example (LatentSync)

This example demonstrates how to re-sync a face video's mouth movements to a driving audio clip using LatentSync, exposed through model-compose's built-in lip-sync task.

## Overview

This workflow provides local lip-sync generation that:

1. **Local LatentSync Pipeline**: Runs the InsightFace + Whisper + Stable Diffusion VAE + UNet3D stack end-to-end without any external API
2. **Video-Driven Face Preservation**: Only the mouth region is regenerated; the rest of every frame (identity, expression, head pose, background) comes straight from the source video
3. **Two Release Variants**: `1.6` renders at 512×512 for the sharpest results; `1.5` renders at 256×256 for faster inference on lighter hardware
4. **Diffusion-Based Sampling**: 20–50 DDIM steps with classifier-free guidance produce cleaner mouth shapes than the classical Wav2Lip generator, at the cost of longer inference time
5. **Automatic Model Management**: Downloads the LatentSync UNet from `ByteDance/LatentSync-1.6` on first run; the VAE and InsightFace `buffalo_l` weights are auto-fetched on first pipeline load

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A CUDA-capable GPU with **at least 12 GB VRAM** is recommended for 1.6 at 512×512; 1.5 at 256×256 fits in ~6 GB
- A Python environment where `torch==2.5.1`, `diffusers==0.32.2`, `insightface`, and the rest of LatentSync's pinned dependency chain can be installed — the first run installs them automatically

### Why Local Lip-Sync

Unlike cloud lip-sync services, running LatentSync locally provides:

**Benefits of Local Processing:**
- **Privacy**: Face video and voice recordings never leave the machine
- **Cost**: No per-second or per-render API fees; the same clip can be re-driven cheaply
- **Offline**: Works without an internet connection after the initial checkpoint download
- **Quality**: LatentSync's diffusion-based generator produces sharper mouths than classical GAN-based lip-sync

**Trade-offs:**
- **Not Real-Time**: Diffusion sampling with 20+ steps is slower than one-shot GAN inference; expect several minutes per short clip on a mid-range GPU
- **VRAM**: 512×512 at float16 needs ~12 GB VRAM; drop to `preset: 1.5` for lighter hardware
- **License**: LatentSync weights are released under Apache 2.0, but review the model card for any usage restrictions

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/lip-sync-latentsync
   ```

2. No additional environment configuration required — the LatentSync UNet is downloaded from Hugging Face and cached automatically on first run. The VAE (`stabilityai/sd-vae-ft-mse`) and InsightFace `buffalo_l` face detector are downloaded on first pipeline load.

3. This example runs the model worker in a dedicated **virtualenv** (`.venv/latentsync`) so LatentSync's torch and diffusers pins don't clash with the controller's own site-packages.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will fetch the LatentSync source, install its Python dependencies, and download several checkpoints (LatentSync UNet ~5 GB, Whisper-tiny, VAE, InsightFace). Expect several minutes and multi-GB downloads before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — re-sync a video's lips to a new audio track
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "face=@/path/to/face.mp4" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"video": "@face", "audio": "@voice"}'

   # Higher-quality render with more denoising steps and stronger guidance
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "face=@/path/to/face.mp4" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"video": "@face", "audio": "@voice", "inference_steps": 50, "guidance_scale": 2.0}'

   # Faster preview with DeepCache enabled
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "face=@/path/to/face.mp4" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"video": "@face", "audio": "@voice", "enable_deepcache": true, "inference_steps": 20}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` (a clip with a clearly visible face works best) and an `audio` clip (WAV/MP3)
   - Optionally tune `inference_steps`, `guidance_scale`, toggle `enable_deepcache` or `use_float16`
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field    | Description                                                                                              | Default                       |
|----------|----------------------------------------------------------------------------------------------------------|-------------------------------|
| `task`   | Must be `lip-sync`.                                                                                      | —                             |
| `driver` | Must be `custom`.                                                                                        | —                             |
| `family` | Lip-sync model family. `wav2lip`, `latentsync`, or `musetalk`.                                           | —                             |
| `preset` | LatentSync release: `1.5` (256×256) or `1.6` (512×512).                                                  | `1.6`                         |
| `model`  | UNet snapshot. Leave unset to auto-fetch the preset's HuggingFace repo.                                  | `ByteDance/LatentSync-<preset>` |

### Action Fields

| Field                                | Description                                                                                                                            | Default           |
|--------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `video`                              | Source face video (or list/stream of videos) whose mouth region is re-synced.                                                          | —                 |
| `audio`                              | Driving audio clip (or list of clips) whose speech the mouth follows.                                                                  | —                 |
| `params.inference_steps`             | Number of DDIM denoising steps; upstream recommends 20–50.                                                                             | `20`              |
| `params.guidance_scale`              | Classifier-free guidance scale; upstream recommends 1.0–3.0.                                                                           | `1.5`             |
| `params.enable_deepcache`            | Enable DeepCache for a ~2x speedup at a small quality cost.                                                                            | `false`           |
| `params.use_float16`                 | Run the pipeline in float16 for a memory and latency win.                                                                              | `true`            |
| `params.fps`                         | Output video frame rate. Defaults to the source video's frame rate when unset.                                                         | (source fps)      |
| `batch_size`                         | Number of `(video, audio)` pairs processed per batch when both inputs are lists or streams.                                            | `1`               |
| `seed`                               | Random seed for reproducibility. Defaults to upstream's fixed seed (1247) when unset.                                                  | (none)            |

## Notes

- **First run is slow**: The controller has to fetch the LatentSync source, install its dependencies, and download several checkpoints (~5 GB LatentSync UNet, VAE, Whisper, InsightFace). Subsequent runs reuse the cached install and model files.
- **Face detection failures**: LatentSync uses InsightFace's `buffalo_l` for detection + landmark alignment. If no face is found, the pipeline raises. Use a clearer, larger, front-facing video.
- **Inference speed**: 512×512 at 20 steps takes ~2× longer than 256×256; DeepCache halves that at the cost of a small quality reduction. Expect several minutes per short clip on a mid-range GPU.
- **Guidance scale**: Higher values (2–3) produce more pronounced mouth movement but can look exaggerated; 1.5 is a balanced default.
- **v1.5 vs v1.6**: 1.6 is the current default with sharper 512×512 output. Use 1.5 when the source footage is 256p already or when VRAM is tight.
- **Pipeline pairing**: Pair with `text-to-speech` upstream (feed generated speech as `audio`) and `video-processor` downstream for a fully local voice-swap or dubbing pipeline.
