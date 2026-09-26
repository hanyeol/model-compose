# Image-Generation Model Task Example (Qwen-Image 2.1 + Pruna LoRA)

This example demonstrates how to accelerate Alibaba's Qwen-Image-2.1 with [PrunaAI's distilled LoRA](https://huggingface.co/PrunaAI/Pruna-Qwen-Image-2.1), running text-to-image generation in as few as 5 or 8 denoising steps instead of the base pipeline's 40.

## Overview

This workflow attaches a PEFT LoRA adapter to the base Qwen-Image-2.1 pipeline and runs it at a reduced step count:

1. **Base Qwen-Image 2.1 Pipeline**: The same local pipeline as the [image-generation-qwen-image](../image-generation-qwen-image) example — 7B diffusion transformer, Qwen3-VL text encoder, multilingual prompts.
2. **Pruna Distilled LoRA**: A published LoRA adapter that Pruna distilled from the base model, letting the pipeline converge in far fewer steps.
3. **Declarative Adapter Composition**: The adapter is attached via the standard `peft_adapters` field on the model component — no code, just YAML.
4. **Isolated Runtime**: Same virtualenv strategy as the base Qwen-Image example, keeping the unreleased `diffusers` build (which ships `QwenImage21Pipeline`) out of the controller's environment.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU. The example uses `cpu_offload: model` to fit the pipeline on a single 24 GB card; remove or downgrade the offload if you have more VRAM.
- A Python environment where `torch`, `diffusers` (main), `transformers>=5.17`, and `peft` can be installed — the first run installs them automatically into an isolated virtualenv.
- A HuggingFace access token accepted for `Qwen/Qwen-Image-2.1`. Set it via the `HF_TOKEN` environment variable before starting model-compose.

### About the Adapter

`PrunaAI/Pruna-Qwen-Image-2.1` ships two `.safetensors` variants in the same repository:

| Variant                                         | Denoising Steps | Notes                                       |
|-------------------------------------------------|-----------------|---------------------------------------------|
| `p_qwen_image_2.1_8step_v0.1.safetensors`       | 8               | Default in this example. Best quality/speed. |
| `p_qwen_image_2.1_5step_v0.1.safetensors`       | 5               | Maximum speed; more visible quality drop.    |

Switch variants by editing three fields together:

- `peft_adapters[0].model.filename`
- `action.params.inference_steps`
- `action.params.sigmas` (the LoRA is trained against a specific sigma schedule per variant)

For the 5-step variant, use `sigmas: [1.0, 0.94, 0.857142857, 0.666666667, 0.4]` and `inference_steps: 5`.

The Pruna model card notes that v0.1 quality does not yet match the base model at 40 steps — treat this as a speed/quality trade-off rather than a drop-in replacement.

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
| `params.inference_steps` | Match the LoRA variant: `8` for the 8-step file, `5` for the 5-step file.               | `8`     |
| `params.true_cfg_scale`  | Pruna's distillation targets `1.0`. Raising it defeats the acceleration.                | `1.0`   |

## Notes

- **Work-in-progress adapter**: Pruna's model card explicitly labels v0.1 a work in progress — quality does not yet match the base pipeline at 40 steps. Use this example when latency matters more than peak fidelity.
- **`true_cfg_scale` is pinned**: The distilled adapter was trained without classifier-free guidance. Raising `true_cfg_scale` above `1.0` will cost you the extra forward pass without a corresponding quality gain; `negative_prompt` is accepted for symmetry with the base example but has no effect at this scale.
- **VRAM planning**: Attaching a LoRA does not materially change VRAM footprint versus the base pipeline. See the VRAM notes in the base example if you need to trade speed for lower peak memory.
- **Switching step count**: Editing `filename` alone is not enough — the two fields (`filename`, `inference_steps`) must be changed together. The pipeline will happily run an 8-step LoRA at 5 steps, but the output will be visibly under-denoised.
- **License**: Both `Qwen/Qwen-Image-2.1` and the Pruna LoRA are subject to their respective HuggingFace licenses. Review the terms on each repository before production use.
