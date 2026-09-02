# Object Tracking Model Task Example

This example demonstrates how to track objects across a video's frames using Ultralytics YOLO via model-compose's built-in `object-tracking` task. Frames are sampled from an uploaded video at a fixed interval, run through YOLO detection plus the built-in tracker (ByteTrack / BoT-SORT), and grouped so the same object keeps a stable identity across frames — yielding a per-object segment report with timecoded segments, labels, and best-frame bounding boxes.

## Overview

This workflow provides local object tracking that:

1. **Local YOLO Model**: Runs an Ultralytics YOLO detection checkpoint locally without external APIs
2. **Frame Sampling**: Extracts frames from the input video at a user-controlled interval with ffmpeg
3. **Identity Tracking**: Feeds frames into YOLO's built-in tracker (ByteTrack or BoT-SORT) so each object keeps a stable `track_id` across frames
4. **Segments**: Aggregates per-frame timestamps into merged `start_time / end_time / duration` segments per object
5. **Streaming Ingestion**: The extractor streams frames to the tracker as ffmpeg produces them, so long videos never buffer whole
6. **Automatic Model Management**: Downloads and caches the default `yolov8n.pt` checkpoint on first use

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- ffmpeg installed and available in your PATH (for frame extraction)
- Sufficient system resources to run YOLO (recommended: 4GB+ RAM)
- Python environment with `ultralytics` and `lap` (installed automatically on first run)

### YOLO Model Weights

No manual preparation is required. The `model.path` in [model-compose.yml](model-compose.yml) points at `./models/yolov8n.pt`; on first run, the file is fetched from the Ultralytics release matching its filename and cached under `./models/`. Subsequent runs reuse that file.

To use a different checkpoint (e.g. a larger or fine-tuned model), either drop your `.pt` into `./models/` and point `model.path` at it, or set `model.path` to any Ultralytics preset name (`yolov8n.pt`, `yolo11n.pt`, `yolo11s.pt`, …).

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/object-tracking
   ```

2. No additional environment configuration required. The first run downloads the checkpoint automatically.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Track all COCO classes with the default yolov8n.pt
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "frame_interval": 5, "sampled_frame_rate": 6.0}'

   # Restrict to specific labels
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "labels": ["person", "car"], "min_confidence": 0.35}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` file
   - Adjust `frame_interval` / `sampled_frame_rate` / `labels` / `tracker` if desired
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
- **Streaming**: On. The extractor's per-chunk shape is `{image, timestamp, number, ...}`; `output: ${result[].image}` projects each chunk down to just the `image` so downstream consumers see a bare image stream. Frames flow to object-tracking as ffmpeg produces them, so long videos never buffer whole.

### Object Tracking Model Component
- **Type**: Model component with `object-tracking` task
- **Family**: `yolo`
- **Model**: local `./models/yolov8n.pt` (auto-downloaded on first use)
- **Features**:
  - Runs YOLO detection per frame, then feeds detections through ByteTrack or BoT-SORT to keep a stable `track_id` across frames
  - Consumes the frame stream lazily — no full-video buffering
  - Aggregates per-frame detections into per-track segments (`start_time / end_time / duration`) in H:MM:SS.mmm timecode form, with the best-frame label and bounding box per segment
  - Serial execution (`max_concurrent_count: 1`) to keep GPU memory bounded

### Model Information: yolov8n (Ultralytics)
- **Provider**: Ultralytics
- **Task**: Object detection (80-class COCO by default)
- **Size**: Nano — smallest / fastest variant of YOLOv8
- **Trackers Available**: ByteTrack (default), BoT-SORT
- **License**: AGPL-3.0 (Ultralytics)

## Workflow Details

### Default Workflow

**Description**: Sample frames from an uploaded video, run object tracking, and return per-object segments.

#### Job Flow

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[{image, timestamp, ...}]| J1

    J1 --> J2((track<br/>job))
    J2 -.-> C2[Object Tracker<br/>yolo]
    C2 -.-> |{tracks, detections}| J2

    J2 --> Output((Output<br/>report))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | Yes | - | Input video file |
| `frame_interval` | number | No | 5 | Sample every Nth frame at extraction time |
| `sampled_frame_rate` | number | No | 6.0 | Frames-per-second of the *sampled* sequence, used to derive per-frame timestamps. Set this to `source_fps / frame_interval` |
| `labels` | list[string] | No | - | Restrict detections to these class labels (e.g. `["person", "car"]`). Unknown labels fail fast. Unset returns all classes the model knows |
| `min_confidence` | number | No | 0.25 | Minimum detection confidence in `[0, 1]` |
| `min_frame_count` | number | No | 3 | Discard tracks that appear in fewer than this many sampled frames |
| `merge_gap` | number | No | 0.5 | Extra seconds an object may be undetected before its segment is split. Consecutive frames always merge |
| `tracker` | string | No | `bytetrack` | Underlying Ultralytics tracker — `bytetrack` or `botsort` |
| `return_detections` | boolean | No | true | Whether to include the frame-centric detection view (one entry per sampled frame, tagged by `track_id`) alongside `tracks` |
| `return_frame_image` | boolean | No | false | Attach the full source frame to each detection entry. Requires `return_detections: true` |

#### Output Format

`report` is a JSON object with:

| Field | Type | Description |
|-------|------|-------------|
| `tracks` | array | One entry per detected object identity (see below) |
| `detections` | array | Per-frame detection view — one entry per sampled frame, each carrying its detected objects tagged by `track_id`. Present only when `return_detections` is enabled |

Each `tracks[i]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `track_id` | integer | Tracker-assigned identity, stable across the video |
| `label` | string | Class label of the best-scoring frame (e.g. `"person"`, `"car"`) |
| `label_id` | integer | Integer class index reported by the model |
| `segments` | array | List of segments this track appears in. See below |
| `frame_count` | integer | Total sampled frames this track appeared in |
| `score` | number | Highest detection confidence across all frames in this track |

Each `segments[j]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | string | Segment start in `H:MM:SS.mmm` timecode |
| `end_time` | string | Segment end in `H:MM:SS.mmm` timecode |
| `duration` | string | `end_time - start_time` in `H:MM:SS.mmm` timecode |
| `label` | string | Class label of the segment's best-scoring frame |
| `label_id` | integer | Integer class index of the segment's best-scoring frame |
| `score` | number | Detection confidence of the segment's best-scoring frame |
| `bounding_box` | object | `{x, y, width, height}` in pixels of the segment's best-scoring frame, top-left origin |

Each `detections[k]` entry (when `return_detections` is enabled):

| Field | Type | Description |
|-------|------|-------------|
| `number` | integer | 1-based index of this sampled frame |
| `timestamp` | string | Frame timestamp in `H:MM:SS.mmm` timecode |
| `objects` | array | Detected objects in this frame, each with `track_id`, `label`, `label_id`, `bounding_box`, `score`, and optionally `interpolated: true` when the box was linearly interpolated across a gap of missing detections |
| `image` | image | The full sampled frame. Present only when `return_frame_image` is enabled |

Example (with `return_detections: false`):

```json
{
  "report": {
    "tracks": [
      {
        "track_id": 1,
        "label": "person",
        "label_id": 0,
        "segments": [
          {
            "start_time": "0:00:00.500", "end_time": "0:00:04.833", "duration": "0:00:04.333",
            "label": "person", "label_id": 0, "score": 0.91,
            "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 460 }
          }
        ],
        "frame_count": 26,
        "score": 0.91
      }
    ]
  }
}
```

## System Requirements

### Minimum Requirements
- **RAM**: 4GB (recommended 8GB+)
- **Disk Space**: ~10MB for `yolov8n.pt` (larger variants: `yolov8s.pt` ~22MB, `yolov8m.pt` ~52MB, `yolov8l.pt` ~87MB, `yolov8x.pt` ~136MB)
- **CPU**: Any modern x86_64 or ARM64 processor
- **Internet**: Required for the one-time weights download

### Performance Notes
- Detection cost scales with the number of sampled frames — pick `frame_interval` so the sampled fps covers the shortest segment you want to catch (e.g. sample at 6 fps to catch segments ≥ ~0.5 s of continuous presence)
- GPU (CUDA) significantly improves throughput; on Apple Silicon the MPS backend is used automatically when available
- First run initializes YOLO and its tracker — subsequent runs are faster
- The tracker consumes frames lazily from the extractor's stream, so peak memory does not scale with video length

## Customization

### Sampling More Densely

Lower `frame_interval` and raise `sampled_frame_rate` accordingly. For a 30 fps source, sampling every 2nd frame gives 15 fps:

```bash
model-compose run --input '{"video": "clip.mp4", "frame_interval": 2, "sampled_frame_rate": 15.0}'
```

### Switching Tracker

`bytetrack` is faster and works well for most scenes; `botsort` adds appearance features (ReID) and tends to be more robust across short occlusions:

```bash
model-compose run --input '{"video": "clip.mp4", "tracker": "botsort"}'
```

### Restricting to Specific Classes

Pass a `labels` list to keep only the classes you care about. Detections outside the list are dropped before tracking, which also speeds up processing:

```bash
model-compose run --input '{"video": "clip.mp4", "labels": ["person"], "min_confidence": 0.4}'
```

### Using a Custom Model

Replace the `model` block in `model-compose.yml` to point at any Ultralytics YOLO checkpoint. For a fine-tuned detector trained on your own dataset:

```yaml
- id: object-tracker
  type: model
  task: object-tracking
  driver: custom
  family: yolo
  model:
    provider: local
    path: /path/to/your/model.pt
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    labels: [ your_class_a, your_class_b ]
    params:
      tracker: bytetrack
      min_confidence: 0.3
```

Segmentation checkpoints (`yolo11*-seg.pt`, etc.) are also supported — only the bounding boxes are read.

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

`object-tracking` handles both materialized lists and async iterators transparently.

## Troubleshooting

### Common Issues

1. **`frame_rate` mismatch**: If timecodes look off, verify `sampled_frame_rate` matches `source_fps / frame_interval`. A wrong value doesn't break tracking but shifts all reported timestamps proportionally.
2. **No tracks returned**: Raise the sampling rate (lower `frame_interval`) or lower `min_frame_count` — the object may only appear in a couple of sampled frames.
3. **Same object split into multiple tracks**: Raise `merge_gap` if the splits are caused by short occlusions, or try `tracker: botsort` for its appearance-based re-identification.
4. **Different objects merged into one track**: Lower `merge_gap`, raise `min_confidence`, or narrow `labels` — very close bounding boxes of the same class can confuse ID assignment.
5. **Model file not found**: Verify `./models/yolov8n.pt` exists (or that `model.path` points at a valid Ultralytics preset name so first-run download can resolve).

### Performance Optimization

- **GPU**: Install PyTorch with CUDA support for a large speedup; Apple Silicon uses MPS automatically
- **Sample Rate**: The single biggest lever — halving the sampled fps roughly halves runtime
- **Label Filter**: Passing `labels` drops out-of-interest classes before tracking, reducing the number of tracks the associator has to manage
- **Model Size**: `yolov8n.pt` is the fastest; step up to `yolov8s/m/l/x` for better recall at the cost of throughput

## Related Examples

- `object-detection`: Detect objects in a single image with the same YOLO family (no tracking)
- `pose-tracking`: Track people's poses (keypoints) across a video, same streaming/segment shape
- `face-tracking`: Track faces across a video with InsightFace, embedding-based identity clustering
