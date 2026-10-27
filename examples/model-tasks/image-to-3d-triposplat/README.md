# Image-to-3D Gaussian Splat Example

This example demonstrates how to convert a single image into a 3D Gaussian Splat using **TripoSplat** (by TripoAI), exposed through model-compose's built-in `image-to-3d` task.

## Overview

TripoSplat produces a 3D Gaussian Splatting asset (`.ply` or `.splat`) from one 2D image. Unlike mesh-based image-to-3D models, the output is a cloud of oriented Gaussians that renders cleanly in browser-based viewers (SparkJS, SuperSplat, Three.js) and composes well into interactive scenes.

This workflow provides:

1. **Local single-image Gaussian splat generation**: The flow-matching pipeline + VAE decoder run end-to-end on one image — no external API.
2. **Variable Gaussian count**: `num_gaussians` picks any count in the range `[32768, 262144]` (rounded to a multiple of 32). Trade off visual quality against rendering and storage cost.
3. **Bundled background removal**: BiRefNet is loaded as part of the pipeline, so cluttered backgrounds are stripped automatically before the flow model sees the image.
4. **Dual output formats**: Export as `.ply` (universal gaussian viewer input) or `.splat` (compact binary preferred by browser viewers).
5. **Automatic weight management**: `VAST-AI/TripoSplat` (~5 GB total, five safetensors files across `diffusion_models/`, `vae/`, `clip_vision/`, `background_removal/`) is downloaded on first run and cached locally.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU. The pipeline runs its weights in bfloat16 / float16, so a CUDA device is required — CPU and MPS (Apple Silicon) are not supported.
- A Python environment where `torch`, `torchvision`, `numpy`, `safetensors`, `pillow`, and `tqdm` can be installed — the first run installs them automatically into the isolated `.venv/triposplat`. No transformers, diffusers, flash-attn, or spconv dependencies.
- A HuggingFace token is not required — `VAST-AI/TripoSplat` is a public repository.

### License

TripoSplat code and weights are released under the **MIT License** — commercial use is permitted without additional notification. Review the [upstream license](https://github.com/VAST-AI-Research/TripoSplat/blob/main/LICENSE) for the full terms.

### Why Gaussian Splats

Compared to mesh-based image-to-3D output:

- **Fast browser rendering**: Pure point-cloud rasterization — no triangle setup, no UV baking, no PBR shading pipeline.
- **High visual fidelity**: Captures soft silhouettes, hair, foliage, and transparent surfaces that triangle meshes struggle with.
- **Not a drop-in mesh replacement**: Game engines, DCC tools, and physics pipelines still require meshes. Use TripoSplat for web viewers, AR/VR scenes, and visualization; use Pixal3D / AniGen / Hi3D when you need a GLB.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-to-3d-triposplat
   ```

2. (Optional) If your HuggingFace account is rate-limited, set `HF_TOKEN`:
   ```bash
   export HF_TOKEN=hf_xxx
   ```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup creates `.venv/triposplat`, installs the minimal dependency set, clones TripoSplat's inference code (~2k LOC across two Python files), and downloads ~5 GB of weights. Expect several minutes before the controller reports ready; subsequent runs reuse the cached venv and artefacts.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — generate a .ply splat with default settings
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img"}' \
     -o output.ply

   # Reproducible sampling with a fixed seed
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img", "seed": 42}' \
     -o output.ply

   # Lower Gaussian count for faster rendering in-browser
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img", "num_gaussians": 65536}' \
     -o output.ply

   # Export as .splat (compact binary for Three.js)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img", "format": "splat"}' \
     -o output.splat
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an `image` (subject on any background — BiRefNet handles the removal)
   - Optionally set `seed`, `num_gaussians` (32768 / 65536 / 131072 / 262144), or `format` (`ply` / `splat`)
   - Click "Run Workflow" to receive the splat file back

3. **Visualize the result**: drop the `.ply` or `.splat` into [SparkJS](https://sparkjs.dev) or [SuperSplat](https://superspl.at/editor), or load it from a Three.js scene with `@mkkellogg/gaussian-splats-3d`.

## Configuration Reference

### Component Fields

| Field    | Description                                                                 | Default |
|----------|-----------------------------------------------------------------------------|---------|
| `task`   | Must be `image-to-3d`.                                                      | —       |
| `driver` | Must be `custom`.                                                           | —       |
| `family` | Must be `triposplat`.                                                       | —       |
| `model`  | TripoSplat model repository (HuggingFace repo or local path).               | —       |
| `device` | Compute device. Must resolve to `cuda` — bfloat16 / fp16 weights only.      | `auto`  |

### Action Fields

| Field                   | Description                                                                                | Default    |
|-------------------------|--------------------------------------------------------------------------------------------|------------|
| `image`                 | Input image (single, list, or stream).                                                     | —          |
| `seed`                  | Random seed for reproducible sampling.                                                     | `42`       |
| `batch_size`            | Number of inputs processed per batch when the input is a list or stream.                   | `1`        |
| `format`                | Output format: `ply` or `splat`.                                                           | `ply`      |
| `params.steps`          | Flow-matching sampler steps. Recommend 10-20.                                              | `20`       |
| `params.guidance_scale` | Classifier-free guidance strength. `<= 1.0` disables CFG. Recommend 3.0.                   | `3.0`      |
| `params.shift`          | Flow-matching timestep schedule shift. `1.0` is uniform; higher shifts weight to early.    | `3.0`      |
| `params.num_gaussians`  | Target Gaussian count in `[32768, 262144]`, rounded to a multiple of 32.                   | `262144`   |
| `params.erode_radius`   | Alpha-matte erosion radius after background removal; `0` disables, `1` is a 3x3 min.      | `1`        |

## Notes

- **Minimal dependencies**: TripoSplat deliberately avoids `transformers`, `diffusers`, `flash-attn`, and `spconv`. The first-run install is noticeably faster than other image-to-3d pipelines (pixal3d, anigen, hi3d).
- **No pip package**: Upstream ships `triposplat.py` and `model.py` as bare top-level files without `setup.py` or `pyproject.toml`. The driver installs them next to `mindor` as a `triposplat_pipeline/` package, rewriting the internal `from model import ...` to `from triposplat_pipeline.model import ...`.
- **Isolated runtime**: The model worker runs in `.venv/triposplat` so TripoSplat's torch build does not clash with the controller's site-packages.
- **CUDA is required**: Weights load as bfloat16 (DINOv3, VAE encoder) and float16 (BiRefNet, flow model, decoder). CPU and MPS have no supported path.
- **Gaussian count granularity**: `num_gaussians` is rounded to the nearest multiple of the decoder's `gaussians_per_point` (typically 32). The driver forwards the user's value verbatim; TripoSplat prints the actual count used.
- **Output viewing**: `.ply` is the most portable gaussian splat format; `.splat` is a compact binary preferred by Three.js. Neither opens in Blender or Unity's glTFast — those expect meshes, not Gaussians.
- **Output**: The result is a single `.ply` or `.splat` file per input (or a list for batched inputs).
