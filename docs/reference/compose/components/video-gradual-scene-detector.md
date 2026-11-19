# Video Gradual Scene Detector Component

The video gradual scene detector scans a decoded frame sequence for **gradual scene transitions** — fades, dissolves, wipes, slides — that hard-cut detectors cannot see because each step is a small frame-to-frame change. It returns the frames over which the transition unfolds plus the frame where the new shot takes over.

Pair it with `video-scene-detector` (hard cuts) to cover both kinds of boundary: hard cuts come from the cut detector, gradual boundaries come from here. Pass the cut-detector output as `known_boundaries` so the scanner does not re-report windows that already contain a cut.

## Basic Configuration

```yaml
components:
  - id: extractor
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}

  - id: gradual
    type: video-gradual-scene-detector
    driver: opencv
    action:
      frames: ${jobs.extract.output}
      frame_rate: 30
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-gradual-scene-detector` |
| `driver` | string | `opencv` | Scanner backend: `opencv` |
| `actions` | array | `[]` | List of detection actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | any | **required** | Decoded frame sequence (typically `${jobs.extract.output}` from a `video-frame-extractor`) |
| `frame_rate` | float | **required** | Source frame rate in frames per second; window lengths are derived from this |
| `known_boundaries` | array | `null` | Frame indices of boundaries already found by a hard-cut detector; windows around them are skipped |
| `batch_size` | integer | `1` | Number of independent frame sequences processed per iteration |
| `streaming` | boolean | `false` | Whether partial results are emitted incrementally |
| `output` | string | `null` | Output template applied to the collected result |

### OpenCV Driver Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `downsample_width` | integer | `96` | Width in pixels the frames are resampled to before scanning (16-4096) |
| `window_lengths` | array of (float or duration string) | `["200ms", "350ms", "600ms", "1s", "1.5s"]` | Candidate window lengths the scanner tries at each position; each value is seconds or a duration string (e.g. `"200ms"`, `"1.5s"`) |
| `plateau_share` | float | `0.3` | Maximum ratio of 'just-outside' change to 'across-the-window' change for the two ends to count as steady (0.0-1.0) |
| `min_changed_share` | float | `0.5` | Minimum share of the 6×8 block grid that must differ between window ends for the pair to count as different pictures (0.0-1.0) |
| `endpoint_min_std` | float | `12.0` | Minimum luma standard deviation at each window end; flatter ends count as empty-page fades, not shot changes |
| `endpoint_diff_threshold` | float | `10.0` | Minimum low-resolution mean absolute luma difference between the two window ends for the window to be considered at all |
| `motion_warp_threshold` | float | `0.45` | Maximum ratio of post-warp to pre-warp residual for optical-flow warp to 'explain' the change — the gate that rejects pan / zoom inside one take (0.0-1.0) |

## Supported Drivers

### OpenCV

Scans each frame pair at several window lengths, filters out windows explained by camera motion (Farneback optical flow) or by brightness-normalized block correlation (same scene under different light), and keeps the ones that look like a steady→ramp→steady progression between two different pictures.

```yaml
component:
  type: video-gradual-scene-detector
  driver: opencv
  action:
    frames: ${jobs.extract.output}
    frame_rate: 30
    known_boundaries: ${jobs.cuts.output[*].end_frame}
```

**Auto-installed dependencies:** `numpy`, `opencv-python`

## Output Format

Each detected gradual transition is one record in the result list:

```python
[
  {
    "start_frame":    412,      # last frame still showing the old shot
    "end_frame":      428,      # first frame fully showing the new shot
    "boundary_frame": 420,      # frame where the new shot takes over (progress crosses 0.5)
    "frame_rate":      30.0,
  },
  ...
]
```

Empty list when no gradual transition is found.

## Integration with Workflows

### Combined Hard-Cut + Gradual Detection

Streaming platform content often mixes hard cuts (most of the edit) with the occasional fade or dissolve (scene changes, title cards). A single pipeline:

```yaml
workflows:
  - id: all-boundaries
    jobs:
      - id: extract
        component: extractor
        input:
          video: ${input.video}
      - id: cuts
        component: cut-detector
        input:
          video: ${input.video}
      - id: gradual
        component: gradual-detector
        input:
          frames: ${jobs.extract.output}
          known_boundaries: ${jobs.cuts.output[*].end_frame}

components:
  - id: extractor
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}
      frame_rate: 30     # native rate; skipping frames hides short transitions

  - id: cut-detector
    type: video-scene-detector
    driver: pyscenedetect
    action:
      video: ${input.video}

  - id: gradual-detector
    type: video-gradual-scene-detector
    driver: opencv
    action:
      frames: ${input.frames}
      frame_rate: 30
      known_boundaries: ${input.known_boundaries}
```

The cut detector's boundaries become `known_boundaries` for the gradual scanner, so a fade that `pyscenedetect` already picked up is not reported twice.

## Best Practices

1. **Pass `known_boundaries` from the cut detector**: the scanner does scan every window position, but a cut always wins over a gradual interpretation and double-reporting the same edit is noisy. The pad around each taken boundary also prevents gradual windows from straddling a cut.
2. **Keep the native frame rate**: `window_lengths` is converted to frames via `frame_rate`. If the extractor downsamples (`frame_rate: 10` on a 30 fps source), short transitions (fast wipes, flashes) collapse into a handful of frames and the plateau/ramp/plateau structure stops reading.
3. **The motion gate is the main defense against false positives**: pans, push-ins, and focus pulls all produce steady-start-to-steady-end windows. Lower `motion_warp_threshold` to be stricter (more pans rejected, more real transitions may also go); raise it to be laxer.
4. **`endpoint_diff_threshold` on the low-resolution thumbnail is a fast reject**: at 12×16 the frames are summarized to block means, which cancels small motion. If a shot is visually busy but the two ends summarize to the same thing at that scale, the window is rejected before any expensive gate runs.
5. **`endpoint_min_std ≥ 12` rejects fades-on-plain-ground**: things fading in or out on a flat background (lower-third titles over a dark background, subtitle animations) have one steady end with very low std and get rejected. Lower this only if you specifically want to detect those.
6. **This component does not classify**: it finds boundaries but does not label them as fade / dissolve / wipe / slide. Chain `video-scene-transition-classifier` after it to assign a kind to each boundary.
