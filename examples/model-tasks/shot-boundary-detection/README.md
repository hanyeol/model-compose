# Shot Boundary Detection Example (TransNetV2)

This example demonstrates how to use model-compose with the `shot-boundary-detection` model task to detect shot boundaries in video files using the **TransNetV2** deep learning model.

## Overview

TransNetV2 is a CNN-based shot boundary detection model that outperforms heuristic approaches (frame-difference, histogram) on hard cases such as dissolves, fades, wipes, and fast motion.

This example provides 2 workflows:

1. **Default Detection**: Detect shot boundaries across the whole video
2. **Time Range Detection**: Detect shot boundaries within a specific time range

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- FFmpeg installed (used internally to extract frames)
- Python dependencies are automatically installed on first run:
  - `transnetv2` (installs the TransNetV2 package)

### Download Model Weights

The `transnetv2` pip package does **not** include the pretrained weights. You must download the SavedModel weights from the [official TransNetV2 repository](https://github.com/soCzech/TransNetV2) and place them under `./models/transnetv2-weights/`.

```bash
# From this example directory:
mkdir -p ./models

# Option 1: Clone the repo (requires git-lfs)
git lfs install
git clone https://github.com/soCzech/TransNetV2.git /tmp/TransNetV2
cp -r /tmp/TransNetV2/inference/transnetv2-weights ./models/

# Option 2: If you already have the weights, symlink or copy them into place
ln -s /path/to/transnetv2-weights ./models/transnetv2-weights
```

After this step the directory layout should be:
```
./models/transnetv2-weights/
├── saved_model.pb
└── variables/
    ├── variables.data-00000-of-00001
    └── variables.index
```

> Note: A GPU is recommended for reasonable throughput; CPU inference works but is significantly slower.

### Setup

Navigate to this example directory:
```bash
cd examples/model-tasks/shot-boundary-detection
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
   # Default detection
   model-compose run detect-shots --input '{"video": "/path/to/video.mp4"}'

   # Custom threshold
   model-compose run detect-shots --input '{"video": "/path/to/video.mp4", "threshold": 0.4}'

   # Time range detection
   model-compose run detect-shots-range --input '{
     "video": "/path/to/video.mp4",
     "start_time": "00:01:00",
     "end_time": "00:05:00"
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-shots" \
     -F "video=@/path/to/video.mp4"
   ```

## Component Details

### Shot Boundary Detection Component

- **Type**: `model`
- **Task**: `shot-boundary-detection`
- **Driver**: `custom`
- **Family**: `transnetv2`
- **Purpose**: Detect shot boundaries and transitions in video files using a deep learning model

## Workflow Details

### 1. Detect Shots

**ID**: `detect-shots`
**Description**: Detect shot boundaries across the whole video

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Video file to analyze |
| `threshold` | number | No | `0.5` | Detection confidence threshold (0.0 - 1.0) |

---

### 2. Detect Shots (Time Range)

**ID**: `detect-shots-range`
**Description**: Detect shot boundaries within a specific time range

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Video file to analyze |
| `threshold` | number | No | `0.5` | Detection confidence threshold (0.0 - 1.0) |
| `start_time` | string | No | - | Start time (e.g., `00:01:00`) |
| `end_time` | string | No | - | End time (e.g., `00:05:00`) |

---

### Output Format

All workflows return a flat list of detected shots.

| Field | Type | Description |
|-------|------|-------------|
| `index` | integer | Shot index (0-based) |
| `start_time` | string | Shot start timecode (HH:MM:SS.mmm) |
| `end_time` | string | Shot end timecode (HH:MM:SS.mmm) |
| `start_frame` | integer | Shot start frame number |
| `end_frame` | integer | Shot end frame number |
| `duration` | string | Shot duration timecode |

#### Example Output

```json
[
  {
    "index": 0,
    "start_time": "00:00:00.000",
    "end_time": "00:00:12.345",
    "start_frame": 0,
    "end_frame": 370,
    "duration": "00:00:12.345"
  },
  {
    "index": 1,
    "start_time": "00:00:12.345",
    "end_time": "00:00:28.678",
    "start_frame": 370,
    "end_frame": 860,
    "duration": "00:00:16.333"
  }
]
```

## Threshold Guide

The TransNetV2 threshold ranges from `0.0` to `1.0` and controls how confident the model must be before marking a frame as a shot boundary:

- `0.3` - More sensitive (detects subtle transitions, may over-segment)
- `0.5` - Default (balanced)
- `0.7` - Less sensitive (only strong transitions)

## When to Use TransNetV2

TransNetV2 shines on content with varied transition effects. For simpler content or environments without a GPU, the `video-scene-detector` component (with `pyscenedetect` or `ffmpeg` drivers) may be a better fit.

| Content Type | Recommended |
|--------------|-------------|
| Movies, dramas, documentaries with dissolves and fades | `shot-boundary-detection` (this example) |
| Music videos, commercials with varied transition effects | `shot-boundary-detection` (this example) |
| User-generated content with mostly hard cuts | `video-scene-detector` with `pyscenedetect` or `ffmpeg` |
| Quick prototyping or CPU-only environments | `video-scene-detector` with `ffmpeg` |
