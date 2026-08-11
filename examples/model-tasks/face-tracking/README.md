# Face Tracking Model Task Example

This example demonstrates how to track faces across a video's frames using InsightFace via model-compose's built-in `face-tracking` task. Frames are sampled from an uploaded video at a fixed interval, run through detection + embedding, and clustered so the same person stays grouped into a single track across frames — yielding a per-person segment report with timecoded segments.

## Overview

This workflow provides local face tracking that:

1. **Local Face Tracking Model**: Runs InsightFace's `antelopev2` model pack locally without external APIs
2. **Frame Sampling**: Extracts frames from the input video at a user-controlled interval with ffmpeg
3. **Identity Clustering**: Clusters per-frame face embeddings by cosine similarity so each unique face becomes a single track
4. **Segments**: Aggregates per-frame timestamps into merged `start_time / end_time / duration` segments per person
5. **Automatic Model Management**: Fetches the `antelopev2` pack from the InsightFace GitHub release on first run, extracts it into `./.models/antelopev2`, and reuses it thereafter

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- ffmpeg installed and available in your PATH (for frame extraction)
- Sufficient system resources to run onnxruntime (recommended: 4GB+ RAM)
- Python environment with `insightface`, `opencv-python`, and `onnxruntime` (installed automatically on first run)
- The `antelopev2` model pack placed at `./.models/antelopev2`

### Downloading the antelopev2 Model Pack

Download the model pack from InsightFace and place it under `./.models/antelopev2`:

```bash
mkdir -p .models
# Download antelopev2.zip from the InsightFace model zoo and extract it into ./.models/antelopev2
```

The expected layout is:

```
.models/
└── antelopev2/
    ├── 1k3d68.onnx
    ├── 2d106det.onnx
    ├── genderage.onnx
    ├── glintr100.onnx
    └── scrfd_10g_bnkps.onnx
```

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/face-tracking
   ```

2. No additional environment configuration required beyond placing the model pack under `./.models/antelopev2`.

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
     -F 'input={"video": "@clip", "frame_interval": 15, "sampled_frame_rate": 2.0}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` file
   - Adjust `frame_interval` / `sampled_frame_rate` / `similarity_threshold` if desired
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 15, "sampled_frame_rate": 2.0}'
   ```

## Component Details

### Frame Extractor Component
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **Purpose**: Sample frames from the input video at a fixed cadence and stream them to the tracker as bare images
- **Key knob**: `frame_interval` (1 = every frame, 15 = every 15th frame, etc.)
- **Streaming**: On. The extractor's per-chunk shape is `{image, timestamp, number, ...}`; `output: ${result[].image}` projects each chunk down to just the `image` so downstream consumers see a bare image stream. Frames flow to face-tracking as ffmpeg produces them, so long videos never buffer whole.

### Face Tracking Model Component
- **Type**: Model component with `face-tracking` task
- **Family**: `insightface`
- **Model**: local `./.models/antelopev2` pack
- **Features**:
  - Detects faces per frame and extracts a 512-d identity embedding
  - Clusters embeddings online by cosine similarity so each identity becomes a single track
  - Emits per-track segments (start/end/duration) in H:MM:SS.mmm timecode form
  - Serial execution (`max_concurrent_count: 1`) to keep GPU memory bounded

### Model Information: antelopev2 (InsightFace)
- **Provider**: InsightFace
- **Backbone**: ResNet-100 (`glintr100.onnx`)
- **Embedding Dimension**: 512
- **Detector**: SCRFD-10G (`scrfd_10g_bnkps.onnx`)
- **Normalization**: L2-normalized embeddings — cosine similarity is equivalent to a dot product
- **License**: Non-commercial research use only

## Workflow Details

### Default Workflow

**Description**: Sample frames from an uploaded video, run face tracking, and return per-person segments.

#### Job Flow

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[{image, timestamp, ...}]| J1

    J1 --> J2((track<br/>job))
    J2 --> C2[Face Tracker<br/>insightface]
    C2 -.-> |{tracks, frame_count}| J2

    J2 --> Output((Output<br/>report))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | Yes | - | Input video file |
| `frame_interval` | number | No | 15 | Sample every Nth frame at extraction time |
| `sampled_frame_rate` | number | No | 2.0 | Frames-per-second of the *sampled* sequence, used to derive per-frame timestamps. Set this to `source_fps / frame_interval` |
| `similarity_threshold` | number | No | 0.4 | Cosine similarity above which two faces are grouped into the same track |
| `min_frame_count` | number | No | 2 | Discard tracks that appear in fewer than this many sampled frames |
| `merge_gap` | number | No | 1.0 | Merge adjacent segments separated by less than this many seconds |
| `return_image` | boolean | No | true | Attach one face crop per segment, taken at the detected bounding box in the original frame's resolution. Useful for displaying the face, resizing it for a UI, or feeding it into another embedding backbone (see [Re-embedding with a Different Model](#re-embedding-with-a-different-model)). Set to `false` to trim the payload when you only need timecodes. |
| `return_gender_age` | boolean | No | false | Attach `gender` (`"male"` / `"female"`) and `age` (integer) to each track, taken from the track's highest-scoring frame. Requires a model pack that ships gender/age submodels (`antelopev2`, `buffalo_l`). |
| `bounding_box_padding` | number | No | 0.2 | Grow each face crop's bounding box by this fraction on every side (e.g. `0.2` = +20% left/right/top/bottom). Only affects the returned crop image; embeddings and clustering still use the un-padded box. Useful when the detected box is too tight (hair, chin, ears cut off) or when the crop looks blurry because the face is small in the frame. |

#### Output Format

`report` is a JSON object with:

| Field | Type | Description |
|-------|------|-------------|
| `tracks` | array | One entry per detected identity. See below. |
| `frame_count` | integer | Total number of sampled frames analyzed |

Each `tracks[i]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `embedding` | number[] | L2-normalized identity centroid (512-d for antelopev2). Suitable for direct cosine matching against an identity DB or for merging tracks that turn out to be the same person. Present only when `return_embedding` is enabled. |
| `segments` | array | List of `{start_time, end_time, duration, score}` (with `image` when `return_image` is enabled). See below. |
| `frame_count` | integer | Number of sampled frames this track appeared in |
| `score` | number | Highest detection confidence across all frames in this track. Useful for ranking or filtering tracks. |
| `gender` | string | `"male"` or `"female"`, taken from the track's highest-scoring frame. Present only when `return_gender_age` is enabled and the model pack ships a gender submodel. |
| `age` | integer | Age estimate, taken from the track's highest-scoring frame. Present only when `return_gender_age` is enabled and the model pack ships an age submodel. |

Each `segments[j]` entry:

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | string | Segment start in `H:MM:SS.mmm` timecode |
| `end_time` | string | Segment end in `H:MM:SS.mmm` timecode |
| `duration` | string | `end_time - start_time` in `H:MM:SS.mmm` timecode |
| `score` | number | Detection confidence of the representative frame for this segment (the highest-scoring frame within the segment; same frame `image` is cropped from) |
| `image` | image | Face crop from the best-scoring frame in this segment, taken at the detected bounding box in the frame's original resolution (variable size per face). Present only when `return_image` is enabled. |

Example (with `return_image: false`, `return_embedding: false`):

```json
{
  "report": {
    "tracks": [
      {
        "segments": [
          { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "duration": "0:00:06.500", "score": 0.94 },
          { "start_time": "0:00:14.000", "end_time": "0:00:17.000", "duration": "0:00:03.000", "score": 0.88 }
        ],
        "frame_count": 21,
        "score": 0.94
      }
    ],
    "frame_count": 40
  }
}
```

### Re-embedding with a Different Model

Enabling `return_image` gives you one face crop per segment — the highest-scoring frame in that segment, cropped at the detected bounding box in the frame's original resolution. Pipe those crops into a separate `face-embedding` component (or your own vision model) to obtain embeddings from a different backbone while reusing this task's detection and clustering work. The downstream component runs its own detection/alignment step on the crop, so the two embedding models stay decoupled:

```yaml
- id: track
  component: face-tracker
  input:
    frames: ${jobs.frames.output}
    frame_rate: ${input.sampled_frame_rate}
    return_image: true

- id: reembed
  component: alt-face-embedder
  # For each track, for each segment, re-embed the representative crop.
  input:
    face_image: ${jobs.track.output.tracks[*].segments[*].image}
```

The `embedding` field on each track is the running centroid of insightface's own embeddings and is always present, so downstream code can also compare tracks directly (e.g. to merge two tracks that likely represent the same person under different lighting).

## System Requirements

### Minimum Requirements
- **RAM**: 4GB (recommended 8GB+)
- **Disk Space**: ~1GB for the `antelopev2` pack
- **CPU**: Any modern x86_64 or ARM64 processor
- **Internet**: Required for the one-time model pack download

### Performance Notes
- Detection cost scales with the number of sampled frames — pick `frame_interval` so the sampled fps covers the shortest segment you want to catch (e.g. sample at 2 fps to catch segments ≥ 1 s)
- GPU (CUDA / CoreML / DirectML via onnxruntime) significantly improves throughput
- First run initializes onnxruntime and the detector — subsequent runs are faster

## Customization

### Sampling More Densely

Lower `frame_interval` and raise `sampled_frame_rate` accordingly. For a 30 fps source, sampling every 5th frame gives 6 fps:

```bash
model-compose run --input '{"video": "clip.mp4", "frame_interval": 5, "sampled_frame_rate": 6.0}'
```

### Tightening Identity Grouping

Raise `similarity_threshold` to make the clusterer more conservative (fewer merges, more distinct tracks). Typical ranges:

- `0.30 – 0.40`: aggressive grouping, may merge similar-looking people
- `0.40 – 0.55`: balanced
- `> 0.55`: strict, may split the same person under lighting/angle changes

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

`face-tracking` handles both materialized lists and async iterators transparently.

## Troubleshooting

### Common Issues

1. **`frame_rate` mismatch**: If timecodes look off, verify `sampled_frame_rate` matches `source_fps / frame_interval`. A wrong value doesn't break clustering but shifts all reported timestamps proportionally.
2. **No tracks returned**: Raise the sampling rate (lower `frame_interval`) or lower `min_frame_count` — the person may only appear in a single sampled frame.
3. **Same person split into multiple tracks**: Lower `similarity_threshold` (e.g. 0.35) or raise `merge_gap` if the splits are just adjacent gaps.
4. **Different people merged into one track**: Raise `similarity_threshold` (e.g. 0.5) — the default is tuned for recall over precision.
5. **Model files not found**: Verify the `./.models/antelopev2` directory contains all `.onnx` files listed above.

### Performance Optimization

- **GPU**: Install `onnxruntime-gpu` (CUDA) or `onnxruntime-silicon` (Apple) for faster inference
- **Detection Size**: Larger detection input improves recall on small faces but slows down inference — see `detection_size` in the InsightFace family config
- **Sample Rate**: The single biggest lever — halving the sampled fps roughly halves runtime

## Related Examples

- `face-embedding`: Extract a single identity embedding from a still image
- `face-swap`: Transfer a face identity from a source image to a target image
- `find-person-scenes` (showcase): Given a target face, locate the scenes in a video where that person appears — uses `face-embedding` + `vector-processor` rather than the built-in tracker
