# Text-to-Video Model Task Example (pi-H3)

This example runs **pi-H3**, a 2/4-step distillation of MiniMax-H3 by LakonLab that pairs pi-Flow v2 few-step sampling with DWD (Decoding Without a Decoder) to skip the video VAE on the final step. It is exposed through model-compose's built-in text-to-video task.

## Overview

MiniMax-H3's released weights are already CFG-distilled, so the community route to fewer steps is a distillation adapter. Where the LightX2V Turbo LoRA variant trims the base from 50 to 4–8 steps, pi-H3 goes further:

1. **2 or 4 scheduler steps** (bake the step count into the adapter).
2. **DWD**: the final denoising step predicts pixels directly, so the video VAE decoder drops out of the pipeline.
3. **Pruned base**: runs on `multimodalart/MiniMax-H3-Pruned` instead of the full 70 GB release.

The driver loads the pruned base through diffusers' `ModularPipeline`, then calls LakonLab's adapter loader to splice in the DWD head and distilled weights. Inference uses the standard pipeline call with `num_inference_steps` pinned to `step_count`.

## Preparation

### Prerequisites

- `model-compose` on PATH
- A CUDA-capable GPU. Consumer-class (24 GB) should keep `cpu_offload: true` (already set); Blackwell-class (B200 / H200) can turn it off and enable `quantization: {type: fp8}`.
- ~45 GB free disk for the pruned base checkpoint plus ~1 GB for the pi-H3 adapter.
- A Python environment where `torch`, `diffusers (>= 0.36)`, `transformers (>= 4.45)`, `lakonlab (>= 0.3)`, and `av` can be installed. The driver lists these in its setup requirements, so model-compose installs them into `.venv/pi-h3` on first run.

### Model Access

- **Base model**: `multimodalart/MiniMax-H3-Pruned` on Hugging Face. Governed by the MiniMax H3 Community License — accept the license and run `hf auth login` (or export `HF_TOKEN`) before starting the service.
- **Distillation adapter**: `Lakonik/pi-H3` on Hugging Face. Distributed as "Model Derivatives of MiniMax H3" under the same community license. Pin a revision or point at a local snapshot via the `distillation` field.

## Adapter Variants

The driver auto-picks the subfolder from `step_count` and `dwd`:

| `step_count` | `dwd`   | Loaded subfolder            | Output path                    |
| :----------- | :------ | :-------------------------- | :----------------------------- |
| `2`          | `true`  | `pi_h3_2step_dwd_adapter`   | Direct pixels on the last step |
| `4`          | `true`  | `pi_h3_4step_dwd_adapter`   | Direct pixels on the last step |
| `2`          | `false` | `pi_h3_2step_adapter`       | Standard video VAE decode      |
| `4`          | `false` | `pi_h3_4step_adapter`       | Standard video VAE decode      |

The 4-step DWD variant is the recommended default — it is the closest match to the 50-step base in motion and texture fidelity while still finishing a 5-second clip in a few seconds on a B200.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup downloads the pruned base (~45 GB) plus the pi-H3 adapter. Subsequent runs reuse the cached shards.

2. **Run the workflow:**
   ```bash
   # Minimal call — step_count, DWD, and scheduler shift are already wired.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "a quiet alleyway at dusk, warm neon reflections on wet pavement, slow dolly in"}}'

   # Pin the seed and request a longer clip.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "waves crashing on a rocky coast, overcast sky, slow-motion spray", "num_frames": 192, "seed": 42}}'
   ```

3. **Open the Web UI:**
   `http://localhost:8081` opens a Gradio form that drives the same workflow.

## Tuning Notes

- **There is no `guidance_scale` or `negative_prompt`.** pi-H3 is a few-step distilled adapter; it runs a single forward per step with no classifier-free guidance. The schema omits both fields on purpose.
- **Do not layer a user LoRA under `peft_adapter`.** The distilled adapter owns the LoRA slot; stacking another one changes the few-step trajectory it was tuned for. The schema rejects the field.
- **`quantization: {type: fp8}` requires Blackwell-class hardware** (B200 / H200). On SM89 and below the LakonLab FP8 kernels either fall back to slow paths or fail to load — leave `quantization` unset unless you've validated the host.
- **Leave `video_shift` / `audio_shift` unset to keep the scheduler defaults** (12 / 3). The DWD adapter is tuned for those; override only when matching a specific recipe published by LakonLab.
- **`num_frames` is snapped upward** to the nearest `17*n + 5` the video VAE can decode (124–345). Requests below 124 round up; requests above 345 error out.

## Shutdown

```bash
model-compose down
```
