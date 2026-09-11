# Talking Head Model Task Example

This example demonstrates how to animate a still portrait so that it lip-syncs (and gently head-moves) with a driving audio clip using SadTalker, exposed through model-compose's built-in talking-head task.

## Overview

This workflow provides local talking-head generation that:

1. **Local SadTalker Pipeline**: Runs SadTalker's Audio2Coeff + face renderer end-to-end without any external API
2. **Audio-Driven Lip Sync**: Predicts head-pose and expression coefficients directly from the driving audio, then renders a video where the portrait's mouth and face follow the speech
3. **Automatic Face Detection & Crop**: Detects and aligns the face in the source portrait; supports keeping the full-frame background or a tight face crop
4. **Optional Face Enhancement**: Runs GFPGAN (or RestoreFormer) as a per-frame enhancer for sharper faces
5. **Automatic Model Management**: Downloads the SadTalker checkpoint bundle from Hugging Face on first run; the pipeline is renamed and imports are rewritten in place so the upstream `src/` layout doesn't collide with model-compose's own source tree

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A CUDA-capable GPU is strongly recommended; CPU-only runs are impractically slow for real-length audio
- A Python environment where torch/torchvision and the SadTalker dependency chain (`librosa`, `numba`, `face-alignment`, `gfpgan`, `basicsr`, `facexlib`, `av`, ...) can be installed — the first run installs them automatically

### Why Local Talking-Head

Unlike cloud talking-head services, running SadTalker locally provides:

**Benefits of Local Processing:**
- **Privacy**: Portraits and voice recordings never leave the machine
- **Cost**: No per-second or per-render API fees; the same portrait can be re-driven cheaply
- **Offline**: Works without an internet connection after the initial checkpoint download
- **Pipeline Friendly**: Composes cleanly with other model-compose tasks (text-to-speech upstream, image-upscale downstream, etc.) for end-to-end avatar pipelines

**Trade-offs:**
- **Hardware Requirements**: The 256 preset needs ~6 GB VRAM; the 512 preset ~12 GB. First run also downloads several GB of checkpoints
- **Not Real-Time**: SadTalker consumes the whole audio to solve for a consistent head-pose/expression sequence — streaming input isn't supported
- **License**: SadTalker weights are released for **non-commercial research use only**

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/talking-head-sadtalker
   ```

2. No additional environment configuration required — the SadTalker checkpoint bundle (`vinthony/SadTalker`) is downloaded from Hugging Face and cached automatically on first run.

3. This example runs the model worker in a dedicated **virtualenv** (`.venv/sadtalker`) so SadTalker's old numpy/numba/librosa pins don't clash with the controller's own site-packages. The venv is created on first run and reused afterwards.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will fetch the SadTalker source, install its Python dependencies, and download the checkpoint bundle. Expect several minutes and multi-GB downloads before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — animate a portrait with a driving audio clip
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # Full-frame render with only the mouth moving (recommended for photos with body/background)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "preprocess": "full", "still": true}'

   # More expressive face motion, without the GFPGAN enhancer
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "expression_scale": 1.4, "enhancer": null}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an `image` (a front-facing portrait works best) and an `audio` clip (WAV/MP3)
   - Optionally tune `preprocess`, toggle `still`, choose an `enhancer`, or dial `expression_scale` / `pose_style`
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field    | Description                                                                                          | Default        |
|----------|------------------------------------------------------------------------------------------------------|----------------|
| `task`   | Must be `talking-head`.                                                                              | —              |
| `driver` | Must be `custom`.                                                                                    | —              |
| `family` | Talking-head model family. Currently only `sadtalker`.                                               | —              |
| `preset` | SadTalker checkpoint variant: `v0.0.2-256` (256×256, lighter) or `v0.0.2-512` (512×512, sharper).    | `v0.0.2-256`   |
| `model`  | Checkpoint bundle. A Hugging Face repo id (e.g. `vinthony/SadTalker`) or a local directory path.     | —              |

### Action Fields

| Field                  | Description                                                                                                   | Default       |
|------------------------|---------------------------------------------------------------------------------------------------------------|---------------|
| `image`                | Source portrait (or list/stream of portraits) providing the identity to animate.                              | —             |
| `audio`                | Driving audio clip (or list of clips) whose speech the mouth follows.                                         | —             |
| `params.preprocess`    | Face preprocessing mode: `crop`, `extcrop`, `resize`, `full`, `extfull`. Use `full` to keep the whole photo.  | `crop`        |
| `params.still`         | Keep the head still (only the mouth moves). Recommended when `preprocess` is `full`.                          | `false`       |
| `params.enhancer`      | Per-frame face enhancer: `gfpgan` or `RestoreFormer`. Leave unset to skip the enhancer pass.                  | (none)        |
| `params.background_enhancer` | Background super-resolution enhancer: `realesrgan`. Leave unset to skip.                                | (none)        |
| `params.expression_scale`    | Multiplier applied to predicted facial expression intensity. Larger values look more dramatic.          | `1.0`         |
| `params.pose_style`    | Head-pose style index in `[0, 46]`. Different values sample different pose patterns from the same audio.      | `0`           |
| `params.ref_eyeblink`  | Optional reference video whose eye-blink motion is transferred onto the output.                               | (none)        |
| `params.ref_pose`      | Optional reference video whose head-pose motion is transferred onto the output.                               | (none)        |
| `params.input_yaw` / `input_pitch` / `input_roll` | Manual head-rotation keyframes in degrees (list of ints). Override predicted rotation.  | (none)        |
| `params.face3dvis`     | Render an additional 3D-face debug video alongside the output.                                                | `false`       |
| `params.size`          | Face renderer resolution. Should match the loaded preset (`256` for `v0.0.2-256`, `512` for `v0.0.2-512`).    | `256`         |
| `params.facerender_batch_size` | Batch size used by the face renderer inference loop.                                                  | `2`           |
| `params.fps`           | Output video frame rate. SadTalker's renderer targets 25 fps internally.                                      | `25`          |
| `batch_size`           | Number of `(image, audio)` pairs processed per batch when both inputs are lists or streams.                   | `1`           |
| `seed`                 | Random seed for reproducibility. Leave unset for a fresh sample each call.                                    | (none)        |

## Notes

- **First run is slow**: The controller has to fetch the SadTalker source, install its dependencies, and download the checkpoint bundle. Subsequent runs reuse the cached install and model files.
- **Long audio**: Generation time scales linearly with the audio length. Consider splitting long clips into paragraphs and stitching the outputs downstream.
- **Face detection failures**: If no face is detected in the source image, the workflow raises "SadTalker failed to detect a face in the input image". Use a clearer, larger, front-facing portrait.
- **Full-frame photos**: For photos where the person occupies only part of the frame, use `preprocess: full` together with `still: true` so the background stays static while the mouth animates in place.
- **Enhancers cost time**: GFPGAN adds meaningful per-frame latency. Turn it off for previews and enable it only for final renders.
- **Pipeline pairing**: Pair with `text-to-speech` upstream (feed generated speech as `audio`) and `image-upscale` downstream for a fully local text-to-avatar pipeline.
