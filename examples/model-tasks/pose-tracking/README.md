# Pose Tracking Model Task Example

This example demonstrates how to track human poses across a video's frames using YOLOv8-pose via model-compose's built-in `pose-tracking` task. Frames are sampled from an uploaded video at a fixed interval, run through detection + a ByteTrack / BoT-SORT tracker, and grouped so each person keeps a stable `track_id` across frames — yielding a per-person segment report with timecoded segments and the representative pose from each segment's best-scoring frame.

## Overview

This workflow provides local pose tracking that:

1. **Local Pose Tracking Model**: Runs Ultralytics YOLOv8-pose locally without external APIs
2. **Frame Sampling**: Extracts frames from the input video at a user-controlled interval with ffmpeg
3. **Identity Tracking**: Uses YOLO's built-in tracker (ByteTrack or BoT-SORT) to keep the same person on a stable `track_id` across frames
4. **Segments**: Aggregates per-frame timestamps into merged `start_time / end_time / duration` segments per person
5. **Representative Pose**: Each segment carries the keypoints (and optionally the skeleton image) of its highest-scoring frame
6. **Automatic Model Management**: Downloads the YOLOv8-pose checkpoint on first run into `~/.cache/models/ultralytics` and reuses it thereafter

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- ffmpeg installed and available in your PATH (for frame extraction)
- Sufficient system resources to run ultralytics (recommended: 4GB+ RAM)
- Python environment with `ultralytics` and `lap` (installed automatically on first run)

### Why YOLO for Tracking

Unlike face tracking, human pose has no identity embedding by default. Instead, this task relies on YOLO's built-in trackers (ByteTrack / BoT-SORT), which associate frames by motion + IoU. That means:

- Stable identities work well when a person stays in view frame-to-frame
- Long occlusions or a person leaving and re-entering the frame will typically be assigned a new `track_id`
- To stitch tracks across long gaps, post-process with an appearance model of your own

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/pose-tracking
   ```

2. No additional environment configuration required — the model and dependencies are managed automatically.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "frame_interval": 5, "sampled_frame_rate": 6.0}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` file
   - Adjust `frame_interval` / `sampled_frame_rate` / `tracker` / `min_confidence` if desired
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 5, "sampled_frame_rate": 6.0}'
   ```

## Component Details

### Frame Extractor Component
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **Purpose**: Sample frames from the input video at a fixed cadence and stream them to the tracker as bare images
- **Key knob**: `frame_interval` (1 = every frame, 5 = every 5th frame, etc.)
- **Streaming**: On. The extractor's per-chunk shape is `{image, timestamp, number, ...}`; `output: ${result[].image}` projects each chunk down to just the `image` so downstream consumers see a bare image stream. Frames flow to pose-tracking as ffmpeg produces them, so long videos never buffer whole.

### Pose Tracking Model Component
- **Type**: Model component with `pose-tracking` task
- **Family**: `yolo`
- **Model**: `yolov8n-pose.pt` (downloaded from the Ultralytics release on first run)
- **Features**:
  - Detects poses per frame and assigns each detection a tracker id via ByteTrack / BoT-SORT
  - Aggregates same-id detections into per-track segments (`start_time / end_time / duration`) in H:MM:SS.mmm timecode form
  - Emits COCO 17-point keypoints and, optionally, OpenPose BODY_18 keypoints and a rendered skeleton image
  - Serial execution (`max_concurrent_count: 1`) to keep GPU memory bounded and tracker state coherent

### Model Information: YOLOv8-pose (Ultralytics)
- **Developer**: Ultralytics
- **Task**: Multi-person pose estimation
- **Keypoints**: 17 (COCO layout)
- **Tracker**: ByteTrack (default) or BoT-SORT via the ultralytics `.track()` API
- **License**: AGPL-3.0

## Workflow Details

### Default Workflow

**Description**: Sample frames from an uploaded video, run pose tracking, and return per-person segments.

#### Job Flow

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[{image, timestamp, ...}]| J1

    J1 --> J2((track<br/>job))
    J2 --> C2[Pose Tracker<br/>yolo]
    C2 -.-> |{tracks, frame_count}| J2

    J2 --> Output((Output<br/>report))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | Yes | - | Input video file |
| `frame_interval` | number | No | 5 | Sample every Nth frame at extraction time |
| `sampled_frame_rate` | number | No | 6.0 | Frames-per-second of the *sampled* sequence, used to derive per-frame timestamps. Set this to `source_fps / frame_interval` |
| `tracker` | string | No | `bytetrack` | Underlying ultralytics tracker: `bytetrack` (default, fast) or `botsort` (slightly better under occlusion, uses more compute) |
| `min_confidence` | number | No | 0.4 | Minimum YOLO detection confidence (0.0 - 1.0). Detections below this score never reach the tracker |
| `min_frame_count` | number | No | 3 | Discard tracks that appear in fewer than this many sampled frames |
| `merge_gap` | number | No | 1.0 | Merge adjacent segments separated by less than this many seconds |
| `return_keypoints` | boolean | No | true | Return the representative frame's 17 COCO keypoints per segment |
| `return_openpose_keypoints` | boolean | No | false | Return the representative frame's OpenPose BODY_18 keypoints per segment |
| `return_skeleton_image` | boolean | No | false | Render a skeleton image on a black canvas for each segment's representative frame |
| `skeleton_format` | string | No | `natural` | Skeleton layout: `natural` (COCO 17-point) or `openpose` (BODY_18, ControlNet-ready) |

Note: the tracker is fed at the *sampled* fps, not the source fps. If you set `frame_interval=5` on a 30 fps source, use `sampled_frame_rate=6.0`. A wrong value doesn't break tracking but shifts all reported timestamps proportionally.

#### Output Format

`report` is a JSON object with:

| Field | Type | Description |
|-------|------|-------------|
| `tracks` | array | One entry per tracker-assigned identity. See below. |
| `frame_count` | integer | Total number of sampled frames analyzed |

Each `tracks[i]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `track_id` | integer | The tracker's assigned id for this person. Stable within a single tracking run but not portable across runs. |
| `segments` | array | List of `{start_time, end_time, duration, score, bounding_box, ...}`. See below. |
| `frame_count` | integer | Number of sampled frames this track appeared in |
| `score` | number | Highest detection confidence across all frames in this track |

Each `segments[j]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | string | Segment start in `H:MM:SS.mmm` timecode |
| `end_time` | string | Segment end in `H:MM:SS.mmm` timecode |
| `duration` | string | `end_time - start_time` in `H:MM:SS.mmm` timecode |
| `score` | number | Detection confidence of the representative frame for this segment (the highest-scoring frame within the segment) |
| `bounding_box` | object | `{x, y, width, height}` in pixel coordinates, from the representative frame |
| `keypoints` | array | 17 COCO keypoints `{x, y, visibility}` from the representative frame. Present only when `return_keypoints` is enabled |
| `openpose_keypoints` | array | OpenPose BODY_18 keypoints from the representative frame. Present only when `return_openpose_keypoints` is enabled |
| `skeleton_image` | image | PNG-encoded skeleton on a black canvas (layout determined by `skeleton_format`). Present only when `return_skeleton_image` is enabled |

Example (with `return_keypoints: false`, `return_skeleton_image: false`):

```json
{
  "report": {
    "tracks": [
      {
        "track_id": 1,
        "segments": [
          { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "duration": "0:00:06.500", "score": 0.92, "bounding_box": { "x": 240, "y": 90, "width": 180, "height": 460 } },
          { "start_time": "0:00:14.000", "end_time": "0:00:17.000", "duration": "0:00:03.000", "score": 0.87, "bounding_box": { "x": 210, "y": 80, "width": 200, "height": 470 } }
        ],
        "frame_count": 21,
        "score": 0.92
      }
    ],
    "frame_count": 40
  }
}
```

### Rendering ControlNet-Ready Skeleton Images

Set `return_skeleton_image: true` and `skeleton_format: openpose` to get a BODY_18 skeleton image per segment, drawn with the standard OpenPose palette. Piping the flattened `skeleton_images` list into a downstream image processor / ControlNet component gives you a per-segment pose reference without redoing detection.

```bash
model-compose run --input '{
  "video": "/path/to/clip.mp4",
  "return_skeleton_image": true,
  "skeleton_format": "openpose"
}'
```

## System Requirements

### Minimum Requirements
- **RAM**: 4GB (recommended 8GB+)
- **Disk Space**: ~10MB for the `yolov8n-pose.pt` checkpoint (larger for `s / m / l / x` variants)
- **CPU**: Any modern x86_64 or ARM64 processor
- **Internet**: Required for the one-time model download

### Performance Notes
- Detection cost scales with the number of sampled frames — pick `frame_interval` so the sampled fps covers the shortest segment you want to catch (e.g. sample at 6 fps to catch segments ≥ 0.5 s cleanly)
- The tracker needs enough temporal density to associate detections; if `sampled_frame_rate` drops too low (e.g. < 2 fps) the same person may repeatedly be assigned a new `track_id`
- GPU (CUDA / MPS) significantly improves throughput
- First run downloads the checkpoint and initializes the tracker — subsequent runs are faster

## Customization

### Sampling More Densely

Lower `frame_interval` and raise `sampled_frame_rate` accordingly. For a 30 fps source, sampling every 2nd frame gives 15 fps:

```bash
model-compose run --input '{"video": "clip.mp4", "frame_interval": 2, "sampled_frame_rate": 15.0}'
```

Denser sampling improves track stability (fewer id swaps) at the cost of runtime.

### Swapping Tracker

BoT-SORT applies re-identification-style features and Kalman-filter improvements over ByteTrack. It's slightly heavier but usually keeps ids more stable through short occlusions:

```bash
model-compose run --input '{"video": "clip.mp4", "tracker": "botsort"}'
```

Both trackers use ultralytics' default `bytetrack.yaml` / `botsort.yaml` configs. To tune tracker parameters (association thresholds, buffer size, etc.), drop a custom YAML at the same name in your working directory — ultralytics picks it up automatically.

### Using a Higher-Accuracy Variant

Point `model.url` (or `model.path` for a locally downloaded file) at a heavier YOLOv8-pose checkpoint:

```yaml
components:
  - id: pose-tracker
    model:
      provider: local
      url: https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8m-pose.pt
```

Available variants (accuracy ↑, speed ↓): `yolov8n-pose`, `yolov8s-pose`, `yolov8m-pose`, `yolov8l-pose`, `yolov8x-pose`.

### Filtering Weak Tracks

Raise `min_frame_count` to drop tracks that only show up in a handful of sampled frames — usually noise or a person briefly walking through the edge of the frame:

```bash
model-compose run --input '{"video": "clip.mp4", "min_frame_count": 10}'
```

### Materialized Frame List (non-streaming)

This example runs the extractor in streaming mode. If you'd rather materialize the full frame list first (e.g. to inspect it in a `for-each` job or persist to disk), drop `streaming` and switch the projection to `[*]`:

```yaml
- id: frame-extractor
  type: video-frame-extractor
  driver: ffmpeg
  action:
    video: ${input.video}
    frame_interval: ${input.frame_interval}
    streaming: false
    output: ${result[*].image}
```

`pose-tracking` handles both materialized lists and async iterators transparently.

## Troubleshooting

### Common Issues

1. **`frame_rate` mismatch**: If timecodes look off, verify `sampled_frame_rate` matches `source_fps / frame_interval`. A wrong value doesn't break tracking but shifts all reported timestamps proportionally.
2. **No tracks returned**: Raise the sampling rate (lower `frame_interval`), lower `min_frame_count`, or lower `min_confidence` — the person may only appear in a single sampled frame or be detected below threshold.
3. **Same person split into multiple tracks**: Raise `sampled_frame_rate` (denser sampling) or try `tracker: botsort`. Long occlusions will still trigger a new id — the built-in trackers don't do appearance-based re-id across large gaps.
4. **Two people merged into one track**: Rare with ByteTrack / BoT-SORT, but can happen when two people cross tightly. Denser sampling and BoT-SORT help.
5. **`lap` install fails**: `lap` is a C-extension used by the trackers. On macOS you may need Xcode command-line tools (`xcode-select --install`); on Linux, a `gcc` toolchain.

### Performance Optimization

- **GPU**: Install a CUDA / MPS build of PyTorch that matches your hardware — ultralytics uses whatever `torch` finds
- **Model Size**: `yolov8n-pose` is the fastest; step up only if the small variant misses subjects (e.g. small figures in the background)
- **Sample Rate**: The single biggest lever — halving the sampled fps roughly halves runtime, but too-sparse sampling degrades id stability

## Related Examples

- `pose-detection`: Single-image pose estimation (no tracking, no video) with the same BlazePose / YOLO families
- `face-tracking`: The identity-embedding-based counterpart for faces
