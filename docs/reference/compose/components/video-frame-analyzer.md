# Video Frame Analyzer Component

The video frame analyzer component measures **sequence-level** properties of a frame stream — temporal noise, pair differences, zero-pixel share, moving pairs, duplicate-frame cadence (pulldown fingerprint), and sharpness oscillation (frame-interpolation fingerprint) — and returns a compact summary. Use it on frames produced by `video-frame-extractor` (or any upstream source that yields an image array) for forensic classification (live action vs rendered / AI / interpolated content), scene-stability checks, and frame-rate detection.

Unlike `image-analyzer`, every metric reads **relationships between adjacent frames** (or the whole sequence); a single frame has no sequence-level signal. Unlike `video-analyzer`, the input is a decoded frame sequence, not a video file — the extractor controls sampling, start/end range, and streaming.

## Basic Configuration

```yaml
components:
  - id: extractor
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}

  - id: cadence
    type: video-frame-analyzer
    driver: opencv
    action:
      metric: duplicate
      frames: ${jobs.extract.output}
      frame_rate: 30
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-frame-analyzer` |
| `driver` | string | `native` | Analysis backend. `native` (numpy only) or `opencv` (OpenCV + numpy) |
| `actions` | array | `[]` | List of measurement actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric` | string | **required** | Measurement to run. Native: `temporal_noise`, `pair_difference`, `zero_pixel_ratio`. OpenCV: `moving_pairs`, `duplicate`, `sharpness` |
| `frames` | any | **required** | Frame sequence to analyze: a flat list of frames, a stream of batches, or a variable reference to a `video-frame-extractor` output |
| `frame_rate` | float | `null` | Source frame rate in frames per second; required for metrics that interpret cadence (duplicate-frame pulldown classification) |
| `batch_size` | integer | `1` | Number of independent frame sequences processed per iteration |
| `streaming` | boolean | `false` | Whether partial measurements are emitted incrementally; metrics that need the full sequence (autocorrelation) ignore this flag |
| `output` | string | `null` | Output template applied to the collected result |

### Temporal Noise Metric Fields (`metric: temporal_noise`, native)

Mean of per-pair standard deviations of `current - previous`. High values indicate grainy content (sensor noise, film grain); low values indicate smooth inter-frame motion or rendered content.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_width` | integer | `96` | Width in pixels the frames are resampled to before measurement (16-4096) |

### Pair Difference Metric Fields (`metric: pair_difference`, native)

Per-pair mean absolute luma difference statistics plus start-to-end difference. Reveals whether the sequence is static, slowly moving, or jumpy.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_width` | integer | `96` | Width in pixels the frames are resampled to (16-4096) |
| `move_threshold` | float | `2.0` | Mean absolute luma difference above which a frame pair counts as moving |

### Zero Pixel Ratio Metric Fields (`metric: zero_pixel_ratio`, native)

Share of pixels that never change between consecutive frames. High values are the signature of 2D compositing or motion-graphics animation, where the background plate stays pixel-identical while only a few elements move.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_width` | integer | `96` | Width in pixels the frames are resampled to (16-4096) |
| `exact_match` | boolean | `true` | When true, a pixel counts as zero only when identical between frames; when false, pixels with sub-quantization-step differences also count |

### Moving Pairs Metric Fields (`metric: moving_pairs`, OpenCV)

Fraction of frame pairs where more than a threshold share of pixels changed. Distinguishes "mostly static scene" from "scene with ongoing motion".

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_width` | integer | `96` | Width in pixels the frames are resampled to (16-4096) |
| `change_threshold` | float | `6.0` | Per-pixel absolute luma difference above which a pixel counts as changed |
| `moving_share_threshold` | float | `0.01` | Minimum share of changed pixels for a frame pair to count as moving (0.0-1.0) |

### Duplicate Metric Fields (`metric: duplicate`, OpenCV)

Per-pair duplicate detection plus autocorrelation of the duplicate mask. The dominant lag is the pulldown period; known cadences are classified (24→30 fps, 25→30 fps, 24→60 fps). Irregular duplicates leave `pulldown` null.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_width` | integer | `96` | Width in pixels the frames are resampled to (16-4096) |
| `duplicate_threshold` | float | `0.5` | Mean absolute luma difference below which two consecutive frames count as duplicates |
| `max_period` | integer | `8` | Largest duplicate-pattern period searched for via autocorrelation (2-32) |

### Sharpness Metric Fields (`metric: sharpness`, OpenCV)

Per-frame Laplacian variance as a sharpness proxy, then autocorrelation. Frame interpolation introduces a periodic sharpness dip (synthetic frames are softer than originals) that autocorrelation exposes.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_width` | integer | `96` | Width in pixels the frames are resampled to (16-4096) |
| `max_period` | integer | `8` | Largest sharpness-oscillation period searched for via autocorrelation (2-32) |

## Supported Drivers

### Native

Uses numpy on resized luma thumbnails; runs in a thread executor. Carries the metrics whose per-pair arithmetic is well-served by plain numpy.

```yaml
component:
  type: video-frame-analyzer
  driver: native
  action:
    metric: temporal_noise
    frames: ${jobs.extract.output}
```

**Auto-installed dependency:** `numpy`

### OpenCV

Uses OpenCV plus numpy. Carries metrics that lean on OpenCV's fast resize (`INTER_AREA`), `absdiff`, and `Laplacian`, plus the autocorrelation-based cadence classifiers.

```yaml
component:
  type: video-frame-analyzer
  driver: opencv
  action:
    metric: duplicate
    frames: ${jobs.extract.output}
    frame_rate: 30
```

**Auto-installed dependencies:** `opencv-python`, `numpy`

## Output Format

### Temporal Noise Output (`metric: temporal_noise`)

```python
{
  "temporal_noise": 2.7,     # grainy phone footage ~ 1-5; rendered content ~ 0
  "pair_count":  119,
  "frame_count": 120,
  "frame_rate":  30.0,
  "analysis_width": 96,
}
```

### Pair Difference Output (`metric: pair_difference`)

```python
{
  "pair_count":        119,
  "pair_mad_mean":       6.1,
  "pair_mad_p90":       18.4,
  "pair_mad_max":       32.7,
  "moving_pair_ratio":    0.89,   # share of pairs above move_threshold
  "start_end_mad":      24.3,     # raw difference between first and last frame
  "move_threshold":      2.0,
  "frame_count":  120,
  "frame_rate":    30.0,
  "analysis_width": 96,
}
```

### Zero Pixel Ratio Output (`metric: zero_pixel_ratio`)

```python
{
  "zero_pixel_ratio_mean": 0.78,   # high = large unchanged background (2D composition / MG)
  "zero_pixel_ratio_min":  0.52,
  "zero_pixel_ratio_max":  0.95,
  "pair_count":  119,
  "frame_count": 120,
  "exact_match": True,
  "frame_rate":   30.0,
  "analysis_width": 96,
}
```

### Moving Pairs Output (`metric: moving_pairs`)

```python
{
  "moving_pair_ratio":        0.92,   # share of pairs crossing moving_share_threshold
  "moving_pair_count":      110,
  "pair_count":             119,
  "mean_changed_pixel_share":  0.14,
  "max_changed_pixel_share":   0.47,
  "change_threshold":        6.0,
  "moving_share_threshold":  0.01,
  "frame_count":  120,
  "frame_rate":    30.0,
  "analysis_width": 96,
}
```

### Duplicate Output (`metric: duplicate`)

```python
{
  "dup_ratio":       0.20,          # 24->30 pulldown repeats every 5th frame
  "dup_count":      24,
  "pair_count":    119,
  "dup_period":      5,             # strongest autocorrelation lag; None if no regular pattern
  "dup_regularity":  0.98,          # normalized autocorrelation at dup_period
  "pulldown":       "24->30",       # or "25->30", "24->60", or None (irregular)
  "duplicate_threshold": 0.5,
  "max_period":          8,
  "frame_count":  120,
  "frame_rate":    30.0,
  "analysis_width": 96,
}
```

### Sharpness Output (`metric: sharpness`)

```python
{
  "sharpness_mean":   145.2,         # mean per-frame Laplacian variance
  "sharpness_std":     42.1,
  "sharp_alt":         0.74,         # share of adjacent sharpness pairs with sign-flip (oscillation)
  "sharp_period":      2,            # strongest autocorrelation lag; None if no oscillation
  "sharp_period_ac":   0.88,         # normalized autocorrelation at sharp_period
  "frame_count":   120,
  "frame_rate":     30.0,
  "max_period":     8,
  "analysis_width": 96,
}
```

## Multiple Actions Configuration

Native and OpenCV metrics live in separate components because they are different drivers:

```yaml
components:
  - id: extractor
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}

  - id: native-stats
    type: video-frame-analyzer
    driver: native
    actions:
      - id: noise
        metric: temporal_noise
        frames: ${jobs.extract.output}
      - id: zero
        metric: zero_pixel_ratio
        frames: ${jobs.extract.output}

  - id: cv-stats
    type: video-frame-analyzer
    driver: opencv
    actions:
      - id: duplicate
        metric: duplicate
        frames: ${jobs.extract.output}
        frame_rate: ${input.frame_rate}
      - id: sharpness
        metric: sharpness
        frames: ${jobs.extract.output}
```

Extracting the frame sequence once and running several analyzer actions against it avoids re-decoding the source video per metric.

## Integration with Workflows

### Pulldown Detection (24 fps → 30 fps content)

AI-generated video and cinema content both emit 24 fps and get pulled up to 30 fps on streaming platforms, leaving a period-5 duplicate-frame pattern. Native phone footage at 30 fps has no duplicates.

```yaml
workflows:
  - id: detect-pulldown
    jobs:
      - id: extract
        component: extractor
        input:
          video: ${input.video}
      - id: cadence
        component: cadence-analyzer
        input:
          frames: ${jobs.extract.output}

components:
  - id: extractor
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}

  - id: cadence-analyzer
    type: video-frame-analyzer
    driver: opencv
    action:
      metric: duplicate
      frames: ${input.frames}
      frame_rate: 30
```

`pulldown == "24->30"` with `dup_regularity > 0.9` is the signature of 24p source transcoded to 30 fps.

### Interpolation Forensics

Frame-interpolation models (RIFE, FILM, DAIN) insert synthetic frames between real ones. Those synthetic frames are softer, producing a period-2 sharpness oscillation.

```yaml
component:
  type: video-frame-analyzer
  driver: opencv
  action:
    metric: sharpness
    frames: ${jobs.extract.output}
```

`sharp_period == 2` with high `sharp_period_ac` is the interpolation signature.

### Motion-Graphics vs Live Action

2D composition and motion-graphics clips keep large parts of the frame pixel-identical, while live action keeps noise everywhere.

```yaml
components:
  - id: native-stats
    type: video-frame-analyzer
    driver: native
    actions:
      - id: zero
        metric: zero_pixel_ratio
        frames: ${input.frames}
      - id: noise
        metric: temporal_noise
        frames: ${input.frames}
```

High `zero_pixel_ratio_mean` with near-zero `temporal_noise` is the MG/composition signature. Phone footage shows the opposite.

## Best Practices

1. **Pair with `video-frame-extractor`**: analyzer takes an `ImageArrayValue`, so the extractor controls sampling cadence and time range. Extracting once and running multiple analyzer actions against the same output avoids re-decoding.
2. **Keep `analysis_width` modest**: 96 pixels on the long side is plenty for pair-level and autocorrelation signals. Larger widths slow the analyzer down linearly with no measurement benefit at this frame rate.
3. **`duplicate` needs native frame rate**: if the extractor downsamples (`frame_rate: 10` on a 30 fps source), the duplicate pattern disappears. Extract at native rate for pulldown detection.
4. **Autocorrelation metrics need enough frames**: `duplicate` and `sharpness` scan lags up to `max_period`; feed at least `3 × max_period` frames, otherwise `dup_period` / `sharp_period` return `null`.
5. **`temporal_noise` vs image-analyzer `noise`**: the two measure different things. Image-analyzer `noise` is **Immerkær spatial** noise in a single frame; `temporal_noise` here is **inter-frame** noise across the sequence. Both near zero means rendered content.
6. **Platform transcodes raise `dup_ratio` slightly**: re-encoding leaves occasional near-duplicate frames even on genuine 30 fps sources. Treat `dup_regularity < 0.5` as "no cadence" rather than trusting the measured `dup_period`.
7. **`sharp_alt` is a cheaper interpolation probe**: if you only care about "is this interpolated or not" (not the exact period), `sharp_alt > 0.7` on live-action footage is the fast signal and avoids reading `sharp_period_ac`.
8. **`frame_rate` is metadata, not a sampling setting**: the analyzer does not resample; set it so `duplicate` can classify `pulldown` against known cadences.
