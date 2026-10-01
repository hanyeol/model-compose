# Text-to-Video Model Task Example (MiniMax-H3)

This example demonstrates how to generate a short clip with native stereo audio from a text prompt using MiniMax-H3's Omni-Transformer. It is exposed through model-compose's built-in text-to-video task.

## Overview

MiniMax-H3 packs the text condition, the audio track, and the target video frames into one sequence and runs full self-attention over that sequence to produce **joint video + audio** in a single pipeline call. The example wires this up as a local, declarative workflow:

1. **Local Diffusion Pipeline**: Runs the HuggingFace diffusers `MiniMaxH3ModularPipeline` end-to-end — no external API.
2. **Joint Video + Audio**: Each generation returns a 24 fps video track and a 32 kHz stereo audio track; both are muxed into a single mp4.
3. **Optional Sol-Attn Acceleration**: On NVIDIA Blackwell consumer GPUs (SM120), opting in to `sol_attn` routes the main transformer blocks through Sol-Attn's compiled `flex_attention` kernel, which is faster than SDPA on long packed sequences while keeping the trailing denoising steps dense for quality.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- A CUDA-capable GPU. The Omni-Transformer is ~33B parameters — a single consumer GPU needs `cpu_offload: true` (set in the example) to fit. H100-class hardware can run without offload.
- Enough disk space for the checkpoint (~70 GB across the base transformer, Qwen3-VL text encoder, VAE, and audio VAE).
- A Python environment where `torch`, `diffusers (>= 0.36)`, `transformers (>= 4.45)`, and `av` can be installed — the first run installs them automatically.
- (Optional) To use Sol-Attn, an NVIDIA Blackwell consumer GPU reporting compute capability 12.0 (RTX 5090 / RTX PRO 6000). The example auto-installs the `mindor-sol-attn-blackwell` kernel package when `sol_attn` is enabled; other GPUs are routed to dense attention transparently.

### Model Access

MiniMax-H3 weights live on Hugging Face at `MiniMaxAI/MiniMax-H3` and are gated by the MiniMax H3 Community License. Accept the license on the model's Hugging Face page and run `hf auth login` (or export `HF_TOKEN`) before starting the service.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup downloads the checkpoint from Hugging Face (~70 GB). Expect a long initial setup; subsequent runs reuse the cached shards.

2. **Run the workflow:**
   ```bash
   # Minimal call — generate a short cinematic clip with the defaults.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "a quiet alleyway at dusk, warm neon reflections on wet pavement, slow dolly in"}}'

   # Pin the seed and request a longer clip.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "waves crashing on a rocky coast, overcast sky, slow-motion spray", "num_frames": 240, "seed": 42}}'
   ```

3. **Open the Web UI:**
   `http://localhost:8081` opens a Gradio form that drives the same workflow.

## Switching the Attention Backend

The example defaults to `backend: torch` on the component, which routes attention through diffusers' standard SDPA / FlashAttention dispatch. To use Sol-Attn on a supported Blackwell host, set the backend on the component:

```yaml
component:
  # ...
  family: minimax-h3
  backend: sol
```

Optional Sol-Attn tuning lives under `action.params.sol_attn`:

```yaml
params:
  sol_attn:
    tau: 1.0
    thresh_type: diag
    dense_steps: 1
```

Behavior notes:

- `tau` controls the routing threshold. Higher skips more KV blocks (faster, lower fidelity); lower approaches dense attention.
- `thresh_type: diag` is the faster estimator; `exact` is more precise at a small cost.
- `dense_steps` runs the last N denoising steps on full dense attention. The final steps are where sparse approximation is most visible, so keeping 1 trailing dense step is a cheap quality guard.
- On non-SM120 hardware the processor logs a warning and falls back to dense attention on each attention call — no code change needed to run portably.
- Omitting the `sol_attn` block under `backend: sol` is valid; the defaults above are already in effect.

## Shutdown

```bash
model-compose down
```
