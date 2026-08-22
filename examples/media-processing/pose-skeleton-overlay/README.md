# Pose Skeleton Overlay Example

This example demonstrates a workflow that detects and tracks every person in a video with YOLOv8-pose, renders a skeleton on top of each pose in every frame, and reassembles the overlaid frames back into an mp4 — preserving the original audio track. The whole pipeline runs end-to-end in streaming mode, so memory stays bounded regardless of clip length.

> **License note**: This example auto-downloads Ultralytics' YOLOv8-pose weights, which are released under **AGPL-3.0**. Personal use, research, and open-source demos are fine. For commercial use, either comply with AGPL-3.0 (open-sourcing the whole system) or obtain an Ultralytics Enterprise License — see [ultralytics.com/license](https://www.ultralytics.com/license).

## Overview

Given an input video, the workflow returns a version of the same video with a coloured skeleton drawn over every detected person's pose in every frame.

The strategy is:

1. **Stash the uploaded video** on a local `file-store` so the audio branch and the frame extractor can each re-read it (the raw upload stream is single-use).
2. **Split the audio track** out of the stored video with `audio-extractor` (preserved unchanged).
3. **Stream every frame** out of the stored video with `video-frame-extractor` (`streaming: true` — no full-video buffering).
4. **Run pose-tracking on the frame stream** with `streaming: true`, configured to emit a stream of per-frame chunks that each carry the source image plus one full-frame skeleton PNG per detected pose. Track segments, aggregate track metadata, and the terminal metadata chunk are all suppressed — the overlay step only needs frames.
5. **For each per-frame chunk**, `merge` composites the source frame with every pose's skeleton image in one pass. The `for-each` job's output is also a stream, so overlaid frames flow lazily to the encoder.
6. **Encode the overlaid frame stream** back into an mp4 with `video-encoder`, muxing the extracted audio into the output. ffmpeg pulls frames from the upstream stream as it is ready for them, so no full-video buffering happens at this stage either.

### Why streaming matters

The naive design would materialise every frame in memory, run detection on the whole list, then hand the overlaid list to the encoder. That works for short clips but blows up memory on longer videos (a 1080p 30 fps 10-minute clip = 18,000 frames × ~6 MB decoded = ~110 GB of PIL images).

With streaming end-to-end, at most `batch_size` frames are in flight through the overlay step at once, and the encoder consumes each overlaid frame as it arrives. Memory stays bounded regardless of clip length.

### Why pose-tracking (not bare detection)

Pose-tracking is used purely as a per-frame detector-plus-renderer here — track identity is not required for the overlay, and those chunk types are all disabled. The reason to use the tracker anyway is that its per-frame chunk already packages the source image (`return_frame_image: true`) alongside one full-frame skeleton PNG per detected pose (`return_skeleton_image: true`). Each skeleton PNG is rendered at the source frame's own resolution with a transparent background, so the merge step just alpha-composites the whole stack — no per-pose x/y math needed. A bare detector would only emit keypoints, forcing the workflow to draw the skeleton itself.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- FFmpeg installed and available in your PATH
- Python dependencies for YOLO pose detection:
  ```bash
  pip install ultralytics lap
  ```
- The YOLOv8n-pose weights are downloaded automatically on first run into model-compose's model cache.

### Setup

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/pose-skeleton-overlay
   ```

2. Prepare a video file to overlay.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload the video and optionally override `frame_rate` / `min_confidence` / `skeleton_format`
   - Click "Run Workflow"

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"frame_rate": 30, "min_confidence": 0.4, "skeleton_format": "natural"};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "frame_rate": 30,
     "min_confidence": 0.4,
     "skeleton_format": "natural"
   }'
   ```

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | Yes | - | Input video to overlay |
| `min_confidence` | number | No | `0.4` | Minimum pose-detection confidence (0.0 – 1.0). Lower it (e.g. `0.25`) if any person is still missed |
| `skeleton_format` | string | No | `natural` | Skeleton layout: `natural` (COCO-17 keypoints, matches YOLO's native output) or `openpose` (BODY_18) |
| `frame_rate` | number | No | `30` | Output frame rate. Set to the source's true fps to avoid audio drift |

## Component Details

### Storage (`storage`)
- **Type**: `file-store`
- **Driver**: `local`
- **Function**: Persists the uploaded video under `./storage/uploads/<task_id>` so the audio branch and the frame extractor can each open it independently. The raw upload stream is single-use, so without this step whichever job read it first would consume it.

### Audio Extractor (`audio-extractor`)
- **Type**: `audio-extractor`
- **Driver**: `ffmpeg`
- **Function**: Reads the stored video and splits the audio track out into an mp3. Used later by the encoder to mux the audio back into the overlaid video.

### Frame Extractor (`frame-extractor`)
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **Function**: Streams every frame (`frame_interval: 1`) as ffmpeg decodes it. `streaming: true` means the extractor never buffers the whole video — each frame flows directly into the tracker below.

### Pose Tracker (`pose-tracker`)
- **Type**: `model` — `pose-tracking` task
- **Driver**: `custom` (YOLO family, `yolov8n-pose.pt` weights)
- **Function**: Consumes the frame stream and emits a stream of per-frame chunks shaped like `{type: "frame", number, timestamp, poses: [{track_id, bounding_box, skeleton_image}], image}`. `return_frame_image: true` bundles the source image into every frame chunk, and `return_skeleton_image: true` renders one transparent-background skeleton PNG at the source resolution for every detected pose. The tracker's other chunk types are suppressed: `return_tracks: false` drops per-segment and per-track chunks, and `return_metadata: false` drops the terminal `metadata` chunk.

### Skeleton Merger (`skeleton-merger`)
- **Type**: `image-processor` (`merge` method)
- **Driver**: `native`
- **Function**: Alpha-composites every image in the input list onto a shared canvas sized to the largest input. Since the skeleton renders are the same resolution as the source frame, everything lines up 1:1 — the source frame goes first as the base layer, then each pose's skeleton PNG is stacked on top in one pass.

### Encoder (`encoder`)
- **Type**: `video-encoder`
- **Driver**: `ffmpeg`
- **Function**: Encodes the overlaid frame stream into an mp4 (`libx264 @ 8M`) and muxes the extracted audio (`aac @ 192k`). Accepts a stream input, so ffmpeg pulls frames as it is ready for them.

## Notes and Tuning

- **Cost**: Pose detection runs on every frame, and one skeleton PNG is rendered per detected pose per frame. A 10-second 30 fps clip = 300 detector invocations; wall time scales linearly with frame count. YOLOv8n-pose is the smallest and fastest weight — swap for `yolov8s/m/l/x-pose.pt` (larger, more accurate) if precision matters more than latency.
- **Concurrency**: `batch_size: 8` on the `for-each` job runs up to 8 merge pipelines concurrently. Raise it to trade memory for throughput; lower it if the merge component becomes a bottleneck under contention.
- **Frame rate**: If the source and output frame rates differ, the audio and video will drift. Pass the source's true fps as `frame_rate`.
- **Missed poses**: Lower `min_confidence` (e.g. `0.25`) if any person is still missed. Very small / distant people may still be dropped by the underlying detector — swap in a larger YOLO weight for better recall.
- **Skeleton style**: `skeleton_format: natural` uses COCO-17 keypoints (matches what YOLO natively outputs); `openpose` converts to the BODY_18 layout common in downstream pose-editing tools like ControlNet. Pick `openpose` if you plan to feed the output into an OpenPose-conditioned diffusion pipeline.
- **Interpolated frames**: When the detector misses a pose in one frame but recatches it in a nearby frame (within `merge_gap`), the tracker fills the gap with an interpolated bounding box and skeleton so the overlay stays visually smooth across brief detection dropouts. Interpolated poses are tagged with `interpolated: true` on the chunk but are otherwise treated the same by the overlay pipeline.
