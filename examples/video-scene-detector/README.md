# Video Scene Detector Example

This example demonstrates how to use model-compose with the `video-scene-detector` component to detect scene changes in video files using different detection backends.

## Overview

This example provides 4 different scene detection workflows:

1. **Adaptive Detection**: Detect scenes using PySceneDetect's adaptive detector (recommended for most videos)
2. **Content Detection**: Detect scenes using PySceneDetect's content-aware detector
3. **Time Range Detection**: Detect scenes within a specific time range with configurable detector
4. **FFmpeg Detection**: Detect scenes using FFmpeg's built-in scene filter

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- FFmpeg installed (required for the `ffmpeg` driver)
- Python dependencies are automatically installed on first run:
  - `scenedetect[opencv]` for the `pyscenedetect` driver

### Setup

Navigate to this example directory:
```bash
cd examples/video-scene-detector
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
   - Upload a video file
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Adaptive detection
   model-compose run detect-scenes --input '{"video": "/path/to/video.mp4"}'

   # Content detection with custom threshold
   model-compose run detect-scenes-content --input '{"video": "/path/to/video.mp4", "threshold": 30.0}'

   # Time range detection
   model-compose run detect-scenes-range --input '{
     "video": "/path/to/video.mp4",
     "detector": "content",
     "start_time": "00:01:00",
     "end_time": "00:05:00"
   }'

   # FFmpeg detection
   model-compose run detect-scenes-ffmpeg --input '{"video": "/path/to/video.mp4", "threshold": 0.4}'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-scenes" \
     -F "video=@/path/to/video.mp4"
   ```

## Component Details

### Video Scene Detector Component

- **Type**: `video-scene-detector`
- **Purpose**: Detect scene changes and transitions in video files
- **Drivers**:
  - `pyscenedetect` - PySceneDetect library with 5 detector types (default)
  - `ffmpeg` - FFmpeg scene filter
  - `transnetv2` - TransNetV2 deep learning model

## Workflow Details

### 1. Detect Scenes (Adaptive)

**ID**: `detect-scenes`
**Description**: Detect scene changes using PySceneDetect's adaptive detector

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Video file to analyze |
| `threshold` | number | No | `27.0` | Detection sensitivity threshold |

---

### 2. Detect Scenes (Content)

**ID**: `detect-scenes-content`
**Description**: Detect scene changes using PySceneDetect's content-aware detector

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Video file to analyze |
| `threshold` | number | No | `27.0` | Detection sensitivity threshold |

---

### 3. Detect Scenes (Time Range)

**ID**: `detect-scenes-range`
**Description**: Detect scene changes within a specific time range

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Video file to analyze |
| `detector` | select | No | `adaptive` | Detector type: adaptive, content, threshold, histogram, hash |
| `threshold` | number | No | - | Detection sensitivity threshold |
| `start_time` | string | No | - | Start time (e.g., `00:01:00`) |
| `end_time` | string | No | - | End time (e.g., `00:05:00`) |

---

### 4. Detect Scenes (FFmpeg)

**ID**: `detect-scenes-ffmpeg`
**Description**: Detect scene changes using FFmpeg's scene filter

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Video file to analyze |
| `threshold` | number | No | `0.3` | Scene change threshold (0.0 - 1.0) |

---

### Output Format

All workflows return the same output structure:

| Field | Type | Description |
|-------|------|-------------|
| `scenes` | array | List of detected scenes |
| `scenes[].index` | integer | Scene index (0-based) |
| `scenes[].start` | string | Scene start timecode (HH:MM:SS.mmm) |
| `scenes[].end` | string | Scene end timecode (HH:MM:SS.mmm) |
| `scenes[].start_frame` | integer | Scene start frame number |
| `scenes[].end_frame` | integer | Scene end frame number |
| `scenes[].duration` | string | Scene duration timecode |
| `total_scenes` | integer | Total number of detected scenes |

#### Example Output

```json
{
  "scenes": [
    {
      "index": 0,
      "start": "00:00:00.000",
      "end": "00:00:12.345",
      "start_frame": 0,
      "end_frame": 370,
      "duration": "00:00:12.345"
    },
    {
      "index": 1,
      "start": "00:00:12.345",
      "end": "00:00:28.678",
      "start_frame": 370,
      "end_frame": 860,
      "duration": "00:00:16.333"
    }
  ],
  "total_scenes": 2
}
```

## Customization

### Switching Drivers

Change the `driver` field to use a different detection backend:

```yaml
components:
  - id: scene-detector
    type: video-scene-detector
    driver: ffmpeg           # pyscenedetect, ffmpeg, transnetv2
```

### PySceneDetect Detector Types

| Detector | Description | Default Threshold |
|----------|-------------|-------------------|
| `adaptive` | Adaptive content detection (recommended) | 27.0 |
| `content` | Content-aware detection based on frame difference | 27.0 |
| `threshold` | Fade-in/fade-out detection | 12.0 |
| `histogram` | HSV histogram-based detection | 0.05 |
| `hash` | Perceptual hash-based detection | 0.395 |

### FFmpeg Threshold Guide

The FFmpeg scene filter threshold ranges from `0.0` to `1.0`:
- `0.1` - Very sensitive (detects minor changes)
- `0.3` - Default (balanced detection)
- `0.5` - Less sensitive (detects major scene changes only)
