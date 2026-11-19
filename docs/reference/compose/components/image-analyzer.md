# Image Analyzer Component

The image analyzer component measures image properties — luma statistics (brightness, contrast, exposure, darkness), texture/structural detail (sharpness, noise, flat regions), color (palette, color variety), gradient structure, edge structure, multi-scale texture, and lit/ink structure — and returns a compact summary. Use it for photo QA, thumbnail scoring, OCR pre-flight checks, archive-scan validation, and pixel-level forensic cues (live action vs rendered / AI / code-drawn content). Every metric is a pure read; the image is never modified.

## Basic Configuration

```yaml
component:
  type: image-analyzer
  driver: native
  action:
    metric: sharpness
    image: ${input.image}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `image-analyzer` |
| `driver` | string | `native` | Analysis backend. `native` (Pillow + numpy) or `opencv` (OpenCV + numpy) |
| `actions` | array | `[]` | List of measurement actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric` | string | **required** | Measurement to run. Native: `brightness`, `contrast`, `exposure`, `darkness`, `sharpness`, `noise`, `flat-regions`, `palette`, `color-variety`. OpenCV: `gradient`, `edge-structure`, `texture`, `lit-structure` |
| `image` | any | **required** | Image source: file path, variable reference, or upload stream |
| `batch_size` | integer | `null` | Number of input images to process in a single batch |
| `output` | string | `null` | Output template applied to the collected result |

### Brightness Metric Fields (`metric: brightness`)

Mean, min, max, and standard deviation of luma (BT.601 grayscale). No configurable fields beyond the common ones.

### Contrast Metric Fields (`metric: contrast`)

RMS contrast (luma standard deviation) and percentile-clipped Michelson contrast. No configurable fields beyond the common ones.

### Exposure Metric Fields (`metric: exposure`)

Shadow and highlight clipping detection.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `shadow_threshold` | integer | `16` | Pixel value (0-255) at or below which a pixel counts as clipped-shadow |
| `highlight_threshold` | integer | `239` | Pixel value (0-255) at or above which a pixel counts as clipped-highlight |

### Darkness Metric Fields (`metric: darkness`)

Dark-region profile plus block-level flatness within the dark region — distinguishes crushed-shadow night footage (grain survives) from rendered dark backgrounds (zero std per block).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dark_threshold` | integer | `32` | Luma value (0-255) at or below which a pixel counts as dark |
| `block_size` | integer | `8` | Side length in pixels of the square blocks used to compute dark-region flatness (2-64) |
| `flat_std_threshold` | float | `0.6` | Luma standard-deviation threshold identifying flat blocks within the dark region |

### Sharpness Metric Fields (`metric: sharpness`)

Blur detection via Laplacian variance — the classic cheap out-of-focus detector.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `blur_threshold` | float | `100.0` | Laplacian variance below which `is_blurry` is set to true |

### Noise Metric Fields (`metric: noise`)

Immerkær (1996) fast noise estimate. The 3×3 mask annihilates smooth regions and quadratic ramps, so the convolution response is dominated by noise. Edge pixels (above a gradient-magnitude quantile) are excluded.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `edge_quantile` | float | `0.6` | Gradient-magnitude quantile above which pixels are treated as edges and excluded from the noise estimate (0.0-1.0) |

### Flat Regions Metric Fields (`metric: flat-regions`)

Fraction of block-sized tiles whose luma standard deviation falls below a threshold. Rendered graphics (flat color fills) score high; photographic content scores low.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `block_size` | integer | `8` | Side length in pixels of the square blocks analyzed for flatness (2-64) |
| `std_threshold` | float | `0.6` | Luma standard-deviation threshold below which a block is classified as flat |

### Palette Metric Fields (`metric: palette`)

Quantizes RGB to a reduced bit depth and counts the smallest palette covering the requested share of pixels. Reports entropy and top-K dominant colors.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bits_per_channel` | integer | `4` | Bits retained per RGB channel when quantizing the image for palette counting (1-8) |
| `coverage` | float | `0.95` | Fraction of pixels the counted palette must cover; the reported count is the smallest palette reaching this coverage |
| `top_k` | integer | `8` | Number of dominant colors returned in order of pixel share |

### Color Variety Metric Fields (`metric: color-variety`)

Counts vivid pixels and distinct hue bands. Captures both saturation diversity (how colorful) and hue diversity (how many different colors).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vivid_saturation` | float | `0.6` | Saturation threshold (0.0-1.0) above which a pixel counts as vivid |
| `vivid_value` | float | `0.4` | Value/brightness threshold (0.0-1.0) above which a pixel counts as vivid |
| `hue_bins` | integer | `12` | Number of hue bins used to count distinct hue bands (1-36) |
| `hue_bin_min_share` | float | `0.01` | Minimum share of vivid pixels a hue bin must hold to count as a distinct band |

### Gradient Metric Fields (`metric: gradient`, OpenCV driver)

Gentle-gradient band: pixels brighter than flat (`gradient_min`) but below an edge (`gradient_max`). Code-rendered gradients occupy wide bands cleanly; photographic shading occupies them with fine-scale curvature.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `gradient_min` | float | `2.0` | Lower Sobel-magnitude bound of the gentle-gradient band (below is treated as flat) |
| `gradient_max` | float | `20.0` | Upper Sobel-magnitude bound of the gentle-gradient band (above is treated as an edge) |
| `curvature_threshold` | float | `1.0` | Second-derivative magnitude below which a gentle-gradient pixel counts as `clean` (smoothly curving) |

### Edge Structure Metric Fields (`metric: edge-structure`, OpenCV driver)

Edge density, axis-aligned ratio (horizontal/vertical strokes — a UI signature), and orientation entropy over edge pixels.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `edge_threshold` | float | `80.0` | Sobel gradient-magnitude threshold above which a pixel is counted as an edge |
| `axis_tolerance_degrees` | float | `4.0` | Angular tolerance in degrees around 0°/90° within which an edge counts as axis-aligned (0.0-45.0) |
| `orientation_bins` | integer | `18` | Number of orientation bins used to compute edge-direction entropy (2-180) |

### Texture Metric Fields (`metric: texture`, OpenCV driver)

Band-pass residuals at three scales via progressive median blurs. A rendered gradient keeps all three near zero; photographic grain survives the fine blur; fabric weave survives the mid blur; surface markings survive the coarse one.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `fine_kernel` | integer | `3` | Median-blur kernel size (odd, ≥3) that removes fine-scale texture |
| `mid_kernel` | integer | `7` | Median-blur kernel size (odd, ≥3) that removes mid-scale texture |
| `coarse_kernel` | integer | `15` | Median-blur kernel size (odd, ≥3) that removes coarse-scale texture |
| `detail_threshold` | float | `6.0` | Absolute high-pass residual above which a pixel counts as carrying detail at the target scale |

Kernels must be strictly increasing: `fine_kernel < mid_kernel < coarse_kernel`.

### Lit Structure Metric Fields (`metric: lit-structure`, OpenCV driver)

Local-maxima peaks and neighbourhood smoothness for lit pixels (bright on dark) and ink pixels (dark on light). Particle/wireframe graphics produce many peaks and little smoothness; photographic shading produces few peaks and high smoothness.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lit_threshold` | integer | `128` | Luma value (0-255) above which a pixel is considered lit |
| `ink_threshold` | integer | `96` | Luma value (0-255) below which a pixel is considered ink (dark mark on light ground) |
| `peak_window` | integer | `3` | Dilation window side length (odd, ≥3) used to detect local-maxima peaks |
| `smooth_tolerance` | float | `8.0` | Luma difference below which a lit/ink pixel counts as shading smoothly with its neighbourhood |

## Supported Drivers

### Native

Uses Pillow to decode and numpy for the numeric work; runs in a thread executor to avoid blocking the event loop. Carries the luma-statistics, texture (sharpness/noise/flat-regions), and color metrics.

```yaml
component:
  type: image-analyzer
  driver: native
  action:
    metric: sharpness
    image: ${input.image}
```

**Auto-installed dependency:** `numpy`

### OpenCV

Uses OpenCV plus numpy; same thread-executor model. Carries metrics that lean on Sobel derivatives, median-blur stacks, dilation/erosion, and Gaussian blur — operations where OpenCV's native implementations are substantially faster than pure numpy.

```yaml
component:
  type: image-analyzer
  driver: opencv
  action:
    metric: edge-structure
    image: ${input.image}
```

**Auto-installed dependencies:** `opencv-python`, `numpy`

## Output Format

### Brightness Output (`metric: brightness`)

```python
{
  "mean_brightness": 128.4,   # 0-255
  "min_brightness":    3.0,
  "max_brightness":  252.0,
  "std_brightness":   45.1,
  "width":  1920,
  "height": 1080,
}
```

### Contrast Output (`metric: contrast`)

```python
{
  "rms_contrast":       45.1,   # luma std dev
  "michelson_contrast":  0.82,  # (high - low) / (high + low) on 1st/99th percentiles
  "luma_percentile_1":   14.0,
  "luma_percentile_99": 241.0,
  "width":  1920,
  "height": 1080,
}
```

### Exposure Output (`metric: exposure`)

```python
{
  "shadow_threshold":            16,
  "highlight_threshold":        239,
  "shadow_clipped_pixels":     1240,
  "highlight_clipped_pixels":  8321,
  "shadow_clipped_ratio":         0.000598,
  "highlight_clipped_ratio":      0.004013,
  "mean_brightness":            128.4,
  "width":  1920,
  "height": 1080,
}
```

### Darkness Output (`metric: darkness`)

```python
{
  "dark_ratio":          0.42,     # share of pixels at/below dark_threshold
  "dark_std":            4.7,      # luma std among dark pixels (low = crushed shadows, high = grainy night)
  "dark_flat":           0.18,     # share of mostly-dark blocks that are also flat (1.0 = rendered dark bg)
  "dark_pixels":      348160,
  "dark_blocks":         312,
  "dark_threshold":       32,
  "block_size":            8,
  "flat_std_threshold":    0.6,
  "width":  1920,
  "height": 1080,
}
```

### Sharpness Output (`metric: sharpness`)

```python
{
  "laplacian_variance": 245.8,   # higher = sharper
  "blur_threshold":     100.0,
  "is_blurry":          False,
  "width":  1920,
  "height": 1080,
}
```

### Noise Output (`metric: noise`)

```python
{
  "noise_sigma":     3.2,     # Immerkær sigma estimate; ~0 for rendered, ~1-5 for phone footage
  "edge_quantile":   0.6,
  "edge_cutoff":    24.5,     # gradient magnitude at the 60th percentile
  "non_edge_pixels": 1245678,
  "non_edge_ratio":  0.601,
  "width":  1920,
  "height": 1080,
}
```

### Flat Regions Output (`metric: flat-regions`)

```python
{
  "flat_ratio":     0.73,    # share of blocks under std_threshold
  "flat_blocks":   23552,
  "total_blocks":  32400,
  "block_size":        8,
  "std_threshold":     0.6,
  "mean_block_std":    1.4,
  "width":  1920,
  "height": 1080,
}
```

### Palette Output (`metric: palette`)

```python
{
  "bits_per_channel":  4,
  "coverage":          0.95,
  "palette_size":     16,    # smallest palette covering 95% of pixels
  "unique_colors":    47,
  "palette_entropy":   3.8,  # Shannon entropy in bits
  "dominant_colors": [
    {"rgb": [136,  72,  40], "share": 0.42},
    {"rgb": [ 24,  24,  24], "share": 0.18},
    {"rgb": [248, 248, 248], "share": 0.11},
    # ...
  ],
  "width":  1920,
  "height": 1080,
}
```

### Color Variety Output (`metric: color-variety`)

```python
{
  "vivid_ratio":        0.34,       # share of pixels above vivid thresholds
  "vivid_pixels":   705024,
  "sat_p90":            0.78,       # 90th-percentile saturation
  "hue_bands":          3,          # distinct hue bins meeting min_share
  "hue_histogram": [0.33, 0.0, 0.0, 0.0, 0.33, 0.0, 0.0, 0.0, 0.33, 0.0, 0.0, 0.0],
  "vivid_saturation":   0.6,
  "vivid_value":        0.4,
  "width":  1920,
  "height": 1080,
}
```

### Gradient Output (`metric: gradient`)

```python
{
  "grad_share":           0.42,   # share of pixels in the gentle-gradient band
  "grad_pixels":       860160,
  "grad_clean":           0.91,   # share of gentle pixels with sub-threshold curvature
  "grad_mean_curvature":  0.4,
  "gradient_min":         2.0,
  "gradient_max":        20.0,
  "curvature_threshold":  1.0,
  "width":  1920,
  "height": 1080,
}
```

### Edge Structure Output (`metric: edge-structure`)

```python
{
  "edge_density":              0.22,   # share of pixels above edge_threshold
  "edge_pixels":           455808,
  "axis_edge_ratio":           0.94,   # share of edges within axis_tolerance_degrees of 0°/90° (UI signature)
  "axis_aligned_pixels":   428459,
  "edge_orientation_entropy":  0.63,   # Shannon entropy over orientation_bins
  "edge_threshold":           80.0,
  "axis_tolerance_degrees":    4.0,
  "orientation_bins":         18,
  "width":  1920,
  "height": 1080,
}
```

### Texture Output (`metric: texture`)

```python
{
  "tex_fine":         0.036,   # mean |luma - fine_blur| / 255
  "tex_mid":          0.016,
  "tex_coarse":       0.007,
  "detail_ratio":     0.61,    # share of pixels with fine residual >= detail_threshold
  "detail_threshold": 6.0,
  "fine_kernel":      3,
  "mid_kernel":       7,
  "coarse_kernel":   15,
  "width":  1920,
  "height": 1080,
}
```

### Lit Structure Output (`metric: lit-structure`)

```python
{
  "lit_ratio":        0.21,    # share of pixels at/above lit_threshold
  "lit_pixels":    435456,
  "lit_smooth":       0.78,    # share of lit pixels whose residual <= smooth_tolerance (high = shaded)
  "lit_peaks":        0.004,   # share of lit pixels that are local maxima (high = particles / points / line art)
  "ink_ratio":        0.03,
  "ink_pixels":     62208,
  "ink_smooth":       0.82,
  "ink_peaks":        0.002,
  "lit_threshold":   128,
  "ink_threshold":    96,
  "peak_window":       3,
  "smooth_tolerance":  8.0,
  "width":  1920,
  "height": 1080,
}
```

## Multiple Actions Configuration

```yaml
component:
  type: image-analyzer
  driver: native
  actions:
    - id: brightness
      metric: brightness
      image: ${input.image}

    - id: sharpness
      metric: sharpness
      image: ${input.image}
      blur_threshold: 150

    - id: exposure
      metric: exposure
      image: ${input.image}
```

Native and OpenCV metrics live in separate components because they are different drivers:

```yaml
components:
  - id: native-stats
    type: image-analyzer
    driver: native
    actions:
      - id: noise
        metric: noise
        image: ${input.image}
      - id: flat
        metric: flat-regions
        image: ${input.image}

  - id: cv-stats
    type: image-analyzer
    driver: opencv
    actions:
      - id: edges
        metric: edge-structure
        image: ${input.image}
      - id: texture
        metric: texture
        image: ${input.image}
```

## Integration with Workflows

### Reject Blurry Uploads

```yaml
workflows:
  - id: upload-qa
    jobs:
      - id: check
        component: analyzer
        action: sharpness
        input:
          image: ${input.image}

components:
  - id: analyzer
    type: image-analyzer
    action:
      metric: sharpness
      image: ${input.image}
      blur_threshold: 120
```

### Thumbnail Candidate Scoring

Score candidate frames by brightness and sharpness together:

```yaml
components:
  - id: analyzer
    type: image-analyzer
    actions:
      - id: brightness
        metric: brightness
        image: ${input.image}
      - id: sharpness
        metric: sharpness
        image: ${input.image}
```

### Rendered-vs-Photographic Hint

Combine noise, flat regions, and edge structure to score how likely an image is rendered (UI, code graphics, 3D) versus photographic. All three metrics return `float`s, so a workflow step can compute a weighted score without extra code.

```yaml
components:
  - id: native-stats
    type: image-analyzer
    driver: native
    actions:
      - id: noise
        metric: noise
        image: ${input.image}
      - id: flat
        metric: flat-regions
        image: ${input.image}

  - id: cv-stats
    type: image-analyzer
    driver: opencv
    actions:
      - id: edges
        metric: edge-structure
        image: ${input.image}
```

High `axis_edge_ratio` + high `flat_ratio` + low `noise_sigma` is the UI/code-render signature. Photographic content shows the opposite.

## Best Practices

1. **This component is read-only** — pair it with `image-processor` (resize, adjust brightness/contrast), `image-compressor` (PNG shrink), or a downstream renderer when you also want to change the image.
2. **`sharpness` needs content-appropriate thresholds**: 100 works for typical 8-bit photos, but scanned documents may sit around 30-60 while high-detail nature photos exceed 500. Calibrate against a small labeled set before wiring it into a gate.
3. **`contrast` reports two numbers on purpose**: `rms_contrast` for photographic content, `michelson_contrast` for high-contrast material like OCR pages. They can disagree — pick the one that matches your source.
4. **`exposure` percentages beat absolute counts for gates**: `highlight_clipped_ratio > 0.05` (5%) is a more portable check than raw pixel counts, which scale with resolution.
5. **`noise` excludes edges by design**: the `edge_quantile` cut keeps strong boundaries out of the sigma estimate. On text-heavy frames the glyph edges still leak noise upward; verify on representative content before setting thresholds.
6. **`darkness` tells crushed shadows from a rendered dark background**: `dark_std` near zero plus `dark_flat` near 1.0 means a code-drawn dark panel; photographic night scenes keep grain and stay closer to `dark_std` ≈ 3-8, `dark_flat` well below 1.0.
7. **`palette` is sensitive to `bits_per_channel`**: at 4 bits the palette tops out at 4096 colors, which is often what distinguishes "heavily quantized export" from "natural photo". Lower the bit depth for a coarser summary.
8. **`color-variety`'s `hue_bands` works best on vivid content**: dim or desaturated frames rarely cross the `vivid_value` / `vivid_saturation` thresholds, so `hue_bands` stays low. Not a flaw — just means the metric is a vivid-color-diversity probe, not a general palette counter.
9. **`gradient` + `edge-structure` cover opposite ends of the derivative range**: gentle gradients (0-20) versus edges (≥80 by default). If `grad_share` is high and `edge_density` is low, the image is mostly smooth color.
10. **`texture` kernels control scale sensitivity**: `(3, 7, 15)` is a good default. Larger media (above ~2K) benefits from `(5, 11, 23)` or similar. Keep the ratio roughly 1 : 2.3 : 5.
11. **`lit-structure`'s `lit_peaks` near 1.0 indicates point-cloud / particle / dot-matrix imagery** — the dilation-equals-source test is extremely sensitive to isolated bright pixels. Natural images peak around 0.01-0.05.
12. **Batch multiple images with `batch_size`**: the batch runs metrics in parallel with `asyncio.gather` — helpful for scanning a library.
13. **All metrics use BT.601 luma**: the same coefficients Pillow's `convert("L")` uses. If you need a different color space (Rec. 709, linear light) that isn't currently exposed — file it as a request.
