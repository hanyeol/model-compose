# Camera Pose Estimator Component

The camera pose estimator component recovers per-image camera poses and a sparse 3D point cloud from a set of overlapping photos using Structure-from-Motion (SfM). Reconstruction is performed by the selected driver (currently COLMAP via `pycolmap`) and written to a COLMAP-format workspace (`images/`, `database.db`, `sparse/`) that downstream jobs — 3D Gaussian Splatting trainers, NeRF pipelines, mesh extractors — can consume without any conversion.

## Basic Configuration

```yaml
component:
  type: camera-pose-estimator
  driver: colmap
  action:
    images: ${input.images as image[]}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `camera-pose-estimator` |
| `driver` | string | `colmap` | SfM backend driver. Currently only `colmap` (pycolmap-based). |
| `camera_model` | string | `opencv` | COLMAP camera model assumed for input images. See [Camera Models](#camera-models). |
| `matcher` | string | `exhaustive` | Feature matching strategy. One of `exhaustive`, `sequential`, `spatial`. |
| `single_camera` | boolean | `true` | Whether all input images share one physical camera and intrinsics. |
| `use_gpu` | boolean | `false` | Route SIFT feature extraction/matching to the GPU. Requires a CUDA-enabled pycolmap build. |
| `thread_count` | integer | `null` | Number of CPU threads used by COLMAP. Auto when omitted. |
| `actions` | array | `[]` | List of estimation actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `images` | string \| string[] | `null` | Image or list of images the reconstruction is built from. When omitted, images already present under `workspace_dir/images/` are used. |
| `workspace_dir` | string | `null` | Directory holding the COLMAP workspace (`images/`, `database.db`, `sparse/`). Defaults to `.workspace/<component-id>/<run-id>/` when omitted. |
| `return_cameras` | boolean \| string | `true` | Include recovered camera intrinsics as a list of dicts in the result. Cheap to compute — turn off only when the HTTP response noise is undesirable. |
| `return_poses` | boolean \| string | `true` | Include per-image world-from-camera poses as a list of dicts in the result. Cheap to compute — turn off only when the HTTP response noise is undesirable. |
| `return_points` | boolean \| string | `false` | Include the sparse point cloud (with camera frustums) as a GLB model in the result. Opt-in — the primary downstream consumer is a workspace-reading job (3DGS trainer, mesh extractor), not a viewer. Enable it when the workflow output feeds a Gradio `Model3D` component or another GLB consumer. |
| `return_metadata` | boolean \| string | `true` | Include the reconstruction summary (`workspace_dir`, `images_count`, `points_count`) in the result. Turn off when downstream consumers derive the workspace path themselves and don't need the counters. |
| `batch_size` | integer \| string | `1` | Number of scenes buffered before results are emitted downstream on a streaming input. Scenes within a batch are still reconstructed sequentially — this is a flow-control knob for streaming consumers, not a parallelism setting. |

Exactly one of `images` or `workspace_dir` (or both) must be provided.

## Supported Drivers

### COLMAP (pycolmap)

Runs the [COLMAP](https://colmap.github.io/) SfM pipeline (SIFT feature extraction → pairwise matching → incremental mapping with bundle adjustment) via the [pycolmap](https://pypi.org/project/pycolmap/) Python bindings.

```yaml
component:
  type: camera-pose-estimator
  driver: colmap
  camera_model: opencv
  matcher: exhaustive
```

**Requires:** `pip install pycolmap`. For GPU-accelerated SIFT on Linux, install `pycolmap-cuda12` instead of `pycolmap` and set `use_gpu: true`.

## Camera Models

The `camera_model` field selects the COLMAP camera model applied to input images. Choose based on lens characteristics:

| Model | Use When |
|-------|----------|
| `simple-pinhole` | No calibration hints; single focal length, principal point at image center. |
| `pinhole` | Rectilinear lens; independent fx / fy, arbitrary principal point. |
| `simple-radial` | Rectilinear lens with mild radial distortion (one distortion coefficient). |
| `radial` | Rectilinear lens with two radial distortion coefficients. |
| `opencv` | Rectilinear lens; k1/k2 radial + p1/p2 tangential distortion. Recommended default. |
| `opencv-fisheye` | Fisheye lens; OpenCV's four-parameter fisheye model. |
| `full-opencv` | Rectilinear lens with the full 12-parameter OpenCV model (k1..k6, p1, p2). |
| `fov` | Field-of-view distortion model. |
| `simple-radial-fisheye` | Fisheye with one distortion coefficient. |
| `radial-fisheye` | Fisheye with two distortion coefficients. |
| `thin-prism-fisheye` | Fisheye with thin-prism distortion terms. |

## Matcher Strategies

The `matcher` field selects how image pairs are chosen for feature matching:

| Matcher | Use When |
|---------|----------|
| `exhaustive` | All-pairs matching. Recommended default for photo sets up to a few hundred images. |
| `sequential` | Adjacent-frame matching only. Much faster for frames extracted from a video; assumes sequential capture order. |
| `spatial` | Match nearby images based on GPS metadata embedded in EXIF. Requires images that still carry their original GPS EXIF tags — see [EXIF Preservation](#exif-preservation) for what survives the pipeline. |

## Output Format

The action returns one result dict per scene (or a single dict when the input is a single scene) describing the reconstruction:

```json
{
  "workspace_dir": "./data/gerrard-hall/sparse/0",
  "images_count": 100,
  "points_count": 15234,
  "cameras": [
    {
      "id": 1,
      "model": "OPENCV",
      "width": 1920,
      "height": 1080,
      "params": [ 1200.0, 1200.0, 960.0, 540.0, 0.01, -0.005, 0.001, 0.0002 ]
    }
  ],
  "poses": [
    {
      "image": "0001.jpg",
      "camera_id": 1,
      "quaternion": [ 0.9998, 0.012, -0.015, 0.002 ],
      "translation": [ -3.31, 0.21, 2.20 ]
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `cameras` | Recovered camera intrinsics. `params` follows the parameter order defined by `model` (e.g. `[fx, fy, cx, cy, k1, k2, p1, p2]` for `OPENCV`). Present when `return_cameras: true` (default). |
| `poses` | Per-image world-from-camera pose. `quaternion` is `[qw, qx, qy, qz]` (COLMAP text convention). Present when `return_poses: true` (default). |
| `points` | Sparse point cloud + camera frustums as a GLB `Model3DStreamResource`, only present when `return_points: true`. Route with `${output.points as model-3d/glb}`. |
| `workspace_dir` | Absolute or relative path to the produced `sparse/N/` folder in COLMAP binary format. Downstream jobs (3DGS trainers, mesh extractors) point at this directory. Present when `return_metadata: true` (default). |
| `images_count` | Number of input images whose pose was successfully recovered. Present when `return_metadata: true` (default). |
| `points_count` | Number of triangulated 3D points in the sparse reconstruction. Present when `return_metadata: true` (default). |

Extra partial reconstructions produced during incremental mapping are left on disk under `workspace_dir/sparse/1/`, `sparse/2/`, ... but are not summarised in the returned dict.

## Workspace Layout and Routing

The driver writes into a workspace folder with this layout:

```
<workspace>/
├── images/           # Input images (either dumped from `images` or reused as-is)
├── database.db       # COLMAP database — features, matches, two-view geometry
└── sparse/
    └── 0/            # Best reconstruction (cameras.bin, images.bin, points3D.bin)
```

How the base workspace is chosen:

| `workspace_dir` | `images` | Base workspace |
|-----------------|----------|----------------|
| omitted or scalar | scalar or omitted | `{workspace_dir or ".workspace/<component-id>"}/<run-id>/` |
| omitted or scalar | list or stream (N scenes) | `{workspace_dir or ".workspace/<component-id>"}/<run-id>-0/`, `<run-id>-1/`, ..., `<run-id>-(N-1)/` |
| list or stream | any | Each entry used as-is, zipped with `images` slot-for-slot |

The per-run subfolder (`<run-id>/`) prevents parallel runs from colliding. The `-N` suffix on multi-scene runs prevents scenes from overwriting each other when they share a scalar base.

## EXIF Preservation

COLMAP consults EXIF metadata for two things: the `FocalLength` tag becomes a per-image focal-length prior that seeds intrinsics estimation, and GPS tags feed the `spatial` matcher. Anything that strips those tags weakens the reconstruction — the focal-length prior falls back to a `1.2 × max(width, height)` heuristic, and the spatial matcher has nothing to sort image pairs by.

To keep the metadata intact, the driver writes each input image out as its original encoded bytes rather than re-encoding via PIL. In practice, EXIF survives when the image reaches the driver as a stream that was never decoded upstream:

- **Preserved**: images that arrive as an `ImageStreamResource` carrying raw bytes — typical for uploads (`gr.File`), URLs fetched by an upstream component, or files read from disk.
- **Lost**: images that were decoded to PIL somewhere upstream (for example, another component that returned rendered `PIL.Image` objects). Re-encoding at that earlier step already dropped EXIF; the driver cannot recover it.
- **Recommended for GPS-critical runs**: keep the original files on disk and use the `estimate-from-workspace` mode — the driver reads them straight from `workspace_dir/images/` without touching the encoding.

## Integration with Workflows

### Single Reconstruction from Uploaded Images

```yaml
workflows:
  - id: estimate
    job:
      component: estimator
      input:
        images: ${input.images as image[]}
      output: ${output as json}

components:
  - id: estimator
    type: camera-pose-estimator
    driver: colmap
    action:
      images: ${input.images}
```

### Rerun Against an Existing COLMAP Dataset

Standard COLMAP datasets ship with an `images/` subfolder already in place. Point at the dataset directory as the workspace and omit `images`:

```yaml
workflows:
  - id: estimate-existing
    job:
      component: estimator
      input:
        workspace_dir: ${input.workspace_dir as string}
      output: ${output as json}

components:
  - id: estimator
    type: camera-pose-estimator
    driver: colmap
    action:
      workspace_dir: ${input.workspace_dir}
```

### Pipe from a Video Frame Extractor

Feed video frames straight into SfM to reconstruct a scene captured on camera:

```yaml
workflows:
  - id: video-to-poses
    jobs:
      - id: extract
        component: video-frame-extractor
        input:
          video: ${input.video as video}
        output:
          frames: ${output as image[]}

      - id: estimate
        component: estimator
        input:
          images: ${jobs.extract.output.frames}
        depends_on: [ extract ]
        output: ${output as json}
```

Consider setting `matcher: sequential` on the estimator when the input is a video: sequential frames have known temporal order, and matching only nearby frames keeps matching time linear in the number of images.

## Best Practices

1. **Aim for at least 60% overlap between consecutive photos.** Reconstruction quality depends heavily on image overlap; sparse coverage leaves gaps that fail to register.
2. **Cover the scene from many angles.** Move around the subject rather than shooting from a single viewpoint — SfM needs baseline to triangulate points.
3. **Avoid featureless surfaces.** Blank walls, water, glass, and uniform grass are hard for SIFT and often cause partial or failed reconstructions.
4. **Match `camera_model` to the lens.** The default `opencv` works well for most rectilinear photos, but 360° or fisheye captures need `opencv-fisheye` or `radial-fisheye`.
5. **Use `matcher: sequential` for video frames.** Exhaustive matching is O(N²) in image count; sequential matching stays linear and produces equivalent results when frames come from a single continuous capture.
6. **Persist important results to a named `workspace_dir`.** The default `.workspace/<component-id>/<run-id>/` is convenient for one-off runs but harder to locate later. Point at a well-known directory when the reconstruction feeds a longer-term downstream pipeline.
