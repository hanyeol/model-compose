# Image Edge Detection Model Task Example

This example demonstrates model-based edge detectors in model-compose: HED, PiDiNet, and Lineart. All three produce single-channel edge maps suitable as ControlNet conditioning inputs for image or video generation.

## Overview

Three models exposed as separate workflows:

1. **HED** (Holistically-Nested Edge Detection) — classical soft edges, widely used by ControlNet HED/softedge
2. **PiDiNet** (Pixel Difference Network) — compact soft edges, lighter weights than HED
3. **Lineart** — anime-style line extraction, two variants (realistic / coarse)

All weights live in the public `lllyasviel/Annotators` HuggingFace repo and are downloaded automatically on first use.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python environment with torch, numpy, PIL (automatically managed)
- Internet access for the first run (model download)

### Model Weights

| Family       | Weight file          | Size   |
|--------------|----------------------|--------|
| HED          | `ControlNetHED.pth`  | ~56 MB |
| PiDiNet      | `table5_pidinet.pth` | ~2 MB  |
| Lineart (realistic) | `sk_model.pth`  | ~17 MB |
| Lineart (coarse)    | `sk_model2.pth` | ~17 MB |

All checkpoints come from `lllyasviel/Annotators` and are cached under the standard HuggingFace cache directory.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run a workflow:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/hed/runs \
     -F "image=@/path/to/your/input-image.jpg"
   ```

   Replace `hed` with `pidinet` or `lineart` to invoke the other preprocessors.

   **Using Web UI:**
   - Open http://localhost:8081
   - Choose the workflow and upload an image
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run hed --input '{"image": "/path/to/your/input-image.jpg"}'
   ```

## Component Details

### HED Component
- **Architecture**: VGG16-style five-stage encoder with side-output score layers (Xie & Tu, 2015), fused into a single edge map
- **Input preprocessing**: BGR, ImageNet mean subtraction, [0, 255]
- **Output**: Grayscale edge map, bright pixels = edges

### PiDiNet Component
- **Architecture**: Pixel-difference convolution network (Su et al., ICCV 2021), Table 5 variant used by `lllyasviel/Annotators`
- **Input preprocessing**: RGB, normalized to [0, 1]
- **Output**: Grayscale edge map

### Lineart Component
- **Architecture**: ResNet-9 U-Net generator (Anime2Sketch / Mukosame), used by ControlNet 1.1 lineart
- **Variants**:
  - `realistic` — `sk_model.pth`, detailed line extraction
  - `coarse` — `sk_model2.pth`, simplified lines
- **Input preprocessing**: RGB in `[-1, 1]`
- **Output**: Grayscale line map (output already inverted so edges are bright on a dark background, matching ControlNet convention)

## Customization

### Invert the Output

ControlNet lineart variants sometimes expect dark lines on a bright background instead of the default (bright on dark). Flip the output:

```yaml
action:
  image: ${input.image as image}
  invert: true
```

### Change Input Resolution

The default input size is 512 (model native). Raise it for sharper details, lower it for speed:

```yaml
action:
  image: ${input.image as image}
  params:
    image_size: 768
```

### Safe Mode (HED / PiDiNet)

Suppress weak edges that often become spurious background texture under ControlNet:

```yaml
action:
  image: ${input.image as image}
  params:
    use_safe_mode: true
```

### Feeding into a ControlNet Workflow

Chain the edge preprocessor before a ControlNet-based image or video generator:

```yaml
workflow:
  jobs:
    - id: edges
      component: hed
      input:
        image: ${input.image}
    - id: generate
      component: controlnet-generator
      input:
        prompt: ${input.prompt}
        control_image: ${edges.output}
```

### Batch and Streaming

Pass a list of images or a frame-extractor stream to generate per-frame edge maps for a video pipeline:

```yaml
action:
  image: ${input.frames}
  batch_size: 4
```

## Troubleshooting

### Common Issues

1. **Out of Memory**: Reduce `params.image_size` or `batch_size`; switch to PiDiNet (lightest)
2. **Model Download Fails**: Check internet connection and HuggingFace cache directory permissions
3. **Flat / Noisy Output**: Try `use_safe_mode: true` (HED/PiDiNet) or raise `image_size`
4. **Wrong Convention**: If your ControlNet expects dark edges on bright background, add `invert: true`

## Model-based vs Algorithmic Edge Detection

For pure algorithmic edge detection without model weights, see the `image-processor` component's OpenCV driver with the `canny` method. The two serve complementary roles:

- **Canny** — fast, no weights, deterministic. Best for well-lit subjects with clear boundaries.
- **HED / PiDiNet / Lineart** — model-based, better at semantic edges (hair, soft gradients, cloth folds) that classical algorithms miss. Required for most ControlNet 1.1 edge/line conditioning.
