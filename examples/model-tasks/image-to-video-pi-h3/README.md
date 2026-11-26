# Image-to-Video Model Task Example (pi-H3)

This example animates a still image into a short clip with native stereo audio using **pi-H3**, a 2/4-step distillation of MiniMax-H3 by LakonLab. Provide a first-frame image, optionally a last-frame image for keyframe interpolation (fl2va), and a prompt describing the motion. It is exposed through model-compose's built-in image-to-video task.

## Overview

pi-H3 pairs pi-Flow v2 few-step sampling with DWD (Decoding Without a Decoder) so the final denoising step predicts pixels directly and the video VAE drops out of the pipeline. For image-to-video the driver pins the pipeline workflow to `fl2va`, which fetches only the keyframe transformer partition and accepts both:

- `image` — first-frame condition (required)
- `last_image` — closing keyframe (optional); when set, the model interpolates smoothly between the two frames

The rest is the same as the text-to-video example: pruned base + LakonLab adapter + optional FP8, `num_inference_steps` pinned to `step_count`, `num_frames` snapped to the nearest `17*n + 5`.

## Preparation

### Prerequisites

- `model-compose` on PATH
- A CUDA-capable GPU. Consumer-class (24 GB) should keep `cpu_offload: true` (already set); Blackwell-class (B200 / H200) can turn it off and enable `quantization: {type: fp8}`.
- ~45 GB free disk for the pruned base checkpoint plus ~1 GB for the pi-H3 adapter.
- A Python environment where `torch`, `diffusers==0.40.0`, `peft==0.20.0`, `transformers (>= 4.45)`, `mmcv==1.6.1`, and `av` can be installed. The driver installs these into `.venv/pi-h3` on first run; LakonLab itself (`v0.3.0`) is pulled from GitHub because it is not published on PyPI.
- A C/C++ toolchain (`build-essential` on Debian/Ubuntu, Xcode CLT on macOS) so `mmcv==1.6.1` can build its CUDA/C++ extensions. mmcv 1.x predates PEP 517, so the driver installs it with `--no-build-isolation` to reuse the venv's torch at build time.

### Model Access

- **Base model**: `multimodalart/MiniMax-H3-Pruned` on Hugging Face. Governed by the MiniMax H3 Community License — accept the license and run `hf auth login` (or export `HF_TOKEN`) before starting the service.
- **Distillation adapter**: `Lakonik/pi-H3` on Hugging Face. Distributed as "Model Derivatives of MiniMax H3" under the same community license. Pin a revision or point at a local snapshot via the `distillation` field.

## Adapter Variants

Same adapter matrix as the text-to-video example — the driver auto-picks the subfolder from `step_count` and `dwd`:

| `step_count` | `dwd`   | Loaded subfolder            | Output path                    |
| :----------- | :------ | :-------------------------- | :----------------------------- |
| `2`          | `true`  | `pi_h3_2step_dwd_adapter`   | Direct pixels on the last step |
| `4`          | `true`  | `pi_h3_4step_dwd_adapter`   | Direct pixels on the last step |
| `2`          | `false` | `pi_h3_2step_adapter`       | Standard video VAE decode      |
| `4`          | `false` | `pi_h3_4step_adapter`       | Standard video VAE decode      |

The 4-step DWD variant is the recommended default.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup downloads the pruned base (~45 GB) plus the pi-H3 adapter. Subsequent runs reuse the cached shards.

2. **Run the workflow — first-frame only:**
   ```bash
   # Animate a still with the prompt driving motion.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"image": "https://example.com/first.jpg", "prompt": "camera slowly dollies in, leaves rustle in the wind"}}'
   ```

3. **Run the workflow — first + last frame (keyframe interpolation):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"image": "https://example.com/first.jpg", "last_image": "https://example.com/last.jpg", "prompt": "smooth transition, locked-off camera"}}'
   ```

4. **Open the Web UI:**
   `http://localhost:8081` opens a Gradio form that drives the same workflow.

## Tuning Notes

- **There is no `guidance_scale` or `negative_prompt`.** pi-H3 is few-step distilled with no CFG.
- **Do not layer a user LoRA under `peft_adapter`.** The distilled adapter owns the LoRA slot; the schema rejects the field.
- **`width`/`height` default to the input image dimensions** when unset in the action. Set them to upscale/downscale without re-authoring the image.
- **`quantization: {type: fp8}` requires Blackwell-class hardware** (B200 / H200). Leave `quantization` unset otherwise.
- **`num_frames` is snapped upward** to the nearest `17*n + 5` the video VAE can decode (124–345).

## Shutdown

```bash
model-compose down
```
