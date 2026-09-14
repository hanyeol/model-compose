# Lip Sync Model Task Example (MuseTalk)

This example demonstrates how to re-sync a face video's mouth movements to a driving audio clip using MuseTalk, exposed through model-compose's built-in lip-sync task.

## Overview

This workflow provides local lip-sync generation that:

1. **Local MuseTalk Pipeline**: Runs the InsightFace + Whisper + VAE + UNet stack end-to-end without any external API
2. **Video-Driven Face Preservation**: Only the mouth region is regenerated; the rest of every frame (identity, expression, head pose, background) comes straight from the source video
3. **Two Release Variants**: `v15` uses parsing-mask blending for softer edges; `v1` exposes a `bbox_shift` knob for manual mouth region tuning
4. **Automatic Model Management**: Downloads MuseTalk's own UNet from `TMElyralab/MuseTalk` on first run; the side snapshots (VAE, whisper-tiny, DWPose, face-parse-bisent, torchvision ResNet18) are auto-fetched into the installed package's `models/` directory

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A CUDA-capable GPU is strongly recommended; Apple Silicon (MPS) works but is slower; pure CPU inference is impractically slow for anything but short clips
- A Python environment where `torch` and MuseTalk's dependency chain (`diffusers==0.30.2`, `transformers==4.39.2`, `librosa`, `opencv-python`, ...) can be installed — the first run installs them automatically

### Why Local Lip-Sync

Unlike cloud lip-sync services, running MuseTalk locally provides:

**Benefits of Local Processing:**
- **Privacy**: Face video and voice recordings never leave the machine
- **Cost**: No per-second or per-render API fees; the same clip can be re-driven cheaply
- **Offline**: Works without an internet connection after the initial checkpoint download
- **Pipeline Friendly**: Composes cleanly with other model-compose tasks (text-to-speech upstream, video-processor downstream, etc.) for end-to-end voice-swap pipelines

**Trade-offs:**
- **Hardware Requirements**: v1.5 needs ~8 GB VRAM at 256×256; face detection and parsing add extra memory
- **Not Real-Time**: The generator consumes the whole audio + video pair up front; streaming input isn't supported
- **License**: MuseTalk weights are released under a research-only license — review upstream terms before commercial use

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/lip-sync-musetalk
   ```

2. No additional environment configuration required — the MuseTalk UNet is downloaded from Hugging Face and cached automatically on first run. The VAE (`stabilityai/sd-vae-ft-mse`), Whisper-tiny (`openai/whisper-tiny`), DWPose (`yzd-v/DWPose`), and face-parse-bisent (`vivym/face-parsing-bisenet`) snapshots are downloaded into the installed MuseTalk package's `models/` directory the first time the pipeline loads.

3. This example runs the model worker in a dedicated **virtualenv** (`.venv/musetalk`) so MuseTalk's older `diffusers`/`transformers` pins don't clash with the controller's own site-packages.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will fetch the MuseTalk source, install its Python dependencies, and download several checkpoints (UNet, VAE, Whisper, DWPose, face-parse-bisent). Expect several minutes and a few GB of downloads before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — re-sync a video's lips to a new audio track
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "face=@/path/to/face.mp4" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"video": "@face", "audio": "@voice"}'

   # Use the `neck` parsing mask to widen the blended region (v15)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "face=@/path/to/face.mp4" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"video": "@face", "audio": "@voice", "parsing_mode": "neck", "extra_margin": 20}'

   # Faster preview with float16
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "face=@/path/to/face.mp4" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"video": "@face", "audio": "@voice", "use_float16": true, "generator_batch_size": 16}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` (a clip with a clearly visible face works best) and an `audio` clip (WAV/MP3)
   - Optionally tune `parsing_mode`, `extra_margin`, `bbox_shift`, `generator_batch_size`, or toggle `use_float16`
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field    | Description                                                                                              | Default          |
|----------|----------------------------------------------------------------------------------------------------------|------------------|
| `task`   | Must be `lip-sync`.                                                                                      | —                |
| `driver` | Must be `custom`.                                                                                        | —                |
| `family` | Lip-sync model family. `wav2lip`, `latentsync`, or `musetalk`.                                           | —                |
| `preset` | MuseTalk release: `v1` (bbox_shift tuning) or `v15` (parsing-based blending).                            | `v15`            |
| `model`  | UNet snapshot. Leave unset to auto-fetch the preset's subdir from `TMElyralab/MuseTalk`.                 | (from preset)    |

### Action Fields

| Field                                | Description                                                                                                                            | Default           |
|--------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `video`                              | Source face video (or list/stream of videos) whose mouth region is re-synced.                                                          | —                 |
| `audio`                              | Driving audio clip (or list of clips) whose speech the mouth follows.                                                                  | —                 |
| `params.parsing_mode`                | Face parsing region used for blending (v15 only): `jaw` (tight), `neck` (widest), `raw` (default face region).                         | `jaw`             |
| `params.extra_margin`                | Extra chin margin (in pixels) added to the face region before blending (v15 only).                                                     | `10`              |
| `params.left_cheek_width` / `right_cheek_width` | Cheek width used by the parsing mask (v15 only).                                                                            | `90`              |
| `params.bbox_shift`                  | Vertical shift (in pixels) applied to the detected face bounding box (v1 only).                                                        | `0`               |
| `params.audio_padding_length_left` / `right` | Number of audio feature frames padded on each side of every window.                                                            | `2`               |
| `params.generator_batch_size`        | Number of samples processed per MuseTalk generator batch.                                                                              | `8`               |
| `params.use_float16`                 | Run the pipeline in float16 for a memory and latency win.                                                                              | `false`           |
| `params.fps`                         | Output video frame rate. Defaults to the source video's frame rate when unset.                                                         | (source fps)      |
| `batch_size`                         | Number of `(video, audio)` pairs processed per batch when both inputs are lists or streams.                                            | `1`               |
| `seed`                               | Random seed for reproducibility. Leave unset for a fresh sample each call.                                                             | (none)            |

## Notes

- **First run is slow**: The controller has to fetch the MuseTalk source, install its dependencies, and download several checkpoints. Subsequent runs reuse the cached install and model files.
- **Face detection failures**: If MuseTalk can't find a face in a frame, that frame is skipped and the workflow raises if no faces at all are detected. Use a clearer, larger, front-facing video.
- **Audio length**: If the audio is longer than the video, the source frames are ping-ponged (played forward, then reversed, then forward, ...) to fill the timeline; if shorter, the video is trimmed to match. Pre-align the two upstream when precise sync matters.
- **Parsing mode**: On v15, `jaw` produces the tightest blend (best for a single moving face); `neck` widens the mask to include the neck (better when the chin moves relative to a static neck line); `raw` skips the cheek-erosion refinement entirely.
- **v1 vs v15**: v15 is the newer, higher-quality default. Use v1 only when you need `bbox_shift` for a specific footage that v15 handles poorly.
- **Pipeline pairing**: Pair with `text-to-speech` upstream (feed generated speech as `audio`) and `video-processor` downstream for a fully local voice-swap or dubbing pipeline.
