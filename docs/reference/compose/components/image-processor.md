# Image Processor Component

The image processor component provides a comprehensive set of image manipulation operations including resizing, cropping, rotating, flipping, and various filters. It's built on the Pillow (PIL) library and supports common image formats while enabling complex image processing workflows.

## Basic Configuration

```yaml
component:
  type: image-processor
  action:
    method: resize
    image: ${input.image}
    width: 800
    height: 600
    scale_mode: fit
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `image-processor` |
| `driver` | string | `native` | Image processing backend. Currently only `native` (Pillow) is supported. |
| `actions` | array | `[]` | List of image processing actions |

### Common Action Configuration

All image processor actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Processing method: `resize`, `crop`, `rotate`, `flip`, `grayscale`, `blur`, `sharpen`, `adjust-brightness`, `adjust-contrast`, `adjust-saturation`, `concat`, `merge`, `overlay`, `mosaic` |
| `image` | string / array | **required** | Input image(s) — a single image (file path, base64 string, or variable reference) or a list of images |
| `batch_size` | integer / string | `null` | Number of input images to process in a single batch |
| `output` | any | `null` | Output variable mapping |

## Image Processing Methods

### Resize

Resize images with different scaling modes:

```yaml
component:
  type: image-processor
  action:
    method: resize
    image: ${input.image}
    width: 1024
    height: 768
    scale_mode: fit
    output: ${output}
```

**Resize Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `width` | integer | `null` | Target width in pixels (at least one of width/height required) |
| `height` | integer | `null` | Target height in pixels (at least one of width/height required) |
| `scale_mode` | string | `fit` | Scaling mode: `fit`, `fill`, `stretch` |

**Scale Modes:**

- **`fit`**: Maintain aspect ratio, fit inside target dimensions (may have empty space)
- **`fill`**: Maintain aspect ratio, fill target dimensions (may crop excess)
- **`stretch`**: Ignore aspect ratio, stretch to exact dimensions

### Crop

Extract a rectangular region from an image:

```yaml
component:
  type: image-processor
  action:
    method: crop
    image: ${input.image}
    x: 100
    y: 100
    width: 400
    height: 300
    output: ${output}
```

**Crop Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | integer | **required** | X coordinate of top-left corner |
| `y` | integer | **required** | Y coordinate of top-left corner |
| `width` | integer | **required** | Crop width in pixels |
| `height` | integer | **required** | Crop height in pixels |

### Rotate

Rotate an image by a specified angle:

```yaml
component:
  type: image-processor
  action:
    method: rotate
    image: ${input.image}
    angle: 45
    expand: true
    output: ${output}
```

**Rotate Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `angle` | number | **required** | Rotation angle in degrees (positive = counter-clockwise) |
| `expand` | boolean | `true` | Expand canvas to fit rotated image (prevents cropping) |

### Flip

Flip an image horizontally or vertically:

```yaml
component:
  type: image-processor
  action:
    method: flip
    image: ${input.image}
    direction: horizontal
    output: ${output}
```

**Flip Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `direction` | string | **required** | Flip direction: `horizontal` or `vertical` |

### Grayscale

Convert an image to grayscale:

```yaml
component:
  type: image-processor
  action:
    method: grayscale
    image: ${input.image}
    output: ${output}
```

### Blur

Apply Gaussian blur to an image:

```yaml
component:
  type: image-processor
  action:
    method: blur
    image: ${input.image}
    radius: 5.0
    output: ${output}
```

**Blur Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `radius` | number | `2.0` | Blur radius in pixels (higher = more blur) |

### Sharpen

Enhance image sharpness:

```yaml
component:
  type: image-processor
  action:
    method: sharpen
    image: ${input.image}
    factor: 2.0
    output: ${output}
```

**Sharpen Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `factor` | number | `1.0` | Sharpening factor (1.0 = original, >1.0 = sharper) |

### Adjust Brightness

Adjust image brightness:

```yaml
component:
  type: image-processor
  action:
    method: adjust-brightness
    image: ${input.image}
    factor: 1.3
    output: ${output}
```

**Brightness Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `factor` | number | **required** | Brightness factor (1.0 = original, <1.0 = darker, >1.0 = brighter) |

### Adjust Contrast

Adjust image contrast:

```yaml
component:
  type: image-processor
  action:
    method: adjust-contrast
    image: ${input.image}
    factor: 1.5
    output: ${output}
```

**Contrast Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `factor` | number | **required** | Contrast factor (1.0 = original, <1.0 = less contrast, >1.0 = more contrast) |

### Adjust Saturation

Adjust image color saturation:

```yaml
component:
  type: image-processor
  action:
    method: adjust-saturation
    image: ${input.image}
    factor: 1.2
    output: ${output}
```

**Saturation Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `factor` | number | **required** | Saturation factor (0.0 = grayscale, 1.0 = original, >1.0 = more saturated) |

### Concat

Concatenate multiple images side-by-side, stacked, or in a grid. This method requires the `image` field to be a **list of images**.

```yaml
component:
  type: image-processor
  action:
    method: concat
    image:
      - ${input.image_a}
      - ${input.image_b}
      - ${input.image_c}
    mode: horizontal
    spacing: 10
    background: "#ffffffff"
    output: ${output}
```

**Concat Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `horizontal` | Concat layout: `horizontal`, `vertical`, or `grid` |
| `columns` | integer | `null` | Number of columns for `grid` mode |
| `rows` | integer | `null` | Number of rows for `grid` mode |
| `spacing` | integer | `0` | Pixel spacing between images (applies to `horizontal`, `vertical`, and `grid` modes) |
| `background` | string / RGBA | `"#00000000"` | Background color as a hex string (e.g. `"#ffffffff"`) or `[r, g, b, a]` tuple |

Use `grid` mode with `columns` and/or `rows` to lay images out in a matrix. When only one dimension is specified, the other is derived from the input list length.

### Merge

Compose multiple images onto a shared canvas by overlaying them at their native positions (alpha channels are preserved). Like `concat`, this method requires the `image` field to be a **list of images**.

```yaml
component:
  type: image-processor
  action:
    method: merge
    image:
      - ${input.base}
      - ${input.overlay_a}
      - ${input.overlay_b}
    anchor: center
    background: "#00000000"
    output: ${output}
```

**Merge Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `anchor` | string | `center` | Where each image is aligned on the shared canvas. One of `top-left`, `top-center`, `top-right`, `center-left`, `center`, `center-right`, `bottom-left`, `bottom-center`, `bottom-right`. |
| `background` | string / RGBA | `"#00000000"` | Background color of the output canvas (hex string or `[r, g, b, a]` tuple) |

`merge` alpha-composites each input in order onto a canvas sized to fit the union of all inputs, aligning each image at `anchor`. `concat` tiles inputs edge-to-edge without overlap.

### Overlay

Paste one overlay image onto the base image at an explicit position. Unlike `merge` (which centers all inputs on a shared canvas) and `concat` (which tiles inputs), `overlay` places a single overlay at a caller-supplied `(x, y)`, optionally resizing and adjusting opacity. The base image size and color mode are preserved.

```yaml
component:
  type: image-processor
  action:
    method: overlay
    image: ${input.base}
    overlay: ${input.logo}
    x: 20
    y: 20
    width: 120
    opacity: 0.8
    output: ${output}
```

**Overlay Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `overlay` | string | **required** | Overlay image (file path, base64 string, or variable reference). Must resolve to a single image. |
| `x` | integer | **required** | X coordinate of the anchor point on the base image. |
| `y` | integer | **required** | Y coordinate of the anchor point on the base image. |
| `width` | integer | `null` | Resize overlay width in pixels before pasting. If only one of `width`/`height` is set, the other is derived from the overlay's native aspect ratio. When both are set, the overlay is resized to exactly `(width, height)` and may be distorted. |
| `height` | integer | `null` | Resize overlay height in pixels before pasting. |
| `anchor` | string | `top-left` | Which point of the overlay is placed at `(x, y)`. One of `top-left`, `top-center`, `top-right`, `center-left`, `center`, `center-right`, `bottom-left`, `bottom-center`, `bottom-right`. |
| `opacity` | number | `1.0` | Alpha multiplier for the overlay (0.0 = fully transparent, 1.0 = as-is). |

Overlays whose bounding box extends past the base image are clipped naturally (no error). The base image's color mode is preserved: an RGB base returns RGB, an RGBA base returns RGBA. As with other single-image methods, `image` accepts a single image, a list, or a stream — `overlay` and the placement parameters are then applied to every base image.

### Mosaic

Obscure one or more rectangular regions of an image (or the whole image) with a mosaic effect. Typical use is redacting faces or license plates — pipe `face-detection` / `face-tracking` bounding boxes straight in.

```yaml
component:
  type: image-processor
  action:
    method: mosaic
    image: ${input.image}
    mode: pixelate
    # Pipe a detection component's bounding boxes directly. Each box is
    # `{x, y, width, height}` matching the mosaic region shape.
    region: ${jobs.detect.output.faces[*].bounding_box}
    block_size: 16
    output: ${output}
```

**Mosaic Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `pixelate` | Algorithm: `pixelate` (block-based downsample) or `blur` (Gaussian blur) |
| `region` | object or list | `null` | Region(s) to mosaic as `{x, y, width, height}` (single) or `[{...}, ...]` (multiple). Omit to apply the mosaic to the whole image. |
| `block_size` | integer | `16` | Absolute pixelate block size in pixels (larger = more pixelated). Used when `mode` is `pixelate`. Mutually exclusive with `block_scale`. Applied when neither is specified. |
| `block_scale` | number | `null` | Pixelate block size relative to each region's shorter side, in `(0.0, 1.0]`. Adapts automatically to region size — small faces get a proportionally finer block than large ones. Prefer this over `block_size` when regions vary widely in size (e.g. face bounding boxes at different distances). Used when `mode` is `pixelate`. Mutually exclusive with `block_size`. |
| `min_block_size` | integer | `8` | Minimum pixelate block size in pixels. Only takes effect with `block_scale` — clamps the computed block size so tiny regions still get a visible mosaic instead of a 1–2 pixel block that looks nearly untouched. |
| `max_block_size` | integer | `32` | Maximum pixelate block size in pixels. Only takes effect with `block_scale` — clamps the computed block size so large regions do not turn into a handful of oversized blocks that look like pixel art. |
| `blur_radius` | number | `8.0` | Blur radius in pixels. Used when `mode` is `blur`. |
| `corner_radius` | integer | `0` | Absolute corner radius in pixels for rounded-rectangle mosaic regions. `0` keeps square corners; larger values round each region's corners and leave the original pixels outside the rounded shape untouched. Mutually exclusive with `corner_scale`. Applied when neither is specified. |
| `corner_scale` | number | `null` | Corner radius relative to each region's shorter side, in `[0.0, 0.5]`. Adapts automatically to region size — small faces get a proportionally smaller corner than large ones. Prefer this over `corner_radius` when regions vary widely in size. Mutually exclusive with `corner_radius`. |

`block_size` and `block_scale` are mutually exclusive; setting both raises a validation error. When neither is set, `block_size: 16` is applied — a sensible fixed default matching FFmpeg's `pixelize` filter. For workflows where regions vary widely in size (e.g. face bounding boxes at different distances), set `block_scale` instead so the mosaic strength stays visually consistent across regions. `min_block_size` and `max_block_size` clamp `block_scale`'s output — the effective block size is `min(max_block_size, max(min_block_size, round(shorter_side * block_scale)))`.

`corner_radius` and `corner_scale` are mutually exclusive; setting both raises a validation error. When neither is set, corners stay square. Radius (absolute or computed from `corner_scale`) is automatically clamped to half of each region's shorter side so it never exceeds the region. Under `mode: pixelate` the corner mask snaps to the block grid — each block is either fully kept or fully dropped, so no block is cut in half at the rounded edge and the pixel-art look stays intact. Under `mode: blur` the corner is a smooth anti-aliased curve.

Each region shares the same `{x, y, width, height}` shape used by detection components' `bounding_box` outputs. Regions that extend past the image are clipped naturally. When multiple regions overlap, later regions mosaic the already-mosaicked pixels of earlier ones (so overlapping faces stay redacted).

> For PNG compression, see the [`image-compressor`](image-compressor.md) component.

## Multiple Actions Configuration

Define multiple image processing operations:

```yaml
component:
  type: image-processor
  actions:
    - id: thumbnail
      method: resize
      image: ${input.image}
      width: 200
      height: 200
      scale_mode: fill
      output: ${thumbnail}

    - id: enhance
      method: sharpen
      image: ${input.image}
      factor: 1.5
      output: ${enhanced}

    - id: convert-grayscale
      method: grayscale
      image: ${input.image}
      output: ${grayscale}
```

## Usage Examples

### Image Enhancement Pipeline

Apply multiple enhancements sequentially:

```yaml
workflows:
  - id: enhance-photo
    jobs:
      - id: sharpen
        component: image-processor
        action: sharpen-image
        input:
          image: ${input.photo}
        output:
          sharpened: ${output}

      - id: adjust-colors
        component: image-processor
        action: boost-saturation
        input:
          image: ${jobs.sharpen.output.sharpened}
        output:
          enhanced: ${output}
        depends_on: [ sharpen ]

      - id: final-brightness
        component: image-processor
        action: brighten
        input:
          image: ${jobs.adjust-colors.output.enhanced}
        depends_on: [ adjust-colors ]

components:
  - id: image-processor
    type: image-processor
    actions:
      - id: sharpen-image
        method: sharpen
        image: ${input.image}
        factor: 1.5
        output: ${output}

      - id: boost-saturation
        method: adjust-saturation
        image: ${input.image}
        factor: 1.2
        output: ${output}

      - id: brighten
        method: adjust-brightness
        image: ${input.image}
        factor: 1.1
        output: ${output}
```

### Photo Filters

Create Instagram-style filters:

```yaml
workflows:
  - id: vintage-filter
    title: Apply Vintage Filter
    jobs:
      - id: desaturate
        component: image-processor
        action: adjust-saturation
        input:
          image: ${input.photo}
        output:
          desaturated: ${output}

      - id: warm-contrast
        component: image-processor
        action: adjust-contrast
        input:
          image: ${jobs.desaturate.output.desaturated}
        output:
          filtered: ${output}
        depends_on: [ desaturate ]

      - id: brighten
        component: image-processor
        action: adjust-brightness
        input:
          image: ${jobs.warm-contrast.output.filtered}
        depends_on: [ warm-contrast ]

  - id: noir-filter
    title: Apply Noir Filter
    jobs:
      - id: convert-grayscale
        component: image-processor
        action: grayscale
        input:
          image: ${input.photo}
        output:
          grayscale: ${output}

      - id: boost-contrast
        component: image-processor
        action: adjust-contrast
        input:
          image: ${jobs.convert-grayscale.output.grayscale}
        depends_on: [ convert-grayscale ]

components:
  - id: image-processor
    type: image-processor
    actions:
      - id: adjust-saturation
        method: adjust-saturation
        image: ${input.image}
        factor: 0.7
        output: ${output}

      - id: adjust-contrast
        method: adjust-contrast
        image: ${input.image}
        factor: 1.2
        output: ${output}

      - id: adjust-brightness
        method: adjust-brightness
        image: ${input.image}
        factor: 1.05
        output: ${output}

      - id: grayscale
        method: grayscale
        image: ${input.image}
        output: ${output}
```

### Responsive Image Generation

Generate multiple sizes for responsive web design:

```yaml
workflows:
  - id: generate-responsive-images
    jobs:
      - id: mobile
        component: image-processor
        action: mobile-size
        input:
          image: ${input.original}
        output:
          mobile: ${output}

      - id: tablet
        component: image-processor
        action: tablet-size
        input:
          image: ${input.original}
        output:
          tablet: ${output}

      - id: desktop
        component: image-processor
        action: desktop-size
        input:
          image: ${input.original}
        output:
          desktop: ${output}

components:
  - id: image-processor
    type: image-processor
    actions:
      - id: mobile-size
        method: resize
        image: ${input.image}
        width: 640
        scale_mode: fit
        output: ${output}

      - id: tablet-size
        method: resize
        image: ${input.image}
        width: 1024
        scale_mode: fit
        output: ${output}

      - id: desktop-size
        method: resize
        image: ${input.image}
        width: 1920
        scale_mode: fit
        output: ${output}
```

### Watermark Preparation

Prepare images for watermarking:

```yaml
workflows:
  - id: prepare-for-watermark
    title: Prepare Image for Watermarking
    jobs:
      - id: resize-image
        component: image-processor
        action: resize-standard
        input:
          image: ${input.photo}
        output:
          resized: ${output}

      - id: adjust-brightness
        component: image-processor
        action: reduce-brightness
        input:
          image: ${jobs.resize-image.output.resized}
        output:
          prepared: ${output}
        depends_on: [ resize-image ]

      - id: enhance-contrast
        component: image-processor
        action: boost-contrast
        input:
          image: ${jobs.adjust-brightness.output.prepared}
        depends_on: [ adjust-brightness ]

components:
  - id: image-processor
    type: image-processor
    actions:
      - id: resize-standard
        method: resize
        image: ${input.image}
        width: 1200
        scale_mode: fit
        output: ${output}

      - id: reduce-brightness
        method: adjust-brightness
        image: ${input.image}
        factor: 0.9
        output: ${output}

      - id: boost-contrast
        method: adjust-contrast
        image: ${input.image}
        factor: 1.1
        output: ${output}
```

### Smart Cropping

Center crop with different aspect ratios:

```yaml
component:
  type: image-processor
  actions:
    - id: crop-square
      method: resize
      image: ${input.image}
      width: 800
      height: 800
      scale_mode: fill
      output: ${result}

    - id: crop-landscape
      method: resize
      image: ${input.image}
      width: 1200
      height: 675
      scale_mode: fill
      output: ${result}

    - id: crop-portrait
      method: resize
      image: ${input.image}
      width: 675
      height: 1200
      scale_mode: fill
      output: ${result}
```

## Advanced Usage Examples

### Conditional Image Processing

Apply different processing based on image properties:

```yaml
workflows:
  - id: smart-resize
    jobs:
      - id: process-image
        component: image-processor
        action: ${input.orientation == 'landscape' ? 'resize-landscape' : 'resize-portrait'}
        input:
          image: ${input.photo}

components:
  - id: image-processor
    type: image-processor
    actions:
      - id: resize-landscape
        method: resize
        image: ${input.image}
        width: 1600
        height: 900
        scale_mode: fit

      - id: resize-portrait
        method: resize
        image: ${input.image}
        width: 900
        height: 1600
        scale_mode: fit
```

### Batch Image Processing

Process multiple images in parallel:

```yaml
workflows:
  - id: batch-thumbnail-creation
    jobs:
      - id: process-batch
        component: image-processor
        action: create-thumbnail
        input:
          images: ${input.image_batch}  # Array of images
        output:
          thumbnails: ${output}

components:
  - id: image-processor
    type: image-processor
    actions:
      - id: create-thumbnail
        method: resize
        image: ${input.images}
        width: 200
        height: 200
        scale_mode: fill
        output: ${output}
```

### Color Correction Pipeline

Automatic color correction workflow:

```yaml
workflows:
  - id: auto-correct-colors
    jobs:
      - id: adjust-brightness
        component: image-processor
        action: auto-brightness
        input:
          image: ${input.photo}
        output:
          brightness_corrected: ${output}

      - id: adjust-contrast
        component: image-processor
        action: auto-contrast
        input:
          image: ${jobs.adjust-brightness.output.brightness_corrected}
        output:
          contrast_corrected: ${output}
        depends_on: [ adjust-brightness ]

      - id: adjust-saturation
        component: image-processor
        action: auto-saturation
        input:
          image: ${jobs.adjust-contrast.output.contrast_corrected}
        depends_on: [ adjust-contrast ]

components:
  - id: image-processor
    type: image-processor
    actions:
      - id: auto-brightness
        method: adjust-brightness
        image: ${input.image}
        factor: ${input.brightness_factor | 1.1}
        output: ${output}

      - id: auto-contrast
        method: adjust-contrast
        image: ${input.image}
        factor: ${input.contrast_factor | 1.2}
        output: ${output}

      - id: auto-saturation
        method: adjust-saturation
        image: ${input.image}
        factor: ${input.saturation_factor | 1.1}
        output: ${output}
```

## Image Format Support

The image processor supports common image formats through Pillow:

- **JPEG/JPG**: Lossy compression, good for photos
- **PNG**: Lossless compression, supports transparency
- **WebP**: Modern format with better compression
- **GIF**: Animation support (first frame processed)
- **BMP**: Uncompressed bitmap
- **TIFF**: High-quality, multi-page support

## Integration with Workflows

### E-commerce Product Images

```yaml
workflows:
  - id: product-image-pipeline
    jobs:
      - id: main-image
        component: image-processor
        action: product-main
        input:
          image: ${input.product_photo}
        output:
          main: ${output}

      - id: thumbnail
        component: image-processor
        action: product-thumb
        input:
          image: ${input.product_photo}
        output:
          thumb: ${output}

      - id: zoom-view
        component: image-processor
        action: product-zoom
        input:
          image: ${input.product_photo}
        output:
          zoom: ${output}

components:
  - id: image-processor
    type: image-processor
    actions:
      - id: product-main
        method: resize
        image: ${input.image}
        width: 800
        height: 800
        scale_mode: fit
        output: ${output}

      - id: product-thumb
        method: resize
        image: ${input.image}
        width: 150
        height: 150
        scale_mode: fill
        output: ${output}

      - id: product-zoom
        method: resize
        image: ${input.image}
        width: 2000
        height: 2000
        scale_mode: fit
        output: ${output}
```

### Social Media Image Preparation

```yaml
component:
  type: image-processor
  actions:
    - id: instagram-square
      method: resize
      image: ${input.image}
      width: 1080
      height: 1080
      scale_mode: fill
      output: ${instagram_square}

    - id: instagram-story
      method: resize
      image: ${input.image}
      width: 1080
      height: 1920
      scale_mode: fill
      output: ${instagram_story}

    - id: twitter-post
      method: resize
      image: ${input.image}
      width: 1200
      height: 675
      scale_mode: fill
      output: ${twitter_post}

    - id: facebook-cover
      method: resize
      image: ${input.image}
      width: 820
      height: 312
      scale_mode: fill
      output: ${facebook_cover}
```

## Variable Interpolation

Image processor supports dynamic configuration:

```yaml
component:
  type: image-processor
  action:
    method: ${input.operation | resize}
    image: ${input.image}
    width: ${input.target_width as integer | 800}
    height: ${input.target_height as integer | 600}
    scale_mode: ${input.mode as select/fit,fill,stretch | fit}
    # For adjustments
    factor: ${input.adjustment_factor as number | 1.0}
    # For rotation
    angle: ${input.rotation_angle as number | 0}
    expand: ${input.expand_canvas as boolean | false}
    # For blur
    radius: ${input.blur_radius as number | 2.0}
```

## Best Practices

1. **Choose Appropriate Scale Mode**: Use `fit` for previews, `fill` for thumbnails, `stretch` only when necessary
2. **Preserve Aspect Ratios**: Maintain original proportions for most use cases
3. **Quality vs Size**: Balance image quality with file size for web delivery
4. **Pipeline Order**: Apply resize before filters for better performance
5. **Use Appropriate Formats**: JPEG for photos, PNG for graphics with transparency
6. **Batch Processing**: Process multiple images in parallel when possible
7. **Error Handling**: Validate image inputs and handle corrupt files gracefully
8. **Caching**: Cache processed images to avoid redundant operations

## Performance Considerations

- **Resize First**: Always resize before applying filters to reduce processing time
- **Batch Operations**: Process multiple images in parallel workflows
- **Quality Settings**: Adjust quality parameters based on use case
- **Format Selection**: Choose efficient formats (WebP) for web delivery
- **Memory Management**: Process very large images in streaming mode when available

## Common Use Cases

- **Thumbnail Generation**: Create preview images for galleries
- **Responsive Images**: Generate multiple sizes for different devices
- **Photo Enhancement**: Apply filters and adjustments to improve photos
- **Social Media**: Prepare images for various social platforms
- **E-commerce**: Process product photos for online stores
- **Content Management**: Optimize images for web publishing
- **Image Normalization**: Standardize image sizes and formats
- **Watermark Preparation**: Prepare images for watermarking systems
