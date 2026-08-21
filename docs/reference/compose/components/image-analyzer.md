# Image Analyzer Component

The image analyzer component measures quality properties of an image — brightness, contrast, sharpness (blur), and exposure clipping — and returns a compact summary. Use it for photo QA, thumbnail scoring, OCR pre-flight checks, and archive-scan validation. Every metric is a pure read; the image is never modified.

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
| `driver` | string | `native` | Analysis backend. Currently: `native` (Pillow + numpy) |
| `actions` | array | `[]` | List of measurement actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric` | string | **required** | Measurement to run: `brightness`, `contrast`, `sharpness`, `exposure` |
| `image` | any | **required** | Image source: file path, variable reference, or upload stream |
| `batch_size` | integer | `null` | Number of input images to process in a single batch |
| `output` | string | `null` | Output template applied to the collected result |

### Brightness Metric Fields (`metric: brightness`)

Mean, min, max, and standard deviation of luma (BT.601 grayscale). No configurable fields beyond the common ones.

### Contrast Metric Fields (`metric: contrast`)

RMS contrast (luma standard deviation) and percentile-clipped Michelson contrast. No configurable fields beyond the common ones.

### Sharpness Metric Fields (`metric: sharpness`)

Blur detection via Laplacian variance — the classic cheap out-of-focus detector.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `blur_threshold` | float | `100.0` | Laplacian variance below which `is_blurry` is set to true |

### Exposure Metric Fields (`metric: exposure`)

Shadow and highlight clipping detection.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `shadow_threshold` | integer | `16` | Pixel value (0-255) at or below which a pixel counts as clipped-shadow |
| `highlight_threshold` | integer | `239` | Pixel value (0-255) at or above which a pixel counts as clipped-highlight |

## Supported Drivers

### Native

Uses Pillow to decode and numpy for the numeric work; runs in a thread executor to avoid blocking the event loop. All metrics operate on an 8-bit luma channel derived from Pillow's `convert("L")` (BT.601).

```yaml
component:
  type: image-analyzer
  driver: native
  action:
    metric: sharpness
    image: ${input.image}
```

**Auto-installed dependency:** `numpy`

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

## Best Practices

1. **This component is read-only** — pair it with `image-processor` (resize, adjust brightness/contrast), `image-compressor` (PNG shrink), or a downstream renderer when you also want to change the image.
2. **`sharpness` needs content-appropriate thresholds**: 100 works for typical 8-bit photos, but scanned documents may sit around 30-60 while high-detail nature photos exceed 500. Calibrate against a small labeled set before wiring it into a gate.
3. **`contrast` reports two numbers on purpose**: `rms_contrast` for photographic content, `michelson_contrast` for high-contrast material like OCR pages. They can disagree — pick the one that matches your source.
4. **`exposure` percentages beat absolute counts for gates**: `highlight_clipped_ratio > 0.05` (5%) is a more portable check than raw pixel counts, which scale with resolution.
5. **Batch multiple images with `batch_size`**: the batch runs metrics in parallel with `asyncio.gather` — helpful for scanning a library.
6. **All metrics use BT.601 luma**: the same coefficients Pillow's `convert("L")` uses. If you need a different color space (Rec. 709, linear light) that isn't currently exposed — file it as a request.
