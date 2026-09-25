# Camera Pose Estimator Example

This example demonstrates the `camera-pose-estimator` component with the COLMAP backend, showing how model-compose can recover camera intrinsics and per-image poses from a set of overlapping photos.

## Overview

This workflow provides a Structure-from-Motion (SfM) service that:

1. **Feature extraction and matching**: Detects SIFT keypoints in every input image and matches them across image pairs.
2. **Incremental reconstruction**: Bundle-adjusts an incremental sparse reconstruction, producing per-image camera poses plus a sparse 3D point cloud.
3. **COLMAP-format workspace**: Writes `workspace_dir/sparse/0/` in COLMAP binary format (`cameras.bin`, `images.bin`, `points3D.bin`) so downstream jobs (3D Gaussian Splatting trainers, NeRF pipelines, mesh extractors) can consume it without any conversion.

Two workflows are exposed, one for each input mode:

- `estimate-from-images`: You provide the images directly (typical when they come from an upstream job — a video frame extractor, downloader, web scraper, ...). The workspace is created automatically.
- `estimate-from-workspace`: You point at a workspace that already contains an `images/` subfolder — the layout standard COLMAP datasets ship in.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- `pycolmap` installed (`pip install pycolmap`)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/camera-pose-estimator
   ```

2. Verify pycolmap is installed:
   ```bash
   python -c "import pycolmap; print(pycolmap.__version__)"
   ```

3. For the `estimate-from-workspace` flow, pick a test dataset. Small, well-behaved datasets from the COLMAP project work well as a first run:
   ```bash
   mkdir -p ./data
   curl -L -o ./data/gerrard-hall.zip https://demuc.de/colmap/datasets/gerrard-hall.zip
   unzip -q ./data/gerrard-hall.zip -d ./data
   ```
   The dataset unpacks to `./data/gerrard-hall/` with an `images/` subfolder — that folder is a workspace ready for the second workflow.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run a workflow:**

   **Estimate from an uploaded image set (Web UI):**
   - Open the Web UI: http://localhost:8081
   - Pick the `estimate-from-images` workflow
   - Upload the image files that cover the scene
   - Click the "Run Workflow" button

   **Estimate from an uploaded image set (API):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/estimate-from-images/runs \
     -F "images=@scene/img_0001.jpg" \
     -F "images=@scene/img_0002.jpg" \
     -F "images=@scene/img_0003.jpg"
   ```

   **Estimate from an existing workspace (CLI):**
   ```bash
   model-compose run estimate-from-workspace \
     --input '{"workspace_dir": "./data/gerrard-hall"}'
   ```

3. **Inspect the result:**

   The workflow returns a JSON summary of the reconstruction:
   ```json
   {
     "workspace_dir": "./data/gerrard-hall/sparse/0",
     "images_count": 100,
     "points_count": 15234,
     "cameras": [ { "id": 1, "model": "OPENCV", "width": 1920, "height": 1080, "params": [...] } ],
     "poses": [ { "image": "0001.jpg", "camera_id": 1, "quaternion": [qw, qx, qy, qz], "translation": [tx, ty, tz] } ]
   }
   ```

   The full reconstruction lives on disk at `workspace_dir/sparse/0/` in COLMAP binary format. If more than one partial reconstruction was produced, additional folders (`sparse/1/`, `sparse/2/`, ...) are left in place for inspection.

## Component Details

### `estimator` — Camera Pose Estimator (COLMAP)

Runs the COLMAP feature extraction, matching, and incremental mapping pipeline against a set of images.

Key options:

- `camera_model` (default `opencv`): COLMAP camera model assumed for the input images. Use `pinhole` for photos with negligible distortion, `opencv-fisheye` or `radial-fisheye` for fisheye lenses, `simple-pinhole` when you have no calibration hints.
- `matcher` (default `exhaustive`): Pair selection strategy. `sequential` is much faster for frames extracted from a video (only nearby frames are matched); `spatial` uses GPS metadata.
- `single_camera` (default `true`): Assume all input images share one physical camera and one set of intrinsics. Turn off for mixed-source datasets.
- `use_gpu` (default `false`): Route SIFT extraction and matching to the GPU. Requires `pycolmap` to be built with CUDA support (the plain `pycolmap` wheel is CPU-only; use `pycolmap-cuda12` on Linux).

### Action inputs

- `images`: The images that make up one scene (or a batch/stream of scenes). Every element is a rendered image — typically wired from an upstream job (`${jobs.frame-extractor.output}`) or an uploaded image array.
- `workspace_dir`: Directory holding the COLMAP workspace (`images/`, `database.db`, `sparse/`). When omitted, `.workspace/<component-id>/<run-id>/` is used. When `images` is also omitted, images already present under `workspace_dir/images/` are reused.
- Exactly one of `images` or `workspace_dir` (or both) must be provided.

### Batch / streaming

If `images` is a list or stream of image arrays, each entry is treated as a separate scene and reconstructed independently. When `workspace_dir` is a scalar (or omitted), per-scene workspaces get a `-N` suffix appended to the run-id (`{run-id}-0/`, `{run-id}-1/`, ...) so scenes don't overwrite each other. When `workspace_dir` is itself a list or stream, its entries are zipped with `images` slot-for-slot and used as-is.

## Notes

- Reconstruction quality depends heavily on image overlap. Aim for at least 60% overlap between consecutive photos and cover the scene from many angles.
- Featureless surfaces (blank walls, water, glass, uniform grass) are hard for SIFT and often cause partial or failed reconstructions.
- The CPU pipeline on ~100 images typically takes several minutes on a modern laptop. Use `matcher: sequential` for video frames to keep matching time linear in the number of images.
- The driver keeps original image bytes intact so EXIF (focal length, GPS) survives — but only when images arrive as an unopened stream. If an upstream step already decoded them to PIL, EXIF is gone by the time the driver sees them, and `matcher: spatial` will have no GPS priors to sort by. Keep files on disk and use `estimate-from-workspace` when GPS-based matching matters.
