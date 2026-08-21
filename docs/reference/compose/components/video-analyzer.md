# Video Analyzer Component

The video analyzer component measures visual properties of a video file — black frames, freeze regions, brightness, and motion — and returns a compact summary. Use it for QA of encoded output, ad-break/intro-outro discovery, thumbnail candidate scoring, and stream-health checks. It never re-encodes; every metric runs a null-output ffmpeg pass and parses the filter's stderr.

## Basic Configuration

```yaml
component:
  type: video-analyzer
  driver: ffmpeg
  action:
    metric: black
    video: ${input.video}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-analyzer` |
| `driver` | string | `ffmpeg` | Analysis backend. Currently: `ffmpeg` |
| `actions` | array | `[]` | List of measurement actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric` | string | **required** | Measurement to run: `black`, `freeze`, `brightness`, `motion` |
| `video` | any | **required** | Video source: file path, variable reference, or upload stream |
| `batch_size` | integer | `null` | Number of input videos to process in a single batch |
| `output` | string | `null` | Output template applied to the collected result |

### Black Metric Fields (`metric: black`)

Detect black-frame regions via ffmpeg's `blackdetect` filter (intro/outro, ad breaks, scene padding).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_duration` | string \| float | `2s` | Minimum region length to report (e.g., `500ms`, `2s`) |
| `pixel_threshold` | float | `0.10` | Per-pixel luminance below which a pixel counts as black (0.0-1.0) |
| `picture_threshold` | float | `0.98` | Fraction of pixels that must be black for a frame to count as black (0.0-1.0) |

### Freeze Metric Fields (`metric: freeze`)

Detect frozen-frame regions via ffmpeg's `freezedetect` filter (stream errors, buffering artifacts).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_duration` | string \| float | `2s` | Minimum region length to report |
| `noise_threshold` | float | `0.001` | Maximum inter-frame difference (0.0-1.0) still treated as a freeze |

### Brightness Metric Fields (`metric: brightness`)

Sample mean-luma (YAVG) at a chosen rate and summarize.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sample_rate` | float | `1.0` | Frames per second sampled from the source; lower values speed up long videos |
| `include_timeline` | boolean | `false` | If `true`, per-sampled-frame values are included in the result |

### Motion Metric Fields (`metric: motion`)

Sample a scene-change score at a chosen rate as a cheap motion proxy (higher = more visual change from the previous frame).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sample_rate` | float | `1.0` | Frames per second sampled from the source |
| `include_timeline` | boolean | `false` | If `true`, per-sampled-frame values are included in the result |

## Supported Drivers

### FFmpeg

Runs a null-output ffmpeg pass with the appropriate filter (`blackdetect`, `freezedetect`, `signalstats`, `scdet`) and parses the summary printed on stderr. Requires the `ffmpeg` binary on the system path.

```yaml
component:
  type: video-analyzer
  driver: ffmpeg
  action:
    metric: brightness
    video: ${input.video}
```

**Requires:** `ffmpeg` binary on the system path

## Output Format

### Black Output (`metric: black`)

```python
{
  "min_duration":      2.0,
  "pixel_threshold":   0.10,
  "picture_threshold": 0.98,
  "duration":        180.4,
  "total_black":       6.2,
  "black_ratio":       0.034,
  "regions": [
    {"start": 0.0,   "end": 3.2,   "duration": 3.2},
    {"start": 178.0, "end": 181.0, "duration": 3.0},
  ],
}
```

### Freeze Output (`metric: freeze`)

```python
{
  "min_duration":    2.0,
  "noise_threshold": 0.001,
  "duration":      180.4,
  "total_freeze":    4.5,
  "freeze_ratio":    0.025,
  "regions": [
    {"start": 42.3, "end": 46.8, "duration": 4.5},
  ],
}
```

### Brightness Output (`metric: brightness`)

```python
{
  "sample_rate":     1.0,
  "sample_count":  180,
  "duration":      180.4,
  "mean_brightness":  118.4,   # 0-255 for 8-bit sources
  "min_brightness":     3.2,
  "max_brightness":   238.7,
  "std_brightness":    41.5,
  # Only present when include_timeline is true:
  # "timeline": [{"frame": 0, "time": 0.0, "value": 118.4}, ...]
}
```

### Motion Output (`metric: motion`)

```python
{
  "sample_rate":  1.0,
  "sample_count": 180,
  "duration":    180.4,
  "mean_motion":   6.4,   # scdet score; higher = more inter-frame change
  "min_motion":    0.0,
  "max_motion":   42.7,
  "std_motion":    5.1,
  # Only present when include_timeline is true:
  # "timeline": [{"frame": 0, "time": 0.0, "value": 6.4}, ...]
}
```

## Multiple Actions Configuration

```yaml
component:
  type: video-analyzer
  driver: ffmpeg
  actions:
    - id: black
      metric: black
      video: ${input.video}
      min_duration: 3s

    - id: freeze
      metric: freeze
      video: ${input.video}
      min_duration: 2s

    - id: brightness
      metric: brightness
      video: ${input.video}
      sample_rate: 2
```

## Integration with Workflows

### Encode QA — Reject Freezes and Long Black Frames

```yaml
workflows:
  - id: encode-qa
    jobs:
      - id: freeze
        component: analyzer
        action: freeze
        input:
          video: ${input.video}

      - id: black
        component: analyzer
        action: black
        input:
          video: ${input.video}

components:
  - id: analyzer
    type: video-analyzer
    actions:
      - id: freeze
        metric: freeze
        video: ${input.video}
      - id: black
        metric: black
        video: ${input.video}
        min_duration: 5s
```

### Thumbnail Candidate Scoring

Pick frames with high brightness variance and low motion for cover-image candidates:

```yaml
components:
  - id: thumb-scorer
    type: video-analyzer
    action:
      metric: brightness
      video: ${input.video}
      sample_rate: 4
      include_timeline: true
```

## Best Practices

1. **This component is read-only** — pair it with `video-clipper` (trim black intros/outros), `video-encoder` (re-encode after a QA gate), or `video-scene-detector` (finer scene analysis) when you also want to change the video.
2. **Pick `sample_rate` to match how fast the property changes**: brightness rarely needs more than `1` fps for a summary; use `4`–`8` fps only when you need `include_timeline` for a per-second cover-image scoring pass.
3. **Loosen `min_duration` for freeze/black on real content**: many videos hold a still-frame or fade-to-black shot for a beat — set `min_duration: 3s` or higher to avoid false positives.
4. **`motion` is a proxy, not motion vectors**: it uses ffmpeg's `scdet` scene-change score — great for "is anything happening?" checks, poor for tracking physical motion. If you need real motion vectors, extract frames and run an optical-flow model.
5. **For scene boundaries use `video-scene-detector` instead**: video-analyzer's `motion` metric only summarizes; the dedicated scene detector returns the actual cut list.
6. **Batch multiple files with `batch_size`**: when scanning a library, `batch_size` parallelizes independent ffmpeg passes.
