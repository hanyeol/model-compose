# Image-to-Rigged-3D Model Task Example

This example demonstrates how to generate a fully rigged GLB mesh (with skeleton and skin weights) plus a stand-alone skeleton visualization from a single image using AniGen, exposed through model-compose's built-in image-to-3d task.

## Overview

This workflow provides local single-image animate-ready 3D asset generation that:

1. **Local AniGen Pipeline**: Runs AniGen's sparse-structure and structured-latent flow-matching stages end-to-end — no external API.
2. **Rigged Mesh**: The output GLB carries bones, hierarchical parents, and per-vertex skin weights baked into a standard glTF skinned-mesh — drop it into Blender, Unity, Unreal, or three.js and drive it with any motion clip.
3. **Skeleton Visualization**: A second GLB renders the predicted skeleton as visible bones — useful for debugging joint placement before committing to the rigged mesh.
4. **Configurable Sampling**: Per-stage CFG scales, sampling steps, joint density, and texture size trade off between rig fidelity, mesh detail, and VRAM / time.
5. **Automatic Model Management**: The AniGen weights (SS-Flow + SLAT-Flow + DAE + DINOv2 + DSINE + VGG) are downloaded from HuggingFace Hub on first run and cached locally.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU with **at least 18 GB VRAM** (A800, RTX 3090, RTX 4090, A100 confirmed working by upstream). Apple Silicon (MPS) and CPU-only inference are not supported — AniGen's kernels are CUDA-only.
- A Linux host with the CUDA toolkit installed (11.8 or 12.x). The first run builds pytorch3d and nvdiffrast against nvcc, which requires the toolkit rather than just the runtime.
- A Python environment where `torch`, `spconv`, `pytorch3d`, `nvdiffrast`, and AniGen's ancillary packages can be installed — the first run installs them automatically.

### Why Local Rigged-3D Generation

Compared to cloud-hosted 3D-with-rig services:

**Benefits of Local Processing:**
- **Privacy**: Reference images and generated assets never leave the machine.
- **Cost**: No per-generation API fees.
- **Iteration**: Sampler steps, CFG scales, joint density, and skinning smoothing can be tuned freely per call.
- **Pipeline Friendly**: Composes with other model-compose tasks (image-background-removal upstream, file-store downstream) for end-to-end rigged-asset pipelines.

**Trade-offs:**
- **Hardware Requirements**: Non-negotiable CUDA GPU with 18 GB VRAM.
- **First-Run Cost**: The pipeline downloads the AniGen HuggingFace snapshot (~10+ GB across SS-Flow / SLAT-Flow / DAE / auxiliary models) and compiles CUDA kernels — expect the controller to take 20-30 minutes before it reports ready the first time.
- **License**: AniGen and its component models each carry their own license. The upstream repo also flags `extensions/CUBVH/` as non-commercial research-only (relevant only for training, not inference). Review before commercial use.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-to-3d-anigen
   ```

2. No HuggingFace token is required by default — the `VAST-AI/AniGen` snapshot is publicly downloadable. If you host behind an authenticated mirror, set `HF_TOKEN` in a `.env` file the usual way.

3. Pick the SS-Flow / SLAT-Flow variants in `model-compose.yml`:
   - `ss_variant: solo` (default) — accurate geometry, works well for most inputs
   - `ss_variant: duet` — more detailed skeleton (fingers etc.), slightly softer geometry
   - `ss_variant: epic` — balanced
   - `slat_variant: auto` (default) — network picks joint count
   - `slat_variant: control` — joint count follows `params.joints_density` (0-4)

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup downloads the AniGen HF snapshot and compiles CUDA kernels. Expect 20-30 minutes before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — generate a rigged mesh and its skeleton from an image
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img"}' \
     -o response.json

   # Reproducible sampling with a fixed seed
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "seed": 42}' \
     -o response.json

   # Higher-fidelity sampling with more steps and stronger SLAT guidance
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "ss_steps": 50, "slat_steps": 50, "cfg_scale_slat": 4.0}' \
     -o response.json

   # Denser skeleton (only meaningful with `slat_variant: control`)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "joints_density": 3}' \
     -o response.json
   ```

   The response is a JSON object referencing two GLB resources — `mesh` (rigged mesh) and `skeleton` (skeleton visualization) — which can be streamed or downloaded via the returned URLs.

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an `image` (subject on a clean background works best — AniGen removes the background automatically)
   - Optionally set `seed` for reproducibility
   - Click "Run Workflow" to receive both `mesh.glb` and `skeleton.glb`

## Configuration Reference

### Component Fields

| Field          | Description                                                                                        | Default |
|----------------|----------------------------------------------------------------------------------------------------|---------|
| `task`         | Must be `image-to-3d`.                                                                             | —       |
| `driver`       | Must be `custom`.                                                                                  | —       |
| `family`       | Must be `anigen`.                                                                                  | —       |
| `model`        | AniGen model repository (HuggingFace repo or local path).                                          | —       |
| `device`       | Compute device. Must resolve to `cuda` — AniGen does not support CPU or MPS.                       | `auto`  |
| `ss_variant`   | SS-Flow checkpoint variant (`solo`, `epic`, `duet`).                                               | `solo`  |
| `slat_variant` | SLAT-Flow checkpoint variant (`auto`, `control`).                                                  | `auto`  |

### Action Fields

| Field                              | Description                                                                                  | Default          |
|------------------------------------|----------------------------------------------------------------------------------------------|------------------|
| `image`                            | Input image (or list/stream of images).                                                      | —                |
| `seed`                             | Random seed for reproducibility. Leave unset for a fresh sample per call.                    | (none)           |
| `batch_size`                       | Number of inputs processed per batch when the input is a list or stream.                     | `1`              |
| `return_mesh`                      | Include the rigged mesh GLB in the result.                                                   | `true`           |
| `return_skeleton`                  | Include the skeleton visualization GLB in the result.                                        | `true`           |
| `return_image`                     | Include the background-removed conditioning image in the result.                             | `false`          |
| `params.cfg_scale_ss`              | Sparse-structure classifier-free guidance scale.                                             | `7.5`            |
| `params.cfg_scale_slat`            | Structured-latent classifier-free guidance scale.                                            | `3.0`            |
| `params.ss_steps`                  | Sparse-structure flow-matching sampling steps.                                               | `25`             |
| `params.slat_steps`                | Structured-latent flow-matching sampling steps.                                              | `25`             |
| `params.joints_density`            | Joint density level (0-4) — only used by `slat_variant: control`.                            | `1`              |
| `params.simplify_ratio`            | Mesh simplification ratio applied during postprocessing.                                     | `0.95`           |
| `params.fill_holes`                | Fill holes during mesh postprocessing.                                                       | `true`           |
| `params.no_smooth_skin_weights`    | Disable skin-weight smoothing.                                                               | `false`          |
| `params.smooth_skin_weights_iters` | Skin-weight smoothing iterations.                                                            | `100`            |
| `params.smooth_skin_weights_alpha` | Skin-weight smoothing alpha.                                                                 | `1.0`            |
| `params.no_filter_skin_weights`    | Disable geodesic filtering of mesh skinning weights.                                         | `false`          |
| `params.texture_size`              | Baked texture size (pixels); `0` disables texture baking.                                    | `1024`           |

## Notes

- **First run is slow**: The controller creates the `.venv/anigen` isolated environment, installs AniGen's pinned dependencies, compiles pytorch3d / nvdiffrast, and downloads the AniGen HF snapshot on first startup. Expect 20-30 minutes before the controller reports ready. Subsequent runs reuse the cached venv and artefacts.
- **Isolated runtime**: The model worker runs in a dedicated virtualenv (`runtime.type: virtualenv`, `path: .venv/anigen`) so AniGen's torch 2.4/2.5 pin and its CUDA-specific extensions don't clash with the controller's own site-packages. The driver refuses to run in the controller's native environment.
- **CUDA is required**: AniGen hardcodes CUDA device placement and CUDA-only kernels; the driver refuses to load on non-CUDA hosts rather than silently falling back to a broken path.
- **Two outputs, both GLB**: The workflow exposes `mesh` (rigged, skinned, textured) and `skeleton` (bones-only visualization). Set `return_skeleton: false` if you only need the rigged mesh; set `return_image: true` to also receive the background-removed conditioning image alongside.
- **Variant trade-offs**: `ss_variant: solo` prioritizes accurate geometry (README's default recommendation). Switch to `duet` when the subject has fine articulation (hands with fingers, complex machinery). Use `slat_variant: control` + `params.joints_density` only when you want deterministic joint counts — the default `auto` picks a sensible value per subject.
- **Background robustness**: AniGen removes the background automatically as a preprocessing step, but a subject touching the frame edges or heavily occluded may still produce distorted geometry. Consider running `image-background-removal` upstream if the auto-preprocess isn't clean.
- **Sampler tuning**: The default 25 steps per stage balances quality and speed. For final assets, raise both `ss_steps` and `slat_steps` to 50; extra `slat_steps` help more than extra `ss_steps`.
- **Output**: Each result carries a `mesh` and/or `skeleton` and/or `image` field, depending on the `return_*` flags. Any glTF-compatible viewer (`<model-viewer>`, Blender, three.js, Unity's glTFast) can load the GLB files directly and play back the rig with off-the-shelf motion clips.
