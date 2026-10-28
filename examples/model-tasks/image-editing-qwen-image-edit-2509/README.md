# Image-Editing Model Task Example (Qwen-Image-Edit-2509)

This example demonstrates how to edit one or more reference images with a natural-language instruction using Alibaba's Qwen-Image-Edit-2509, exposed through model-compose's built-in image-generation task.

## Overview

This workflow provides local instruction-based image editing that:

1. **Local Qwen-Image-Edit-2509 Pipeline**: Runs the 20B diffusion transformer end-to-end — no external API.
2. **Qwen2.5-VL Text Encoder**: The pipeline uses Qwen2.5-VL as its vision-language conditioner, enabling instructions that reference image content directly ("make the jacket red", "put the subject in a snowy forest").
3. **Multi-Reference Editing**: Pass a single reference image or a list of up to three; the model fuses them for identity-preserving edits, product composition, or pose transfer.
4. **True-CFG Guidance**: `true_cfg_scale` defaults to `4.0` so `negative_prompt` actively steers sampling. Lower it to `1.0` to skip the extra forward pass and halve inference time at the cost of negative-prompt guidance.
5. **Automatic Model Management**: Weights are downloaded from HuggingFace Hub on first run and cached locally.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU. This example ships with `cpu_offload: model`, which fits Qwen-Image-Edit-2509 into a single **24 GB** GPU at 1024×1024 in bfloat16. Switch to `cpu_offload: sequential` for layer-level offload on smaller cards, or drop the option on 48 GB+ cards for peak speed.
- A Python environment where `torch`, `diffusers>=0.41.0`, and `transformers>=4.51.3` can be installed — the first run installs them automatically into an isolated virtualenv.
- A HuggingFace access token accepted for `Qwen/Qwen-Image-Edit-2509`. Set it via the `HF_TOKEN` environment variable before starting model-compose.

### Why an Isolated Runtime

`QwenImageEditPlusPipeline` is available on `diffusers >= 0.41.0`, but the controller's shared environment may still be pinned to an older release used by other components. The model worker runs in a dedicated `virtualenv` (`.venv/qwen-image-edit`) so this component's `diffusers` upgrade does not shadow the controller's own install or clash with other diffusion components in the same compose file.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-editing-qwen-image-edit-2509
   ```

2. Accept the Qwen Research License at https://huggingface.co/Qwen/Qwen-Image-Edit-2509, then set `HF_TOKEN` in your shell or a `.env` file next to this README:
   ```bash
   export HF_TOKEN=hf_xxx
   ```

3. To reduce peak VRAM, lower `width` / `height` (e.g. 768×768) or drop `inference_steps` from the default 40.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup creates `.venv/qwen-image-edit`, installs `diffusers` and `transformers`, downloads ~40 GB of weights, and loads the pipeline into VRAM. Expect 10-20 minutes before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Single-reference edit — attach one image and describe the edit
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/subject.png" \
     -F 'input={"prompt": "Place the subject in a snowy pine forest at dusk, cinematic light", "image": "@ref"}' \
     -o output.png

   # Reproducible edit with a fixed seed and negative prompt
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/subject.png" \
     -F 'input={"prompt": "Change the jacket to a red leather bomber", "negative_prompt": "blurry, extra limbs, watermark", "image": "@ref", "seed": 42}' \
     -o output.png

   # Multi-reference edit — compose two images with one instruction
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "a=@/path/to/person.png" \
     -F "b=@/path/to/outfit.png" \
     -F 'input={"prompt": "Dress the person from the first image in the outfit from the second", "image": ["@a", "@b"]}' \
     -o output.png
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload one or more reference images into `image`
   - Enter a `prompt` describing the edit
   - Optionally set `seed`, `negative_prompt`, or a non-square `width`/`height`
   - Click "Run Workflow" to receive a `.png` file back

## Configuration Reference

### Component Fields

| Field           | Description                                                       | Default |
|-----------------|-------------------------------------------------------------------|---------|
| `task`          | Must be `image-generation`.                                       | —       |
| `driver`        | Must be `huggingface`.                                            | —       |
| `architecture`  | Must be `qwen-image-edit`.                                        | —       |
| `model`         | Qwen-Image-Edit repository (`Qwen/Qwen-Image-Edit-2509` or a local path). | — |
| `device`        | Compute device. `cuda` is strongly recommended.                   | `auto`  |
| `cpu_offload`   | VRAM-reduction strategy. `model` fits a single 24 GB GPU.         | (none)  |

### Action Fields

| Field                         | Description                                                                             | Default |
|-------------------------------|-----------------------------------------------------------------------------------------|---------|
| `prompt`                      | Natural-language editing instruction (or list/stream of instructions).                  | —       |
| `negative_prompt`             | Text describing what to avoid. Only takes effect when `true_cfg_scale > 1.0`.           | (none)  |
| `image`                       | **Required.** One reference image or a list of up to three.                             | —       |
| `width`                       | Output image width in pixels.                                                           | `1024`  |
| `height`                      | Output image height in pixels.                                                          | `1024`  |
| `num_return_images`           | Number of images returned per prompt.                                                   | `1`     |
| `seed`                        | Random seed for reproducibility. Leave unset for a fresh sample per call.               | (none)  |
| `batch_size`                  | Number of prompts processed per batch when the input is a list or stream.               | `1`     |
| `params.inference_steps`      | Number of denoising steps.                                                              | `40`    |
| `params.true_cfg_scale`       | True classifier-free guidance scale. Values above 1.0 enable negative-prompt guidance.  | `4.0`   |
| `params.max_sequence_length`  | Maximum token length for the Qwen2.5-VL text encoder.                                   | `512`   |

## Notes

- **First run is slow**: The controller creates the `.venv/qwen-image-edit` environment, installs `diffusers` and `transformers`, and downloads ~40 GB of weights on first startup. Subsequent runs reuse the cached venv and weights.
- **Qwen Research License**: `Qwen/Qwen-Image-Edit-2509` is released under the Qwen Research License Agreement (non-commercial). Review the terms at https://huggingface.co/Qwen/Qwen-Image-Edit-2509 before production use.
- **VRAM planning**: The 20B transformer plus the Qwen2.5-VL text encoder (~7B) exceeds 24 GB when both are resident. This example uses `cpu_offload: model` (whole-pipeline module-level offload) to keep peak VRAM under 24 GB at 1024×1024. For lower peak VRAM at some latency cost, switch to `cpu_offload: sequential` (layer-level offload, ~90% VRAM cut but 2–5× slower). Adding a `quantization` config further reduces weights — the driver marks `transformer` and `text_encoder` as quantizable so 4-bit or 8-bit saves the most.
- **`true_cfg_scale` vs speed**: With `true_cfg_scale > 1.0` the pipeline runs an extra forward pass per step for the negative prompt, roughly doubling inference time. The default is `4.0` because Edit-2509 is tuned for negative-prompt guidance; lower it to `1.0` only when you don't need `negative_prompt`.
- **Multi-reference inputs**: Pass `image` as a JSON array for identity-preserving composition, product placement, or outfit transfer. Edit-2509 is validated for 1-3 reference images; longer lists are allowed but quality degrades.
- **Multilingual instructions**: Qwen2.5-VL handles Chinese, Korean, Japanese, and English prompts natively; mixed-language prompts also work.
- **Output**: The result is a single `.png` per input (or a list for batched inputs), decoded from the diffusion VAE.
