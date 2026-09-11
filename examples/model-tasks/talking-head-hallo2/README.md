# Talking Head Model Task Example (Hallo2)

This example demonstrates how to generate high-resolution, long-form talking-head videos from a still portrait and a driving audio clip using Hallo2, exposed through model-compose's built-in talking-head task.

## Overview

This workflow provides local talking-head generation that:

1. **Local Hallo2 Diffusion Pipeline**: Runs Hallo2's `FaceAnimatePipeline` (reference UNet + denoising UNet + face locator + motion module) end-to-end without any external API
2. **Long-Form Audio Support**: Hallo2 chunks long audio into 60-second segments, animates each, and stitches them into a single output via its built-in `merge_videos` step — usable for multi-minute clips
3. **Motion-Weighted Conditioning**: Separate `pose_weight` / `face_weight` / `lip_weight` scales let you tune how strongly the driving audio's implied motion overrides the source portrait's static pose
4. **Automatic Model Management**: Downloads the Hallo2 checkpoint bundle from Hugging Face on first run; SadTalker-style rewrites are unnecessary here since Hallo2 already ships a clean `hallo/` package layout

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A CUDA-capable GPU is strongly recommended; the 40-step diffusion loop is impractically slow on CPU
- A Python environment where torch/torchvision and the Hallo2 dependency chain (`diffusers`, `transformers`, `librosa`, `audio-separator`, `insightface`, `moviepy`, `av`, ...) can be installed — the first run installs them automatically into the sandbox venv

### Why Local Talking-Head

Unlike cloud talking-head services, running Hallo2 locally provides:

**Benefits of Local Processing:**
- **Privacy**: Portraits and voice recordings never leave the machine
- **Cost**: No per-second or per-render API fees; the same portrait can be re-driven cheaply
- **Offline**: Works without an internet connection after the initial checkpoint download
- **Pipeline Friendly**: Composes cleanly with other model-compose tasks (text-to-speech upstream, image-upscale downstream, etc.) for end-to-end avatar pipelines

**Trade-offs:**
- **Hardware Requirements**: Needs ~12 GB VRAM at the default resolution; the first run also downloads several GB of checkpoints
- **Not Real-Time**: The diffusion loop plus segment stitching means multi-second latency per second of output audio, even on high-end GPUs
- **License**: Hallo2 weights are released for **non-commercial research use only**

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/talking-head-hallo2
   ```

2. No additional environment configuration required — the Hallo2 checkpoint bundle (`fudan-generative-ai/hallo2`) is downloaded from Hugging Face and cached automatically on first run.

3. This example runs the model worker in a dedicated **virtualenv** (`.venv/hallo2`) so Hallo2's diffusers/transformers pins don't clash with the controller's own site-packages. The venv is created on first run and reused afterwards.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will fetch the Hallo2 source, install its Python dependencies, and download the checkpoint bundle. Expect ten-plus minutes and multi-GB downloads before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — animate a portrait with a driving audio clip
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # Push the audio-driven motion harder by raising the lip / face weights
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "lip_weight": 1.4, "face_weight": 1.3}'

   # Faster preview with fewer diffusion steps
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "inference_steps": 20}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an `image` (a front-facing portrait works best) and an `audio` clip (WAV/MP3)
   - Optionally tune the motion weights, `face_expand_ratio`, `inference_steps`, or `cfg_scale`
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field    | Description                                                                                          | Default |
|----------|------------------------------------------------------------------------------------------------------|---------|
| `task`   | Must be `talking-head`.                                                                              | —       |
| `driver` | Must be `custom`.                                                                                    | —       |
| `family` | Talking-head model family. Set to `hallo2`.                                                          | —       |
| `model`  | Checkpoint bundle. A Hugging Face repo id (e.g. `fudan-generative-ai/hallo2`) or a local directory.  | —       |

### Action Fields

| Field                        | Description                                                                                                  | Default |
|------------------------------|--------------------------------------------------------------------------------------------------------------|---------|
| `image`                      | Source portrait (or list/stream of portraits) providing the identity to animate.                             | —       |
| `audio`                      | Driving audio clip (or list of clips) whose speech the mouth follows.                                        | —       |
| `params.pose_weight`         | Weight applied to the driving pose signal during motion-module conditioning.                                 | `1.1`   |
| `params.face_weight`         | Weight applied to the driving face signal during motion-module conditioning.                                 | `1.1`   |
| `params.lip_weight`          | Weight applied to the driving lip signal during motion-module conditioning.                                  | `1.1`   |
| `params.face_expand_ratio`   | Face crop expansion ratio around the detected face box.                                                      | `1.2`   |
| `params.inference_steps`     | Number of diffusion inference steps per denoising loop.                                                      | `40`    |
| `params.cfg_scale`           | Classifier-free guidance scale.                                                                              | `3.5`   |
| `params.motion_module_frames`| Number of frames processed per motion-module window.                                                         | `16`    |
| `params.long_video`          | Enable Hallo2's long-video mode (chunk-and-blend) for audio longer than one window.                          | `true`  |
| `params.high_resolution`     | Run the built-in super-resolution pass to produce a higher-resolution output.                                | `false` |
| `params.fps`                 | Output video frame rate.                                                                                     | `25`    |
| `batch_size`                 | Number of `(image, audio)` pairs processed per batch when both inputs are lists or streams.                  | `1`     |
| `seed`                       | Random seed for reproducibility. Leave unset for a fresh sample each call.                                   | (none)  |

## Notes

- **First run is slow**: The controller has to fetch the Hallo2 source, install its dependencies, and download the checkpoint bundle. Subsequent runs reuse the cached install and model files.
- **Long audio**: Generation time scales linearly with audio length. Multi-minute inputs are supported natively; expect proportional runtime.
- **Motion weights**: Bumping `lip_weight` and `face_weight` above 1.0 makes speech-driven motion more pronounced at the cost of identity fidelity. `pose_weight` controls how much head motion the model is willing to introduce.
- **`long_video`**: Leave this on for anything longer than the default motion window — Hallo2's segment/stitch pipeline is what makes multi-minute output possible.
- **`high_resolution`**: The upsampler is a separate diffusion pass; expect roughly doubled latency and VRAM when enabled.
- **Pipeline pairing**: Pair with `text-to-speech` upstream (feed generated speech as `audio`) and `image-upscale` downstream for a fully local text-to-avatar pipeline.
