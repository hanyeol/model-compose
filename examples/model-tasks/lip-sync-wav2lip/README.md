# Lip Sync Model Task Example

This example demonstrates how to re-sync a face video's mouth movements to a driving audio clip using Wav2Lip, exposed through model-compose's built-in lip-sync task.

## Overview

This workflow provides local lip-sync generation that:

1. **Local Wav2Lip Pipeline**: Runs the S3FD face detector + Wav2Lip generator end-to-end without any external API
2. **Video-Driven Face Preservation**: Only the mouth region is regenerated; the rest of every frame (identity, expression, head pose, background) comes straight from the source video
3. **Automatic Face Detection & Smoothing**: Detects faces per frame with S3FD, optionally smooths the bounding boxes across neighbouring frames to remove per-frame jitter
4. **Automatic Model Management**: Downloads the Wav2Lip generator checkpoint on first run; the S3FD detector weights are dropped inside the installed Wav2Lip package so upstream's own `load_url` fallback never has to fire

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A CUDA-capable GPU is strongly recommended; Apple Silicon (MPS) works but is slower; pure CPU inference is impractically slow for anything but short clips
- A Python environment where `torch` and the Wav2Lip dependency chain (`librosa`, `numba`, `opencv-python`, `soundfile`, ...) can be installed — the first run installs them automatically

### Why Local Lip-Sync

Unlike cloud lip-sync services, running Wav2Lip locally provides:

**Benefits of Local Processing:**
- **Privacy**: Face video and voice recordings never leave the machine
- **Cost**: No per-second or per-render API fees; the same clip can be re-driven cheaply
- **Offline**: Works without an internet connection after the initial checkpoint download
- **Pipeline Friendly**: Composes cleanly with other model-compose tasks (text-to-speech upstream, video-processor downstream, etc.) for end-to-end voice-swap pipelines

**Trade-offs:**
- **Hardware Requirements**: The generator itself is small (~200 MB VRAM), but S3FD face detection dominates runtime and benefits from a GPU
- **Not Real-Time**: The generator consumes the whole audio + video pair up front; streaming input isn't supported
- **License**: Wav2Lip weights are released for **non-commercial research use only**

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/lip-sync-wav2lip
   ```

2. No additional environment configuration required — the Wav2Lip generator checkpoint (`Wav2Lip_GAN.pth`) is downloaded from the Easy-Wav2Lip release mirror and cached under `~/.cache/models/wav2lip/` on first run.

3. This example runs the model worker in a dedicated **virtualenv** (`.venv/wav2lip`) so Wav2Lip's old `librosa`/`numba` pins don't clash with the controller's own site-packages. The venv is created on first run and reused afterwards.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup will fetch the Wav2Lip source, install its Python dependencies, download the Wav2Lip generator checkpoint, and drop the S3FD detector weights into the installed package. Expect several minutes before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — re-sync a video's lips to a new audio track
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "face=@/path/to/face.mp4" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"video": "@face", "audio": "@voice"}'

   # Faster preview (2x downscale) with smoothing disabled
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "face=@/path/to/face.mp4" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"video": "@face", "audio": "@voice", "resize_factor": 2, "face_smoothing": false}'

   # Extra bottom padding so chin motion isn't clipped on close-up shots
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "face=@/path/to/face.mp4" \
     -F "voice=@/path/to/speech.wav" \
     -F 'input={"video": "@face", "audio": "@voice", "face_bounding_box_padding": [0, 0, 0, 20]}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` (a clip with a clearly visible face works best) and an `audio` clip (WAV/MP3)
   - Optionally tune `face_bounding_box_padding`, `resize_factor`, or toggle `face_smoothing`
   - Click the "Run Workflow" button to receive an MP4 back

## Configuration Reference

### Component Fields

| Field    | Description                                                                                              | Default          |
|----------|----------------------------------------------------------------------------------------------------------|------------------|
| `task`   | Must be `lip-sync`.                                                                                      | —                |
| `driver` | Must be `custom`.                                                                                        | —                |
| `family` | Lip-sync model family. `wav2lip`, `latentsync`, or `musetalk` (only `wav2lip` is implemented today).     | —                |
| `preset` | Wav2Lip checkpoint variant: `wav2lip` (accuracy-tuned) or `wav2lip-gan` (sharper faces).                 | `wav2lip-gan`    |
| `model`  | Checkpoint file. Leave unset to auto-fetch the preset's checkpoint into `~/.cache/models/wav2lip/`.      | (from preset)    |

### Action Fields

| Field                                | Description                                                                                                                            | Default           |
|--------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|-------------------|
| `video`                              | Source face video (or list/stream of videos) whose mouth region is re-synced.                                                          | —                 |
| `audio`                              | Driving audio clip (or list of clips) whose speech the mouth follows.                                                                  | —                 |
| `params.face_bounding_box`           | Fixed face bounding box `(left, top, right, bottom)` in pixels that bypasses face detection. Leave unset to detect per frame.          | (none)            |
| `params.face_bounding_box_padding`   | Pixel padding `(left, top, right, bottom)` added around each detected face box before mouth swap.                                      | `[0, 0, 0, 10]`   |
| `params.frame_crop_box`              | Manual crop rectangle `(left, top, right, bottom)` applied to input frames; `null` on any edge keeps the frame edge.                   | (none)            |
| `params.resize_factor`               | Downscale factor applied to input frames before inference. Higher values trade quality for speed.                                      | `1`               |
| `params.face_smoothing`              | Temporal smoothing of face detections across frames; disable for short clips or fast head motion.                                      | `true`            |
| `params.face_detection_batch_size`   | Number of frames processed per S3FD face-detection batch.                                                                              | `16`              |
| `params.generator_batch_size`        | Number of samples processed per Wav2Lip generator batch.                                                                               | `128`             |
| `params.static`                      | Reuse the first frame as a still image for the entire audio (photo-to-lipsync mode).                                                   | `false`           |
| `params.fps`                         | Output video frame rate. Defaults to the source video's frame rate when unset.                                                         | (source fps)      |
| `batch_size`                         | Number of `(video, audio)` pairs processed per batch when both inputs are lists or streams.                                            | `1`               |
| `seed`                               | Random seed for reproducibility. Leave unset for a fresh sample each call.                                                             | (none)            |

## Notes

- **First run is slow**: The controller has to fetch the Wav2Lip source, install its dependencies, and download two checkpoints (generator + S3FD detector). Subsequent runs reuse the cached install and model files.
- **Face detection failures**: If S3FD can't find a face in a frame, the workflow raises "Face not detected in one of the frames". Provide a `face_bounding_box` to bypass detection or use a video with a clearer, larger face.
- **Silent output regions**: Where the audio is quiet, the mouth still moves slightly because the mel spectrogram encodes ambient tone. Trim silence upstream if a fully-closed mouth is required.
- **Audio length**: If the audio is longer than the video, the source frames are looped to fill the timeline; if shorter, the video is trimmed to match. Pre-align the two upstream when precise sync matters.
- **Downscaling helps**: On CPU or MPS, setting `resize_factor: 2` roughly halves inference time with minimal visible quality loss for talking-head shots.
- **Pipeline pairing**: Pair with `text-to-speech` upstream (feed generated speech as `audio`) and `video-processor` downstream for a fully local voice-swap or dubbing pipeline.
