# Video Motion Estimator Component

The video motion estimator component fits **parametric motion models** to adjacent frame pairs using sparse feature tracking (Lucas-Kanade) and RANSAC similarity estimation. Unlike `video-frame-analyzer` — which summarizes a sequence as descriptive statistics — this component returns **estimates** of the underlying 2D motion (scale, rotation, translation), from which per-second rates (`zoom_per_s`, `pan_px_per_s`) and motion-class signals (Ken Burns, rigid camera move) are derived. Feed it a decoded frame sequence from `video-frame-extractor`.

Use it to:

- distinguish still-image-with-pan ("Ken Burns") from true camera motion,
- recover the pan/zoom parameters needed to reproduce a shot with ffmpeg `scale` + `crop` + `overlay`,
- gate a downstream "rigid motion" path (where a single planar transform fits the whole pair) from "complex motion" (where it does not).

## Basic Configuration

```yaml
components:
  - id: extractor
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}

  - id: motion
    type: video-motion-estimator
    driver: opencv
    action:
      mode: rigid
      frames: ${jobs.extract.output}
      frame_rate: 30
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-motion-estimator` |
| `driver` | string | `opencv` | Estimation backend. Only `opencv` is currently supported (LK + RANSAC rely on OpenCV) |
| `actions` | array | `[]` | List of estimation actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | **required** | Estimation to run. OpenCV: `rigid`, `kenburns` |
| `frames` | any | **required** | Frame sequence to estimate from: a flat list of frames, a stream of batches, or a variable reference to a `video-frame-extractor` output |
| `frame_rate` | float | `null` | Source frame rate in frames per second; required to convert per-pair deltas into per-second rates (`zoom_per_s`, `pan_px_per_s`) |
| `batch_size` | integer | `1` | Number of independent frame sequences processed per iteration |
| `streaming` | boolean | `false` | Whether partial estimates are emitted incrementally; modes that need the full sequence ignore this flag |
| `output` | string | `null` | Output template applied to the collected result |

### Rigid Mode Fields (`mode: rigid`, OpenCV)

Per-pair similarity (scale + rotation + translation) fit via `cv2.estimateAffinePartial2D` with RANSAC. Aggregates over pairs with enough inliers to yield `zoom_per_s` and `pan_px_per_s`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_width` | integer | `320` | Width in pixels the frames are resampled to before tracking (64-4096) |
| `max_features` | integer | `200` | Maximum number of feature points tracked per frame pair (16-2000) |
| `feature_quality` | float | `0.01` | `goodFeaturesToTrack` quality level (0.0-1.0) |
| `feature_min_distance` | float | `8.0` | Minimum pixel distance between features at analysis resolution |
| `ransac_threshold` | float | `3.0` | Maximum reprojection error (analysis-resolution pixels) for an inlier |
| `min_inliers` | integer | `10` | Minimum inliers for a pair to count towards the aggregated zoom/pan rates (4-1000) |

### Ken Burns Mode Fields (`mode: kenburns`, OpenCV)

Per-pair detector that fires when (a) tracked features barely move in scene coordinates (still content) **and** (b) a single planar transform fits the whole pair (camera moving across a static image). Returns the share of pairs where both conditions hold.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `analysis_width` | integer | `320` | Width in pixels the frames are resampled to before tracking (64-4096) |
| `max_features` | integer | `200` | Maximum number of feature points tracked per frame pair (16-2000) |
| `feature_quality` | float | `0.01` | `goodFeaturesToTrack` quality level (0.0-1.0) |
| `feature_min_distance` | float | `8.0` | Minimum pixel distance between features at analysis resolution |
| `ransac_threshold` | float | `3.0` | Maximum reprojection error (analysis-resolution pixels) for an inlier |
| `stillness_threshold` | float | `0.3` | Median feature displacement (analysis-resolution pixels) below which the content is treated as near-static |
| `rigid_inlier_floor` | float | `0.85` | Minimum RANSAC inlier ratio for the pair to be considered plane-like (0.0-1.0) |

## Supported Drivers

### OpenCV

Uses OpenCV (`goodFeaturesToTrack`, `calcOpticalFlowPyrLK`, `estimateAffinePartial2D`) plus numpy. Runs the per-pair fit in a thread executor.

```yaml
component:
  type: video-motion-estimator
  driver: opencv
  action:
    mode: rigid
    frames: ${jobs.extract.output}
    frame_rate: 30
```

**Auto-installed dependencies:** `opencv-python`, `numpy`

## Output Format

### Rigid Output (`mode: rigid`)

```python
{
  "rigid_inlier_ratio":  0.91,     # mean RANSAC inlier ratio across pairs; > 0.8 ≈ plane fits
  "rigid_residual":      0.42,     # mean inlier reprojection error (analysis-resolution px)
  "zoom_per_s":          0.08,     # 8% zoom-in per second; negative = zoom-out
  "pan_px_per_s":       24.6,      # pan magnitude in SOURCE-resolution pixels per second
  "pair_count":        119,
  "valid_pair_count":  115,        # pairs that cleared `min_inliers`
  "frame_count":       120,
  "frame_rate":         30.0,
  "analysis_width":    320,
  "min_inliers":        10,
}
```

Translations are reported in source-resolution pixels (the analysis-width downscale is undone internally) so the values are directly reusable in a reproduction pipeline.

### Ken Burns Output (`mode: kenburns`)

```python
{
  "kenburns_score":       0.86,    # fraction of pairs where content was still AND rigid fit held
  "kenburns_pair_count": 102,
  "median_displacement":   0.22,   # mean of per-pair median feature displacement (analysis-resolution px)
  "rigid_inlier_ratio":    0.94,   # mean RANSAC inlier ratio across pairs
  "pair_count":           119,
  "frame_count":          120,
  "frame_rate":            30.0,
  "analysis_width":       320,
  "stillness_threshold":    0.3,
  "rigid_inlier_floor":     0.85,
}
```

## Multiple Actions Configuration

`rigid` and `kenburns` share the same analysis cost per pair (both run LK tracking); when you need both, declare one component with two actions and feed the same extractor output:

```yaml
components:
  - id: extractor
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}

  - id: motion
    type: video-motion-estimator
    driver: opencv
    actions:
      - id: rigid
        mode: rigid
        frames: ${jobs.extract.output}
        frame_rate: ${input.frame_rate}
      - id: kenburns
        mode: kenburns
        frames: ${jobs.extract.output}
```

## Integration with Workflows

### Ken Burns vs True Camera Move

A still-photo panning montage ("Ken Burns") and a handheld camera move both produce apparent motion in the frame. The distinguishing signal is **feature displacement in scene coordinates**: Ken Burns features barely move in the scene (the content is one still image), while a true camera move has features sliding with parallax.

```yaml
workflows:
  - id: classify-motion
    jobs:
      - id: extract
        component: extractor
        input:
          video: ${input.video}
      - id: rigid
        component: motion
        action: rigid
        input:
          frames: ${jobs.extract.output}
          frame_rate: ${input.frame_rate}
      - id: kenburns
        component: motion
        action: kenburns
        input:
          frames: ${jobs.extract.output}

components:
  - id: motion
    type: video-motion-estimator
    driver: opencv
    actions:
      - id: rigid
        mode: rigid
      - id: kenburns
        mode: kenburns
```

`kenburns_score > 0.7` with `rigid_inlier_ratio > 0.9` indicates still-photo-with-pan. `kenburns_score < 0.2` with high `rigid_inlier_ratio` indicates a true planar camera move.

### Reproducing a Shot with ffmpeg

The `rigid` output's `zoom_per_s` and `pan_px_per_s` are directly usable to recreate a shot via `scale` + `crop` + `overlay` without re-measuring frame-by-frame:

```yaml
component:
  type: video-motion-estimator
  driver: opencv
  action:
    mode: rigid
    frames: ${jobs.extract.output}
    frame_rate: ${input.frame_rate}
```

Downstream, apply a per-second zoom of `zoom_per_s` and a per-second translation of `pan_px_per_s` (direction taken from the sign of the aggregated translation vector).

## Best Practices

1. **Pair with `video-frame-extractor`**: the estimator takes an `ImageArrayValue`; the extractor controls sampling cadence. A denser sampling means smaller per-pair deltas and a more stable aggregate — aim for ≥ 24 pairs per shot.
2. **Set `frame_rate`**: `zoom_per_s` and `pan_px_per_s` are 0.0 unless `frame_rate` is set — per-pair deltas are unitless without it.
3. **Keep `analysis_width` ≥ 240**: unlike the analyzer's metric work (which tolerates 96 px), LK + RANSAC need enough texture to find reliable features. 320 px on the long side is the usable floor; 96 px will produce empty inlier sets on smooth content.
4. **`min_inliers` gates aggregation, not reporting**: pairs below `min_inliers` still appear in `rigid_inlier_ratio`/`rigid_residual` but do not contribute to `zoom_per_s`/`pan_px_per_s`. `valid_pair_count` tells you how many pairs cleared the gate.
5. **`kenburns` is pair-local**: it fires per pair — a long static clip punctuated by one jump cut will dilute `kenburns_score`. For a cleaner read, run the estimator per shot (use `video-scene-detector` first).
6. **High `rigid_residual` with high `rigid_inlier_ratio`**: the fit is accepting a weak plane. Lower `ransac_threshold` (e.g. `1.5`) to force a tighter fit, at the cost of fewer inliers.
7. **Translations are in source-resolution pixels**: `analysis_width` is a speed knob, not a unit. `pan_px_per_s` is rescaled internally so it matches the extractor's output resolution — no post-processing needed.
