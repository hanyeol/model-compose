# Face Gender Annotate Example

This example demonstrates a workflow that detects every face in an input image, classifies each face as male or female with the same detector's genderage head, and returns the source image with a colored bounding box drawn around each face — **blue for male**, **red for female**, gray if the detector was unsure.

## Overview

Given an input image, the workflow returns two fields: `annotated_image` (the source image with per-face colored boxes drawn on top) and `faces` (the raw detection records — bounding boxes, scores, gender, age — for downstream processing).

The strategy is:

1. **Spool the upload into two branches** with a `fan-out` job in `spool: true` mode. The upload is single-use, and the two readers consume it at very different times: `detect` drains its branch immediately, while `annotate` only opens its branch after `detect` finishes (to seed the accumulator with the source image). Spool lands the upload on a tempfile once so both branches can open the file at their own pace; the tempfile is deleted after every branch closes.
2. **Run face detection** with the InsightFace antelopev2 pack. Turning on `return_gender_age: true` populates `face.gender` (`"male"` or `"female"`) and `face.age` on every detection, using the pack's built-in genderage head. No separate classifier is needed.
3. **Fold one bounding box per face** onto the source image with an inline `accumulate` job. Each iteration takes the running image (`${accumulator}`) and returns the same image with one more outlined rectangle drawn on it. The outline color is picked per face by a conditional expression on `item.gender`.

### Why gender lives on `face-detection` (not a separate classifier)

The InsightFace antelopev2 pack ships the SCRFD detector *and* a genderage classifier — the same forward pass that finds each face also assigns it a gender and an age. Exposing that on `face-detection` (via `return_gender_age: true`, mirroring `face-embedding` and `face-tracking`) avoids the round-trip of cropping every face and feeding it to a second model just to answer "male or female". If you swap in a pack that doesn't ship genderage, the `gender` and `age` fields are simply omitted rather than raising an error.

### Why an inline accumulate for the drawing step

`image-drawing` exposes one drawing operation per action call (rectangle, text, line, …), so drawing N boxes needs N calls. `accumulate` runs one `do:` per input item and threads the running image forward as the next iteration's `${accumulator}`, so the natural way to layer N boxes on the source image is an `accumulate` job that folds each detection onto the accumulator. If a face has no detected gender, the color conditional's `if_false` gray fallback applies — the box still draws.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python dependencies for InsightFace detection:
  ```bash
  pip install insightface opencv-python onnxruntime pillow
  ```
- The InsightFace **antelopev2** pack is downloaded automatically on first run into model-compose's model cache. No manual download needed.

### Setup

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/face-gender-annotate
   ```

2. Prepare an image with at least one visible face.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload the image and optionally override `min_confidence` / `line_width`
   - Click "Run Workflow"
   - The response contains `annotated_image` (the input with colored face boxes drawn) and `faces` (the raw detection records).

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"min_confidence": 0.5};type=application/json' \
     -F 'image=@./people.jpg'
   ```

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "image": "./people.jpg",
     "min_confidence": 0.5
   }'
   ```

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | image (file) | Yes | - | Input image to detect and annotate faces in |
| `min_confidence` | number | No | `0.5` | Minimum detection confidence (0.0 – 1.0). Lower it (e.g. `0.35`) to recover borderline / partially-occluded faces at the cost of a few false positives |
| `line_width` | number | No | `3` | Rectangle outline thickness in pixels |

## Output Shape

```json
{
  "annotated_image": "<image PNG>",
  "faces": [
    {
      "bounding_box": { "x": 120, "y": 84, "width": 156, "height": 202 },
      "score": 0.94,
      "gender": "male",
      "age": 34
    },
    {
      "bounding_box": { "x": 380, "y": 96, "width": 148, "height": 194 },
      "score": 0.91,
      "gender": "female",
      "age": 28
    }
  ]
}
```

- `annotated_image` — the source image with one bounding box drawn per detected face. Blue (`#1E90FF`) for `"male"`, red (`#DC143C`) for `"female"`, gray (`#808080`) if the pack didn't return a gender for that face.
- `faces[].gender` — `"male"` or `"female"`, or absent if the detector's genderage head didn't produce a value.
- `faces[].age` — integer estimated age in years, or absent if unavailable.
- `faces[].bounding_box` — `{x, y, width, height}` in pixels of the source image's coordinate system.
- `faces[].score` — detector confidence, 0.0 – 1.0.

## Job Details

### Fan-Out (`fanout-image`)
- **Type**: `fan-out` (`spool: true`)
- **Function**: Tees the single-use image upload into two independent branches — `for-detect` (feeds the detector) and `for-annotate` (seeds the `accumulate` job's initial accumulator once `detect` finishes). With `spool: true` the upload is landed on a tempfile once and each branch opens the file at its own pace; the tempfile is deleted after every branch closes. Spool avoids the queue backpressure the ordinary fan-out path would otherwise hit because the annotate branch only starts consuming after the detector finishes.

## Component Details

### Face Detector (`face-detector`)
- **Type**: `model` — `face-detection` task
- **Driver**: `custom` (InsightFace family, `antelopev2` pack)
- **Function**: Detects every face in the input image and, with `return_gender_age: true`, tags each detection with the pack's genderage prediction (`"male"` / `"female"` plus an integer age). `max_concurrent_count: 1` serialises inference so ONNX Runtime memory stays bounded. Raise `detection_size` to `(960, 960)` or `(1280, 1280)` to recover smaller / more distant faces at proportional cost per image.

### Box Drawer (`box-drawer`)
- **Type**: `image-drawing` (`rectangle` method)
- **Driver**: `native`
- **Function**: Draws one outlined rectangle onto the running accumulator. Outline color is picked per detection by a conditional on `item.gender`: male → dodger blue (`#1E90FF`), female → crimson (`#DC143C`), else gray (`#808080`). `line_width` sets the outline thickness in pixels.

## Notes and Tuning

- **Cost**: One InsightFace forward pass per image. On CPU-only inference this is dominated by detection; the genderage head is a small extra cost per detected face. On Apple Silicon the example prefers the CoreML execution provider when available, which typically brings per-image latency down to well under a second for HD input.
- **No gender returned**: The `gender` field is only populated when the loaded pack ships a genderage model. `antelopev2` (this example's default) does. If you swap `model.url` to a detection-only pack, boxes still draw but they'll all be gray (the fallback color) — that's the annotator's signal that gender was requested but the pack couldn't answer.
- **Missed faces**: If a face is skipped at the default `min_confidence: 0.5`, lower it to `0.35` first; if faces are missed at every threshold, they're likely too small for the default `(640, 640)` detection input — bump `detection_size` on the `face-detector` component.
- **False positives**: Very high `min_confidence` (e.g. `0.85`) drops occluded / profile faces before they can be annotated. If you're seeing spurious boxes at the default threshold, raising it in `0.05` increments is usually enough.
- **Custom colors**: The color palette is encoded inline in the `annotate` job's `outline` conditional — blue `#1E90FF` for male, red `#DC143C` for female, gray `#808080` for unknown. Edit the hex strings to change the scheme, or add branches (e.g. per-age brackets) by extending the `"?"` list.
- **Spool tempfile**: The fan-out spool writes to the OS temp directory returned by `tempfile.NamedTemporaryFile` (respects `TMPDIR`). Files are deleted after all branches close, so no manual cleanup is needed. If your temp partition is small and inputs are large, point `TMPDIR` at a bigger disk.
