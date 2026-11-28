# Audio Source Separation Model Task Example (SAM-Audio)

This example demonstrates how to isolate an arbitrary sound from a complex audio mixture using model-compose's `audio-source-separation` task with Meta's **SAM-Audio** model, guided by a natural-language description of the target sound.

## Overview

The workflow returns a WAV file containing only the sound described by your prompt — anything else is discarded:

1. **Language-queried separation**: Describe the target sound in plain text (for example, `thunder`, `man speaking`, `car honking`)
2. **Isolation via a foundation model**: SAM-Audio-Large is pulled from HuggingFace on first run
3. **Optional time anchoring**: Narrow the target to specific `{start, end}` spans when the sound only occurs in part of the clip
4. **Optional reranking**: Generate multiple candidates and keep the best per CLAP/Judge scores for higher quality at the cost of latency

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- A **Linux x86_64 host with a CUDA GPU** — this example is not runnable on Apple Silicon or Windows (see platform note below)
- A HuggingFace account with access to `facebook/sam-audio-large` approved (the checkpoint is gated)
- A HuggingFace token available to the process (`hf auth login` or `HF_TOKEN` env var)

> SAM-Audio relies on several Git-only dependencies (`dacvae`, `imagebind`, `perception-models`, a CLAP fork). model-compose installs the `sam-audio` package on first component setup, which cascades those installs.

> **Platform note**: SAM-Audio pulls in `decord` (via `perception-models`), which only ships wheels for `manylinux2010_x86_64` and `win_amd64`. Installation on Apple Silicon (`macosx_*_arm64`) fails during setup. Windows wheels exist for `decord` but the broader CUDA toolchain targeted by this example assumes Linux. Use a Linux x86_64 host with an NVIDIA GPU.

### Why Language-Queried Separation

Traditional music source separation splits a mixture into fixed stems (vocals / drums / bass / other). Audio source separation generalises this to **any** sound you can describe:

- **Sound design clean-up**: Pull out a specific effect (rain, applause, rotor noise) from field recordings or film mixes
- **Dataset curation**: Isolate a target sound class for downstream model training
- **Accessibility / translation**: Attenuate background music or SFX from spoken content prior to ASR
- **Creative remixing**: Keep only the sound you want and discard the mix

Note: SAM-Audio returns *unmixed audio*, not time labels. If you only need event boundaries, use a detection-oriented task instead.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Basic language-queried separation
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "audio=@/path/to/your/clip.mp3" \
     -F "input={\"audio\": \"@audio\", \"prompt\": \"thunder\"}" \
     -o target.wav

   # Higher-quality separation (span prediction + candidate reranking)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "audio=@/path/to/your/clip.mp3" \
     -F "input={\"audio\": \"@audio\", \"prompt\": \"car honking\", \"predict_spans\": true, \"reranking_candidates\": 8}" \
     -o target.wav
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload an audio file (MP3, WAV, FLAC, etc.)
   - Enter a short noun-phrase or verb-phrase describing the target sound (lowercase, e.g. `thunder`, not `Thunder can be heard in the background`)
   - Optionally enable `predict_spans` and raise `reranking_candidates`
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   # Basic language-queried separation
   model-compose run audio-source-separation-with-sam-audio --input '{
     "audio": "/path/to/your/clip.mp3",
     "prompt": "thunder"
   }'

   # With span prediction and reranking
   model-compose run audio-source-separation-with-sam-audio --input '{
     "audio": "/path/to/your/clip.mp3",
     "prompt": "car honking",
     "predict_spans": true,
     "reranking_candidates": 8
   }'
   ```

## Component Details

### Audio Source Separation Model Component (Default)

The `separator` component loads SAM-Audio-Large locally and exposes the separation action. Key YAML keys:

- `prompt` — natural-language description of the target sound. Lowercase noun-/verb-phrase form matches the training distribution; use `thunder`, not a full sentence.
- `params.predict_spans` — when `true`, SAM-Audio auto-detects when the target sound occurs. Especially useful for non-ambience events (claps, honks). Costs extra latency and VRAM.
- `params.reranking_candidates` — generate N candidate separations and pick the best per internal rankers. `1` is fastest; `4-8` yields markedly cleaner output on hard inputs.
- `params.sample_rate` — override the sample rate of the returned audio. Defaults to the model's native rate (48 kHz).

The component also accepts (not shown in this example):

- `spans` — explicit time ranges where the target sound occurs. Each entry is `{start, end}` in seconds, with optional `polarity: positive | negative` — a positive span marks where the target is; a negative span actively suppresses the model there. Unspecified regions are left neutral.
- `visual` — a `{video, mask}` pair for visual prompting: a video clip plus a binary mask (same frame count) that isolates the visual object whose sound should be separated. Use the `*-tv` variants (`facebook/sam-audio-large-tv`) for this mode.

### Alternative Models

Three size tiers plus visual-tuned variants are available:

| Model | Variant | Best for |
|---|---|---|
| `facebook/sam-audio-small` | base | Fastest; lower VRAM |
| `facebook/sam-audio-base` | base | Balanced |
| `facebook/sam-audio-large` | base | Best general quality (used in this example) |
| `facebook/sam-audio-*-tv` | tv | Better target correctness and visual prompting |

Swap the `model` key in the YAML to try a different one. Each model needs its own HuggingFace access request.

## Troubleshooting

- **"The model repo is gated"** on first run: request access on the HuggingFace page for the model and make sure your token is loaded (`hf auth login` or `HF_TOKEN`).
- **Out-of-memory on the large model**: drop to `facebook/sam-audio-base` or `-small`, or disable `predict_spans` and lower `reranking_candidates` to `1`.
- **Prompt returns silence / noise**: rephrase to a short lowercase noun phrase ("thunder" instead of "a thunderclap"). Enabling `predict_spans=true` often helps with short, non-ambience sounds.
- **MPS / CPU runs fail or stall**: SAM-Audio is only practical on CUDA; its visual encoder and DAC-VAE codec assume a real GPU.
