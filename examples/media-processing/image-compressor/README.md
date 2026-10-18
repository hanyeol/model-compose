# Image Compressor Example

This example demonstrates PNG compression using the `image-compressor` component, showcasing all three drivers it ships with: Pillow (`native`), `oxipng`, and `pngquant`. Each driver trades off size, speed, and dependency footprint.

## Overview

Three workflows wrap the three drivers:

1. **Compress PNG (Pillow)** — pure-Pillow DEFLATE encode. No extra dependencies.
2. **Lossless Shrink (oxipng)** — runs oxipng on top of a Pillow-encoded PNG for an extra 10–30% lossless size reduction.
3. **Lossy Palette Quantization (pngquant)** — reduces the image to a ≤256-color adaptive palette, typically 50–70% smaller than lossless at visually similar quality for photographic or gradient-heavy images.

All workflows return the compressed PNG as a base64 image.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- The `oxipng` workflow needs the `pyoxipng` Python package
- The `pngquant` workflow needs the `pngquant` binary in `PATH`:
  - macOS: `brew install pngquant`
  - Debian/Ubuntu: `apt install pngquant`

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/image-compressor
   ```

2. No additional environment configuration required — all processing is done locally.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run a workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select a workflow (Compress PNG, Lossless Shrink, Lossy Palette Quantization)
   - Upload an image and tune the driver-specific parameters
   - Click the "Run Workflow" button
   - View and download the compressed PNG

   **Using API:**
   ```bash
   # Pillow — maximum DEFLATE level
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow_id=compress-native" \
     -F "image=@input.png" \
     -F "compress_level=9"

   # oxipng — extra lossless shrink
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow_id=compress-oxipng" \
     -F "image=@input.png" \
     -F "level=4"

   # pngquant — lossy palette quantization
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow_id=compress-pngquant" \
     -F "image=@input.png" \
     -F "min_quality=65" \
     -F "max_quality=85"
   ```

   **Using CLI:**
   ```bash
   model-compose run compress-native   --input '{"image": "input.png", "compress_level": 9}'
   model-compose run compress-oxipng   --input '{"image": "input.png", "level": 4}'
   model-compose run compress-pngquant --input '{"image": "input.png", "min_quality": 65, "max_quality": 85}'
   ```

## Component Details

### Image Compressor Component
- **Type**: `image-compressor`
- **Drivers**: `native` (Pillow), `oxipng`, `pngquant`
- **Output**: compressed PNG bytes (returned as base64 image to the workflow)

A single `image-compressor` component is bound to a single driver, so this example declares three separate component instances — one per driver — and routes each workflow to the matching instance.

## Workflow Details

### "Compress PNG (Pillow)" Workflow

**Description**: Encode the input image as a PNG using Pillow with `optimize=True`.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | image | Yes | - | The image to compress |
| `compress_level` | integer | No | `9` | DEFLATE compression level (0 = store, 9 = maximum) |
| `strip_metadata` | boolean | No | `true` | Strip ancillary PNG metadata chunks (tEXt, eXIf, iCCP, etc.) |

### "Lossless Shrink (oxipng)" Workflow

**Description**: Rerun DEFLATE filter search over a Pillow-encoded PNG with oxipng.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | image | Yes | - | The image to compress |
| `level` | integer | No | `4` | Oxipng optimization level (0 = fast, 6 = best) |
| `strip_metadata` | boolean | No | `true` | Strip ancillary PNG metadata chunks |

### "Lossy Palette Quantization (pngquant)" Workflow

**Description**: Build an adaptive ≤256-color palette with pngquant.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | image | Yes | - | The image to compress |
| `speed` | integer | No | `3` | Pngquant speed from 1 (slowest/best) to 11 (fastest) |
| `min_quality` | integer | No | `65` | Minimum acceptable quality (0–100); encoding fails below this |
| `max_quality` | integer | No | `85` | Maximum quality (0–100) the encoder targets |
| `strip_metadata` | boolean | No | `true` | Strip ancillary PNG metadata chunks |

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `output` | image (base64) | The compressed PNG |

## When to Use Which Driver

- **native** — safe default; no extra install, decent size reduction, works everywhere.
- **oxipng** — chain after any lossless pipeline when every byte counts (icons, screenshots, UI assets).
- **pngquant** — biggest wins on photographic / gradient-heavy PNGs; lossy, so review the output quality.

## Troubleshooting

### Common Issues

1. **`pyoxipng` not found** — install the Python package (`pip install pyoxipng`) in the same environment as model-compose.
2. **`pngquant` not found** — install the CLI (`brew install pngquant` or `apt install pngquant`) and ensure it is on `PATH`.
3. **pngquant encoding fails** — the input could not meet `min_quality`. Lower `min_quality` or drop it entirely to accept whatever quality pngquant produces.
4. **Output looks larger than expected** — PNG compression gains depend heavily on the input. For photographs, consider pngquant; for already-optimized PNGs, further gains are small.
