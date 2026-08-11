# Face Mosaic Example

This example demonstrates a workflow that redacts every face in a video by pixelating (or blurring) each detected face bounding box, then reassembles the redacted frames back into an mp4 — preserving the original audio track. The whole pipeline runs end-to-end in streaming mode, so memory stays bounded regardless of clip length.

> **License note**: This example auto-downloads InsightFace's `antelopev2` model pack, whose training data is licensed for **non-commercial research use only**. Personal use, research, open-source demos, and self-hosted utilities are fine. Do **not** embed this pack in a commercial product or paid service — swap in a permissively-licensed detector (`family: blazeface`) or a self-trained model in that case.

## Overview

Given an input video, the workflow returns a version of the same video with every face obscured by a mosaic effect.

The strategy is:

1. **Stash the uploaded video** on a local `file-store` so the audio branch and the frame extractor can each re-read it (the raw upload stream is single-use).
2. **Split the audio track** out of the stored video with `audio-extractor` (preserved unchanged).
3. **Stream every frame** out of the stored video with `video-frame-extractor` (`streaming: true` — no full-video buffering).
4. **For each frame**, run `face-detection` (InsightFace `antelopev2`) to get every face's bounding box, then feed those boxes as a list into `image-processor mosaic` in a single pass. Since the extractor emits a stream, the `for-each` job's output is also a stream — redacted frames flow lazily to the encoder.
5. **Encode the redacted frame stream** back into an mp4 with `video-encoder`, muxing the extracted audio into the output. ffmpeg pulls frames from the upstream stream as it is ready for them, so no full-video buffering happens at this stage either.

The per-frame detect + mosaic pair is wrapped in a private sub-workflow (`mosaic-faces-in-frame`) so the main workflow's `for-each` stays readable.

### Why streaming matters

The naive design would materialise every frame in memory, run detection on the whole list, then hand the redacted list to the encoder. That works for short clips but blows up memory on longer videos (a 1080p 30 fps 10-minute clip = 18,000 frames × ~6 MB decoded = ~110 GB of PIL images).

With streaming end-to-end, at most `batch_size` frames are in flight through detection at once, and the encoder consumes each redacted frame as it arrives. Memory stays bounded regardless of clip length.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- FFmpeg installed and available in your PATH
- Python dependencies for InsightFace detection:
  ```bash
  pip install insightface opencv-python onnxruntime
  ```
- The `antelopev2` InsightFace model pack is downloaded automatically on first run to `~/.cache/models/insightface/`.

### Setup

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/face-mosaic
   ```

2. Prepare a video file to redact.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload the video and optionally override `mode` / `block_scale` / `radius` / `frame_rate` / `min_confidence`
   - Click "Run Workflow"

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"mode": "pixelate", "block_scale": 0.08, "frame_rate": 30};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "mode": "pixelate",
     "block_scale": 0.08,
     "frame_rate": 30
   }'
   ```

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | Yes | - | Input video to redact |
| `mode` | string | No | `pixelate` | Mosaic algorithm: `pixelate` or `blur` |
| `block_scale` | number | No | `0.1` | Pixelate block size relative to each face's shorter side (0.0 – 1.0). Adapts automatically — small faces get a proportionally finer block than large ones. Used when `mode: pixelate` |
| `radius` | number | No | `8.0` | Blur radius in pixels. Used when `mode: blur` |
| `min_confidence` | number | No | `0.5` | Minimum face-detection confidence (0.0 – 1.0). Passed as InsightFace's `det_thresh`. Lower it (e.g. `0.3`) if any face is still missed — for redaction, extra false positives are safer than misses |
| `frame_rate` | number | No | `30` | Output frame rate. Set to the source's true fps to avoid audio drift |

## Component Details

### Storage (`storage`)
- **Type**: `file-store`
- **Driver**: `local`
- **Function**: Persists the uploaded video under `./storage/uploads/<task_id>` so the audio branch and the frame extractor can each open it independently. The raw upload stream is single-use, so without this step whichever job read it first would consume it.

### Audio Extractor (`audio-extractor`)
- **Type**: `audio-extractor`
- **Driver**: `ffmpeg`
- **Function**: Reads the stored video and splits the audio track out into an mp3. Used later by the encoder to mux the audio back into the redacted video.

### Frame Extractor (`frame-extractor`)
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **Function**: Streams every frame (`frame_interval: 1`) as ffmpeg decodes it. `streaming: true` means the extractor never buffers the whole video — each `{image, timestamp}` chunk flows directly into the `for-each` job below.

### Face Detector (`face-detector`)
- **Type**: `model` — `face-detection` task
- **Driver**: `custom` (InsightFace family, `antelopev2` pack)
- **Function**: Returns `{faces: [{bounding_box: {x, y, width, height}, score, ...}], width, height}` for each frame. Only `bounding_box` is used downstream. Chosen over BlazeFace because it holds up on profile / small / off-frontal faces, which redaction workflows care about most.

### Mosaic (`mosaic`)
- **Type**: `image-processor` (`mosaic` method)
- **Driver**: `native`
- **Function**: Applies the mosaic to every region in one pass. `region` accepts either a single `{x, y, width, height}` dict or a list of them, and `${jobs.detect.output.faces[*].bounding_box}` projects the detector's faces straight into that shape.

### Per-Frame Wrapper (`mosaic-faces-in-frame`)
- **Type**: `workflow` (invokes the private `mosaic-faces-in-frame` sub-workflow)
- **Function**: Lets the main workflow's `for-each` call a two-step (detect + mosaic) pipeline as if it were one component.

### Encoder (`encoder`)
- **Type**: `video-encoder`
- **Driver**: `ffmpeg`
- **Function**: Encodes the redacted frame stream into an mp4 (`libx264 @ 8M`) and muxes the extracted audio (`aac @ 192k`). Accepts a stream input, so ffmpeg pulls frames as it is ready for them.

## Notes and Tuning

- **Cost**: Face detection runs on every frame. A 10-second 30 fps clip = 300 detector invocations. InsightFace's SCRFD detector is heavier than BlazeFace but still fast (tens of ms per frame on CPU, faster with CoreML / CUDA). Total wall time scales linearly with frame count.
- **Concurrency**: `batch_size: 4` on the `for-each` job runs up to 4 detect+mosaic pipelines concurrently. Raise it to trade memory for throughput; lower it if the model component becomes a bottleneck under contention.
- **Frame rate**: If the source and output frame rates differ, the audio and video will drift. Pass the source's true fps as `frame_rate`.
- **Missed faces**: Lower `min_confidence` (e.g. `0.3`) if any face is still missed — extra false positives just get mosaicked too, which is the correct trade-off for redaction. For very small faces, raise `params.detection_size` on `face-detector` (e.g. `[960, 960]` or `[1280, 1280]`) — the detector runs on that input resolution so bigger sizes recover more small faces at the cost of throughput.
- **Redaction strength**: For `pixelate`, larger `block_scale` obscures more aggressively (typical values `0.05`–`0.2`). The block size is computed from each region's shorter side, so the same `block_scale` gives visually consistent strength across near and far faces. The computed block is clamped to `min_block_size` (default `8`) on the low end so tiny faces still get a visible mosaic instead of a 1–2 pixel block, and to `max_block_size` (default `32`) on the high end so large close-up faces do not turn into pixel-art-sized tiles — raise or lower either end if the extremes still look off. Prefer the absolute `block_size` field (in the mosaic component config) only when you specifically want a fixed pixel size regardless of region size. For `blur`, raise `radius` (typical values 8–20). Blur can leave faint outlines at low radii — prefer `pixelate` when the face must be fully unrecognizable.
- **Overlapping faces**: When boxes overlap, later regions mosaic the already-mosaicked pixels of earlier ones, so overlapping faces still stay redacted.
- **Padding the box**: Face detectors sometimes crop tight around the eyes/nose and leave hair/chin exposed. Set `bounding_box_padding` on `face-detector` (e.g. `0.2`) to expand each returned box by 20% on every side before it flows into the mosaic.
