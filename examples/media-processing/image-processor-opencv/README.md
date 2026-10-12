# Image Processor (OpenCV) Example

This example demonstrates the OpenCV driver of model-compose's `image-processor` component. It uses classical computer-vision algorithms that live outside PIL — starting with Canny edge detection, which is a common ControlNet conditioning input.

## Overview

The `opencv` driver complements the default `native` (PIL) driver with OpenCV-only algorithms:

1. **Canny edge detection**: Produces a single-channel edge map from an input image
2. **Headless**: Pure algorithm, no model weights to download
3. **ControlNet ready**: The grayscale output feeds directly into ControlNet canny

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python environment with `opencv-python` and `numpy` (automatically managed)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/image-processor-opencv
   ```

2. No additional configuration required.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/input-image.jpg" \
     -F "low_threshold=100" \
     -F "high_threshold=200"
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an image and tweak the thresholds
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run image-processor-opencv --input '{"image": "/path/to/your/input-image.jpg", "low_threshold": 100, "high_threshold": 200}'
   ```

## Workflow Details

### "Detect Image Edges (Canny)" Workflow

**Description**: Produce a Canny edge map from an input image.

#### Input Parameters

| Parameter        | Type    | Required | Default | Description                                       |
|------------------|---------|----------|---------|---------------------------------------------------|
| `image`          | image   | Yes      | -       | Input image file (JPEG, PNG, etc.)                |
| `low_threshold`  | integer | No       | 100     | Lower hysteresis threshold for gradient magnitude |
| `high_threshold` | integer | No       | 200     | Upper hysteresis threshold for gradient magnitude |

#### Output Format

| Field | Type  | Description                                       |
|-------|-------|---------------------------------------------------|
| -     | image | Single-channel grayscale edge map (L), 0 or 255   |

## Customization

### Tuning Thresholds

Canny's two thresholds control sensitivity:

- Lower both for more edges (noisier but captures weaker gradients)
- Raise both for fewer, cleaner edges
- The ControlNet convention is a 2:1 ratio (e.g., 100/200, 50/100)

### Feeding into a ControlNet Workflow

Chain this component before a ControlNet-based image or video generator by piping its output into the ControlNet's conditioning input:

```yaml
workflow:
  jobs:
    - id: edges
      component: image-processor
      action: canny
      input:
        image: ${input.image}
    - id: generate
      component: controlnet-generator
      input:
        prompt: ${input.prompt}
        control_image: ${edges.output}
```

### Batch and Streaming

Pass a list of images or an upstream frame-extractor stream to produce per-frame edge maps for video pipelines:

```yaml
component:
  type: image-processor
  driver: opencv
  action:
    method: canny
    image: ${input.frames}
    batch_size: 8
```

## Model-less by Design

The OpenCV driver only hosts algorithms that need no learned weights. Model-based edge/line preprocessors (HED, PiDiNet, lineart) belong to the model component family instead.
