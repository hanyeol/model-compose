# Video Refiner Example

This example chains **file-store**, **`audio-extractor`**, **Silero VAD**, and **`video-clipper`** to produce a video that contains only detected speech regions. The pipeline runs end-to-end in streaming mode: VAD emits each speech segment as soon as it is confirmed, and the clipper produces the corresponding video clip on the fly.

## Overview

The workflow runs four jobs, all connected as a streaming pipeline:

1. **`store`** — Stashes the uploaded video on a local `file-store` so both the audio branch and each per-segment clip can independently re-read it. The raw upload stream is single-use, so without this step it would be consumed by whichever job read it first.
2. **`extract`** — Rips the audio track out of the stored video with `audio-extractor` (ffmpeg). The audio flows into VAD directly.
3. **`detect`** — Runs Silero VAD in **streaming mode** (`streaming: true`) so each speech segment is emitted as `{start_time, end_time, confidence}` the moment it is confirmed, without waiting for the full audio to be analysed.
4. **`refine`** — Fans the VAD segment stream out into `(video, span)` pairs using the `"|"` split operator, and feeds each pair into `video-clipper`. For every incoming segment the clipper re-opens the stored video, seeks to `[start_time, end_time]`, and emits a lossless clip. Clips are yielded one at a time as they finish.

VAD's segment schema (`start_time`, `end_time`) matches the clipper's span schema 1:1, so no shape-mapping step is needed — the extra `confidence` field on each segment is simply ignored by the clipper.

Typical use cases:
- Producing a "speech-only" cut of a raw recording for review or captioning.
- Trimming interview or podcast video before uploading to a transcription service — cheaper and less prone to silent-region hallucinations.
- Chaining into a scene-classifier or ASR pipeline that only needs the parts where somebody is talking.

## Pipeline

```
input.video ── store ─┐
                      │
                      ├──► extract ──► detect (streaming) ──┐
                      │                                     │
                      │                    "|": vad output   ← fan-out
                      │                    video: stored path
                      │                    span:  ${item}
                      │                                     │
                      └────────────────────────────────► refine ──► stream of clips
```

The `"|"` split operator (see the [variable-binding reference](../../../docs/user-guide/14-variable-binding.md)) takes the VAD segment stream as its source and produces two parallel per-item streams: one that always resolves to the stored video's path, one that resolves to the current segment. Each `(video, span)` pair triggers a single ffmpeg stream-copy clip.

## Preparation

### Prerequisites

- model-compose installed and available on `PATH`.
- [ffmpeg](https://ffmpeg.org/) installed and available on `PATH` (used by both `audio-extractor` and `video-clipper`).
- Python dependencies are installed automatically on first run:
  - `silero-vad`, `torch`, `torchaudio`, `numpy` — VAD model.

### Setup

Navigate to this example directory:

```bash
cd examples/media-processing/video-refiner
```

Verify ffmpeg is installed:

```bash
ffmpeg -version
```

The local file-store writes to `./storage/` by default (see the `storage` component in `model-compose.yml`). No further setup is required — the directory is created on first run.

## How to Run

1. **Start the service:**

   ```bash
   model-compose up
   ```

   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run the workflow:**

   **Using Web UI:**
   - Open http://localhost:8081.
   - Upload a video file.
   - Optionally override `threshold`, `min_speech_duration`, `min_silence_duration`, `speech_padding_time`.
   - Click **Run Workflow** and download the refined clips as they arrive.

   **Using CLI:**

   ```bash
   # Default parameters
   model-compose run --input '{"video": "/path/to/recording.mp4"}'

   # Stricter VAD (drop more marginal speech), and pad clip boundaries so
   # words aren't clipped at the edges.
   model-compose run --input '{
     "video": "/path/to/recording.mp4",
     "threshold": 0.6,
     "min_speech_duration": "500ms",
     "speech_padding_time": "200ms"
   }'
   ```

   **Using API:**

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "video=@/path/to/recording.mp4" \
     -F 'input={"video": "@video", "threshold": 0.6}'
   ```

## Component Details

### `storage` — File Store

- **Type**: `file-store`
- **Driver**: `local`
- **Purpose**: Persist the uploaded video so both `extract` and `refine` can re-read it. Without this, the single-use upload stream would be consumed by whichever job read it first.
- **Notes**:
  - `base_path: ./storage` keeps everything under the example directory. Swap the driver to `aws-s3` / `gcp-storage` / `azure-blob` for shared/cloud storage.
  - `${context.run_id}` scopes each run's storage key so parallel runs don't collide.

### `extractor` — Audio Extractor

- **Type**: `audio-extractor`
- **Driver**: `ffmpeg`
- **Purpose**: Rip the audio track out of the stored video so VAD can consume it. Emits WAV.

### `vad` — Voice Activity Detection

- **Type**: Model component with `voice-activity-detection` task
- **Driver**: `custom`
- **Family**: `silero`
- **Purpose**: Detect speech regions in the extracted audio.
- **Notes**:
  - `streaming: true` emits each confirmed segment immediately instead of returning the full list at the end.
  - Model is bundled inside the `silero-vad` pip package — no HuggingFace download required.
  - Input is resampled to 16 kHz mono internally.

### `clipper` — Video Clipper

- **Type**: `video-clipper`
- **Driver**: `ffmpeg`
- **Purpose**: For each incoming `(video, span)` pair, cut the span out of the stored video using `ffmpeg -c copy` (no re-encoding).
- **Notes**:
  - `merge` is left at its default (`false`) so clips are yielded one at a time as a stream. To produce a single concatenated file, set `merge: true` — see [Customization](#customization).
  - Because clips are cut without re-encoding, cut points snap to the nearest preceding keyframe. If frame-accurate cuts are required, follow up with `video-encoder` to re-encode.

## Workflow Details

### "Video Refiner" Workflow

**Description**: Detect speech regions with Silero VAD and stream refined video clips out one segment at a time.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video | Yes | - | Source video file (MP4, MOV, MKV, ...) |
| `threshold` | number | No | `0.5` | Silero speech-probability threshold (0.0–1.0); higher = stricter |
| `min_speech_duration` | duration | No | `250ms` | Discard speech chunks shorter than this |
| `min_silence_duration` | duration | No | `500ms` | Silence required to split adjacent chunks |
| `speech_padding_time` | duration | No | `100ms` | Padding added to both sides of each detected chunk |

Duration fields accept values like `"250ms"`, `"0.5s"`, or bare numeric seconds.

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video (stream) | Stream of refined video clips — one per detected speech segment, delivered as it finishes. |

## Customization

### Concatenate all clips into a single refined video

Set `merge: true` on the clipper action and change the workflow output shape from a stream to a single video:

```yaml
components:
  - id: clipper
    type: video-clipper
    action:
      video: ${input.video}
      span: ${input.span}
      merge: true
```

With `merge: true` the clipper waits for the entire span stream to arrive before running ffmpeg's `concat` demuxer, so the pipeline is no longer chunk-by-chunk streaming — but the output is a single ready-to-play file.

### Store the video on cloud object storage instead of the local disk

Swap the `storage` component's driver to `aws-s3` / `gcp-storage` / `azure-blob`:

```yaml
components:
  - id: storage
    type: file-store
    driver: aws-s3
    bucket: ${env.S3_BUCKET}
    region: ${env.AWS_REGION | us-east-1}
    access_key_id: ${env.AWS_ACCESS_KEY_ID}
    secret_access_key: ${env.AWS_SECRET_ACCESS_KEY}
    base_path: video-refiner/
```

The rest of the workflow is unchanged — the logical path returned by `put` is what downstream jobs consume.

### Feed the refined clips into a downstream ASR

Add a job that takes each streamed clip and runs it through a `speech-to-text` model component. Because clips arrive as a stream, downstream jobs process each one as it lands rather than waiting for the whole video to finish.

## Tips

- **Streaming end-to-end**: The entire pipeline flows without waiting for any stage to complete: VAD emits segments as they are confirmed, the clipper cuts each segment on the fly, and each clip is delivered as soon as ffmpeg finishes it.
- **Lossless clipping**: The clipper uses `ffmpeg -c copy`, so clip boundaries land on the nearest keyframe supported by the container. For a lossy codec (h.264, hevc) the cuts may be off by a few ms; use `video-encoder` after clipping if frame accuracy is required.
- **Padding matters**: A `speech_padding_time` of 100–200ms usually prevents word-onset clipping caused by Silero's frame-level threshold.
- **Storage cleanup**: The `storage` component keeps uploads under `./storage/uploads/`. Add a periodic cleanup job or scope storage per run and delete on completion if you plan to run this at scale.

## Troubleshooting

### Common Issues

1. **No clips are produced / stream ends immediately**: The threshold is likely too strict — lower `threshold` (e.g. `0.3`) or reduce `min_speech_duration`.
2. **Words clipped at clip boundaries**: Increase `speech_padding_time` (e.g. `200ms`).
3. **`ffmpeg` not found**: Install ffmpeg (and ffprobe) and ensure both are on `PATH`.
4. **Storage directory permission error**: Ensure the process can write to `./storage/`. Change `storage.base_path` in `model-compose.yml` if you need a different location.
5. **"Upload stream already consumed" error**: This example writes the upload to file-store first specifically to avoid that. If you customize the workflow to skip the `store` job, remember that `${input.video}` can only be consumed once — download it to disk (via `save_to`) or persist it through `file-store` before fanning out.
