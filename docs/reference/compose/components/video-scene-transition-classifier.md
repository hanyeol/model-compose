# Video Scene Transition Classifier Component

The video scene transition classifier labels each **boundary** between consecutive scenes — as produced by `video-scene-detector` — with the kind of edit that joins the two shots. The `native` driver covers luma-based labels (`cut`, `jump`, `dissolve`, `fade_in`, `fade_out`, `flash`, `wipe`, `slide`, `blur`, `unknown`); the `opencv` driver extends it with motion-based labels (`whip`, `zoom`, `spin`, `shake`, `glitch`) by running feature tracking + affine estimation on top of the native signals. For every boundary the action also returns the raw signals that drove the decision (`pair_mad`, `has_same_structure`, `blend_residual`, `brightness_slope`, `edge_residual`, `region_pure`, `blur_rx`, and — for opencv — `motion_zoom`, `motion_rotation`, `motion_path`, etc.) so the result is auditable and tunable, not a black box.

Use it when you already have a scene list and need to know *what kind of edit* joins each pair of shots (editorial style analysis, interpolation/AI-generation forensics, reproduction-pipeline routing).

## Basic Configuration

```yaml
components:
  - id: scenes
    type: video-scene-detector
    driver: pyscenedetect
    action:
      video: ${input.video}

  - id: frames
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}

  - id: transitions
    type: video-scene-transition-classifier
    driver: native
    action:
      scenes:     ${jobs.scenes.output}
      frames:     ${jobs.frames.output}
      frame_rate: 30
```

To also detect motion-hidden cuts (whip / zoom / spin / shake / glitch), switch `driver: native` to `driver: opencv`. The opencv driver accepts every native parameter plus motion-specific ones; the output format is identical with extra `motion_*` signals and five extra labels.

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-scene-transition-classifier` |
| `driver` | string | `native` | Classification backend. `native` (numpy only) or `opencv` (adds motion labels) |
| `actions` | array | `[]` | List of classification actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scenes` | any | **required** | Scene list as produced by `video-scene-detector`; each `end_frame` becomes a boundary classified against the next scene |
| `frames` | any | **required** | Decoded frame sequence covering the full video; the classifier samples a window around each boundary |
| `frame_rate` | float | `null` | Source frame rate; used to report `boundary_time` in seconds and to size the adaptive analysis span |
| `batch_size` | integer | `1` | Number of independent frame sequences processed per iteration |
| `streaming` | boolean | `false` | Whether partial classifications are emitted per boundary as each window completes |
| `output` | string | `null` | Output template applied to the collected result |

### Native Driver Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `downsample_width` | integer | `96` | Width in pixels the frames are resampled to before measurement (16-4096) |
| `window_size` | integer | `15` | Upper bound on frames sampled on each side of a boundary; the analysis span auto-narrows within it to the actual transition ramp (1-64) |
| `cut_mad_threshold` | float | `20.0` | Mean absolute luma difference across the boundary pair above which a cut is considered |
| `dissolve_blend_threshold` | float | `0.25` | Maximum median scale-normalized residual of the linear-blend fit for a boundary to be classified as a dissolve (0.0-1.0; smaller = stricter) |
| `fade_black_threshold` | float | `45.0` | Mean luma below which the window's flat frame reads as a fade through black |
| `fade_white_threshold` | float | `210.0` | Mean luma above which the window's flat frame reads as a fade through white |
| `fade_ramp_min_slope` | float | `2.0` | Minimum per-frame luma slope for a boundary window to be classified as a fade |
| `flash_peak_threshold` | float | `170.0` | Minimum peak frame mean luma for a boundary to be classified as a flash (bright burst between two normal shots) |
| `flash_endpoint_gap` | float | `50.0` | Minimum gap between the peak frame and the brighter endpoint for a boundary to be classified as a flash |
| `wipe_edge_threshold` | float | `0.38` | Maximum relative residual of the straight-edge fit for a boundary to be classified as a wipe or slide (0.0-1.0; smaller = stricter) |
| `wipe_region_pure_threshold` | float | `0.6` | Minimum share of block-wise 'pure old or pure new' agreement for a wipe pattern that is not a straight edge (iris, center-out) |
| `blur_detail_ratio` | float | `0.5` | Maximum ratio of inside-window detail to endpoint detail for a boundary to be classified as blur (0.0-1.0; smaller = stricter, 0.5 = inside has at most half the gradient of a sharp endpoint) |
| `jump_block_min_std` | float | `4.0` | Minimum luma standard deviation inside a block for that block to contribute to the same-structure (jump) check; flatter blocks have no detail to line up |
| `jump_block_correlation` | float | `0.6` | Minimum brightness-normalized correlation per block for the block to count as structurally matching (0.0-1.0) |
| `jump_min_matching_blocks` | integer | `6` | Minimum number of detailed blocks required before the same-structure gate is trusted; too few detailed blocks fall back to cut (1-64) |
| `jump_min_match_ratio` | float | `0.5` | Minimum share of detailed blocks that must structurally match for the boundary to be classified as a jump instead of a cut (0.0-1.0) |

### OpenCV Driver Fields

Inherits every field from the native driver and adds:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `motion_max_features` | integer | `80` | Maximum number of feature points tracked per frame pair for affine motion estimation (16-2000) |
| `motion_feature_quality` | float | `0.01` | Minimum quality level passed to goodFeaturesToTrack (0.0-1.0) |
| `motion_feature_min_distance` | float | `4.0` | Minimum pixel distance between feature points at analysis resolution |
| `motion_ransac_threshold` | float | `2.0` | Maximum reprojection error (analysis-resolution pixels) for a feature correspondence to count as a RANSAC inlier |
| `motion_min_inlier_ratio` | float | `0.5` | Minimum inlier ratio for a pair's affine estimate to be trusted (0.0-1.0) |
| `motion_calm_path_limit` | float | `0.3` | Maximum summed camera path (share of frame) below which the window reads as calm — glitch detection gate |
| `motion_calm_zoom_limit` | float | `0.3` | Maximum summed `|log scale|` below which the window reads as calm — glitch detection gate |
| `motion_calm_rotation_limit` | float | `20.0` | Maximum summed `|rotation|` (degrees) below which the window reads as calm — glitch detection gate |
| `spin_min_rotation_degrees` | float | `25.0` | Minimum summed `|rotation|` (degrees) for a boundary to be classified as spin |
| `spin_turn_share` | float | `0.7` | Minimum share of rotation that must be signed (same direction) for a boundary to be classified as spin (0.0-1.0) |
| `zoom_min_scale_change` | float | `0.5` | Minimum summed `|log scale|` for a boundary to be classified as zoom |
| `whip_min_net_share` | float | `0.3` | Minimum net camera displacement (share of frame) for a boundary to be classified as whip |
| `whip_max_path_ratio` | float | `1.5` | Maximum ratio of total path to net displacement — whip travels mostly in one direction, so path/net must stay below this |
| `whip_max_detail_ratio` | float | `0.7` | Maximum per-axis inside/endpoint gradient ratio — whip motion-blurs the inside, so detail must fall below this (0.0-1.0) |
| `shake_min_path_share` | float | `0.4` | Minimum summed camera path (share of frame) for a boundary to be classified as shake |
| `shake_min_path_net_ratio` | float | `3.0` | Minimum ratio of total path to net displacement — shake oscillates, so path/net must exceed this |
| `shake_min_tracked_pairs` | integer | `3` | Minimum number of frame pairs with a tracked affine estimate for shake to be reported (1-64) |
| `glitch_min_back_swings` | integer | `2` | Minimum number of back-swings (progress curve reversing) for a boundary to be classified as glitch (1-64) |
| `glitch_min_hard_switches` | integer | `2` | Alternative gate: a single back-swing plus this many hard switches inside the window also reads as glitch (1-64) |

## Supported Drivers

### Native

Pure numpy on resampled luma thumbnails. Runs the per-boundary signal measurement in a thread executor. Emits `cut`, `jump`, `dissolve`, `fade_in`, `fade_out`, `flash`, `wipe`, `slide`, `blur`, `unknown`.

```yaml
component:
  type: video-scene-transition-classifier
  driver: native
  action:
    scenes: ${jobs.scenes.output}
    frames: ${jobs.frames.output}
```

**Auto-installed dependency:** `numpy`

### OpenCV

Inherits every native signal and gate, then measures camera motion between consecutive frames (feature tracking + affine estimation) across the full `window_size` so that cuts hidden by camera movement (whip pan, zoom punch, spin, shake) or by displaced frames (glitch) are classified as such instead of falling back to `cut`. The motion gates are checked before the native luma cascade; boundaries that don't match any motion effect are then classified exactly as the native driver would.

```yaml
component:
  type: video-scene-transition-classifier
  driver: opencv
  action:
    scenes: ${jobs.scenes.output}
    frames: ${jobs.frames.output}
```

**Auto-installed dependencies:** `numpy`, `opencv-python-headless`

Prefer `opencv` when the source leans on shorts/music-video editing style with motion-hidden cuts; stay on `native` for narrative drama, documentaries, or any pipeline where the ~10× motion-estimation cost per boundary is not worth the extra labels.

## Labels

| Label | Driver | Meaning | Primary signals |
|-------|--------|---------|-----------------|
| `cut` | both | Hard snap between two shots | `pair_mad >= cut_mad_threshold` (with no linear-blend rise) |
| `jump` | both | Same shot, lighting / exposure changes abruptly — cut-like luma spike but structure lines up block by block | `pair_mad >= cut_mad_threshold` AND `has_same_structure` (brightness-normalized block correlation) |
| `dissolve` | both | Every in-between frame is a linear blend of the two shots | small `blend_residual`, rising unclipped alpha |
| `fade_in` | both | Picture emerges from a flat color (black or white) | flat window frame + ramp slope away from the flat color |
| `fade_out` | both | Picture dissolves into a flat color | flat window frame + ramp slope towards the flat color |
| `flash` | both | Bright burst between two normal shots | `peak_luma` clears threshold AND stands out from the brighter endpoint by a fixed gap |
| `wipe` | both | A moving boundary reveals the new shot — straight edge (horizontal, vertical, or diagonal) or iris/shape mask | small `edge_residual` in `wipe` mode, OR high `region_pure` with any direction |
| `slide` | both | One shot slides over/under the other (push, cover, reveal), straight edge only | small `edge_residual` in `push`/`cover`/`reveal` modes |
| `blur` | both | Picture goes out of focus and comes back as the next shot | `max(blur_rx, blur_ry) < blur_detail_ratio` (both axes lose detail relative to the endpoints) |
| `whip` | opencv | Fast directional pan with motion blur hides the cut | `motion_net` crosses `whip_min_net_share` AND `motion_path/motion_net < whip_max_path_ratio` AND inside detail falls |
| `zoom` | opencv | Fast push-in / pull-out hides the cut | accumulated `motion_zoom` (sum of `|log scale|`) clears `zoom_min_scale_change` |
| `spin` | opencv | Rotation hides the cut | accumulated `motion_rotation` clears `spin_min_rotation_degrees` AND most of it is signed (`spin_turn_share`) |
| `shake` | opencv | Camera shake burst around the cut | `motion_path` oscillates (high path, low net) |
| `glitch` | opencv | Displaced / alternating frames | window progress curve reverses `motion_back` times within an otherwise calm camera |
| `unknown` | both | No gate fires — often a false-positive scene boundary from frame interpolation | — |

## Output Format

With `streaming: false` (default), the action returns a list of classification records — one per boundary between consecutive scenes. With `streaming: true`, each record is yielded as soon as its window is complete, letting downstream jobs react before the whole video is processed.

```python
[
  {
    "boundary_frame":  158,
    "boundary_time":    5.267,          # null when frame_rate is unset
    "label":           "cut",
    "confidence":       0.91,
    "signals": {
      "pair_mad":           36.4,       # luma jump across the boundary pair
      "has_same_structure": False,      # cut, not jump
      "blend_residual":   float("inf"), # linear-blend rising check failed
      "blend_length":       10,
      "brightness_slope":    0.3,
      "min_luma":          102.0,
      "max_luma":          118.0,
      "peak_luma":         118.0,
      "endpoint_max_luma": 118.0,
      "edge_residual":    float("inf"),
      "edge_mode":          None,
      "edge_direction":     None,
      "region_pure":         0.0,
      "region_direction":   None,
      "blur_rx":             1.0,
      "blur_ry":             1.0,
      # opencv driver only:
      # "motion_zoom":       0.08,
      # "motion_rotation":   3.2,
      # "motion_turn":       0.4,
      # "motion_path":       0.11,
      # "motion_net":        0.09,
      # "motion_heading":    "right",
      # "motion_tracked":    9,
      # "motion_back":       0,
      # "motion_jumps":      1,
    },
  },
]
```

Per-label counts (e.g. `cut_count`) are not aggregated here — compute them downstream when needed (`len([t for t in result if t["label"] == "cut"])`).

## Integration with Workflows

### Editorial Style Profile

Cutting style (ratio of cuts vs dissolves vs fades vs flashes vs wipes) is a strong editorial signature: documentaries lean on dissolves, narrative drama on cuts, music videos on hard cuts + flashes + motion-hidden cuts, broadcast news on wipes + slides.

```yaml
workflows:
  - id: profile-edits
    jobs:
      - id: scenes
        component: scene-detector
        input:
          video: ${input.video}
      - id: frames
        component: frame-extractor
        input:
          video: ${input.video}
      - id: transitions
        component: transition-classifier
        input:
          scenes:     ${jobs.scenes.output}
          frames:     ${jobs.frames.output}
          frame_rate: ${input.frame_rate}
```

Count labels downstream (`sum(1 for t in result if t["label"] == "cut")`) to build a label histogram you can treat as an editorial fingerprint. Switching the classifier component from `native` to `opencv` is enough to separate `whip`/`zoom`/`spin` cuts from plain `cut`s — downstream code reads the same dict shape.

### AI-Generated Clip Detection

AI-generated short-form video typically has **no real transitions** — a single long shot or frame-interpolated flow. If `video-scene-detector` reports multiple scenes but `transition-classifier` labels nearly all boundaries as `unknown` with low `pair_mad`, the "scenes" are detection false positives from frame-interpolation artifacts, not real cuts.

Pair with `video-frame-analyzer`'s `sharpness` metric: AI-interpolated video shows `sharp_period == 2` *and* `unknown` dominance in transitions.

### Reproduction Pipeline Routing

When reproducing a reference video shot by shot, each boundary needs the matching join:

- `cut` → concatenate shots directly
- `jump` → keep the two scenes as one shot with a lighting / exposure change (do not concatenate), or apply color-balance correction between them
- `dissolve` → ffmpeg `xfade=dissolve:duration=…`
- `fade_in` / `fade_out` → ffmpeg `fade=t=in` / `fade=t=out`
- `flash` → ffmpeg `xfade=fadewhite` (or an overlaid white flash frame)
- `wipe` → ffmpeg `xfade=wipeleft/wiperight/wipeup/wipedown:…` — pick by `signals.edge_direction`
- `slide` → ffmpeg `xfade=slideleft/slideright/slideup/slidedown:…`
- `blur` → blend via a blurred intermediate (`gblur` + `xfade=dissolve`)
- `whip` → ffmpeg `xfade=slideleft/slideright` with added motion blur (`gblur` + `tblend`) — direction from `signals.motion_heading`
- `zoom` → ffmpeg `xfade=zoomin` or a scaled-crop ramp
- `spin` → ffmpeg `rotate` ramp joined with `xfade=dissolve`
- `shake` / `glitch` → overlaid shake/glitch filter or a prebuilt effect clip

`boundary_time` and `signals.blend_length` give the duration needed by the xfade filter directly.

## Best Practices

1. **Pair both upstreams off the same source**: `scenes` from `video-scene-detector` and `frames` from `video-frame-extractor` must both describe the **same video** at the same frame rate — otherwise the boundary indices from `scenes` won't line up with `frames`.
2. **Keep `downsample_width` modest**: 96 px on the long side is enough for luma-difference, blend-residual, and gradient signals. The opencv driver's feature tracking also tolerates this width; bumping it higher raises motion-estimation cost without a quality bump on typical boundaries.
3. **`window_size` trade-off**: this is the upper bound on frames buffered around a boundary — the classifier auto-narrows the analysis span within it to the actual transition ramp (plateau-steady outer pad + rising-progress inside). Larger values catch longer fades and dissolves at the cost of more frame buffering; 15 (0.5 s at 30 fps) is a balanced default. Shrink it only when streaming memory matters more than gradual-transition recall.
4. **Pick the driver by content**: `native` is faster and numpy-only, which suits documentary / drama / interview footage where motion-hidden cuts are rare. `opencv` adds ~10 ms per boundary for feature tracking but is required to label whip / zoom / spin / shake / glitch — the dominant transition style in short-form video.
5. **`fade_*` relies on absolute black/white**: if the source has a letterbox or logo-corner that never goes to zero, the "flat frame" check will stay above `fade_black_threshold`. Preprocess with a crop if needed.
6. **`flash` vs `fade_in` through white**: a flash is a single-frame burst between two normal shots (endpoint picture → bright peak → endpoint picture); a fade-in through white is a sustained bright plateau that resolves to a picture. The `flash_endpoint_gap` gate requires the peak to clearly stand out from the brighter endpoint, which a fade cannot satisfy.
7. **`blur` requires sharp endpoints**: the gate compares inside-window detail to endpoint detail, so a boundary where either endpoint is already a flat/soft frame will not read as blur. This is intentional — a defocus into black is a fade, not a blur.
8. **`dissolve` vs `fade` order**: a fade-out → fade-in ("fade to black") is detected as two separate fade events, not one dissolve, because the brightness-slope signature dominates over the blend-residual signature. If you want to merge them, post-process the `transitions` list (adjacent `fade_out` + `fade_in` → "fade-through-black").
9. **`confidence` is heuristic**: it reflects how strongly the chosen signal cleared its threshold, not a calibrated probability. Use it for sorting, not for probabilistic reasoning.
