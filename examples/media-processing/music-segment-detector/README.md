# Music Segment Detector Example

This example demonstrates how to use model-compose with the `music-segment-detector` component to find structural segment boundaries in music (intro, verse, chorus, etc.) using beat-synchronized chroma features and clustering.

## Overview

This example provides 2 music segmentation workflows:

1. **Laplacian Segmentation** (default): Detect segment boundaries via beat-synchronized chroma + MFCC spectral (Laplacian) clustering. Repeating sections (verse, chorus) tend to receive the same structural label — good for music with clear repeating form.
2. **Agglomerative Segmentation**: Detect boundaries using agglomerative clustering with a data-driven segment count. Use when the Laplacian output looks unstable on short clips or unusual material.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python dependencies are automatically installed on first run:
  - `librosa`, `numpy`, `scipy`, `scikit-learn` (used by the `native` driver)

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/music-segment-detector
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
   # Laplacian segmentation (default)
   model-compose run detect-segments --input '{"audio": "/path/to/track.mp3"}'

   # Custom sample rate
   model-compose run detect-segments --input '{
     "audio": "/path/to/track.mp3",
     "sample_rate": 44100
   }'

   # Agglomerative segmentation
   model-compose run detect-segments-agglomerative --input '{"audio": "/path/to/track.mp3"}'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-segments" \
     -F "audio=@/path/to/track.mp3"
   ```

## Component Details

### Music Segment Detector Component

- **Type**: `music-segment-detector`
- **Purpose**: Detect structural segment boundaries in music and assign each segment a structural label so repeating sections can be identified.
- **Drivers**:
  - `native` - librosa-based analysis with configurable segmentation strategy (default)

## Workflow Details

### 1. Detect Music Segments (Laplacian)

**ID**: `detect-segments`
**Description**: Detect segment boundaries via beat-synchronized chroma + MFCC spectral clustering. Repeating sections receive the same structural label.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to segment |
| `sample_rate` | integer | No | `22050` | Target mono PCM sample rate used for analysis |

---

### 2. Detect Music Segments (Agglomerative)

**ID**: `detect-segments-agglomerative`
**Description**: Detect segment boundaries via agglomerative clustering with a data-driven segment count. Prefer when the Laplacian output looks unstable on short or non-standard tracks.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to segment |
| `sample_rate` | integer | No | `22050` | Target mono PCM sample rate used for analysis |

---

### Output Format

Each workflow returns a flat list of contiguous segments covering the full audio timeline. Adjacent segments sharing the same label are automatically merged.

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | number | Segment start time in seconds |
| `end_time` | number | Segment end time in seconds |
| `label` | string | Structural label (`A`, `B`, `C`, ...); repeated labels indicate structurally similar sections |

#### Example Output

```json
[
  { "start_time": 0.0,    "end_time": 12.345, "label": "A" },
  { "start_time": 12.345, "end_time": 45.678, "label": "B" },
  { "start_time": 45.678, "end_time": 78.900, "label": "C" },
  { "start_time": 78.900, "end_time": 112.234, "label": "B" }
]
```

In the example above, the two `B` segments are treated as structurally similar (e.g. two chorus sections).

## Customization

### Strategy Guide

- **`laplacian`** — best default for typical songs with recognizable repeated form (verse/chorus/bridge). Produces both boundaries and structural labels in one pass, so repeats align naturally.
- **`agglomerative`** — data-driven segment count without a repetition model. Prefer for very short clips, ambient/experimental material, or when `laplacian` returns unstable boundaries.

### Sample Rate

The default `22050` Hz balances analysis quality and speed and is standard for music information retrieval tasks. Raise to `44100` when working with material where subtle timbral detail matters; the analysis will be slower but boundaries can be marginally more precise.

### Minimum Segment Duration

The component ships with a default `min_segment_duration` of `2s` (segments shorter than this are merged into a neighbor). To surface much finer transitions or, conversely, force coarser structure, set `min_segment_duration` on the action:

```yaml
actions:
  - id: laplacian
    audio: ${input.audio as file}
    strategy: laplacian
    min_segment_duration: 5s   # coarser structural view
```
