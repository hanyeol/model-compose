# NSFW Mosaic Example

This example demonstrates a workflow that redacts NSFW regions in a video by pixelating (or blurring) each detected bounding box, then reassembles the redacted frames back into an mp4 — preserving the original audio track. It is intended for content moderation: given a video that may contain explicit material, produce a version that is safe to display or share.

The pipeline runs end-to-end in streaming mode, so memory stays bounded regardless of clip length.

> **Bring your own model**: this example does not download any NSFW weights. You must supply a YOLO-format detector trained on NSFW classes at `./models/nsfw_detector.pt`. See [Preparing the detector model](#preparing-the-detector-model) below.

> **Use responsibly**: the intent here is one-way redaction of adult content in videos you already have the right to process (moderation queues, legal review, personal libraries). Do not use it to profile or surveil people, or against content you have no right to inspect. Detection is not perfect — assume some regions will be missed, especially at low resolution, motion blur, or unusual angles, and pair with a human review step if the downstream use is safety-critical.

## Overview

Given an input video, the workflow returns a version of the same video with every NSFW region obscured by a mosaic effect.

The strategy is:

1. **Fan the upload stream out** with a `fan-out` job into two independent branches, one for the audio extractor and one for the frame extractor, so both can drain the single-use upload stream in parallel without landing the video on disk.
2. **Split the audio track** out of the video with `audio-extractor` (preserved unchanged).
3. **Stream every frame** out of the video with `video-frame-extractor` (`streaming: true` — no full-video buffering).
4. **Run object-tracking on the frame stream** with `streaming: true`, configured to emit a stream of per-frame detection chunks that each carry the source image plus the detected NSFW bounding boxes. Track segments, aggregate track metadata, and the terminal metadata chunk are all suppressed — the mosaic step only needs the per-frame detections.
5. **For each per-frame chunk**, apply the mosaic to every detected region's bounding box in one pass with an inline `accumulate` step. If a frame has no detections the accumulator falls through unchanged.
6. **Encode the redacted frame stream** back into an mp4 with `video-encoder`, muxing the extracted audio into the output. ffmpeg pulls frames from the upstream stream as it is ready for them, so no full-video buffering happens at this stage either.

### Why streaming matters

The naive design would materialise every frame in memory, run detection on the whole list, then hand the redacted list to the encoder. That works for short clips but blows up memory on longer videos (a 1080p 30 fps 10-minute clip = 18,000 frames × ~6 MB decoded = ~110 GB of PIL images).

With streaming end-to-end, at most `batch_size` frames are in flight through the mosaic step at once, and the encoder consumes each redacted frame as it arrives. Memory stays bounded regardless of clip length.

### Why object-tracking (not bare object-detection)

Object-tracking is used purely as a per-frame detector-plus-carrier here — the identity information (`track_id`, segments) is not needed for redaction, and those chunk types are all disabled. There are two reasons to use the tracker anyway:

- **Per-frame chunks bundle the source image**. Each `{type: "detection", ...}` chunk already carries the frame's `image` alongside its `objects`, so the mosaic step needs a single `for-each` — one iteration per frame — instead of the two-step detect-then-accumulate pipeline a bare `object-detection` component would force (which would leave the source image on a separate stream that then needs to be zipped up frame-by-frame).
- **Gap interpolation catches short misses**. When the underlying detector fails on one or two frames between two hits, the tracker fills the gap with an interpolated bounding box on the missed frame's `objects` list, so redaction covers those otherwise-uncovered frames too. The gap-fill window is `params.merge_gap` seconds (default `0.5`).

Detection chunks are emitted only after `merge_gap` seconds have passed so the interpolation window has a chance to close — this adds a small streaming latency but is the mechanism that makes the gap-fill work. `params.min_frame_count` is **not** applied to detection chunks (only to confirmed tracks in the non-streaming result), so 1-frame detections still reach the mosaic step. For redaction this is the correct trade-off: false positives just get mosaicked too, which is far safer than misses.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- FFmpeg installed and available in your PATH
- Python dependencies for Ultralytics YOLO tracking:
  ```bash
  pip install ultralytics lap
  ```

### Preparing the detector model

You need a YOLO-format (`.pt`) detector trained to locate NSFW regions. The recommended default is **NudeNet v3.4 640m** — a YOLOv8m detector with 18 anatomical classes (both exposed and covered variants), trained by [notAI-tech](https://github.com/notAI-tech/NudeNet) and licensed under AGPL-3.0.

Download it from the [Hugging Face mirror](https://huggingface.co/vladmandic/nudenet) (the mirror is used because GitHub release downloads for this repo can redirect to a login page):

```bash
curl -fL -o models/nsfw_detector.pt \
  https://huggingface.co/vladmandic/nudenet/resolve/main/nudenet-v34-640m.pt
```

Verify the file is ~52 MB, not a few KB of HTML — if `file models/nsfw_detector.pt` reports `Zip archive data` the download is good.

Any Ultralytics-compatible `.pt` weights whose class labels correspond to NSFW regions will work here — swap in your own by editing `nsfw-tracker.model.path` in `model-compose.yml`. A faster (but less accurate) option is the same repo's 320n variant (`nudenet-v34-320n.pt`, ~6 MB).

**Class selection.** Every YOLO model exposes its own class-name list. The example's `labels:` list under the `nsfw-tracker` component restricts detection to `FEMALE_GENITALIA_EXPOSED` and `MALE_GENITALIA_EXPOSED` — edit this list to broaden or narrow coverage. Unknown class names raise a clear error at load time with the available list.

### Setup

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/nsfw-mosaic
   ```

2. Place your detector weights at `./models/nsfw_detector.pt` (see above).

3. Prepare a video file to redact.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload the video and optionally override `mode` / `block_scale` / `blur_radius` / `frame_rate` / `min_confidence`
   - Click "Run Workflow"

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"mode": "pixelate", "block_scale": 0.1, "frame_rate": 30};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "mode": "pixelate",
     "block_scale": 0.1,
     "frame_rate": 30
   }'
   ```

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | Yes | - | Input video to redact |
| `mode` | string | No | `pixelate` | Mosaic algorithm: `pixelate` or `blur` |
| `block_scale` | number | No | `0.1` | Pixelate block size relative to each region's shorter side (0.0 – 1.0). Adapts automatically — small regions get a proportionally finer block than large ones. Used when `mode: pixelate` |
| `blur_radius` | number | No | `8.0` | Blur radius in pixels. Used when `mode: blur` |
| `min_confidence` | number | No | `0.35` | Minimum detection confidence (0.0 – 1.0). Lower it (e.g. `0.2`) to catch more borderline regions — for redaction, extra false positives are safer than misses |
| `bounding_box_padding` | number | No | `0.1` | Ratio each detected box is expanded outward before mosaic. A small pad (e.g. `0.1` = 10 %) hides tight-crop edges where a pixel or two of the original region can leak past the box |
| `merge_gap` | number | No | `0.5` | Seconds of missed detections the tracker will interpolate across (also the streaming-latency floor for detection chunks). Raise it to bridge longer detector dropouts at the cost of extra buffering; lower it if latency matters more than gap-fill |
| `frame_rate` | number | No | `30` | Output frame rate. Set to the source's true fps to avoid audio drift |

## Component Details

### Audio Extractor (`audio-extractor`)
- **Type**: `audio-extractor`
- **Driver**: `ffmpeg`
- **Function**: Reads a video stream and splits the audio track out into an mp3. Fed by one branch of the upstream `fan-out` job so it can consume the upload stream in parallel with the frame extractor. Used later by the encoder to mux the audio back into the redacted video.

### Frame Extractor (`frame-extractor`)
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **Function**: Streams every frame (`frame_interval: 1`) as ffmpeg decodes it. `streaming: true` means the extractor never buffers the whole video — each frame flows directly into the tracker below.

### NSFW Tracker (`nsfw-tracker`)
- **Type**: `model` — `object-tracking` task
- **Driver**: `custom` (Ultralytics YOLO family)
- **Function**: Consumes the frame stream and emits a stream of per-frame detection chunks shaped like `{type: "detection", number, timestamp, objects: [{track_id, label, bounding_box}], image}`. The tracker's other chunk types are all suppressed here: `return_tracks: false` drops per-segment and per-track chunks, and `return_metadata: false` drops the terminal `metadata` chunk. `return_frame_image: true` bundles the source image into every detection chunk so the mosaic step needs no separate frame stream to zip against. `max_concurrent_count: 1` serialises the GPU-side work; the outer `for-each` still fans out CPU-side mosaic work across frames.

### Mosaic (`mosaic`)
- **Type**: `image-processor` (`mosaic` method)
- **Driver**: `native`
- **Function**: Applies the mosaic to one bounding box. Called once per detection by the inline `accumulate` step.

### Encoder (`encoder`)
- **Type**: `video-encoder`
- **Driver**: `ffmpeg`
- **Function**: Encodes the redacted frame stream into an mp4 (`libx264 @ 8M`) and muxes the extracted audio (`aac @ 192k`). Accepts a stream input, so ffmpeg pulls frames as it is ready for them.

## Notes and Tuning

- **Cost**: NSFW detection runs on every frame. A 10-second 30 fps clip = 300 detector invocations. YOLO is fast (tens of ms per frame on CPU, faster with CUDA / CoreML), so wall time scales linearly with frame count.
- **Concurrency**: `batch_size: 16` on the outer `for-each` runs up to 16 per-frame mosaic pipelines concurrently. Raise it to trade memory for throughput; lower it if the mosaic becomes a bottleneck under contention.
- **Frame rate**: If the source and output frame rates differ, the audio and video will drift. Pass the source's true fps as `frame_rate`.
- **Missed regions**: Lower `min_confidence` (e.g. `0.2`) if any region is still missed — extra false positives just get mosaicked too, which is the correct trade-off for redaction. If regions are consistently missed at small scale, retrain or swap the detector for a larger YOLO variant.
- **Gap-fill window**: `merge_gap` controls both the interpolation window (how many seconds of missed detections the tracker will bridge) and the minimum streaming latency of detection chunks (chunks are held for that long so interpolation can complete). The default `0.5` s bridges a couple of missed frames at 30 fps; raise it (e.g. `1.0`) if the detector regularly drops longer runs, but be aware that this delays every downstream frame by the same amount.
- **Class selection**: Edit the `labels:` list under the `nsfw-tracker` component to broaden or narrow the classes that get mosaicked (defaults to `FEMALE_GENITALIA_EXPOSED` and `MALE_GENITALIA_EXPOSED`). Class names depend on your weights — check the model's labels list; unknown names raise a clear error at load time.
- **Redaction strength**: For `pixelate`, larger `block_scale` obscures more aggressively (typical values `0.05`–`0.2`). The block size is computed from each region's shorter side, so the same `block_scale` gives visually consistent strength across small and large regions. For `blur`, raise `blur_radius` (typical values 8–20). Blur can leave faint outlines at low radii — prefer `pixelate` when the region must be fully unrecognisable.
- **Overlapping regions**: When boxes overlap, later regions mosaic the already-mosaicked pixels of earlier ones, so overlapping detections still stay redacted.
- **Padding the box**: Detector boxes can crop tight and leak a pixel or two of the original region at the edges. The `bounding_box_padding` parameter (default `0.1` = 10 %) expands each returned box on every side before it flows into the mosaic — raise it if you still see edge leakage, lower it if the pad is bleeding into unrelated content.
- **Frames with no detections**: A clean frame contains zero detections, so the inline `accumulate` step's input list is empty and the accumulator falls through unchanged — the original frame is what reaches the encoder. No special-casing needed at the workflow level.
