# Pose Detection × Brightness Sweep Example

This example demonstrates a workflow that takes a single input image, normalises it to 5 absolute brightness targets on the 0–255 ITU-R BT.601 luma scale, runs YOLOv8-pose on each variant, and returns the 5 pose-overlay images side-by-side — so you can eyeball which brightness band the detector prefers on your specific input.

> **License note**: This example auto-downloads Ultralytics' YOLOv8-pose weights, which are released under **AGPL-3.0**. Personal use, research, and open-source demos are fine. For commercial use, either comply with AGPL-3.0 (open-sourcing the whole system) or obtain an Ultralytics Enterprise License — see [ultralytics.com/license](https://www.ultralytics.com/license).

## Overview

Given an input image, the workflow returns 5 pose-overlay images — one per target luma band (`50`, `90`, `130`, `170`, `210` by default). Each field is a fully-rendered image (brightened + skeleton overlay), addressable by name (`luma_050` … `luma_210`).

The strategy is:

1. **Spool the upload and fan it out in two stages.** The first `fan-out` job runs in `spool: true` mode — it lands the single-use upload on a tempfile once and hands both branches (`for-measure` and `for-sweep`) their own file-backed image resource. Because those resources are copyable, the second `fan-out` splits its input via cheap `copy(N)` (no second tempfile), producing one independent handle per sweep target. Two stages keep the concerns separated: the analyser drains its branch immediately, and the sweep pipeline can wait on `measure` without stalling the analyser (the spooled file is already fully written by then).
2. **Measure the source luma once** with `image-analyzer` (`analyze-brightness` metric). This returns `mean_brightness` on the 0–255 BT.601 luma scale — the divisor every sweep iteration uses to derive its per-target multiplier.
3. **Fan out** with a top-level `for-each` job over the target-luma list, pairing each target with its own second-stage fan-out branch as `{luma, image}` items. Each iteration runs an inline `pipeline` independently, with `batch_size: 5` letting the CPU-side steps overlap.
4. **Inside each iteration** — compute `factor = target / original` with a tiny Python shell job, apply it via `image-processor adjust-brightness`, run YOLOv8-pose (`return_skeleton_image: true` yields a transparent-background skeleton PNG per pose at source resolution), and alpha-composite every skeleton on top of the brightened image with `image-processor merge`.
5. **Project the results** — the top-level workflow's `output:` block picks each iteration by positional index (`jobs.sweep.output[0]` … `[4]`) and exposes its `pose_overlay_image` as a top-level `luma_NNN` field, so the Web UI renders one image card per band. `for-each` preserves input order, so index `N` always corresponds to the Nth entry in the sweep input list.

### Why absolute luma (not a raw multiplier)

A raw multiplier sweep (`0.5×`, `1.0×`, `2.0×`, …) gives you different absolute brightness bands depending on how bright the input was to begin with — a 2× shift on a dark photo lands nowhere near a 2× shift on a bright one. Targeting absolute luma normalises for the source exposure, so the 5 bands (`50, 90, 130, 170, 210`) are the same 5 bands for every input, and comparing runs across different photos is meaningful.

The trade-off: brightness adjustment still uses PIL's `ImageEnhance.Brightness`, which is a linear multiplier that clips at 0 and 255. So pushing a very dark source up to target 210 may land slightly below 210 once the highlight clip is counted in. Good enough for a "which band does the detector like" experiment; not good enough for photometric normalisation.

### Why measure upfront (not inside each iteration)

The source luma doesn't change across the 5 iterations, so re-analysing the same pixels 5 times would just burn CPU. Measuring in the outer workflow (`measure` job) means it happens once, before the fan-out — and the derived value is passed into each iteration's pipeline as a scalar `original_luma` input.

### Why an inline pipeline (not a sub-workflow)

The per-target work is four sequential steps (factor calc → brighten → detect → overlay). `for-each` can run any inline job as its `do:` body, and a `pipeline` job chains steps with implicit `${output}` → next `${input}` wiring — so the whole four-step sequence lives directly inside the `for-each` without needing a separate workflow definition. The trade-off is scoping: pipeline steps only see the pipeline's own `${input}` and the previous step's `${output}` — outer scopes like the enclosing `${item}` aren't reachable. So the pipeline's top-level `input:` block packs everything the steps need (target luma, source image branch, source luma, thresholds) into one dict up front, and each step's `output:` mapping repackages the running state (factor, brightened image, poses) for the next step.

### Why a Python shell job for the factor calc

model-compose's variable-binding DSL renders values and does type conversion, but it doesn't do arithmetic. Computing `target / original_luma` requires shelling out; a one-line `python3 -c` command with the two values as `argv` is the smallest possible detour. The shell step's stdout is a plain float string, which the pipeline's `output:` mapping coerces via `${output as number}` before handing it to the brighten step.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python dependencies for YOLO pose detection and image analysis:
  ```bash
  pip install ultralytics numpy
  ```
- The YOLOv8n-pose weights are downloaded automatically on first run into model-compose's model cache.

### Setup

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/pose-brightness-sweep
   ```

2. Prepare an image with at least one visible person.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload the image and optionally override `min_confidence` / `max_pose_count`
   - Click "Run Workflow"
   - The response contains 5 image fields (`luma_050` … `luma_210`) — one card per brightness band, showing the brightened image with detected skeletons drawn on top.

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"min_confidence": 0.4, "max_pose_count": 5};type=application/json' \
     -F 'image=@./person.jpg'
   ```

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "image": "./person.jpg",
     "min_confidence": 0.4,
     "max_pose_count": 5
   }'
   ```

## Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `image` | image (file) | Yes | - | Input image to sweep brightness over |
| `min_confidence` | number | No | `0.4` | Minimum pose-detection confidence (0.0 – 1.0). Lower it (e.g. `0.25`) if any person is missed at every brightness level |
| `max_pose_count` | integer | No | `5` | Maximum number of poses returned per image |

## Output Shape

Each target brightness band is projected as its own top-level image field named `luma_NNN` (where `NNN` is the target mean luma on the 0–255 scale, zero-padded). This flat shape makes the Web UI render one image card per band side-by-side.

```json
{
  "luma_050": "<image PNG>",
  "luma_090": "<image PNG>",
  "luma_130": "<image PNG>",
  "luma_170": "<image PNG>",
  "luma_210": "<image PNG>"
}
```

The band where the skeleton lines up most cleanly with the person(s) in the image is the exposure sweet spot for the detector on this input. If you need the underlying pose data (scores, bounding boxes) or the pre-overlay brightened image, promote them from the pipeline output — each iteration returns a full `{target_luma, applied_factor, poses, brightened_image, pose_overlay_image}` record; the top-level workflow's `output:` block currently only projects `pose_overlay_image` to keep the UI clean, but you can add more fields there without touching the pipeline steps.

> **Note**: If you change the target-luma list on the `sweep` job, rename the fields in the workflow's `output:` block to match — the field names are static YAML, not derived from the sweep values at runtime.

## Component Details

### Image Analyser (`image-analyzer`)
- **Type**: `image-analyzer`
- **Driver**: `native`
- **Function**: Runs `analyze-brightness` on the source image. Consumes the `for-measure` branch of the upstream `fan-out` job in parallel with the sweep iterations. Returns `mean_brightness` (arithmetic mean of BT.601 luma, 0–255), plus `min/max/std_brightness` and dimensions. Only `mean_brightness` is used here — as the divisor for the per-target factor.

### Factor Calculator (`factor-calc`)
- **Type**: `shell`
- **Function**: Runs a one-line Python script that prints `target / original` (or `1.0` if the source is all-black). Stdout is consumed by the brighten step via `as number`. This is the only place in the pipeline where arithmetic happens — everything else is pure variable binding.

### Image Processor (`image-processor`)
- **Type**: `image-processor`
- **Driver**: `native`
- **Function**: Exposes two actions. `adjust-brightness` multiplies pixel intensity by `factor` (PIL `ImageEnhance.Brightness`, linear multiplier with 0/255 clipping). `merge` alpha-composites a list of same-size images onto one canvas — used here to stack skeleton PNGs on top of each brightened image.

### Pose Detector (`pose-detector`)
- **Type**: `model` — `pose-detection` task
- **Driver**: `custom`
- **Family**: `yolo` (`yolov8n-pose.pt` weights)
- **Function**: Detects up to `max_pose_count` poses in a single image and, for each one, renders a full-resolution skeleton PNG with a transparent background (`return_skeleton_image: true`). Keypoint arrays are suppressed (`return_keypoints: false`) because the overlay pipeline only needs the pre-rendered skeleton image. `max_concurrent_count: 1` serialises inference so GPU memory stays bounded even though the outer `for-each` fans out 5 iterations at once.

## Notes and Tuning

- **Cost**: One pose-detection pass per target band. With the default 5-band sweep, wall time is roughly 5× a single pose-detection invocation, minus whatever the concurrent CPU work overlaps. Swap to `yolov8s/m/l/x-pose.pt` for higher accuracy at proportionally higher cost.
- **Sweep range**: The default `[50, 90, 130, 170, 210]` covers deep shadow → mid → highlight on the 8-bit luma scale. `128` is the exact midpoint; anything below `~40` is essentially crushed shadows and anything above `~215` blows out highlights. Edit the list on the `sweep` job to focus on a narrower band if the default is too coarse for your use case.
- **Missed poses everywhere**: If every variant looks pose-less, the detector never saw a person to begin with — lower `min_confidence` (e.g. `0.25`) or swap in a larger YOLO weight before assuming brightness is the problem.
- **Base image in overlay**: When zero poses are detected at a given target, `pose_overlay_image` is identical to the brightened image (the merge just returns the base). This is deliberate — it keeps the 5 output cards visually aligned so you can flip through them without gaps.
- **Absolute-luma limits**: The brightness action is a linear multiplier with clipping, so extreme shifts (very dark input → high target, or very bright input → low target) will land off-target. If accurate photometric normalisation matters more than the sweep visualisation, use a gamma-based tone map instead — `image-processor` doesn't currently expose one, so you'd need to add it to the core.
