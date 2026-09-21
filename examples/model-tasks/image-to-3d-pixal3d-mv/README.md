# Multi-View Image-to-3D Model Task Example

This example demonstrates how to generate a textured 3D GLB mesh from a posed multi-view image rig using Pixal3D's MV branch, exposed through model-compose's built-in image-to-3d task.

## Overview

Where the single-view Pixal3D pipeline has to guess the input image's camera with MoGe-2, the multi-view flavour takes several posed views of the same object at once. Given per-view `transform_matrix` and `camera_angle_x` values, the pipeline fuses the views inside its cascade denoisers and outputs a single high-fidelity GLB.

The workflow provides local multi-view 3D asset generation that:

1. **Pixal3D MV Pipeline**: Loads the `ckpts/*_mv` checkpoints (via `pipeline_mv.json`) from the same HuggingFace repository as single-view Pixal3D.
2. **Posed Views**: Each input view carries an image plus its 4x4 camera-to-world matrix (NeRF/Blender convention: Z-up world, camera looks -Z with +Y up). Frame 0 must be the canonical front view (`camera at (0, -d, 0)` looking at the origin with world +Z up); otherwise the resulting mesh is posed in that view's frame.
3. **Automatic Matting**: Views without an alpha channel are matted with the same `briaai/RMBG-2.0` model the single-view path uses. Views that already have a non-opaque alpha channel use it as-is.
4. **PBR Textures**: The generated GLB carries baked base colour, metallic, and roughness maps.
5. **Configurable Detail**: `resolution` (1024 or 1536), `max_num_tokens`, and per-stage sampling steps trade off between mesh detail, texture fidelity, and VRAM / time.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU. VRAM requirements match single-view Pixal3D (~18 GB at 1536, ~10-12 GB with `low_vram: true` at 1024).
- A Linux host with the CUDA toolkit installed.
- A HuggingFace access token accepted for `briaai/RMBG-2.0` (the rembg step). Set it via `HF_TOKEN`.

### Input Format

The action expects two parallel arrays plus a shared FOV:

- **`image`**: A list of view images. Element `i` is the image for view `i`.
- **`transform_matrix`**: A list of 4x4 camera-to-world matrices, parallel to `image`.
- **`camera_angle_x`**: Horizontal FOV in radians. Either a single scalar shared across every view, or a list matching `image` length for per-view overrides.
- **`mesh_scale`**: Global mesh scale for camera-distance normalization. Defaults to `1.0`.

If your views were rendered with the shipped Pixal3D dataset conventions (orbit at eye level, azimuths 0°/90°/180°/270°, elevation 0°, 20° FOV), the transforms are:

```yaml
camera_angle_x: 0.349
transform_matrix:
  - [[ 1.0,  0.0,  0.0,  0.0],
     [ 0.0,  0.0, -1.0, -3.1192],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
  - [[ 0.0,  0.0,  1.0,  3.1192],
     [ 1.0,  0.0,  0.0,  0.0],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
  - [[-1.0,  0.0,  0.0,  0.0],
     [ 0.0,  0.0,  1.0,  3.1192],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
  - [[ 0.0,  0.0, -1.0, -3.1192],
     [-1.0,  0.0,  0.0,  0.0],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
```

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-to-3d-pixal3d-mv
   ```

2. Accept the license for `briaai/RMBG-2.0` at https://huggingface.co/briaai/RMBG-2.0, then create `.env` from the sample:
   ```bash
   cp .env.sample .env
   # edit .env and set HF_TOKEN=hf_xxx
   ```

3. To reduce peak VRAM at the cost of slower inference, set `low_vram: true` in `model-compose.yml`. To trade texture fidelity for speed, set `resolution: 1024`.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup downloads Pixal3D's checkpoints (including the MV branch) and compiles CUDA kernels; expect several minutes before the controller reports ready.

2. **Run the workflow with four orbit views:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "front=@/path/to/front.png" \
     -F "right=@/path/to/right.png" \
     -F "back=@/path/to/back.png" \
     -F "left=@/path/to/left.png" \
     -F 'input={
       "image": ["@front", "@right", "@back", "@left"],
       "transform_matrix": [
         [[1,0,0,0],[0,0,-1,-3.1192],[0,1,0,0],[0,0,0,1]],
         [[0,0,1,3.1192],[1,0,0,0],[0,1,0,0],[0,0,0,1]],
         [[-1,0,0,0],[0,0,1,3.1192],[0,1,0,0],[0,0,0,1]],
         [[0,0,-1,-3.1192],[-1,0,0,0],[0,1,0,0],[0,0,0,1]]
       ],
       "camera_angle_x": 0.349
     }' \
     -o output.glb
   ```

## Configuration Reference

### Component Fields

| Field         | Description                                                                                                       | Default            |
|---------------|-------------------------------------------------------------------------------------------------------------------|--------------------|
| `task`        | Must be `image-to-3d`.                                                                                            | —                  |
| `driver`      | Must be `custom`.                                                                                                 | —                  |
| `family`      | Must be `pixal3d-mv`.                                                                                             | —                  |
| `model`       | Pixal3D model repository (HuggingFace repo or local path).                                                        | —                  |
| `device`      | Compute device. Must resolve to `cuda` — Pixal3D does not support CPU or MPS.                                     | `auto`             |
| `low_vram`    | Keep stage models on CPU and page each to GPU per stage.                                                          | `false`            |
| `resolution`  | Pipeline grid resolution (`1024` or `1536`).                                                                      | (see description)  |

### Action Fields

| Field                              | Description                                                                                    | Default          |
|------------------------------------|------------------------------------------------------------------------------------------------|------------------|
| `image`                            | List of view images. Element 0 must be the canonical front view.                               | —                |
| `transform_matrix`                 | List of 4x4 camera-to-world matrices, parallel to `image`.                                     | —                |
| `camera_angle_x`                   | Horizontal FOV in radians. Scalar (shared) or list (per view).                                 | —                |
| `mesh_scale`                       | Global mesh scale for camera-distance normalization.                                           | `1.0`            |
| `seed`                             | Random seed for reproducibility. Leave unset for a fresh sample per call.                      | (none)           |
| `params.image_resolution`          | Working image resolution used during preprocessing.                                            | `512`            |
| `params.ss_sampling_steps`         | Sparse-structure diffusion sampling steps.                                                     | `12`             |
| `params.ss_guidance_strength`      | Sparse-structure classifier-free guidance strength.                                            | `7.5`            |
| `params.ss_guidance_rescale`       | Sparse-structure guidance rescale factor.                                                      | `0.7`            |
| `params.ss_rescale_t`              | Sparse-structure timestep rescale factor.                                                      | `5.0`            |
| `params.shape_slat_sampling_steps` | Shape latent sampling steps.                                                                   | `12`             |
| `params.shape_slat_guidance_strength` | Shape latent classifier-free guidance strength.                                             | `7.5`            |
| `params.shape_slat_guidance_rescale`  | Shape latent guidance rescale factor.                                                       | `0.5`            |
| `params.shape_slat_rescale_t`      | Shape latent timestep rescale factor.                                                          | `3.0`            |
| `params.tex_slat_sampling_steps`   | Texture latent sampling steps.                                                                 | `12`             |
| `params.tex_slat_guidance_strength`| Texture latent classifier-free guidance strength.                                              | `1.0`            |
| `params.tex_slat_guidance_rescale` | Texture latent guidance rescale factor.                                                        | `0.0`            |
| `params.tex_slat_rescale_t`        | Texture latent timestep rescale factor.                                                        | `3.0`            |
| `params.max_num_tokens`            | Maximum sparse tokens per stage.                                                               | `49152`          |
| `params.texture_size`              | Baked texture resolution (pixels).                                                             | `4096`           |
| `params.decimation_target`         | Target face count applied during mesh decimation before GLB export.                            | `1000000`        |

## Notes

- **Frame 0 is the main view**: The pipeline snaps every other view onto its canonical front pose via `calc_mat_i = F @ inv(C_0) @ C_i`. If frame 0 is not itself the canonical front view, the whole rig is rotated relative to the object and the generated mesh comes out in a different frame than the models were trained for.
- **`transform_matrix` and `image` must be the same length**: The DSL validator enforces this. `camera_angle_x` must either be a scalar or a list of the same length.
- **Distance is derived from the matrix translation**: The pipeline computes `camera_distance` from `‖transform_matrix[:, :3, 3]‖`; there is no separate `distance` field to keep in sync.
- **Coordinate convention**: NeRF/Blender — Z-up world, each camera looks along its own -Z axis with its own +Y as up. Same convention the training renders use, so a dataset `transforms.json` maps 1-to-1 onto this action.
- **Alpha as mask**: Views with an existing non-opaque alpha channel bypass the rembg step. Fully opaque or missing alpha triggers `briaai/RMBG-2.0` for automatic segmentation.
- **First run is slow**: Same setup cost as single-view Pixal3D — the isolated virtualenv is a separate `.venv/pixal3d-mv` directory but installs the same pinned dependencies and CUDA extensions.
