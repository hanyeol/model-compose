# NSFW Annotate Example

This example demonstrates a workflow that detects NSFW regions in an input image and returns the same image with a colored, labelled bounding box drawn around each detection — **red for `*_EXPOSED` classes**, **yellow for `*_COVERED` classes**, **gray for anything else** (FACE_*, etc.).

Companion example to [nsfw-mosaic](../nsfw-mosaic/): same detector, but instead of pixelating the regions it draws them so you can visually inspect what the model saw and at what confidence.

> **Bring your own model**: this example does not download any NSFW weights. You must supply a YOLO-format detector trained on NSFW classes at `./models/nsfw_detector.pt` — the same file the `nsfw-mosaic` example uses. See [nsfw-mosaic/README.md](../nsfw-mosaic/README.md#preparing-the-detector-model) for the download command.

## Overview

Given an input image, the workflow returns two fields: `annotated_image` (the source image with per-detection colored boxes and labels drawn on top) and `objects` (the raw detection records — labels, scores, bounding boxes — for downstream processing).

The strategy is:

1. **Spool the upload into three branches** with a `fan-out` job in `spool: true` mode. The upload is single-use and three jobs need to read it: `measure` drains its branch immediately, `brighten` waits on `factor`, and `annotate` waits on `detect` — a significant lag. Spool lands the upload on a tempfile once so each branch can open the file at its own pace; the tempfile is deleted after every branch closes.
2. **Measure mean luma** on the source with `image-analyzer analyze-brightness` — returns `mean_brightness` on the 0–255 ITU-R BT.601 scale.
3. **Compute a brightness factor** (`target_luma / mean_brightness`) with a one-line Python `shell` step. Falls back to `1.0` for all-black inputs or when `target_luma: 0` is passed (the opt-out).
4. **Brighten** the source with `image-processor adjust-brightness` — PIL's linear brightness multiplier. Extreme shifts clip, so a very dark source normalised to luma 200 will land slightly under target; that's fine for feeding a detector.
5. **Run NSFW detection** with an Ultralytics YOLO model on the brightened image. Returns `{objects: [{label, label_id, confidence, bounding_box: {x, y, width, height}}], width, height}`.
6. **Fold one labelled box per detection** onto the **untouched original** image with an inline `accumulate` job. Each iteration runs a two-step inner pipeline: draw the outlined rectangle, then draw the label text just above the box. The outline and text color are picked per detection by a suffix-matching conditional: `*_EXPOSED` → red, `*_COVERED` → yellow, anything else → gray.

### Why normalise brightness before detection

NudeNet (and every other publicly-trained NSFW YOLO) was trained on photos in a normal exposure range. Very dark or very bright inputs sit outside that distribution and confidence scores drop across the board — sometimes below `min_confidence`, which is what turns a "should be obvious" region into a miss. Normalising to an absolute target luma (rather than a relative multiplier like `1.5×`) means every input converges to the same brightness band regardless of its original exposure, so the detector sees inputs it was trained on.

The brightening is applied only to the detector's input. Annotations are drawn on the untouched original so the returned image matches the caller's upload — you see the boxes on the pixels you sent.

### Why draw on the original, not the brightened image

Two reasons:

1. **The output is a labelled version of the caller's file** — dumping brightened pixels back at the user would be surprising if all they wanted was "where are the detections".
2. **Sweep-style comparison stays clean** — you can rerun with different `target_luma` values and diff the returned `objects` arrays without the returned images also changing shape.

If you want to *see* what the detector saw (the brightened frame with the boxes on top), branch the annotate job's accumulator to `${jobs.brighten.output as image}` instead of `${jobs.fanout-image.output.for-annotate}`.

### Why a two-step inner pipeline

`image-drawing` exposes one drawing operation per action call (rectangle, text, line, …), so a "rectangle + label" combo needs two calls. `accumulate` runs a single `do:` per iteration, and the natural way to chain two drawing calls per iteration is an inline `pipeline` — step 1 draws the rectangle onto the running accumulator, step 2 draws the label on top of that. The pipeline's output flows back to `accumulate` as the next iteration's accumulator.

### Why suffix matching for color

NudeNet's 18 classes all end in `_EXPOSED`, `_COVERED`, or are `FACE_MALE` / `FACE_FEMALE`. Rather than enumerating every class in the color conditional (18 branches), the workflow keys off the suffix with the `ends-with` operator — two branches (`_EXPOSED`, `_COVERED`) plus a gray fallback catches everything and stays legible.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python dependencies for Ultralytics YOLO:
  ```bash
  pip install ultralytics
  ```

### Preparing the detector model

Same as [nsfw-mosaic](../nsfw-mosaic/README.md#preparing-the-detector-model). Recommended: NudeNet v3.4 640m via the Hugging Face mirror:

```bash
mkdir -p models
curl -fL -o models/nsfw_detector.pt \
  https://huggingface.co/vladmandic/nudenet/resolve/main/nudenet-v34-640m.pt
```

Verify the file is ~52 MB (`file models/nsfw_detector.pt` should report `Zip archive data`). If you already have the file in the sibling `nsfw-mosaic/models/` directory, a symlink works too:

```bash
mkdir -p models
ln -s ../../nsfw-mosaic/models/nsfw_detector.pt models/nsfw_detector.pt
```

### Setup

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/nsfw-annotate
   ```

2. Place your detector weights at `./models/nsfw_detector.pt`.

3. Prepare an image to annotate.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload the image and optionally override `min_confidence` / `line_width` / `bounding_box_padding`
   - Click "Run Workflow"
   - The response contains `annotated_image` (the input with colored labelled boxes) and `objects` (the raw detection records).

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"min_confidence": 0.35};type=application/json' \
     -F 'image=@./photo.jpg'
   ```

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "image": "./photo.jpg",
     "min_confidence": 0.35
   }'
   ```

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | image (file) | Yes | - | Input image to detect and annotate NSFW regions in |
| `target_luma` | number | No | `130` | Target mean luma (0–255, BT.601). The detector's input is scaled so its mean luma matches this. Set to `0` to skip normalisation and detect on the raw pixels. Typical band: `100`–`160` for photographic content; below `40` crushes shadows, above `215` blows out highlights |
| `min_confidence` | number | No | `0.35` | Minimum detection confidence (0.0 – 1.0). Lower it (e.g. `0.2`) to surface borderline detections during model inspection |
| `bounding_box_padding` | number | No | `0.0` | Ratio each detected box is expanded outward before drawing. Kept at `0.0` here (unlike `nsfw-mosaic`) so the drawn box matches the detector's raw output exactly — useful for visual debugging |
| `line_width` | number | No | `3` | Rectangle outline thickness in pixels |
| `text_stroke_width` | number | No | `2` | Text stroke width in pixels (black outline around the label so it stays readable against any background) |

## Output Shape

```json
{
  "annotated_image": "<image PNG>",
  "objects": [
    {
      "label": "FEMALE_BREAST_EXPOSED",
      "label_id": 3,
      "confidence": 0.87,
      "bounding_box": { "x": 412, "y": 180, "width": 220, "height": 260 }
    },
    {
      "label": "FACE_FEMALE",
      "label_id": 16,
      "confidence": 0.94,
      "bounding_box": { "x": 380, "y": 40, "width": 160, "height": 200 }
    }
  ]
}
```

- `annotated_image` — the source image with one bounding box + label drawn per detection.
- `objects[].label` — the NSFW class name (model-specific; NudeNet v3.4 uses names like `FEMALE_BREAST_EXPOSED`, `MALE_GENITALIA_EXPOSED`, `BUTTOCKS_COVERED`, `FACE_MALE`, …).
- `objects[].confidence` — detector confidence, 0.0 – 1.0.
- `objects[].bounding_box` — `{x, y, width, height}` in pixels of the source image's coordinate system.

## Job Details

### Fan-Out (`fanout-image`)
- **Type**: `fan-out` (`spool: true`)
- **Function**: Tees the single-use image upload into three independent branches — `for-measure` (feeds the brightness analyser), `for-brighten` (feeds the detector's input after `factor` finishes), and `for-annotate` (seeds the accumulate job's initial accumulator once `detect` finishes). With `spool: true` the upload is landed on a tempfile once and each branch opens the file at its own pace; the tempfile is deleted after every branch closes. Spool avoids the queue backpressure the ordinary fan-out path would otherwise hit because two of the branches only start consuming well after `measure`.

## Component Details

### Image Analyzer (`image-analyzer`)
- **Type**: `image-analyzer` (`analyze-brightness` action)
- **Driver**: `native`
- **Function**: Returns `mean_brightness` on the 0–255 BT.601 luma scale. The `factor-calc` job divides `target_luma` by this to produce the multiplier `adjust-brightness` needs. Also returns `min_brightness` / `max_brightness` / `std_brightness` which the workflow doesn't surface but are available if you want to key off contrast too.

### Factor Calc (`factor-calc`)
- **Type**: `shell`
- **Function**: One-line Python that prints `target / original` (falling back to `1.0` when either value is zero). The DSL doesn't do arithmetic, so this is the smallest possible detour. Output is decoded `as number` so the brightener consumes a real float.

### Image Processor (`image-processor`, `adjust-brightness` action)
- **Type**: `image-processor`
- **Driver**: `native`
- **Function**: Multiplies pixel values by the computed factor via PIL's `ImageEnhance.Brightness`. A factor of `1.0` is a no-op, so `target_luma: 0` (which makes `factor-calc` return `1.0`) fully short-circuits normalisation without any special-case wiring.

### NSFW Detector (`nsfw-detector`)
- **Type**: `model` — `object-detection` task
- **Driver**: `custom` (Ultralytics YOLO family)
- **Function**: Runs the user-supplied NSFW YOLO weights on the input image and returns the standard object-detection response shape. `max_concurrent_count: 1` serialises GPU-side work. `bounding_box_padding` is exposed so a caller can widen the drawn boxes for visual clarity without re-running detection.

### Box Drawer (`box-drawer`)
- **Type**: `image-drawing` (`rectangle` method)
- **Driver**: `native`
- **Function**: Draws one outlined rectangle onto the running accumulator. Outline color is picked per detection by a conditional on the label suffix.

### Text Drawer (`text-drawer`)
- **Type**: `image-drawing` (`text` method)
- **Driver**: `native`
- **Function**: Draws the label string just above the rectangle. `anchor: ld` (left / descender) puts the text baseline on the rectangle's top edge so the label sits directly above the box. `stroke_width: 2` with a black stroke keeps the text readable against any background.

## Notes and Tuning

- **Cost**: One `analyze-brightness` pass, one `adjust-brightness` pass, one YOLO forward pass per image, plus two `image-drawing` calls per detection. The pre-processing steps are pure NumPy / PIL and effectively free next to the detection.
- **When to change `target_luma`**: The default `130` (mid-tone) matches the training-set exposure band of most YOLO detectors. Raise it (`150`–`180`) if inputs are consistently dark and the detector is missing regions; lower it (`100`–`120`) if inputs are consistently bright and clipping is starting to swallow highlights. Passing `target_luma: 0` skips normalisation entirely — useful for A/B comparison against the raw baseline.
- **When normalisation hurts**: Well-exposed inputs don't benefit from renormalisation and can lose a little skin-tone gradation to PIL's linear clip. If you know your inputs are already in a normal exposure range, pass `target_luma: 0`.
- **Missed detections**: Lower `min_confidence` (e.g. `0.2`) to see borderline detections the default threshold hides. Useful when debugging why a specific region wasn't flagged.
- **Text overlap**: If two detections sit close together vertically, their labels can overlap because both anchor to the box top-left. This is intentional for the "inspect the model" use case — reordering or repositioning labels to avoid collisions would require a second pass over the full detection list and isn't worth the complexity for a debugging tool.
- **Color scheme**: Two conditionals encode the palette (one for the rectangle, one for the text). Change the RGB hex codes inline to remap; add branches (e.g. a separate color for `FACE_*` classes) if the two-tier grouping isn't specific enough.
- **Comparison with `nsfw-mosaic`**: Both examples use the same detector and the same `bounding_box` field. If you're iterating on `min_confidence` / `iou_threshold` / class-label filters for the mosaic workflow, run those settings through this workflow first — it's much faster to visually verify a detection set on a still image than to re-encode a full video and inspect the mosaic result.
- **Spool tempfile**: The fan-out spool writes to the OS temp directory returned by `tempfile.NamedTemporaryFile` (respects `TMPDIR`). Files are deleted after all branches close, so no manual cleanup is needed. If your temp partition is small and inputs are large, point `TMPDIR` at a bigger disk.
