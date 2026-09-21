# Image-Generation Model Task Example (Qwen-Image 2.1)

This example demonstrates how to generate a high-fidelity image from a text prompt using Alibaba's Qwen-Image-2.1, exposed through model-compose's built-in image-generation task.

## Overview

This workflow provides local text-to-image generation that:

1. **Local Qwen-Image 2.1 Pipeline**: Runs the 7B diffusion transformer end-to-end — no external API.
2. **Qwen3-VL Text Encoder**: The pipeline uses Qwen3-VL as its text conditioner, giving the model strong multilingual prompt handling (Chinese, Korean, and English prompts are all first-class).
3. **True-CFG Guidance**: Optional `true_cfg_scale > 1.0` runs classifier-free guidance with a `negative_prompt`; leave at `1.0` to skip the extra forward pass and halve inference time.
4. **Wide Aspect Support**: 1:1 (2048×2048), 4:3, 3:2, 16:9 and their vertical counterparts are all supported natively.
5. **Automatic Model Management**: Weights are downloaded from HuggingFace Hub on first run and cached locally.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU. Qwen-Image-2.1 loads in bfloat16 and needs roughly **24 GB** of VRAM without offloading at 2048×2048; smaller resolutions or CPU offload reduce this.
- A Python environment where `torch`, `diffusers` (main), and `transformers>=5.17` can be installed — the first run installs them automatically into an isolated virtualenv.
- A HuggingFace access token accepted for `Qwen/Qwen-Image-2.1`. Set it via the `HF_TOKEN` environment variable before starting model-compose.

### Why an Isolated Runtime

`QwenImage21Pipeline` was merged into `diffusers` main but is **not yet in any tagged release** (as of 2026-09; latest is v0.40.0). The image-generation driver appends `diffusers @ git+https://github.com/huggingface/diffusers.git` to this component's setup requirements, so the model worker runs in a dedicated `virtualenv` (`.venv/qwen-image`) to keep that unreleased build from shadowing the controller's own `diffusers` install or clashing with other diffusion components in the same compose file.

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/image-generation-qwen-image
   ```

2. Accept the Qwen Research License at https://huggingface.co/Qwen/Qwen-Image-2.1, then create `.env` from the sample and paste in a HuggingFace access token that has access to it:
   ```bash
   cp .env.sample .env
   # edit .env and set HF_TOKEN=hf_xxx
   ```

3. To reduce peak VRAM, drop `width` / `height` (e.g. 1536×1536 or 1024×1024) or lower `inference_steps` from the default 40.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup creates `.venv/qwen-image`, installs `diffusers` from GitHub main, downloads ~20 GB of weights, and loads the pipeline into VRAM. Expect several minutes before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal call — text-to-image at the default 2048×2048
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A neon shop sign that reads \"QWEN IMAGE 2.1\", rainy night, reflections on wet pavement"}}' \
     -o output.png

   # Reproducible sampling with a fixed seed
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A snow leopard resting on a moss-covered rock, cinematic light", "seed": 42}}' \
     -o output.png

   # Widescreen render with negative prompt and true-CFG
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A vast desert canyon at sunset, ultra-detailed", "negative_prompt": "blurry, low quality, watermark", "true_cfg_scale": 4.0, "width": 2752, "height": 1536}}' \
     -o output.png
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter a `prompt` describing the image you want
   - Optionally set `seed` for reproducibility, `negative_prompt` + `true_cfg_scale > 1.0` for guided sampling, or a non-square `width`/`height`
   - Click "Run Workflow" to receive a `.png` file back

## Configuration Reference

### Component Fields

| Field           | Description                                                       | Default |
|-----------------|-------------------------------------------------------------------|---------|
| `task`          | Must be `image-generation`.                                       | —       |
| `driver`        | Must be `huggingface`.                                            | —       |
| `architecture`  | Must be `qwen-image`.                                             | —       |
| `model`         | Qwen-Image repository (`Qwen/Qwen-Image-2.1` or a local path).    | —       |
| `device`        | Compute device. `cuda` is strongly recommended.                   | `auto`  |

### Action Fields

| Field                    | Description                                                                             | Default |
|--------------------------|-----------------------------------------------------------------------------------------|---------|
| `prompt`                 | Text prompt (or list/stream of prompts).                                                | —       |
| `negative_prompt`        | Text describing what to avoid. Only takes effect when `true_cfg_scale > 1.0`.           | (none)  |
| `width`                  | Output image width in pixels.                                                           | `1024`  |
| `height`                 | Output image height in pixels.                                                          | `1024`  |
| `num_return_images`      | Number of images returned per prompt.                                                   | `1`     |
| `seed`                   | Random seed for reproducibility. Leave unset for a fresh sample per call.               | (none)  |
| `batch_size`             | Number of prompts processed per batch when the input is a list or stream.               | `1`     |
| `params.inference_steps` | Number of denoising steps.                                                              | `40`    |
| `params.true_cfg_scale`  | True classifier-free guidance scale. `1.0` disables negative-prompt guidance.           | `1.0`   |

## Notes

- **First run is slow**: The controller creates the `.venv/qwen-image` environment, installs `diffusers` from GitHub main, and downloads ~20 GB of weights on first startup. Expect 10-15 minutes before the controller reports ready. Subsequent runs reuse the cached venv and weights.
- **Diffusers pinned to main**: Qwen-Image-2.1 relies on classes (`QwenImage21Pipeline`, `QwenImage21Transformer2DModel`, `AutoencoderKLQwenImage21`) that live on `diffusers` main. When the next tagged release includes them, this example's setup can pin `diffusers>=<release>` instead of the git URL — no compose change is required if you update model-compose.
- **Qwen Research License**: `Qwen/Qwen-Image-2.1` is released under the Qwen Research License Agreement (non-commercial). Review the terms at https://huggingface.co/Qwen/Qwen-Image-2.1 before production use.
- **VRAM planning**: The 7B transformer plus the Qwen3-VL text encoder push peak VRAM to ~24 GB at 2048×2048 in bfloat16. Drop resolution or add a `quantization` config to the component to fit on 16 GB cards; the driver marks `transformer` and `text_encoder` as quantizable so 4-bit or 8-bit weights save the most.
- **`true_cfg_scale` vs speed**: With `true_cfg_scale > 1.0` the pipeline runs an extra forward pass per step for the negative prompt, roughly doubling inference time. Leave it at `1.0` for the fastest path and only raise it when a negative prompt is actively needed.
- **Multilingual prompts**: Qwen-Image-2.1's Qwen3-VL text encoder handles Chinese, Korean, Japanese, and English prompts natively; mixed-language prompts also work.
- **Output**: The result is a single `.png` per input (or a list for batched inputs), decoded from the diffusion VAE.
