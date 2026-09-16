# Video-to-Video Model Task Example

This example demonstrates how to restyle an existing video with a text prompt while preserving its motion, using AnimateDiff on top of a Stable Diffusion 1.5 checkpoint. It is exposed through model-compose's built-in video-to-video task.

## Overview

This workflow provides local motion-preserving video restyling that:

1. **Local AnimateDiff Pipeline**: Runs Stable Diffusion 1.5 with an AnimateDiff motion adapter end-to-end via HuggingFace diffusers — no external API.
2. **Motion Preserved From Source**: The input video supplies both the composition and the temporal motion; the prompt only steers appearance and style.
3. **Style Adjustable Per Frame**: A single `denoise_strength` parameter trades off between "follow the prompt more" and "stay close to the source video".
4. **Automatic Model Management**: Base checkpoint and motion adapter are downloaded from HuggingFace Hub on first run and cached locally.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU with **at least 8 GB VRAM** for 16 frames at 512×512 in `float16`. Apple Silicon (MPS) is untested and likely too slow. Pure CPU inference is impractical.
- A Python environment where `torch` and `diffusers` can be installed — the first run installs them automatically.

### Why Local Video-to-Video

Compared to cloud-hosted video restyling services:

**Benefits of Local Processing:**
- **Privacy**: Source footage and prompts never leave the machine.
- **Cost**: No per-second or per-render API fees.
- **Model Choice**: Any SD 1.5 fine-tune from HuggingFace Hub can be used as the appearance backbone — swap `model.repository` to change the entire aesthetic.
- **Pipeline Friendly**: Composes with other model-compose tasks (video-clipper upstream, video-processor downstream) for end-to-end restyling pipelines.

**Trade-offs:**
- **Hardware Requirements**: Comfortable at 8 GB VRAM for short clips; longer clips or higher resolutions scale VRAM linearly with frame count.
- **Motion Scope**: AnimateDiff's motion adapter was trained on short clips; expect coherent motion for ~16 frames and degradation beyond ~32 frames.
- **License**: Check the individual base-model and motion-adapter licenses before commercial use.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/video-to-video-animatediff
   ```

2. No additional environment configuration required — the base checkpoint (`Realistic_Vision_V5.1_noVAE`) and motion adapter (`animatediff-motion-adapter-v1-5-3`) are downloaded from HuggingFace Hub and cached under `~/.cache/huggingface/` on first run.

3. To use a different aesthetic, edit `model.repository` in `model-compose.yml`. Any SD 1.5 fine-tune works — for example an anime or illustration model — as long as the motion adapter targets the same base architecture.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will download the base checkpoint (~2 GB) and the motion adapter (~1.6 GB). Expect several minutes before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — restyle a video with a prompt, defaults for everything else
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F 'input={"video": "@clip", "prompt": "cinematic shot, film grain, warm sunset lighting"}'

   # Stronger style transfer (higher strength) with a specific seed
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F 'input={"video": "@clip", "prompt": "watercolor painting, soft brushstrokes", "denoise_strength": 0.7, "seed": 42}'

   # Longer output (32 frames) at 12 fps
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/source.mp4" \
     -F 'input={"video": "@clip", "prompt": "neon cyberpunk city, rain, reflections", "num_frames": 32, "fps": 12}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` (short clips work best — the model was trained on ~16-frame windows) and enter a `prompt`
   - Optionally tune `denoise_strength`, `num_frames`, `fps`, `guidance_scale`, or set a `seed`
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field            | Description                                                                                                                  | Default                                              |
|------------------|------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------|
| `task`           | Must be `video-to-video`.                                                                                                    | —                                                    |
| `driver`         | Must be `huggingface`.                                                                                                       | —                                                    |
| `architecture`   | Video-to-video architecture. Only `animatediff` is wired up today.                                                           | —                                                    |
| `model`          | Base SD 1.5 style checkpoint (HuggingFace repo or local path). Any SD 1.5 fine-tune works.                                   | —                                                    |
| `motion_adapter` | AnimateDiff motion adapter matching the base architecture.                                                                    | —                                                    |
| `device`         | Compute device (`cuda`, `cuda:0`, etc.). `auto` selects the best available.                                                  | `auto`                                               |

### Action Fields

| Field                        | Description                                                                                                            | Default                                                |
|------------------------------|------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------|
| `video`                      | Source video (or list/stream of videos) whose motion is preserved.                                                     | —                                                      |
| `prompt`                     | Text prompt steering the restyled appearance.                                                                          | (none)                                                 |
| `negative_prompt`            | Text describing content to avoid.                                                                                      | `"bad quality, worst quality, low resolution"`         |
| `seed`                       | Random seed for reproducibility. Leave unset for a fresh sample each call.                                             | (none)                                                 |
| `params.num_frames`          | Frames sampled from the input video (and produced in the output). Longer clips degrade beyond ~32 frames.              | `16`                                                   |
| `params.fps`                 | Output video frame rate.                                                                                               | `8`                                                    |
| `params.height` / `.width`   | Output video resolution. Defaults to the input video's dimensions when unset.                                          | (source dimensions)                                    |
| `params.denoise_strength`    | Denoising strength. `0.4-0.5` preserves motion strongly; `0.6-0.7` follows the prompt more aggressively.               | `0.5`                                                  |
| `params.guidance_scale`      | Classifier-free guidance scale.                                                                                        | `7.5`                                                  |
| `params.inference_steps`     | Diffusion inference steps per frame. More steps = better quality, slower.                                              | `25`                                                   |
| `batch_size`                 | Number of `(video, prompt)` pairs processed per batch when inputs are lists or streams.                                | `1`                                                    |

## Notes

- **First run is slow**: The controller has to fetch both the base checkpoint and the motion adapter. Subsequent runs reuse the cached files.
- **Frame count matters**: AnimateDiff was trained on ~16-frame windows. Going beyond ~32 frames tends to introduce visible drift and motion inconsistencies.
- **Strength sweet spot**: Values below `0.4` barely change the input; values above `0.7` often break coherent motion. Start at `0.5` and adjust from there.
- **Aesthetic swap**: To move from realistic to anime style, change `model.repository` to an SD 1.5 anime fine-tune (e.g. `Meina/MeinaMix_V11` or similar). The motion adapter stays the same.
- **Prompt weight**: Descriptive, style-heavy prompts work better than object-focused prompts — AnimateDiff can't restructure the scene, only recolor and restyle it.
- **VRAM planning**: Roughly 8-10 GB VRAM for 16 frames at 512×512 with `float16`; multiply by ~1.6× for 24 frames. Reduce `num_frames` or resolution if you hit OOM.
- **Pipeline pairing**: Pair with `video-clipper` upstream to trim a specific segment before restyling, or `video-processor` downstream to composite the restyled clip back into a longer edit.
