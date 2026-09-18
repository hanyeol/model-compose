# Image-to-3D Model Task Example

This example demonstrates how to generate a textured 3D GLB mesh from a single image using Pixal3D, exposed through model-compose's built-in image-to-3d task.

## Overview

This workflow provides local single-image 3D asset generation that:

1. **Local Pixal3D Pipeline**: Runs Pixal3D's sparse-structure, shape, and texture flow-matching stages end-to-end — no external API.
2. **Auto Camera Estimation**: A MoGe-2 depth model estimates the input image's camera FOV automatically; manually set `manual_fov` (in radians) if the auto-estimated perspective looks off.
3. **PBR Textures**: The generated GLB carries baked base colour, metallic, and roughness maps — usable in glTF viewers, Blender, Unreal, or any PBR-aware renderer.
4. **Configurable Detail**: `resolution` (1024 or 1536), `max_num_tokens`, and per-stage sampling steps trade off between mesh detail, texture fidelity, and VRAM / time.
5. **Automatic Model Management**: The Pixal3D weights, the MoGe-2 depth model, and the DINOv3 conditioning weights are downloaded from HuggingFace Hub on first run and cached locally.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU. Peak VRAM is roughly **18 GB** at 1536 resolution, or **10-12 GB** with `low_vram: true` at 1024 resolution. Apple Silicon (MPS) and CPU-only inference are not supported — Pixal3D's kernels are CUDA-only.
- A Linux host with the CUDA toolkit installed. The first run compiles neighbourhood attention kernels (natten) against nvcc, which requires the toolkit rather than just the runtime.
- A Python environment where `torch`, `natten`, and Pixal3D's ancillary packages can be installed — the first run installs them automatically.

### Why Local Image-to-3D

Compared to cloud-hosted 3D generation services:

**Benefits of Local Processing:**
- **Privacy**: Reference images and generated assets never leave the machine.
- **Cost**: No per-generation API fees.
- **Iteration**: Sampler steps, texture size, and camera FOV can be tuned freely per call.
- **Pipeline Friendly**: Composes with other model-compose tasks (image-background-removal upstream, file-store downstream) for end-to-end 3D asset pipelines.

**Trade-offs:**
- **Hardware Requirements**: Non-negotiable CUDA GPU with 10 GB VRAM minimum for `low_vram: true`, 18 GB+ for full-detail mode.
- **First-Run Cost**: The pipeline downloads ~15 GB of weights and compiles CUDA kernels — expect the controller to take several minutes before it reports ready the first time.
- **License**: Pixal3D and its component models each carry their own license. Review them before commercial use.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-to-3d-pixal3d
   ```

2. No additional environment configuration required — the Pixal3D checkpoint (`TencentARC/Pixal3D`), the MoGe-2 depth model (`Ruicheng/moge-2-vitl`), and the DINOv3 conditioning weights (`camenduru/dinov3-vitl16-pretrain-lvd1689m`) are downloaded from HuggingFace Hub and cached under `~/.cache/huggingface/` on first run.

3. To reduce peak VRAM at the cost of slower inference, set `low_vram: true` in `model-compose.yml`. To trade texture fidelity for speed, set `resolution: 1024`.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup downloads ~15 GB of weights and compiles CUDA kernels. Expect several minutes before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — generate a GLB from an image with all defaults
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img"}' \
     -o output.glb

   # Reproducible sampling with a fixed seed
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "seed": 42}' \
     -o output.glb

   # Manual camera FOV for images that MoGe misjudges (0.2 rad ≈ 11.5° — narrow lens)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "manual_fov": 0.2}' \
     -o output.glb

   # Higher-fidelity texture (8k baked map) with more sampling steps per stage
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "texture_size": 8192, "shape_slat_sampling_steps": 24, "tex_slat_sampling_steps": 24}' \
     -o output.glb
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an `image` (subject on a clean background works best — Pixal3D removes the background automatically but a busy background still leaks into the pose estimate)
   - Optionally set `seed` for reproducibility, or `manual_fov` if the auto-estimated camera looks off
   - Click "Run Workflow" to receive a `.glb` file back

## Configuration Reference

### Component Fields

| Field         | Description                                                                                                       | Default            |
|---------------|-------------------------------------------------------------------------------------------------------------------|--------------------|
| `task`        | Must be `image-to-3d`.                                                                                            | —                  |
| `driver`      | Must be `custom`.                                                                                                 | —                  |
| `family`      | Must be `pixal3d`.                                                                                                | —                  |
| `model`       | Pixal3D model repository (HuggingFace repo or local path).                                                        | —                  |
| `device`      | Compute device. Must resolve to `cuda` — Pixal3D does not support CPU or MPS.                                     | `auto`             |
| `low_vram`    | Keep stage models on CPU and page each to GPU per stage. Reduces peak VRAM to ~10-12 GB.                          | `false`            |
| `resolution`  | Pipeline grid resolution (`1024` or `1536`). Unset defaults to `1024` in low-VRAM mode, else `1536`.              | (see description)  |

### Action Fields

| Field                              | Description                                                                                    | Default          |
|------------------------------------|------------------------------------------------------------------------------------------------|------------------|
| `image`                            | Input image (or list/stream of images).                                                        | —                |
| `seed`                             | Random seed for reproducibility. Leave unset for a fresh sample per call.                      | (none)           |
| `batch_size`                       | Number of inputs processed per batch when the input is a list or stream.                       | `1`              |
| `params.manual_fov`                | Manual camera FOV in radians. Unset triggers MoGe-2 auto-estimation.                           | (auto-estimated) |
| `params.mesh_scale`                | Target mesh scale used for camera distance computation.                                        | `1.0`            |
| `params.image_resolution`          | Working image resolution used during camera estimation.                                        | `512`            |
| `params.ss_sampling_steps`         | Sparse-structure diffusion sampling steps (coarse voxel layout).                               | `12`             |
| `params.ss_guidance_strength`      | Sparse-structure classifier-free guidance strength.                                            | `7.5`            |
| `params.ss_guidance_rescale`       | Sparse-structure guidance rescale factor.                                                      | `0.7`            |
| `params.ss_rescale_t`              | Sparse-structure timestep rescale factor.                                                      | `5.0`            |
| `params.shape_slat_sampling_steps` | Shape latent sampling steps (geometry refinement).                                             | `12`             |
| `params.shape_slat_guidance_strength` | Shape latent classifier-free guidance strength.                                             | `7.5`            |
| `params.shape_slat_guidance_rescale`  | Shape latent guidance rescale factor.                                                       | `0.5`            |
| `params.shape_slat_rescale_t`      | Shape latent timestep rescale factor.                                                          | `3.0`            |
| `params.tex_slat_sampling_steps`   | Texture latent sampling steps (PBR colour / metallic / roughness).                             | `12`             |
| `params.tex_slat_guidance_strength`| Texture latent classifier-free guidance strength.                                              | `1.0`            |
| `params.tex_slat_guidance_rescale` | Texture latent guidance rescale factor.                                                        | `0.0`            |
| `params.tex_slat_rescale_t`        | Texture latent timestep rescale factor.                                                        | `3.0`            |
| `params.max_num_tokens`            | Maximum sparse tokens per stage. Higher = finer geometry, more VRAM.                           | `49152`          |
| `params.texture_size`              | Baked texture resolution (pixels) applied when exporting the GLB.                              | `4096`           |
| `params.decimation_target`         | Target face count applied during mesh decimation before GLB export.                            | `1000000`        |

## Notes

- **First run is slow**: The controller downloads ~15 GB of weights and compiles neighbourhood-attention CUDA kernels (natten) on first startup. Subsequent runs reuse the cached artefacts.
- **CUDA is required**: Pixal3D hardcodes CUDA device placement and CUDA-only kernels; the driver refuses to load on non-CUDA hosts rather than silently falling back to a broken path.
- **VRAM planning**: `low_vram: true` swaps peak VRAM (~10-12 GB) for latency (~2-3× slower). At `resolution: 1536` in standard mode, peak VRAM is ~18 GB — an A100 40GB or an RTX 6000 Ada handles it comfortably.
- **Camera FOV matters**: If the auto-estimated perspective looks off (subject unusually stretched or flattened), set `manual_fov` — start at `0.2` (narrow lens, ~11.5°) and adjust in `~0.05` increments.
- **Background robustness**: Pixal3D removes the background automatically as a preprocessing step, but a subject touching the frame edges or heavily occluded may still produce distorted geometry. Consider running `image-background-removal` upstream if the auto-preprocess isn't clean.
- **Sampler tuning**: The default 12 steps per stage produces balanced results. For final assets, raise the shape and texture stage steps to 24; the sparse-structure stage benefits less from extra steps.
- **Output**: The result is a single `.glb` file per input (or a list for batched inputs). Any glTF-compatible viewer (`<model-viewer>`, Blender, three.js, Unity's glTFast) can load it directly.
