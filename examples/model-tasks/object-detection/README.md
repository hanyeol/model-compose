# Object Detection Model Task Example

This example demonstrates how to use Ultralytics YOLO to detect objects in an image using model-compose's built-in object-detection task, providing offline detection capabilities.

## Overview

This workflow provides local object detection that:

1. **Local YOLO Model**: Runs an Ultralytics YOLO detection model locally without external APIs
2. **Bounding Boxes**: Returns per-object axis-aligned bounding boxes with class labels and confidence scores
3. **Custom Weights**: Works with any Ultralytics YOLO detection or segmentation checkpoint (`.pt`)
4. **Label Filter**: Optionally restrict detections to specific class labels via the `labels` action parameter
5. **Automatic Model Management**: Downloads and caches the default model automatically on first use

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Sufficient system resources to run YOLO (recommended: 4GB+ RAM)
- Python environment with `ultralytics` (installed automatically on first run)

### Why Local Object Detection

Unlike cloud-based vision APIs, running YOLO locally provides:

**Benefits of Local Processing:**
- **Privacy**: All images are processed locally, no data sent to external services
- **Cost**: No per-image or API usage fees
- **Offline**: Works without an internet connection after the initial model download
- **Latency**: No network round-trip on every inference
- **Custom Models**: Any Ultralytics YOLO checkpoint (`.pt`) can be plugged in, including domain-specific models

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Detect all objects (COCO 80 classes with the default yolo11n.pt)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image"}'

   # Detect only specific labels
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image", "labels": ["person", "dog"], "min_confidence": 0.5}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an image file
   - Optionally adjust `labels`, `min_confidence`, `max_object_count`, `iou_threshold`, `agnostic_nms`, and `bounding_box_padding`
   - Click the "Run Workflow" button

## Result Format

```json
{
  "objects": [
    {
      "label": "person",
      "label_id": 0,
      "score": 0.87,
      "bounding_box": [x, y, width, height]
    }
  ],
  "width": 1920,
  "height": 1080
}
```

- `label` — Human-readable class name from `model.names`.
- `label_id` — Integer class index as reported by the model.
- `score` — Detection confidence in `[0, 1]`.
- `bounding_box` — `[x, y, width, height]` in pixels, top-left origin.

## Using a Custom Model

Replace the `model` block in `model-compose.yml` to point at any Ultralytics YOLO checkpoint. For example, to use a custom detector trained on your own dataset:

```yaml
component:
  type: model
  task: object-detection
  driver: custom
  family: yolo
  model:
    provider: local
    path: /path/to/your/model.pt
  action:
    image: ${input.image as image}
    labels: [ your_class_a, your_class_b ]
    params:
      min_confidence: 0.3
```

Segmentation checkpoints (`yolo11*-seg.pt`, etc.) are also supported — only the bounding boxes are read; the masks are ignored.

## Action Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `image` | image | (required) | Input image |
| `labels` | list[str] | `null` | Restrict detections to these class labels. Unknown labels fail fast |
| `max_object_count` | int | `300` | Maximum detections per image |
| `bounding_box_padding` | float | `0.0` | Expand each bounding box by this ratio of its width/height on every side (e.g. `0.1` = 10%). Clamped to image bounds. Useful when feeding boxes to crop or SAM box prompts |
| `params.min_confidence` | float | `0.25` | Minimum detection confidence |
| `params.iou_threshold` | float | `0.7` | IoU threshold for non-maximum suppression |
| `params.agnostic_nms` | bool | `false` | Perform class-agnostic NMS across all labels |
