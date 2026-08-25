# Audio Silence Detector Example

This example demonstrates how to use model-compose with the `audio-silence-detector` component to locate silent regions in an audio file using FFmpeg's `silencedetect` filter.

## Overview

This example provides 2 silence detection workflows:

1. **Default Detection**: Detect silence with user-configurable threshold and minimum duration (suitable for general silence trimming or segmentation).
2. **Strict Detection**: Detect only longer, quieter silences — a good fit for trimming leading/trailing dead air from recordings.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- FFmpeg installed (required by the `ffmpeg` driver)

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/audio-silence-detector
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
   - Upload an audio file
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Default detection (custom threshold and min duration)
   model-compose run detect-silences --input '{
     "audio": "/path/to/audio.wav",
     "silence_threshold": -30.0,
     "min_silence_duration": "500ms"
   }'

   # Strict detection (fixed -40 dBFS / 2s)
   model-compose run detect-silences-strict --input '{"audio": "/path/to/audio.wav"}'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-silences" \
     -F "audio=@/path/to/audio.wav"
   ```

## Component Details

### Audio Silence Detector Component

- **Type**: `audio-silence-detector`
- **Purpose**: Locate silent (quiet) regions in an audio track and emit an alternating timeline of audible and silent spans.
- **Drivers**:
  - `ffmpeg` - FFmpeg `silencedetect` audio filter (default)

## Workflow Details

### 1. Detect Silences (Default)

**ID**: `detect-silences`
**Description**: Detect silent regions using FFmpeg's `silencedetect` filter with configurable threshold and minimum duration.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `silence_threshold` | number | No | `-30.0` | Silence detection threshold in dBFS (lower is quieter) |
| `min_silence_duration` | string | No | `500ms` | Minimum duration a quiet run must last to be reported (e.g. `500ms`, `1s`, `2.5s`) |

---

### 2. Detect Silences (Strict)

**ID**: `detect-silences-strict`
**Description**: Detect only long, deep silences (fixed `-40.0` dBFS threshold and `2s` minimum duration). Useful for cleanly trimming leading/trailing silence.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |

---

### Output Format

Each workflow returns a flat list of segments covering the full audio timeline. Segments alternate between `audible` (sound present) and `silence` (below threshold for at least `min_silence_duration`).

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | number | Segment start time in seconds |
| `end_time` | number | Segment end time in seconds |
| `type` | string | Segment classification: `audible` or `silence` |

#### Example Output

```json
[
  { "start_time": 0.0,   "end_time": 12.345, "type": "audible" },
  { "start_time": 12.345, "end_time": 15.678, "type": "silence" },
  { "start_time": 15.678, "end_time": 42.100, "type": "audible" },
  { "start_time": 42.100, "end_time": 45.000, "type": "silence" }
]
```

## Customization

### Threshold and Duration Guide

- **`silence_threshold`** (dBFS): how quiet a region must be to count as silence.
  - `-20.0` — very lenient; treats mild dips as silence
  - `-30.0` — balanced default for typical speech/music
  - `-40.0` — strict; only near-total silence qualifies
- **`min_silence_duration`**: how long the quiet run must be.
  - `200ms` — catches short pauses between words
  - `500ms` — natural sentence gaps (default)
  - `2s`+ — leading/trailing dead air only

Combine a lower threshold with a longer duration to isolate structural silences (between takes, songs, chapters); use a higher threshold with a shorter duration to detect fine-grained pauses.
