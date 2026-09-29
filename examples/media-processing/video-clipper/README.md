# Video Clipper Example

This example demonstrates the `video-clipper` component, which cuts one or more time ranges out of a video file using ffmpeg. Two cut modes are supported: `fast` (default, stream-copy, keyframe-aligned) and `accurate` (re-encode, frame-accurate).

## Overview

This example exposes three workflows built on the same `video-clipper` component:

1. **Clip Single Span**: Extract one time range and return it as a video file
2. **Clip Multiple Spans**: Extract several time ranges and return them as a list of clips
3. **Clip and Merge**: Extract several time ranges and concatenate them into a single video file

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- [ffmpeg](https://ffmpeg.org/) installed and available in your PATH

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/video-clipper
```

Verify ffmpeg is installed:
```bash
ffmpeg -version
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   The service will start:
   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run workflows:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select a workflow from the dropdown
   - Upload a video file and provide the span(s)
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Single span (10s..25s), fast (keyframe-aligned) cut
   model-compose run clip-single --input '{
     "video": "/path/to/input.mp4",
     "start_time": "10s",
     "end_time": "25s"
   }'

   # Same span, but frame-accurate (re-encodes)
   model-compose run clip-single --input '{
     "video": "/path/to/input.mp4",
     "start_time": "10s",
     "end_time": "25s",
     "precision": "accurate"
   }'

   # Multiple spans returned as a list of clips
   model-compose run clip-multiple --input '{
     "video": "/path/to/input.mp4",
     "spans": [
       {"start_time": 0, "end_time": 5},
       {"start_time": 30, "end_time": 45}
     ]
   }'

   # Multiple spans merged into a single clip
   model-compose run clip-and-merge --input '{
     "video": "/path/to/input.mp4",
     "spans": [
       {"start_time": "00:00:10", "end_time": "00:00:20"},
       {"start_time": "00:01:00", "end_time": "00:01:15"}
     ]
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=clip-single" \
     -F "video=@/path/to/input.mp4" \
     -F "start_time=10s" \
     -F "end_time=25s"
   ```

## Component Details

### Video Clipper Component

- **Type**: `video-clipper`
- **Driver**: `ffmpeg`
- **Purpose**: Cut one or more time ranges out of a video file using ffmpeg — stream-copy in `fast` mode (default) or re-encode in `accurate` mode.

#### Key Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `video` | video source | Yes | - | The video file to clip |
| `span` | object or list of objects | Yes | - | One or more `{start_time, end_time}` entries. A single object is auto-promoted to a one-element list |
| `merge` | boolean | No | `false` | When `true`, all clips are concatenated into a single video file |
| `precision` | `fast` \| `accurate` | No | `fast` | `fast` stream-copies to the nearest keyframe at or before `start_time`; `accurate` re-encodes so the cut lands on the requested frame |
| `batch_size` | integer | No | `1` | Number of input videos processed per batch when the input is a list/stream |

`start_time` and `end_time` accept:
- Numbers (seconds): `10`, `10.5`
- Duration strings: `"10s"`, `"1m"`, `"250ms"`
- Timecodes: `"00:00:10"`, `"01:23:45"`

The output format is preserved from the input container (via `video.format`, the input file's extension, or an ffprobe probe as a last resort), so `-c copy` remains valid.

## Workflow Details

### 1. Clip Single Span

**Description**: Extract a single `[start_time, end_time]` range from the input video.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Source video file |
| `start_time` | string/number | No | `0s` | Clip start |
| `end_time` | string/number | No | `10s` | Clip end |
| `precision` | `fast` \| `accurate` | No | `fast` | Cut precision (see [Component Details](#video-clipper-component)) |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The extracted clip |

### 2. Clip Multiple Spans

**Description**: Extract multiple ranges and return them as a list of video files.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `video` | file | Yes | Source video file |
| `spans` | json | Yes | JSON array of `{start_time, end_time}` objects |
| `precision` | `fast` \| `accurate` | No | Cut precision (see [Component Details](#video-clipper-component)) |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `videos` | video list | One video per span, in input order |

### 3. Clip and Merge

**Description**: Extract multiple ranges and concatenate them into a single output video using ffmpeg's concat demuxer.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `video` | file | Yes | Source video file |
| `spans` | json | Yes | JSON array of `{start_time, end_time}` objects |
| `precision` | `fast` \| `accurate` | No | Cut precision (see [Component Details](#video-clipper-component)) |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The merged clip |

## Tips

- **Fast vs. accurate**: `precision: fast` (default) uses `-c copy` — lossless and near-instant, but the cut snaps to the nearest keyframe at or before `start_time`, so sources with a long GOP may start slightly earlier than requested. `precision: accurate` re-encodes so the cut lands on the requested frame; the output is no longer bit-exact and encoding takes materially longer, so reach for it only when downstream processing needs exact frame boundaries.
- **Reported cut span**: With `return_timestamp: true`, the `start_time`/`end_time` returned per clip reflect what was actually cut — under `precision: fast` that's the snapped keyframe timestamp, not the originally requested one.
- **Streaming input**: Non-file video sources (bytes, HTTP uploads) are spooled to a temporary file exactly once so each span can seek independently.
- **Streaming spans**: The `spans` list can also be a streaming iterator produced by a preceding component — each span is processed as it arrives (except for `merge=true`, which has to wait for all spans before concatenating).
- **Format mismatch with merge**: `merge=true` uses the ffmpeg `concat` demuxer with `-c copy`; because every clip comes from the same source, codec/container consistency is guaranteed.

## Troubleshooting

### Common Issues

1. **ffmpeg not found**: Ensure ffmpeg (and ffprobe) is installed and available in your `PATH`.
2. **`end_time must be greater than start_time`**: Each span's end must be strictly after its start.
3. **Unknown format**: If the video source has no format hint and no file extension, ffprobe is used to detect the container. Very unusual or corrupt inputs may fail this step — provide a proper file extension or wrap in a `MediaSource` with an explicit format upstream.
4. **Clip starts earlier than expected**: With `precision: fast` the cut snaps to the nearest keyframe at or before `start_time`. This is a tradeoff for the lossless/fast path — sources encoded with a long GOP will show the largest drift. Switch to `precision: accurate` for a frame-exact cut (at the cost of re-encoding time).
