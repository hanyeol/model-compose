# Audio Clipper Example

This example demonstrates the `audio-clipper` component, which cuts one or more time ranges out of an audio file using ffmpeg. Clips are extracted without re-encoding (`-c copy`), so the operation is fast and lossless.

## Overview

This example exposes three workflows built on the same `audio-clipper` component:

1. **Clip Single Span**: Extract one time range and return it as an audio file
2. **Clip Multiple Spans**: Extract several time ranges and return them as a list of clips
3. **Clip and Merge**: Extract several time ranges and concatenate them into a single audio file

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- [ffmpeg](https://ffmpeg.org/) installed and available in your PATH

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/audio-clipper
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
   - Upload an audio file and provide the span(s)
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Single span (10s..25s)
   model-compose run clip-single --input '{
     "audio": "/path/to/input.mp3",
     "start_time": "10s",
     "end_time": "25s"
   }'

   # Multiple spans returned as a list of clips
   model-compose run clip-multiple --input '{
     "audio": "/path/to/input.mp3",
     "spans": [
       {"start_time": 0, "end_time": 5},
       {"start_time": 30, "end_time": 45}
     ]
   }'

   # Multiple spans merged into a single clip
   model-compose run clip-and-merge --input '{
     "audio": "/path/to/input.mp3",
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
     -F "audio=@/path/to/input.mp3" \
     -F "start_time=10s" \
     -F "end_time=25s"
   ```

## Component Details

### Audio Clipper Component

- **Type**: `audio-clipper`
- **Driver**: `ffmpeg`
- **Purpose**: Cut one or more time ranges out of an audio file using `ffmpeg -c copy` (no re-encoding).

#### Key Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `audio` | audio source | Yes | - | The audio file to clip |
| `span` | object or list of objects | Yes | - | One or more `{start_time, end_time}` entries. A single object is auto-promoted to a one-element list |
| `merge` | boolean | No | `false` | When `true`, all clips are concatenated into a single audio file |
| `batch_size` | integer | No | `1` | Number of input audios processed per batch when the input is a list/stream |

`start_time` and `end_time` accept:
- Numbers (seconds): `10`, `10.5`
- Duration strings: `"10s"`, `"1m"`, `"250ms"`
- Timecodes: `"00:00:10"`, `"01:23:45"`

The output format is preserved from the input container (via `audio.format`, the input file's extension, or an ffprobe probe as a last resort), so `-c copy` remains valid.

## Workflow Details

### 1. Clip Single Span

**Description**: Extract a single `[start_time, end_time]` range from the input audio.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `start_time` | string/number | No | `0s` | Clip start |
| `end_time` | string/number | No | `10s` | Clip end |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `audio` | audio | The extracted clip |

### 2. Clip Multiple Spans

**Description**: Extract multiple ranges and return them as a list of audio files.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `audio` | file | Yes | Source audio file |
| `spans` | json | Yes | JSON array of `{start_time, end_time}` objects |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `audios` | audio list | One audio per span, in input order |

### 3. Clip and Merge

**Description**: Extract multiple ranges and concatenate them into a single output audio using ffmpeg's concat demuxer.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `audio` | file | Yes | Source audio file |
| `spans` | json | Yes | JSON array of `{start_time, end_time}` objects |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `audio` | audio | The merged clip |

## Tips

- **Lossless**: `-c copy` means no re-encoding. The output shares the input codec/container, and cut boundaries land on the nearest keyframe/frame boundary supported by the container.
- **Streaming input**: Non-file audio sources (bytes, HTTP uploads) are spooled to a temporary file exactly once so each span can seek independently.
- **Streaming spans**: The `spans` list can also be a streaming iterator produced by a preceding component — each span is processed as it arrives (except for `merge=true`, which has to wait for all spans before concatenating).
- **Format mismatch with merge**: `merge=true` uses the ffmpeg `concat` demuxer with `-c copy`; because every clip comes from the same source, codec/container consistency is guaranteed.

## Troubleshooting

### Common Issues

1. **ffmpeg not found**: Ensure ffmpeg (and ffprobe) is installed and available in your `PATH`.
2. **`end_time must be greater than start_time`**: Each span's end must be strictly after its start.
3. **Unknown format**: If the audio source has no format hint and no file extension, ffprobe is used to detect the container. Very unusual or corrupt inputs may fail this step — provide a proper file extension or wrap in a `MediaSource` with an explicit format upstream.
