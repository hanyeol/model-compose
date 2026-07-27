# Image Segmentation Model Task Example

This example demonstrates how to use Meta's Segment Anything Model (SAM) to generate segmentation masks from images using model-compose's built-in image-segmentation task.

## Overview

This workflow provides local promptable segmentation that:

1. **Local SAM Model**: Runs Meta's Segment Anything Model locally without external APIs
2. **Automatic Mode**: Generates masks for every distinct region in the image without any prompts
3. **Box-Prompted Mode**: Refines masks around user-supplied bounding boxes (e.g. from an object-detection component)
4. **SAM 1 and SAM 2 Support**: Works with any Ultralytics SAM checkpoint (`sam_b.pt`, `sam2_b.pt`, `sam2.1_l.pt`, `mobile_sam.pt`, etc.)
5. **Automatic Model Management**: Downloads and caches the default model on first use

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Sufficient system resources to run SAM (recommended: 8GB+ RAM; GPU strongly recommended for automatic mode)
- Python environment with `ultralytics` (installed automatically on first run)

### Why Local Segmentation

Unlike cloud-based vision APIs, running SAM locally provides:

**Benefits of Local Processing:**
- **Privacy**: All images are processed locally, no data sent to external services
- **Cost**: No per-image or API usage fees
- **Offline**: Works without an internet connection after the initial model download
- **Latency**: No network round-trip on every inference
- **Custom Models**: Any Ultralytics SAM checkpoint can be plugged in

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API — automatic mode:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image"}'
   ```

   **Using API — box-prompted mode:**
   ```bash
   # Single box
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image", "box_prompt": [100, 100, 300, 400]}'

   # Multiple boxes
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image", "box_prompt": [[100, 100, 300, 400], [500, 200, 250, 250]]}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an image file
   - Optionally supply `box_prompt`, `min_confidence`, `min_area`, `max_segment_count`, and `return_mask`
   - Click the "Run Workflow" button

## Result Format

**Automatic mode:**
```json
{
  "segments": [
    {
      "score": 0.92,
      "bounding_box": [x, y, width, height],
      "area": 12345,
      "mask": "<PNG>"
    }
  ],
  "width": 1920,
  "height": 1080
}
```

**Box-prompted mode** adds a `prompt_index` field per segment:
```json
{
  "segments": [
    {
      "score": 0.87,
      "bounding_box": [x, y, width, height],
      "area": 12345,
      "mask": "<PNG>",
      "prompt_index": 0
    }
  ],
  "width": 1920,
  "height": 1080
}
```

- `score` — Segment confidence (SAM's stability estimate).
- `bounding_box` — `[x, y, width, height]` derived from the mask, top-left origin.
- `area` — Mask area in pixels.
- `mask` — Binary mask as a PNG (omitted when `return_mask: false`).
- `prompt_index` — Index of the input `box_prompt` this segment corresponds to (only in box-prompted mode).

Segments are sorted by `score` in descending order and truncated to `max_segment_count`.

## Combining with Object Detection

The output of an [object-detection](../object-detection/README.md) component can feed directly into SAM as box prompts:

```yaml
jobs:
  - id: detect
    component: yolo-detector
    action:
      image: ${input.image as image}
  - id: segment
    component: sam-segmenter
    action:
      image: ${input.image as image}
      box_prompt: ${detect.output.objects[*].bounding_box}
```

## Using a Custom Model

Replace the `model` block in `model-compose.yml` to point at any Ultralytics SAM checkpoint. For example:

```yaml
model:
  provider: local
  path: /path/to/your/mobile_sam.pt
```

Available Ultralytics SAM checkpoints: `sam_b.pt`, `sam_l.pt`, `sam2_t.pt`, `sam2_b.pt`, `sam2_l.pt`, `sam2.1_t.pt`, `sam2.1_b.pt`, `sam2.1_l.pt`, `mobile_sam.pt`.

## Action Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `image` | image | (required) | Input image |
| `box_prompt` | `[x, y, w, h]` or `[[x, y, w, h], ...]` | `null` | Box prompt(s). If omitted, runs in automatic mode |
| `min_confidence` | float | `0.5` | Minimum segment confidence |
| `min_area` | int | `null` | Minimum mask area in pixels (noise filter) |
| `max_segment_count` | int | `100` | Maximum segments per image |
| `return_mask` | bool | `true` | Return per-segment binary mask as PNG |
