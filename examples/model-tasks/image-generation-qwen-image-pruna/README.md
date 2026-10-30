# Image-Generation Model Task Example (Qwen-Image 2.1 + Pruna LoRA)

This example demonstrates how to accelerate Alibaba's Qwen-Image-2.1 with [PrunaAI's distilled LoRA](https://huggingface.co/PrunaAI/P-Q-Image-2.1), running text-to-image generation in as few as 5, 6, or 8 denoising steps instead of the base pipeline's 40.

## Overview

This workflow attaches a PEFT LoRA adapter to the base Qwen-Image-2.1 pipeline and runs it at a reduced step count:

1. **Base Qwen-Image 2.1 Pipeline**: The same local pipeline as the [image-generation-qwen-image](../image-generation-qwen-image) example — 7B diffusion transformer, Qwen3-VL text encoder, multilingual prompts.
2. **Pruna Distilled LoRA**: A published LoRA adapter that Pruna distilled from the base model, letting the pipeline converge in far fewer steps.
3. **Declarative Adapter Composition**: The adapter is attached via the standard `peft_adapter` field on the model component — no code, just YAML.
4. **Isolated Runtime**: Same virtualenv strategy as the base Qwen-Image example, keeping the unreleased `diffusers` build (which ships `QwenImage21Pipeline`) out of the controller's environment.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU. The example uses `cpu_offload: model` to fit the pipeline on a single 24 GB card; remove or downgrade the offload if you have more VRAM.
- A Python environment where `torch`, `diffusers` (main), `transformers>=5.17`, and `peft` can be installed — the first run installs them automatically into an isolated virtualenv.
- A HuggingFace access token accepted for `Qwen/Qwen-Image-2.1`. Set it via the `HF_TOKEN` environment variable before starting model-compose.

### About the Adapter

`PrunaAI/P-Q-Image-2.1` ships four `.safetensors` variants in the same repository:

| Variant                                               | Denoising Steps | Notes                                                                              |
|-------------------------------------------------------|-----------------|------------------------------------------------------------------------------------|
| `p_q_image_2.1_8_steps_v0.1.safetensors`              | 8               | Default in this example. Best quality/speed among v0.1.                            |
| `p_q_image_2.1_5_steps_v0.1.safetensors`              | 5               | Maximum speed for v0.1; more visible quality drop.                                 |
| `p_q_image_2.1_6_steps_v0.2.safetensors`              | 6               | Advanced v0.2 distillation. Best for editing where preserving the input matters.   |
| `p_q_image_2.1_6_steps_upsampled_v0.2.safetensors`    | 6               | v0.2 with prompt upsampling baked in — short prompts, no separate enhancer call.   |

Switch variants by editing four fields together:

- `peft_adapter[0].model.filename`
- `action.params.inference_steps`
- `action.params.sigmas` (the LoRA is trained against a specific sigma schedule per variant)
- `scheduler.options` (v0.1 and v0.2 require different scheduler behavior — see below)

**v0.1 (5-step / 8-step)** uses its sigmas verbatim with no extra shifting:

```yaml
scheduler:
  options:
    use_dynamic_shifting: false
    shift: 1.0
    shift_terminal: null
```

Sigmas:
- 8-step: `[1.0, 0.933333333, 0.857142857, 0.769230769, 0.666666667, 0.545454545, 0.4, 0.222222222]`
- 5-step: `[1.0, 0.94, 0.857142857, 0.666666667, 0.4]`

**v0.2 (6-step / 6-step upsampled)** keeps the resolution-dependent shift and only disables the terminal stretch:

```yaml
scheduler:
  options:
    use_dynamic_shifting: true
    shift_terminal: null
```

Sigmas (both v0.2 variants): `[1.0, 0.925, 0.85, 0.625, 0.375, 0.125]`

Without the matching `scheduler.options`, the pipeline's default `FlowMatchEulerDiscreteScheduler` would re-shift and stretch the custom sigmas (its config has `use_dynamic_shifting: true` and `shift_terminal: 0.02`), producing a schedule the LoRA was not trained for.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-generation-qwen-image-pruna
   ```

2. Accept the Qwen Research License at https://huggingface.co/Qwen/Qwen-Image-2.1, then create `.env` from the sample and paste in an access token that has access to it:
   ```bash
   cp .env.sample .env
   # edit .env and set HF_TOKEN=hf_xxx
   ```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup creates `.venv/qwen-image-pruna`, installs `diffusers` from GitHub main plus `peft`, downloads ~20 GB of base weights and the LoRA file, and loads the pipeline into VRAM.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — 8-step text-to-image at the default 1024×1024
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A neon shop sign that reads \"QWEN IMAGE 2.1\", rainy night, reflections on wet pavement"}}' \
     -o output.png

   # Reproducible sampling with a fixed seed
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A snow leopard resting on a moss-covered rock, cinematic light", "seed": 42}}' \
     -o output.png

   # Image-conditioned generation — pass one or more input images for instruction-based editing
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/input.png" \
     -F 'input={"prompt": "Same subject in a snowy forest at dusk, cinematic light", "image": "@ref"}' \
     -o output.png
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter a `prompt` describing the image you want
   - Optionally set `seed` for reproducibility or a non-square `width`/`height`
   - Click "Run Workflow" to receive a `.png` file back

## Configuration Reference

### PEFT Adapter Fields

| Field                       | Description                                                                            | Default |
|-----------------------------|----------------------------------------------------------------------------------------|---------|
| `type`                      | Adapter type. Diffusion pipelines currently accept `lora` only.                        | —       |
| `name`                      | Identifier used when composing multiple adapters (`set_adapters([...])`).              | (none)  |
| `model.repository`          | HuggingFace repo hosting the adapter weights.                                          | —       |
| `model.filename`            | File within the repo to load. Required when the repo bundles multiple variants.        | (none)  |
| `weight`                    | Adapter strength applied when the LoRA is active.                                      | `1.0`   |

### Action Fields

Same as the base [image-generation-qwen-image](../image-generation-qwen-image) example. Two knobs to tune for this variant:

| Field                    | Description                                                                             | Default |
|--------------------------|-----------------------------------------------------------------------------------------|---------|
| `params.inference_steps` | Match the LoRA variant: `8`, `5`, or `6` for the respective files.                      | `8`     |
| `params.true_cfg_scale`  | Pruna's distillation targets `1.0`. Raising it defeats the acceleration.                | `1.0`   |

## Notes

- **v0.2 vs v0.1**: v0.2's 6-step adapter is Pruna's advanced distillation and is recommended as a drop-in replacement for the base model; v0.1 (5/8-step) remains available for backwards compatibility. The two generations use different sigma schedules and different scheduler settings — do not mix them.
- **`true_cfg_scale` is pinned**: The distilled adapter was trained without classifier-free guidance. Raising `true_cfg_scale` above `1.0` will cost you the extra forward pass without a corresponding quality gain; `negative_prompt` is accepted for symmetry with the base example but has no effect at this scale.
- **VRAM planning**: Attaching a LoRA does not materially change VRAM footprint versus the base pipeline. See the VRAM notes in the base example if you need to trade speed for lower peak memory.
- **Switching variants**: Editing `filename` alone is not enough — `filename`, `inference_steps`, `sigmas`, and `scheduler.options` must be kept consistent. The pipeline will happily run an 8-step LoRA at 5 steps, but the output will be visibly under-denoised.
- **License**: Both `Qwen/Qwen-Image-2.1` and the Pruna LoRA are subject to their respective HuggingFace licenses. Review the terms on each repository before production use.
