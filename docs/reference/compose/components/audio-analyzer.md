# Audio Analyzer Component

The audio analyzer component measures signal-level properties of an audio file — loudness, peak level, gain, clipping, and silence — and returns a compact summary. Use it for mastering QA, level normalization decisions, silence trimming, and any pipeline that needs to *inspect* audio without transforming it.

## Basic Configuration

```yaml
component:
  type: audio-analyzer
  driver: ffmpeg
  action:
    metric: loudness
    audio: ${input.audio}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `audio-analyzer` |
| `driver` | string | `ffmpeg` | Analysis backend. Currently: `ffmpeg` |
| `actions` | array | `[]` | List of measurement actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric` | string | **required** | Measurement to run: `loudness`, `peak`, `gain`, `clipping`, `silence` |
| `audio` | any | **required** | Audio source: file path, variable reference, or upload stream |
| `batch_size` | integer | `null` | Number of input audios to process in a single batch |
| `output` | string | `null` | Output template applied to the collected result |

### Loudness Metric Fields (`metric: loudness`)

Integrated program loudness following EBU R128, plus loudness range (LRA) and true-peak.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `target_loudness` | float | `-23.0` | Reference target loudness in LUFS (EBU R128) |
| `include_timeline` | boolean | `false` | If `true`, return per-window momentary/short-term/integrated timeline |

### Peak Metric Fields (`metric: peak`)

Sample and true peak amplitudes.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `true_peak` | boolean | `true` | If `true`, also compute inter-sample true peak (dBTP) via `ebur128` |

### Gain Metric Fields (`metric: gain`)

RMS, peak, headroom, DC offset, crest/flat factors. No configurable fields beyond the common ones.

### Clipping Metric Fields (`metric: clipping`)

Digital clipping detection based on `astats`. Fine-grained region detection is not yet implemented (`regions` is returned as an empty array).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold` | float | `-0.1` | Amplitude threshold in dBFS above which samples are treated as clipped |
| `min_consecutive_length` | integer | `3` | Minimum number of consecutive over-threshold samples required to count as a clipping region |

### Silence Metric Fields (`metric: silence`)

Silence-region detection via `silencedetect`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold` | float | `-60.0` | Amplitude threshold in dBFS below which audio is considered silent |
| `min_duration` | string \| float | `0.5s` | Minimum below-threshold duration to count as silence (e.g., `500ms`, `0.5s`, or seconds as a number) |

## Supported Drivers

### FFmpeg

Runs a null-output ffmpeg pass with the appropriate filter (`ebur128`, `astats`, `silencedetect`) and parses the summary printed on stderr. Requires the `ffmpeg` binary on the system path.

```yaml
component:
  type: audio-analyzer
  driver: ffmpeg
  action:
    metric: loudness
    audio: ${input.audio}
```

**Requires:** `ffmpeg` binary on the system path

## Output Format

### Loudness Output (`metric: loudness`)

```python
{
  "integrated_loudness":   -18.4,
  "loudness_range":         6.1,
  "loudness_range_low":   -25.7,
  "loudness_range_high":  -19.6,
  "threshold_integrated": -28.4,
  "threshold_range":      -38.4,
  "sample_peak_dbfs":      -1.2,
  "true_peak_dbtp":        -0.8,
  "target_loudness":      -23.0,
  # Only present when include_timeline is true:
  # "timeline": [{"time": 0.4, "momentary": -70.0, "short_term": -70.0, "integrated": -70.0}, ...]
}
```

### Peak Output (`metric: peak`)

```python
{
  "sample_peak_dbfs": -1.2,
  "max_sample":        0.87,
  "min_sample":       -0.85,
  # Only present when true_peak is true:
  "true_peak_dbtp":   -0.8,
}
```

### Gain Output (`metric: gain`)

```python
{
  "rms_dbfs":        -17.3,
  "rms_peak_dbfs":   -12.1,
  "rms_trough_dbfs": -45.6,
  "peak_dbfs":        -1.2,
  "headroom_db":       1.2,
  "dc_offset":         0.00012,
  "crest_factor":     16.1,
  "flat_factor":       0.0,
}
```

### Clipping Output (`metric: clipping`)

```python
{
  "threshold_dbfs":            -0.1,
  "min_consecutive_length":       3,
  "sample_count":           8830000,
  "clipped_sample_count":       142,
  "clipped_ratio":            0.0000161,
  "peak_dbfs":               -0.02,
  "regions":                     [],
}
```

### Silence Output (`metric: silence`)

```python
{
  "threshold_dbfs":  -60.0,
  "min_duration":      0.5,
  "duration":        180.4,
  "total_silent":     12.3,
  "silent_ratio":      0.068,
  "regions": [
    {"start": 0.0,   "end": 3.2,   "duration": 3.2},
    {"start": 88.7,  "end": 91.5,  "duration": 2.8},
    ...
  ],
}
```

## Multiple Actions Configuration

```yaml
component:
  type: audio-analyzer
  driver: ffmpeg
  actions:
    - id: loudness
      metric: loudness
      audio: ${input.audio}
      target_loudness: -14

    - id: silence
      metric: silence
      audio: ${input.audio}
      threshold: -50
      min_duration: 1s
```

## Integration with Workflows

### Loudness-Aware Normalization

Decide whether a track needs level correction before publishing:

```yaml
workflows:
  - id: master-check
    jobs:
      - id: measure
        component: analyzer
        action: loudness
        input:
          audio: ${input.audio}

components:
  - id: analyzer
    type: audio-analyzer
    action:
      metric: loudness
      audio: ${input.audio}
      target_loudness: -14
```

### Silence-Trim Candidate Discovery

Find leading/trailing silence to feed into `audio-clipper`:

```yaml
components:
  - id: silence-scanner
    type: audio-analyzer
    action:
      metric: silence
      audio: ${input.audio}
      threshold: -55
      min_duration: 300ms
```

## Best Practices

1. **Pick a target that matches your delivery**: streaming platforms center on `-14 LUFS` (Spotify/YouTube) and `-16 LUFS` (Apple Music); broadcast uses `-23 LUFS` (EBU R128). Set `target_loudness` accordingly.
2. **Reach for `true_peak` when going lossy**: MP3/AAC/Opus encoders can push inter-sample peaks above the sample peak — `true_peak: true` catches limiter needs the sample peak would miss.
3. **Prefer `metric: gain` over `metric: peak` for headroom decisions**: gain also reports RMS and crest factor, which together are far more useful than peak alone for judging dynamics.
4. **Tune silence detection to the source**: dialogue and speech usually work well with `-50 dB` / `300ms`; music beds need looser thresholds (`-55 dB` / `1s`) to avoid catching quiet passages.
5. **Batch multiple files with `batch_size`**: when scanning a library, `batch_size` parallelizes independent ffmpeg passes.
6. **This component is read-only**: pair it with `audio-processor` (gain, normalize, peak-limit) when you also want to change the signal.
