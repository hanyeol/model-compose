# Face Swap Model Task Example

This example demonstrates how to use InsightFace's inswapper to transfer a face identity from a source image into every face detected in a target image using model-compose's built-in face-swap task, providing offline face swapping capabilities.

## Overview

This workflow provides local face swapping that:

1. **Local Face Swap Model**: Runs InsightFace's `inswapper_128` model locally without external APIs
2. **Identity Transfer**: Extracts the dominant face from the source image and applies its identity to face(s) in the target image
3. **Multi-Face Swap**: Optionally replaces every detected face in the target, or a specific one selected by index
4. **Automatic Alignment**: Uses the `buffalo_l` face-analysis pack for detection, landmarks, and alignment
5. **Graceful Fallback**: Returns the original target image unchanged when no face is detected in it
6. **Automatic Model Management**: Downloads and caches both the swapper and the detector pack automatically on first use

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Sufficient system resources to run onnxruntime (recommended: 4GB+ RAM)
- Python environment with `insightface`, `opencv-python`, and `onnxruntime` (installed automatically on first run)

### Why Local Face Swap

Unlike cloud face-swap services, running InsightFace locally provides:

**Benefits of Local Processing:**
- **Privacy**: All images are processed locally, no faces uploaded to external services
- **Cost**: No per-image or API usage fees
- **Offline**: Works without an internet connection after the initial model download
- **Latency**: No network round-trip on every inference
- **Pipeline Friendly**: Composes cleanly with other model-compose tasks (pose detection, image upscale, etc.) for downstream video pipelines

**Trade-offs:**
- **Hardware Requirements**: Requires adequate CPU/GPU resources; onnxruntime-gpu is recommended for batch or video use
- **Model Limitations**: `inswapper_128` produces 128×128 face crops before pasting back — very high-resolution targets may benefit from an additional face-restoration pass (e.g. GFPGAN, CodeFormer)
- **License**: The `inswapper_128` weights are released for **non-commercial research use only**

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/face-swap
   ```

2. No additional environment configuration required — both the swapper model and the `buffalo_l` detector pack are downloaded and cached automatically on first run.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Swap every face in the target with the identity from the source
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "source=@/path/to/source_face.jpg" \
     -F "target=@/path/to/target_image.jpg" \
     -F 'input={"source_image": "@source", "target_image": "@target"}'

   # Only swap a specific face in the target (index 0 = highest detection score)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "source=@/path/to/source_face.jpg" \
     -F "target=@/path/to/group_photo.jpg" \
     -F 'input={"source_image": "@source", "target_image": "@target", "swap_all_faces": false, "face_index": 1}'

   # Tune detection sensitivity for hard cases (small or partially occluded faces)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "source=@/path/to/source_face.jpg" \
     -F "target=@/path/to/target_image.jpg" \
     -F 'input={"source_image": "@source", "target_image": "@target", "detection_threshold": 0.3}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `source_image` (the face to transfer) and a `target_image` (the image to be modified)
   - Optionally toggle `swap_all_faces`, set `face_index`, or lower `detection_threshold` for harder cases
   - Click the "Run Workflow" button

## Configuration Reference

### Component Fields

| Field            | Description                                                                                     | Default        |
|------------------|-------------------------------------------------------------------------------------------------|----------------|
| `task`           | Must be `face-swap`.                                                                            | —              |
| `driver`         | Must be `custom`.                                                                               | —              |
| `family`         | Face-swap model family. Currently only `insightface`.                                           | —              |
| `model`          | Swapper model source. Point at the `inswapper_128.onnx` weights (URL or local path).            | —              |
| `detector_model` | InsightFace face-analysis pack used for detection/landmarks/alignment on both source and target. | `buffalo_l`    |

### Action Fields

| Field                  | Description                                                                                            | Default       |
|------------------------|--------------------------------------------------------------------------------------------------------|---------------|
| `source_image`         | Image providing the face identity to transfer. Must contain at least one face.                          | —             |
| `target_image`         | Image (or batch/stream) whose faces will be replaced.                                                   | —             |
| `swap_all_faces`       | When `true`, every detected face in the target is replaced. When `false`, only `face_index` is used.    | `true`        |
| `face_index`           | Target face to swap when `swap_all_faces` is `false`. Faces are sorted by detection score (0 = highest).| `0`           |
| `detection_threshold`  | Minimum face-detection confidence (0.0 – 1.0). Lower values catch harder faces at higher false-positive risk. | `0.5`     |
| `detection_size`       | Detection input size as `[width, height]`.                                                             | `[640, 640]`  |
| `batch_size`           | Number of target images processed per batch when `target_image` is a list or stream.                    | `1`           |

## Notes

- **Source image**: The action picks the single face with the highest detection score. If no face is detected in the source, the workflow fails with a clear error.
- **Target image with no face**: The original target is returned unchanged — useful when running frame-by-frame over video where some frames may not contain a person.
- **Batch / video use**: `target_image` accepts a list of images or a stream, so this component drops into a video pipeline (e.g. after motion-transfer generation) without extra glue.
- **Post-processing**: For higher fidelity at high resolution, chain an `image-upscale` (or a face-restoration) component after this one.
