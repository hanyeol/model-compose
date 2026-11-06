# Text-to-Video Model Task Example (MiniMax-H3 + LightX2V Turbo LoRA)

This example is the same workflow as text-to-video-minimax-h3, but drops the LightX2V/ModelTC Turbo LoRA on top of the base MiniMax-H3 Omni-Transformer so generation finishes in a fraction of the steps. It is exposed through model-compose's built-in text-to-video task.

## Overview

MiniMax-H3 does not ship a few-step checkpoint and its released weights are already CFG-distilled, so `guidance_scale` has no real effect. The LightX2V Turbo LoRAs are the step-distilled option most of the community uses — they cut generation from the default 50 scheduler steps down to 4 or 8 model evaluations without retraining the base. This example wires that up declaratively:

1. **Base Pipeline Reused**: Loads the same `MiniMaxH3ModularPipeline` as the vanilla example; only the LoRA and the step/shift settings differ.
2. **Turbo LoRA Attached**: The example declares the LoRA under `peft_adapter`. The driver downloads it from Hugging Face and attaches it on top of the base transformer at load time — no conversion step needed.
3. **Scheduler Shift Matched to the LoRA**: The 768p Turbo files were trained at **video shift 6**, not the scheduler default 12. The example sets `video_shift: 6` so the schedule lands on the sigmas the LoRA expects.

## Preparation

### Prerequisites

Same as the base MiniMax-H3 example: model-compose on PATH, a CUDA-capable GPU (consumer-class needs `cpu_offload: true`, already set), ~70 GB free disk for the base checkpoint plus a few hundred MB for the LoRA, and a Python environment where `torch`, `diffusers (>= 0.36)`, `transformers (>= 4.45)`, and `av` can be installed.

### Model Access

- **Base model**: `MiniMaxAI/MiniMax-H3` on Hugging Face is gated by the MiniMax H3 Community License. Accept the license and run `hf auth login` (or export `HF_TOKEN`) before starting the service.
- **Turbo LoRA**: `lightx2v/Minimax-h3-Turbo` on Hugging Face. The repository ships several variants in one place — see the table below.

## LoRA Variants

The upstream repository bundles five LoRA files. Pairing the file with the right `video_shift` and `inference_steps` matters: a 768p file paired with the default scheduler shift runs off-schedule and visibly degrades motion. From the [ModelTC/Minimax-H3-Turbo model specs](https://github.com/ModelTC/Minimax-H3-Turbo#1-model-specs):

| Filename                                                | Tasks      | Training video_shift | NFE | `inference_steps` |
| ------------------------------------------------------- | ---------- | -------------------: | --: | ----------------: |
| `minimax_h3_fl2v_turbo_4step_v0.1.safetensors`          | T2VA/FL2VA |                   12 |   4 |                 5 |
| `minimax_h3_fl2v_turbo_8step_v1.0_bf16.safetensors`     | T2VA/FL2VA |                   12 |   8 |                 9 |
| `minimax_h3_fl2v_turbo_4step_v1.0_768p_bf16.safetensors`| T2VA/FL2VA |                    6 |   4 |                 5 |
| `minimax_h3_fl2v_turbo_8step_v1.0_768p_bf16.safetensors`| T2VA/FL2VA |                    6 |   8 |                 9 |
| `minimax_h3_ref2v_turbo_4step_v0.1_bf16.safetensors`    | Ref2VA     |                   12 |   4 |                 5 |

Notes:

- The example picks the **8-step 768p** file (`minimax_h3_fl2v_turbo_8step_v1.0_768p_bf16.safetensors`) as a balanced default. To switch, change `peft_adapter[0].model.filename`, `inference_steps`, and `video_shift` together — each row above is a package.
- **`inference_steps` is NFE + 1**, because the MiniMax-H3 scheduler counts sigma grid points including the terminal 0. Passing an "8-step" file as `inference_steps: 8` gives you 7 evaluations, not 8.
- `audio_shift: 3` matches every row above — the audio scheduler is trained at shift 3 across all Turbo variants.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup downloads the base checkpoint (~70 GB) plus the LoRA (a few hundred MB). Subsequent runs reuse the cached shards.

2. **Run the workflow:**
   ```bash
   # Minimal call — the Turbo LoRA + shift are already wired into the example.
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

- **Do not raise `guidance_scale` above 1.0.** The MiniMax-H3 weights are CFG-distilled; a higher value does not improve prompt adherence and breaks the single-forward schedule the Turbo LoRA expects.
- **Match `inference_steps` to the file.** 4-step files want `inference_steps: 5`, 8-step files want `inference_steps: 9`. More steps do not improve quality past the trained budget — the LoRA was distilled for a fixed NFE.
- **Leave `video_shift` / `audio_shift` unset to keep the scheduler defaults** (12 / 3). Omit the keys (or set them to `null`) when running the base model without the Turbo LoRA; the defaults are for the undistilled 50-step recipe.

## Shutdown

```bash
model-compose down
```
