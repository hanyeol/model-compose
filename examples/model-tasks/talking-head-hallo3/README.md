# Talking Head Model Task Example (Hallo3)

This example demonstrates how to generate DiT-based talking-head videos from a still portrait, driving audio, and an optional text prompt using Hallo3 (built on top of CogVideoX-5B), exposed through model-compose's built-in talking-head task.

## Overview

This workflow provides local talking-head generation that:

1. **Local Hallo3 DiT Pipeline**: Runs Hallo3's CogVideoX-based `SATVideoDiffusionEngine` end-to-end without any external API
2. **Text-Guided Motion**: An optional `prompt` conditions the T5-xxl text encoder alongside the driving audio, letting you steer scene, style, or motion (e.g. "cinematic close-up, warm lighting")
3. **Sliding-Window Long Video**: Hallo3 stitches DiT windows together internally so audio longer than one window renders as a coherent single output
4. **Automatic Model Management**: Downloads the Hallo3 checkpoint bundle from Hugging Face on first run; the pipeline resolves its config-relative paths from the installed repo root

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A CUDA-capable GPU with **at least 24 GB VRAM** is strongly recommended; CogVideoX-5B is the heaviest talking-head backbone in this collection
- A Python environment where torch/torchvision and the Hallo3 dependency chain (`diffusers`, `transformers`, `sat`, `sentencepiece`, `librosa`, `audio-separator`, `insightface`, `moviepy`, `av`, ...) can be installed — the first run installs them automatically into the sandbox venv

### Why Local Talking-Head

Unlike cloud talking-head services, running Hallo3 locally provides:

**Benefits of Local Processing:**
- **Privacy**: Portraits and voice recordings never leave the machine
- **Cost**: No per-second or per-render API fees; the same portrait can be re-driven cheaply
- **Offline**: Works without an internet connection after the initial checkpoint download
- **Pipeline Friendly**: Composes cleanly with other model-compose tasks (text-to-speech upstream, image-upscale downstream, etc.) for end-to-end avatar pipelines

**Trade-offs:**
- **Hardware Requirements**: Needs ~24 GB VRAM at the default resolution; the first run also downloads ~15 GB of CogVideoX weights
- **Not Real-Time**: A 50-step DiT loop over CogVideoX-5B means very high per-second latency, even on H100-class hardware
- **License**: Hallo3 weights are released for **non-commercial research use only**

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/talking-head-hallo3
   ```

2. No additional environment configuration required — the Hallo3 checkpoint bundle (`fudan-generative-ai/hallo3`) is downloaded from Hugging Face and cached automatically on first run.

3. This example runs the model worker in a dedicated **virtualenv** (`.venv/hallo3`) so Hallo3's CogVideoX SAT toolkit and transformers pins don't clash with the controller's own site-packages. The venv is created on first run and reused afterwards.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will fetch the Hallo3 source, install its Python dependencies, and download the CogVideoX-5B checkpoint bundle. Expect 20+ minutes and ~15 GB of downloads before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — audio-driven only
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # Guide the scene with a text prompt
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "prompt": "cinematic close-up, warm evening lighting, subtle head movement"}'

   # Faster preview with fewer DiT steps
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "inference_steps": 25}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an `image` (a front-facing portrait works best) and an `audio` clip (WAV/MP3)
   - Optionally add a `prompt`, or tune `inference_steps`, `guidance_scale`, `audio_guidance_scale`, or `resolution`
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field    | Description                                                                                          | Default |
|----------|------------------------------------------------------------------------------------------------------|---------|
| `task`   | Must be `talking-head`.                                                                              | —       |
| `driver` | Must be `custom`.                                                                                    | —       |
| `family` | Talking-head model family. Set to `hallo3`.                                                          | —       |
| `model`  | Checkpoint bundle. A Hugging Face repo id (e.g. `fudan-generative-ai/hallo3`) or a local directory.  | —       |

### Action Fields

| Field                          | Description                                                                                                    | Default |
|--------------------------------|----------------------------------------------------------------------------------------------------------------|---------|
| `image`                        | Source portrait (or list/stream of portraits) providing the identity to animate.                               | —       |
| `audio`                        | Driving audio clip (or list of clips) whose speech the mouth follows.                                          | —       |
| `params.prompt`                | Optional text prompt guiding scene, style, or motion via the T5-xxl text encoder.                              | (empty) |
| `params.negative_prompt`       | Text describing content to avoid.                                                                              | (none)  |
| `params.inference_steps`       | Number of DiT inference steps.                                                                                 | `50`    |
| `params.guidance_scale`        | Classifier-free guidance scale for text conditioning.                                                          | `6.0`   |
| `params.audio_guidance_scale`  | Guidance scale applied to the audio conditioning branch.                                                       | `3.0`   |
| `params.resolution`            | Output frame resolution (short-side length in pixels).                                                         | `480`   |
| `params.num_frames`            | Number of frames generated per DiT window.                                                                     | `97`    |
| `params.shift`                 | Flow-matching timestep shift applied to the scheduler.                                                         | `5.0`   |
| `params.long_video`            | Enable long-video mode (window-and-blend) for audio longer than one DiT window.                                | `true`  |
| `params.fps`                   | Output video frame rate.                                                                                       | `25`    |
| `batch_size`                   | Number of `(image, audio)` pairs processed per batch when both inputs are lists or streams.                    | `1`     |
| `seed`                         | Random seed for reproducibility. Leave unset for a fresh sample each call.                                     | (none)  |

## Notes

- **First run is slow**: The controller has to fetch the Hallo3 source, install its dependencies, and download the CogVideoX-5B checkpoints. Subsequent runs reuse the cached install and model files.
- **Long audio**: Generation time scales linearly with audio length; on a single 24 GB GPU expect roughly 3–5 minutes per second of output audio.
- **Prompt tuning**: The T5-xxl text encoder is powerful but sensitive — start with short cinematic descriptors ("cinematic portrait, soft key light") and iterate. Very long prompts (>226 tokens) are truncated.
- **`long_video`**: Leave this on for anything longer than one DiT window (~4 seconds at default settings). Turning it off will crop audio to a single window.
- **`resolution`**: Bumping to 720 substantially increases VRAM and latency; the default `480` is a good preview/production balance on a 24 GB GPU.
- **Pipeline pairing**: Pair with `text-to-speech` upstream (feed generated speech as `audio`) and `image-upscale` downstream for a fully local text-to-avatar pipeline.
