# Image Compressor Component

The image compressor component encodes an image as a compressed **PNG** and returns the resulting **bytes** (not a PIL image). Three drivers trade off size, speed, and dependency footprint. Feed the output into a `file-store` write, an HTTP upload, or anywhere raw bytes are accepted.

## Basic Configuration

```yaml
component:
  type: image-compressor
  driver: native
  action:
    image: ${input.image}
    compress_level: 9
    output: ${output}
```

## Configuration Options

### Component Settings

All image-compressor drivers share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `image-compressor` |
| `driver` | string | `native` | Backend driver: `native`, `oxipng`, `pngquant` |
| `actions` | array | `[]` | List of compression actions |

### Common Action Configuration

All actions accept these fields (driver-specific fields are listed under each driver):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | string / array | **required** | Input image(s) — file path, base64 string, or variable reference |
| `batch_size` | integer / string | `null` | Number of input images processed per batch |
| `strip_metadata` | boolean | `true` | Strip ancillary PNG metadata chunks (tEXt, eXIf, iCCP, etc.) |
| `output` | any | `null` | Output variable mapping |

## Supported Drivers

### Native (Pillow)

Pure Pillow encode with `optimize=True`. No extra dependencies. Small, predictable gains.

```yaml
component:
  type: image-compressor
  driver: native
  action:
    image: ${input.image}
    compress_level: 9
    strip_metadata: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `compress_level` | integer | `9` | DEFLATE compression level from 0 to 9; higher is smaller and slower |

### Oxipng

Lossless PNG optimization via [oxipng](https://github.com/shssoichiro/oxipng). Reruns DEFLATE filter search on top of a Pillow-encoded PNG for an extra 10–30% size reduction.

```yaml
component:
  type: image-compressor
  driver: oxipng
  action:
    image: ${input.image}
    level: 4
    strip_metadata: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | integer | `4` | Oxipng optimization level from 0 to 6; higher is smaller and slower |

**Requirements:** the `pyoxipng` Python package.

### Pngquant

Lossy palette-based quantization via the `pngquant` CLI. Builds an adaptive ≤256-color palette; typically 50–70% smaller than lossless at visually similar quality for photographic or gradient-heavy images.

```yaml
component:
  type: image-compressor
  driver: pngquant
  action:
    image: ${input.image}
    speed: 3
    min_quality: 65
    max_quality: 85
    strip_metadata: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `speed` | integer | `3` | Pngquant speed from 1 (slowest/best) to 11 (fastest) |
| `min_quality` | integer | `null` | Minimum acceptable quality (0–100); encoding fails when output would fall below this |
| `max_quality` | integer | `null` | Maximum quality (0–100) the encoder targets |

**Quality range examples:**

```yaml
# Balanced — target ≤85 quality, fail if it can't reach 65
min_quality: 65
max_quality: 85

# Cap only — allow any quality up to 80
max_quality: 80

# Floor only — never fall below quality 60
min_quality: 60
```

**Requirements:** the `pngquant` executable in `PATH` (install via `brew install pngquant` / `apt install pngquant`).

## Return Value

Each action returns the compressed PNG as raw `bytes`. When the input is a list or stream, the action returns a list or stream of bytes in the same shape.
