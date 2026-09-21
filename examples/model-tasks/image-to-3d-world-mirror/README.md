# Image-to-3D Model Task Example

This example demonstrates how to reconstruct a 3D scene (Gaussian splats, depth-derived point cloud, and camera parameters) from a set of images using HunyuanWorld-Mirror 2.0, exposed through model-compose's built-in image-to-3d task.

## Overview

Where the Pixal3D flavors *generate* a mesh from what an image implies, WorldMirror *reconstructs* the geometry that the images already contain. Given a set of unposed images of the same scene, the pipeline runs a single feed-forward pass and produces multiple aligned outputs at once.

This workflow provides local multi-image 3D scene reconstruction that:

1. **WorldMirror 2.0 Pipeline**: Runs the full unified WorldMirror model end-to-end — depth, normals, camera poses, point clouds, and 3D Gaussian Splatting all fall out of a single forward pass.
2. **Multiple Outputs, One Call**: A single request returns a dictionary of results — Gaussian splats (`.ply`), point cloud (`.ply`), camera parameters (JSON), and optionally per-view depth and normal maps. Toggle each with the `return_*` flags.
3. **Optional Camera / Depth Priors**: Feed known camera poses (a JSON file matching WorldMirror's own `camera_params.json` schema) or per-view depth maps to condition the reconstruction. Priors are pure conditioning inputs — the model still runs when they are omitted.
4. **Robust Filtering**: Sky masking (ONNX + model fusion), edge filtering at depth/normal discontinuities, and confidence-percentile masks keep the point cloud and Gaussians clean.
5. **Point-Cloud and Gaussian Compression**: Voxel merging plus configurable subsampling caps points and Gaussians without visibly degrading the reconstruction.
6. **Automatic Model Management**: The WorldMirror 2.0 checkpoint is downloaded from HuggingFace Hub on first run and cached locally.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU. Peak VRAM depends on target resolution and `enable_bf16`; roughly **12-16 GB** at the default 952-pixel target with bf16, more without. Apple Silicon (MPS) and CPU-only inference are not supported today — WorldMirror's ops are CUDA-only.
- A Linux host with the CUDA toolkit installed. The first run compiles a custom `gsplat` variant and vendored CUDA extensions, which requires the toolkit rather than just the runtime.
- A Python environment where `torch`, `gsplat`, `flash-attn`, and WorldMirror's ancillary packages can be installed — the first run installs them automatically.
- A HuggingFace access token that can read the `tencent/HY-World-2.0` repository. Set it via the `HF_TOKEN` environment variable before starting model-compose.

### Why Local 3D Reconstruction

Compared to cloud-hosted reconstruction services:

**Benefits of Local Processing:**
- **Privacy**: Reference images and reconstructed geometry never leave the machine.
- **Cost**: No per-scene API fees.
- **Iteration**: Filter thresholds, compression targets, and output selection can be tuned freely per call.
- **Pipeline Friendly**: Composes with other model-compose tasks (image-background-removal upstream, file-store downstream, model-3d-converter for `.glb` conversion) for end-to-end capture-to-asset pipelines.

**Trade-offs:**
- **Hardware Requirements**: A CUDA GPU is non-negotiable, with ~12 GB VRAM as a comfortable minimum at the default resolution.
- **First-Run Cost**: The pipeline downloads the WorldMirror checkpoint and compiles CUDA extensions — expect the controller to take several minutes before it reports ready the first time.
- **License**: WorldMirror 2.0 and its component models each carry their own license. Review them before commercial use.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-to-3d-world-mirror
   ```

2. Create `.env` from the sample and paste in a HuggingFace access token that can read `tencent/HY-World-2.0`:
   ```bash
   cp .env.sample .env
   # edit .env and set HF_TOKEN=hf_xxx
   ```

3. Adjust `enable_bf16: true` in `model-compose.yml` to trade some numerical precision for lower VRAM. Disable prediction heads you do not need via `disable_heads` (e.g. `disable_heads: [normal]` frees ~200M parameters).

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup downloads the WorldMirror checkpoint and compiles CUDA extensions. Expect several minutes before the controller reports ready.

2. **Run the workflow with a set of views:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "view0=@/path/to/view_00.png" \
     -F "view1=@/path/to/view_01.png" \
     -F "view2=@/path/to/view_02.png" \
     -F "view3=@/path/to/view_03.png" \
     -F 'input={"image": ["@view0", "@view1", "@view2", "@view3"]}'
   ```

   The response is a JSON object with the requested outputs — Gaussian splats and point cloud as `.ply` streams, camera parameters as an inline JSON dict, and per-view depth / normal images when their flags are enabled.

3. **Reuse cameras from a previous run** (WorldMirror's own `camera_params.json` schema, so the JSON returned by one call can be fed back into another):
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "view0=@/path/to/view_00.png" \
     -F "view1=@/path/to/view_01.png" \
     -F 'input={"image": ["@view0", "@view1"], "prior_cameras": "/path/to/camera_params.json"}'
   ```

4. **Skip large outputs when you only need geometry**:
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "view0=@/path/to/view_00.png" \
     -F "view1=@/path/to/view_01.png" \
     -F 'input={"image": ["@view0", "@view1"], "return_gaussians": false, "return_normal": false}'
   ```

## Configuration Reference

### Component Fields

| Field           | Description                                                                                            | Default              |
|-----------------|--------------------------------------------------------------------------------------------------------|----------------------|
| `task`          | Must be `image-to-3d`.                                                                                 | —                    |
| `driver`        | Must be `custom`.                                                                                      | —                    |
| `family`        | Must be `world-mirror`.                                                                                | —                    |
| `model`         | WorldMirror model repository (HuggingFace repo or local path).                                         | —                    |
| `subfolder`     | Subfolder inside the repository holding the WorldMirror checkpoint.                                    | `HY-WorldMirror-2.0` |
| `device`        | Compute device. Must resolve to `cuda` — WorldMirror does not support CPU or MPS.                      | `auto`               |
| `enable_bf16`   | Cast the model to bfloat16 for reduced VRAM at the cost of some precision on non-critical layers.      | `false`              |
| `disable_heads` | Prediction heads to disable and free from memory. Options: `camera`, `depth`, `normal`, `points`, `gs`. | `[]`                 |

### Action Fields

| Field                            | Description                                                                                        | Default          |
|----------------------------------|----------------------------------------------------------------------------------------------------|------------------|
| `image`                          | List of image paths / URLs (or a single directory path) forming one scene.                         | —                |
| `priors.cameras`                 | Optional camera priors — path to a JSON file matching WorldMirror's `camera_params.json` schema.   | (none)           |
| `priors.depths`                  | Optional depth priors — path to a directory of per-view depth maps (.npy / .exr / .png).           | (none)           |
| `return_gaussians`               | Include the 3D Gaussian Splatting `.ply` in the result.                                            | `true`           |
| `return_points`                  | Include the depth-derived point cloud `.ply` in the result.                                        | `true`           |
| `return_cameras`                 | Include camera extrinsics and intrinsics as a JSON dict in the result.                             | `true`           |
| `return_depth`                   | Include per-view depth map images in the result.                                                   | `false`          |
| `return_normal`                  | Include per-view surface normal map images in the result.                                          | `false`          |
| `params.target_size`             | Maximum inference resolution (longest edge); images are resized + center-cropped to a multiple of 14. | `952`         |
| `params.apply_sky_mask`          | Filter sky regions out of point clouds and Gaussians.                                              | `true`           |
| `params.apply_edge_mask`         | Filter points near depth / normal discontinuities.                                                 | `true`           |
| `params.apply_confidence_mask`   | Filter the bottom-percentile of points by prediction confidence.                                   | `false`          |
| `params.sky_mask_source`         | Sky-mask source: `auto` (ONNX + model), `model`, or `onnx`.                                        | `auto`           |
| `params.model_sky_threshold`     | Threshold for model-based sky detection.                                                           | `0.45`           |
| `params.confidence_percentile`   | Bottom percentile removed when `apply_confidence_mask` is enabled.                                 | `10.0`           |
| `params.edge_normal_threshold`   | Normal-edge detection tolerance.                                                                   | `1.0`            |
| `params.edge_depth_threshold`    | Depth-edge detection relative tolerance.                                                           | `0.03`           |
| `params.compress_pts`            | Compress the depth-derived point cloud via voxel merging + subsampling.                            | `true`           |
| `params.compress_pts_max_points` | Maximum number of points after point-cloud compression.                                            | `2000000`        |
| `params.compress_pts_voxel_size` | Voxel size used when merging points.                                                               | `0.002`          |
| `params.compress_gs_max_points`  | Maximum number of Gaussians after voxel pruning.                                                   | `5000000`        |
| `params.max_resolution`          | Maximum resolution for saved image outputs (depth / normal PNGs).                                  | `1920`           |

## Notes

- **First run is slow**: The controller creates the `.venv/world-mirror` isolated environment, installs WorldMirror's pinned dependencies, compiles the custom `gsplat` variant, and downloads the WorldMirror checkpoint on first startup. Expect 10-20 minutes before the controller reports ready. Subsequent runs reuse the cached venv and artefacts.
- **Isolated runtime**: The model worker runs in a dedicated virtualenv (`runtime.type: virtualenv`, `path: .venv/world-mirror`) so WorldMirror's pinned transformers / diffusers / cupy / open3d versions don't clash with the controller's own site-packages.
- **CUDA is required**: WorldMirror hardcodes CUDA device placement and CUDA-only kernels; the driver refuses to load on non-CUDA hosts.
- **No video input**: This example accepts image sets only. If your source is a video, extract frames with an upstream component (e.g. `video-frame-extractor`) before feeding them in.
- **Cameras as data**: `return_cameras: true` yields the camera dictionary inline in the response — no file is written. The same schema is what WorldMirror's own `camera_params.json` uses, so the returned dict can be persisted with a `file-store` component and later fed back as `priors.cameras`.
- **VRAM planning**: `enable_bf16: true` roughly halves the model's activation memory; combined with `disable_heads` this is the main lever if you're running on 12 GB cards. On 24 GB or better, the defaults are comfortable.
- **Output usage**: The `.ply` files load in MeshLab, Blender (via add-ons), CloudCompare, and most Gaussian-splatting viewers. The depth / normal PNGs are per-view images sorted in the same order as your inputs.
