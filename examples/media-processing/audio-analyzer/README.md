# Audio Analyzer Example

This example demonstrates how to use model-compose with the `audio-analyzer` component to inspect signal-level properties of an audio file — loudness, peak, gain, clipping, silence, and energy — without transforming the audio itself.

## Overview

This example provides 7 analysis workflows covering every supported metric:

1. **Measure Loudness**: EBU R128 integrated loudness, loudness range (LRA), and true peak.
2. **Measure Peak Levels**: Sample peak and inter-sample true peak (dBTP).
3. **Measure Gain / Headroom**: RMS, peak, headroom, crest/flat factors — inputs for normalization decisions.
4. **Detect Clipping**: Digital clipping counts and ratio.
5. **Detect Silence**: Silent regions and overall silence ratio.
6. **Measure Energy Profile**: Activity ratio, peak, average loudness, and the full per-bucket energy profile.
7. **Find Best BGM Segment**: Scan the energy profile and return the loudest segment of a requested length — useful for picking the strongest slice of a music track for a fixed-length video.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- FFmpeg installed (required by the `ffmpeg` driver)

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/audio-analyzer
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
   - Upload an audio file, adjust parameters, and click "Run Workflow"

   **Using CLI:**
   ```bash
   # EBU R128 loudness with per-window timeline
   model-compose run measure-loudness --input '{
     "audio": "/path/to/track.wav",
     "target_loudness": -23.0,
     "include_timeline": true
   }'

   # Sample and true peak
   model-compose run measure-peak --input '{"audio": "/path/to/track.wav"}'

   # RMS / headroom / crest factor
   model-compose run measure-gain --input '{"audio": "/path/to/track.wav"}'

   # Clipping counts (threshold in dBFS)
   model-compose run detect-clipping --input '{
     "audio": "/path/to/track.wav",
     "threshold": -0.1
   }'

   # Silent regions
   model-compose run detect-silence --input '{
     "audio": "/path/to/track.wav",
     "threshold": -60.0,
     "min_duration": "500ms"
   }'

   # Full energy analysis (profile + activity + peak + best segment)
   model-compose run measure-energy --input '{
     "audio": "/path/to/music.mp3",
     "threshold": -40.0,
     "segment_duration": 30.0,
     "resolution": "1s"
   }'

   # Same analysis, but return only the picked segment
   model-compose run find-best-bgm-segment --input '{
     "audio": "/path/to/music.mp3",
     "threshold": -40.0,
     "segment_duration": 30.0
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=measure-loudness" \
     -F "audio=@/path/to/track.wav"
   ```

## Component Details

### Audio Analyzer Component

- **Type**: `audio-analyzer`
- **Purpose**: Measure signal-level properties of an audio file and return a compact summary. Use it for mastering QA, level normalization decisions, silence trimming, and any pipeline that needs to *inspect* audio without transforming it.
- **Drivers**:
  - `ffmpeg` - FFmpeg-based analysis using `ebur128`, `astats`, and `silencedetect` (default)

## Workflow Details

### 1. Measure Loudness

**ID**: `measure-loudness`
**Description**: Integrated loudness, loudness range, and true peak following EBU R128.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `target_loudness` | number | No | `-23.0` | Reference target loudness in LUFS |
| `include_timeline` | boolean | No | `false` | Include per-window momentary/short-term/integrated timeline |

#### Example Output

```json
{
  "integrated_loudness": -18.4,
  "loudness_range": 6.1,
  "loudness_range_low": -25.7,
  "loudness_range_high": -19.6,
  "sample_peak_dbfs": -1.2,
  "true_peak_dbtp": -0.8,
  "target_loudness": -23.0
}
```

---

### 2. Measure Peak Levels

**ID**: `measure-peak`
**Description**: Sample peak and inter-sample true peak (dBTP).

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `true_peak` | boolean | No | `true` | Also compute inter-sample true peak (dBTP) |

#### Example Output

```json
{
  "sample_peak_dbfs": -0.9,
  "max_sample": 0.902,
  "min_sample": -0.898,
  "true_peak_dbtp": -0.4
}
```

---

### 3. Measure Gain / Headroom

**ID**: `measure-gain`
**Description**: RMS, peak, headroom, DC offset, crest and flat factors — feeds into normalization / compression decisions.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |

#### Example Output

```json
{
  "rms_dbfs": -18.7,
  "rms_peak_dbfs": -6.2,
  "rms_trough_dbfs": -42.1,
  "peak_dbfs": -0.9,
  "headroom_db": 0.9,
  "dc_offset": 0.00012,
  "crest_factor": 8.4,
  "flat_factor": 0.02
}
```

---

### 4. Detect Clipping

**ID**: `detect-clipping`
**Description**: Digital clipping counts and ratio from `astats`. Fine-grained region detection is not yet implemented (`regions` is returned as an empty array).

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `threshold` | number | No | `-0.1` | Amplitude threshold in dBFS above which samples are treated as clipped |
| `min_consecutive_length` | integer | No | `3` | Minimum consecutive over-threshold samples required to count as a clipping region |

#### Example Output

```json
{
  "threshold_dbfs": -0.1,
  "min_consecutive_length": 3,
  "sample_count": 8820000,
  "clipped_sample_count": 342,
  "clipped_ratio": 0.0000387,
  "peak_dbfs": -0.02,
  "regions": []
}
```

---

### 5. Detect Silence

**ID**: `detect-silence`
**Description**: Silent-region detection via FFmpeg's `silencedetect` filter.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `threshold` | number | No | `-60.0` | Amplitude threshold in dBFS below which audio is considered silent |
| `min_duration` | string | No | `500ms` | Minimum below-threshold duration to count as silence (e.g. `500ms`, `1s`, `2.5s`) |

#### Example Output

```json
{
  "threshold_dbfs": -60.0,
  "min_duration": 0.5,
  "duration": 180.5,
  "total_silent": 12.3,
  "silent_ratio": 0.068,
  "regions": [
    { "start": 0.0, "end": 3.4, "duration": 3.4 },
    { "start": 175.6, "end": 180.5, "duration": 4.9 }
  ]
}
```

---

### 6. Measure Energy Profile

**ID**: `measure-energy`
**Description**: Aggregate momentary loudness into a coarse energy profile and return the full analysis — activity ratio, first-active time, peak, average loudness, per-bucket profile, and (when `segment_duration` is set) the loudest segment.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `threshold` | number | No | `-40.0` | Momentary loudness threshold in LUFS above which audio counts as active |
| `segment_duration` | number | No | `30.0` | Length in seconds of the segment to search for. Omit to skip segment search and return only the profile |
| `resolution` | string | No | `1s` | Downsampling interval used to aggregate momentary loudness into the returned profile |

#### Example Output

```json
{
  "threshold": -40.0,
  "duration": 180.5,
  "resolution": 1.0,
  "active_duration": 142.0,
  "active_ratio": 0.787,
  "first_active_time": 12.0,
  "peak_time": 45.0,
  "peak_loudness": -8.3,
  "average_loudness": -22.5,
  "best_segment": {
    "start": 45.0,
    "duration": 30.0,
    "average_loudness": -18.7
  },
  "profile": [
    { "time": 0.0, "loudness": null,  "active": false },
    { "time": 1.0, "loudness": -55.2, "active": false },
    { "time": 2.0, "loudness": -38.1, "active": true }
  ]
}
```

---

### 7. Find Best BGM Segment

**ID**: `find-best-bgm-segment`
**Description**: Same energy analysis as `measure-energy`, but the workflow output is trimmed to just the picked segment — the field a downstream audio-clipper would consume directly.

#### Input Parameters

Same as `measure-energy`.

#### Example Output

```json
{
  "start": 45.0,
  "duration": 30.0,
  "average_loudness": -18.7
}
```

## Customization

### Choosing a Metric

- **`loudness`** — mastering QA, perceptual level checks, broadcast delivery targets.
- **`peak`** — clip-safety checks before encoding, especially with lossy formats where inter-sample peaks matter.
- **`gain`** — pre-normalization inspection: how loud is the track on average, and how much headroom is left.
- **`clipping`** — detect digital overs already present in the source.
- **`silence`** — trim leading/trailing dead air, split long recordings on structural pauses.
- **`energy`** — pick a compelling excerpt from a long track (BGM selection, thumbnails, previews).

### Threshold and Duration Guide

- **Loudness `target_loudness`**: `-23.0` LUFS is EBU R128 broadcast; `-14.0` is common for streaming platforms.
- **Silence `threshold` / `min_duration`**: lower threshold with longer duration isolates structural silences (between takes/songs); higher threshold with shorter duration catches fine-grained pauses.
- **Energy `threshold`**: `-40.0` LUFS is a balanced default; use `-50` to include quiet ambient passages, `-30` to only consider clearly energetic sections.
- **Energy `segment_duration`**: match the length of the video the music will accompany. Omit it if you only want the energy profile without segment scoring.

### Combining Metrics

Chain multiple workflows to build higher-level tools:
- Loudness + peak → mastering pre-flight
- Silence + energy → auto-trim quiet intro/outro, then pick the strongest remaining segment
- Gain + clipping → decide whether to normalize down before further processing
