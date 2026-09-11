# Talking Head Model Task Example (Float)

This example demonstrates how to generate emotion-conditioned talking-head videos from a still portrait and a driving audio clip using Float (DeepBrain AI) — a flow-matching pipeline with explicit emotion labels — exposed through model-compose's built-in talking-head task.

## Overview

This workflow provides local talking-head generation that:

1. **Local Float Flow-Matching Pipeline**: Runs Float's `InferenceAgent.run_inference()` end-to-end without any external API — flow-matching over portrait + audio latents with a wav2vec2 audio encoder
2. **Explicit Emotion Labels**: Pick from `happy`, `sad`, `angry`, `fear`, `disgust`, `surprise`, `neutral`, or leave on the `S2E` sentinel to let Float derive emotion from the audio directly
3. **Fast Inference**: Only 10 flow-matching NFE by default; among the fastest talking-head backbones in this collection
4. **Automatic Model Management**: Downloads the Float checkpoint bundle (Float weights + wav2vec2-base-960h + emotion recognition head) from Hugging Face on first run; upstream's flat repo layout is wrapped into a single `float_talker/` package so top-level names like `models/`, `options/` don't collide with anything else in site-packages

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A CUDA-capable GPU is strongly recommended; CPU inference is much slower
- A Python environment where torch/torchvision and the Float dependency chain (`diffusers`, `transformers`, `librosa`, `face-alignment`, `torchdiffeq`, `moviepy`, ...) can be installed — the first run installs them automatically into the sandbox venv

### Why Local Talking-Head

Unlike cloud talking-head services, running Float locally provides:

**Benefits of Local Processing:**
- **Privacy**: Portraits and voice recordings never leave the machine
- **Cost**: No per-second or per-render API fees
- **Offline**: Works without an internet connection after the initial checkpoint download
- **Pipeline Friendly**: Composes cleanly with other model-compose tasks for end-to-end avatar pipelines

**Trade-offs:**
- **Hardware Requirements**: Reasonably lightweight (~8 GB VRAM) but still faster on higher-end cards
- **English-Centric Emotion Head**: The bundled emotion recognizer is trained on English speech; explicit `emotion` labels are the safer fallback for non-English audio
- **License**: Float weights are released for **non-commercial research use only**

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/talking-head-float
   ```

2. No additional environment configuration required — the Float checkpoint bundle (`yuvraj108c/float`) is downloaded from Hugging Face and cached automatically on first run.

3. This example runs the model worker in a dedicated **virtualenv** (`.venv/float`) so Float's `models/` and `options/` packages (renamed on install into `float_talker.models` / `float_talker.options`) can't clash with the controller's own site-packages. The venv is created on first run and reused afterwards.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will fetch the Float source, install its Python dependencies, and download the checkpoint bundle. Expect several minutes and multi-GB downloads before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — auto-detected emotion
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice"}'

   # Force an explicit emotion label
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "emotion": "happy"}'

   # Skip the face crop to render the full frame (useful when the portrait
   # is already tightly cropped upstream)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "portrait=@/path/to/portrait.jpg" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"image": "@portrait", "audio": "@voice", "crop": false}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an `image` (a front-facing portrait works best) and an `audio` clip (WAV/MP3)
   - Optionally pick an `emotion`, or tune `inference_steps`, `cfg_scale`, `a_cfg_scale`, or `e_cfg_scale`
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field    | Description                                                                                          | Default |
|----------|------------------------------------------------------------------------------------------------------|---------|
| `task`   | Must be `talking-head`.                                                                              | —       |
| `driver` | Must be `custom`.                                                                                    | —       |
| `family` | Talking-head model family. Set to `float`.                                                           | —       |
| `model`  | Checkpoint bundle. A Hugging Face repo id (e.g. `yuvraj108c/float`) or a local directory.            | —       |

### Action Fields

| Field                       | Description                                                                                                    | Default |
|-----------------------------|----------------------------------------------------------------------------------------------------------------|---------|
| `image`                     | Source portrait (or list/stream of portraits) providing the identity to animate.                               | —       |
| `audio`                     | Driving audio clip (or list of clips) whose speech the mouth follows.                                          | —       |
| `params.emotion`            | Emotion label: `happy`, `sad`, `angry`, `fear`, `disgust`, `surprise`, `neutral`, or `S2E` for auto-detect.    | `S2E`   |
| `params.emotion_scale`      | Multiplier applied to the emotion conditioning strength.                                                       | `1.0`   |
| `params.inference_steps`    | Number of flow-matching inference steps (NFE).                                                                 | `10`    |
| `params.cfg_scale`          | Classifier-free guidance scale applied to the reference branch.                                                | `2.0`   |
| `params.a_cfg_scale`        | Guidance scale applied to the audio conditioning branch.                                                       | `2.0`   |
| `params.e_cfg_scale`        | Guidance scale applied to the emotion conditioning branch.                                                     | `1.0`   |
| `params.crop`               | Crop the source portrait to the detected face before rendering; disable to render the full frame.              | `true`  |
| `params.fps`                | Output video frame rate.                                                                                       | `25`    |
| `batch_size`                | Number of `(image, audio)` pairs processed per batch when both inputs are lists or streams.                    | `1`     |
| `seed`                      | Random seed for reproducibility. Leave unset to reuse Float's default (25) each call.                          | `25`    |

## Notes

- **First run is slow**: The controller has to fetch the Float source, install its dependencies, and download the checkpoint bundle. Subsequent runs reuse the cached install and model files.
- **`S2E` vs explicit emotion**: For English speech, `S2E` gives natural results; for other languages, explicit labels (`happy`, `sad`, ...) avoid mispredictions from the English-centric emotion head.
- **`e_cfg_scale`**: Raising this makes the emotion conditioning more literal; combine with an explicit `emotion` label for strongly stylized outputs.
- **`crop: false`**: If the input portrait is already tightly cropped (e.g. from an upstream `image-upscale` component), skip Float's face-crop step for cleaner framing.
- **Face detection failure**: If no face is detected in the source image, Float's built-in preprocessor raises an alignment error. Use a clearer, larger, front-facing portrait.
- **Pipeline pairing**: Pair with `text-to-speech` upstream (feed generated speech as `audio`) and `image-upscale` downstream for a fully local text-to-avatar pipeline.
