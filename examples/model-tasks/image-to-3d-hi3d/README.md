# Image-to-3D Mesh Refinement Example

This example demonstrates how to refine a coarse 3D mesh into high-resolution geometry using **Hi3D v1.0** (built on Sparc3D), exposed through model-compose's built-in `image-to-3d` task.

## Overview

Hi3D v1.0 is a geometry **refinement** model, not a generator. Each request pairs a reference image with a coarse mesh produced upstream — Hi3D sharpens the shape while keeping the overall silhouette aligned to the image. The output is a geometry-only GLB (no textures, materials, or vertex colors).

This workflow provides:

1. **Reference-conditioned refinement**: The flow-matching stack upgrades a coarse mesh to a 1024³ (or 1536³) sparse extraction grid, aligned to the reference image via DINOv2 + CLIP features.
2. **Coarse-stage agnostic**: Any trimesh-readable mesh works as input (GLB, OBJ, PLY, STL). Produce it with any upstream image-to-3d component — `pixal3d`, `world-mirror`, or Hunyuan3D-2 mini are natural pairings.
3. **Automatic weight management**: The Hi3D checkpoint (`hi3d-official/Hi3Dv1.0`) is downloaded from HuggingFace Hub on first run; DINOv2 and CLIP are fetched by the pipeline on first use.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU with compute capability **8.0+** (Ampere or newer). CPU, MPS (Apple Silicon), and AMD ROCm are not supported — Hi3D's spconv and flash-attention kernels are CUDA-only.
- A Linux host with the **CUDA toolkit 12.0–12.5** installed. The pipeline builds spconv and flash-attn against the installed nvcc; mismatched CUDA versions fail at install time.
- A Python environment where `torch==2.5.0`, `flash-attn==2.7.4.post1`, `spconv-cu120==2.3.6`, and Hi3D's `sparc3d` package can be installed — the first run installs them automatically into the isolated `.venv/hi3d`.
- An upstream coarse-mesh producer. See [Producing a Coarse Mesh](#producing-a-coarse-mesh) below.

### License

Hi3D v1.0 ships under the **Hi3D Open License Agreement v1.0**, not Apache or MIT. Commercial use is permitted but requires a separate license if a product exceeds **200,000 monthly active users** or **$1,000,000 monthly revenue**. Review the terms at the [Hi3D v1.0 repository](https://github.com/hi3d-official/Hi3Dv1.0) before shipping.

### Producing a Coarse Mesh

Hi3D refines, it does not generate. Point the `mesh` input at any image-to-3d result:

- **`image-to-3d-pixal3d`** — produces a 1k-face PBR GLB; use its `.glb` output directly.
- **`image-to-3d-world-mirror`** — for scenes/environments; use its `points.ply` or extract a mesh via a converter.
- **Hunyuan3D-2 mini** — Hi3D's own reference pipeline recommends this; adapt it as a separate model-compose component or run `demo/coarse_stage.py` from the Hi3D repo manually.

The coarse mesh does not need to be clean or watertight — Hi3D's refinement is tolerant to topology artifacts, as long as the silhouette roughly matches the reference image.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-to-3d-hi3d
   ```

2. (Optional) If your HuggingFace account is rate-limited, set `HF_TOKEN`:
   ```bash
   export HF_TOKEN=hf_xxx
   ```
   `hi3d-official/Hi3Dv1.0`, `facebook/dinov2-large`, and `openai/clip-vit-large-patch14` are all public, so no token is strictly required.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup creates `.venv/hi3d`, installs Hi3D's pinned dependencies, builds spconv/flash-attn against the local CUDA toolkit, and downloads the Hi3D checkpoint plus DINOv2/CLIP (~10 GB total). Expect 10-20 minutes before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — refine an input mesh with a reference image
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/reference.png" \
     -F "src=@/path/to/coarse.glb" \
     -F 'input={"image": "@img", "mesh": "@src"}' \
     -o refined.glb

   # Reproducible refinement with a fixed seed
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/reference.png" \
     -F "src=@/path/to/coarse.glb" \
     -F 'input={"image": "@img", "mesh": "@src", "seed": 0}' \
     -o refined.glb

   # Higher-resolution refinement (1536 grid) — sharper geometry, more VRAM
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/reference.png" \
     -F "src=@/path/to/coarse.glb" \
     -F 'input={"image": "@img", "mesh": "@src", "resolution": 1536}' \
     -o refined.glb
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a reference `image` and a `mesh` (GLB/OBJ/PLY/STL)
   - Optionally set `seed`, `resolution` (512 / 1024 / 1536), or `num_inference_steps`
   - Click "Run Workflow" to receive a refined `.glb` file back

## Configuration Reference

### Component Fields

| Field    | Description                                                                   | Default |
|----------|-------------------------------------------------------------------------------|---------|
| `task`   | Must be `image-to-3d`.                                                        | —       |
| `driver` | Must be `custom`.                                                             | —       |
| `family` | Must be `hi3d`.                                                               | —       |
| `model`  | Hi3D v1.0 model repository (HuggingFace repo or local path).                  | —       |
| `device` | Compute device. Must resolve to `cuda` — Hi3D does not support CPU or MPS.    | `auto`  |

### Action Fields

| Field                       | Description                                                                                   | Default |
|-----------------------------|-----------------------------------------------------------------------------------------------|---------|
| `image`                     | Reference image (single, list, or stream).                                                    | —       |
| `mesh`                      | Input mesh to be refined (any trimesh-readable format: GLB, OBJ, PLY, STL).                   | —       |
| `seed`                      | Random seed for reproducible refinement.                                                      | `0`     |
| `batch_size`                | Number of inputs processed per batch when the inputs are lists or streams.                    | `1`     |
| `params.resolution`         | Sparse extraction-grid resolution. One of `512`, `1024`, `1536`.                              | `1024`  |
| `params.num_inference_steps`| Flow-matching refinement steps.                                                               | `25`    |

## Notes

- **Refinement-only**: Hi3D does not accept image-only input. Omitting `mesh` raises a validation error at request time rather than silently producing a bad mesh.
- **Geometry only**: The output GLB carries vertex positions and faces; textures, normals, materials, and vertex colors are not produced. Composite textures afterward with an upstream texturing pipeline if needed.
- **First run is slow**: Expect 10-20 minutes on first startup for venv provisioning, extension builds (spconv, flash-attn), and weight downloads. Subsequent runs reuse the cached venv and artefacts.
- **Isolated runtime**: The model worker runs in `.venv/hi3d` so Hi3D's hard-pinned `torch==2.5.0`, `flash-attn==2.7.4.post1`, and `spconv-cu120==2.3.6` do not clash with the controller's site-packages. The driver refuses to run in the controller's native environment.
- **CUDA is required**: Hi3D hardcodes CUDA device placement and relies on spconv kernels compiled against CUDA 12.0–12.5. The driver refuses to load on non-CUDA hosts rather than falling back to a broken path.
- **Input mesh alignment**: Hi3D's refinement is bounded by how well the input mesh matches the reference image's silhouette. A misaligned input (wrong aspect ratio, wrong orientation) yields a refined mesh that preserves the misalignment. Validate the input against the reference image before refining.
- **VRAM**: Peak VRAM at `resolution: 1024` is roughly 20 GB; `1536` is closer to 30 GB. A single 24 GB consumer card handles the 1024 path; 1536 benefits from an A100 40 GB or RTX 6000 Ada.
- **Output**: The result is a single `.glb` file per input (or a list for batched inputs). Load in Blender, three.js, Unity's glTFast, or any glTF-compatible viewer.
