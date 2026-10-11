# Depth Estimation Model Task Example

This example demonstrates how to generate a monocular depth map from an input image using model-compose's built-in depth-estimation task with Depth Anything V2, suitable as a conditioning input for ControlNet or for downstream scene understanding.

## Overview

This workflow produces a per-pixel depth map that:

1. **Local Depth Model**: Runs Depth Anything V2 locally to estimate relative depth
2. **Grayscale Output**: Returns a single-channel depth map normalized to 0–255 (nearer pixels brighter by default)
3. **ControlNet Ready**: The grayscale output can be fed directly to ControlNet depth models
4. **Automatic Model Management**: Downloads and caches models automatically on first use
5. **No External APIs**: Fully offline depth estimation

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Sufficient resources for running Depth Anything V2 (recommended: 8GB+ RAM, GPU preferred)
- Python environment with torch and transformers (automatically managed)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/depth-estimation
   ```

2. No additional configuration required — model and dependencies are managed automatically.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/input-image.jpg"
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select an input image
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run depth-estimation --input '{"image": "/path/to/your/input-image.jpg"}'
   ```

## Component Details

### Depth Estimation Model Component (Default)
- **Type**: Model component with depth-estimation task
- **Purpose**: Monocular relative depth estimation
- **Model**: depth-anything/Depth-Anything-V2-Small-hf
- **Architecture**: Depth Anything V2 (DPT-style ViT)
- **Features**:
  - Robust zero-shot relative depth on in-the-wild images
  - Grayscale output ready for ControlNet depth conditioning
  - GPU acceleration support

### Model Information: Depth Anything V2

- **Developer**: DepthAnything (open source)
- **Architecture**: DPT head on a DINOv2 ViT backbone
- **Training**: Large-scale synthetic + real relative-depth data
- **Strengths**: Sharp boundaries, strong generalization across scenes
- **Input/Output**: RGB image → single-channel relative depth map

## Workflow Details

### "Estimate Image Depth" Workflow (Default)

**Description**: Generate a depth map from an input image using a pretrained monocular depth model.

#### Input Parameters

| Parameter | Type  | Required | Default | Description                       |
|-----------|-------|----------|---------|-----------------------------------|
| `image`   | image | Yes      | -       | Input image file (JPEG, PNG, etc.)|

#### Output Format

| Field | Type  | Description                              |
|-------|-------|------------------------------------------|
| -     | image | Single-channel grayscale depth map (L)   |

## Customization

### Invert the Depth Convention

Some ControlNet depth models expect farther pixels to be brighter rather than nearer. Flip the output:

```yaml
component:
  type: model
  task: depth-estimation
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Small-hf
  action:
    image: ${input.image as image}
    invert: true
```

### Override Model Input Resolution

The default input size follows the model's own image processor. Override it when you need finer detail or faster inference:

```yaml
component:
  type: model
  task: depth-estimation
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Small-hf
  action:
    image: ${input.image as image}
    params:
      input_size: 518    # Depth Anything V2 native size
```

### Using Alternative Models

Any HuggingFace model exposing `AutoModelForDepthEstimation` works. DPT and Depth Anything variants are first-class via the `architecture` field:

```yaml
# Depth Anything V2 Base (higher quality, slower)
component:
  type: model
  task: depth-estimation
  architecture: depth-anything
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Base-hf
  action:
    image: ${input.image as image}

# Intel DPT Large (classic DPT baseline)
component:
  type: model
  task: depth-estimation
  architecture: dpt
  model:
    provider: huggingface
    repository: Intel/dpt-large
  action:
    image: ${input.image as image}
```

### Batch and Video Processing

Pass a list of images or an upstream frame-extractor stream:

```yaml
component:
  type: model
  task: depth-estimation
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Small-hf
  action:
    image: ${input.frames}
    batch_size: 4
```

This makes the component suitable as an upstream preprocessor for ControlNet-based video-to-video pipelines that take `conditioning_frames`.

## Troubleshooting

### Common Issues

1. **Out of Memory**: Reduce `params.input_size` or `batch_size`, or switch to the Small variant
2. **Model Download Fails**: Check internet connection and disk space
3. **Slow Processing**: Ensure GPU acceleration is enabled
4. **Flat / Noisy Depth**: Try a larger variant (Base/Large) or increase `params.input_size`

## Model Variants

- **depth-anything/Depth-Anything-V2-Small-hf**: Default. Fast, ~100MB
- **depth-anything/Depth-Anything-V2-Base-hf**: Better quality, slower
- **depth-anything/Depth-Anything-V2-Large-hf**: Highest quality, slowest
- **Intel/dpt-large**: Classic DPT baseline
- **Intel/dpt-hybrid-midas**: DPT hybrid variant
