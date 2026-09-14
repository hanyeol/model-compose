# Music Generation (YuE2) Model Task Example

This example demonstrates how to generate full songs with YuE2, running locally via model-compose's built-in model task functionality. YuE2 combines symbolic score planning (ABC) with acoustic synthesis, so a song can be created from scratch, produced from an editable score, or exported as a plan without rendering audio.

## Overview

This example exposes three workflows against a single YuE2 component:

1. **generate** — Compose a new song from a style description and lyrics.
2. **cover** — Reinterpret a supplied ABC score in a new style (typically melody-only for zero-shot covers).
3. **score** — Plan an editable ABC score only, without rendering audio.

Each workflow uses YuE2's symbolic chain-of-thought: `cot_mode: full` writes both melody and chord symbols, `melody` writes a melody-only plan (recommended for covers), and `off` skips the score and generates directly from lyrics and style.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- NVIDIA GPU with **CUDA BF16 support and 24 GB VRAM** (YuE2 renders 48 kHz stereo audio without quantization)
- Python 3.12 environment (the `yue2-infer` wheel and its pinned `torch==2.10.0` are installed automatically on first run)
- ~15 GB of disk space for the AR model and VAE decoder (downloaded from Hugging Face on first use)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/music-generation-yue2
   ```

2. No additional environment configuration required — models and dependencies are managed automatically.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the "generate" workflow (default):**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "style": "English, piano-pop, warm lead vocal, tasteful strings",
         "lyrics": "[Verse]\nMorning light on empty streets\n[Chorus]\nWe are the ones who wait"
       }
     }'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Switch between the *Generate*, *Cover*, and *Score* tabs
   - Fill in the style description and lyrics, then click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run generate --input '{"style": "English, piano-pop", "lyrics": "..."}'
   ```

3. **Cover an existing score:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs/cover \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "style": "English, jazz-funk, warm lead vocal, Rhodes, bass and drums",
         "lyrics": "...new lyrics...",
         "abc": "X:1\nT:Sample\nM:4/4\nK:C\n..."
       }
     }'
   ```

4. **Export a score only (no audio):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs/score \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "style": "Mandarin, city-pop, mid tempo",
         "lyrics": "..."
       }
     }'
   ```
   Returns `{ "abc": "...", "truncated": false }` for downstream editing.

## Component Details

### YuE2 Music Generation Component
- **Type**: Model component with `music-generation` task
- **Driver / Family**: `custom` / `yue2`
- **Model**: `m-a-p/YuE2-3B` (autoregressive model) + `m-a-p/YuE2-Vae` (decoder, pulled automatically)
- **Device**: `cuda`
- **Output Format**: 48 kHz stereo audio (`generate`, `cover`) or `{ abc, truncated }` (`score`)
- **Concurrency**: 1 (single request at a time)

### Model Information: YuE2
- **Developer**: M·A·P and collaborators (see the [YuE2 project page](https://map-yue2.github.io/))
- **Type**: AR–NAR Mixture-of-Transformers with flow-matching acoustic synthesis and VAE decoding
- **Chain-of-thought modes**: `full` (score with chords, default), `melody` (best for covers), `off` (direct)
- **Backends**: `torch` (default), `torch-eager`, `vllm` (requires the model's optional `[fast]` extras)
- **Quantization**: optional `fp8` for the AR model — halves AR VRAM at a small quality cost

## Workflow Details

### "Generate" Workflow (Default)

**Description**: Compose a new song from a style description and lyrics.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `style` | text | Yes | - | Style, genre, mood, and instrumentation description |
| `lyrics` | text | Yes | - | Song lyrics with optional structural tags (e.g. `[Verse]`, `[Chorus]`) |
| `cot_mode` | text | No | `full` | `full` (score + chords), `melody` (melody only), or `off` (direct) |
| `cfg_scale` | number | No | model default | Classifier-free guidance scale in `[0, 20]` |
| `seed` | integer | No | `831001` | Random seed for reproducibility |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| - | audio | Generated song (48 kHz stereo WAV) |

### "Cover" Workflow

**Description**: Reinterpret a supplied ABC score in a new style.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `style` | text | Yes | - | Target cover style |
| `lyrics` | text | Yes | - | Lyrics to sing over the covered score |
| `abc` | text | Yes | - | ABC score conditioning the cover (typically a melody transcription without chord symbols) |
| `cot_mode` | text | No | `melody` | Use `melody` for covers; `full` if the ABC includes chord symbols |
| `seed` | integer | No | `831001` | Random seed |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| - | audio | Cover recording (48 kHz stereo WAV) |

### "Score" Workflow

**Description**: Plan an editable ABC score only, without rendering audio.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `style` | text | Yes | - | Style description used to plan the score |
| `lyrics` | text | Yes | - | Lyrics that shape the plan |
| `cot_mode` | text | No | `full` | `full` (with chord symbols) or `melody` (melody only) |
| `seed` | integer | No | `831001` | Random seed |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `abc` | text | Editable ABC notation of the planned song |
| `truncated` | boolean | Whether the plan hit the token budget |

## System Requirements

### Minimum Requirements
- **GPU**: NVIDIA GPU with **BF16 support and 24 GB VRAM** (unquantized preset)
- **RAM**: 32 GB recommended
- **Disk Space**: 15 GB+ for the AR model and VAE decoder
- **Internet**: Required for the initial Hugging Face download only

### Performance Notes
- First run downloads the model weights from Hugging Face (~15 GB)
- The unquantized preset requires 24 GB VRAM; use `quantization.type: fp8` and/or `offload_ar: true` to fit smaller GPUs
- Single concurrent request per component to prevent VRAM exhaustion

## Customization

### Reducing VRAM Usage
```yaml
component:
  quantization:
    type: fp8       # halves AR memory
  offload_ar: true  # move the AR model to CPU during NAR synthesis
  memory_budget_gib: 16
  vae:
    tile_size: 512
```

### Using the vLLM Backend
```yaml
component:
  backend: vllm
  # Requires `pip install "yue2-infer[fast]"` (installs vllm/triton).
```

### Providing an Editable Score for Generation
```yaml
component:
  actions:
    - method: generate
      style: ${input.style as text}
      lyrics: ${input.lyrics as text}
      # `generate` can also seed generation from an externally edited score if you
      # pass it through the DSL as an input variable; see the cover workflow for a
      # pure "reuse an ABC score" pattern.
```

### Adjusting Sampling
```yaml
component:
  actions:
    - method: generate
      style: ${input.style as text}
      lyrics: ${input.lyrics as text}
      params:
        cfg_scale: 1.5
        abc_sampling:
          temperature: 0.7
          top_p: 0.9
        semantic_sampling:
          temperature: 1.0
          top_p: 0.95
          repetition_penalty: 1.2
```

## Related Examples

- **[music-generation](../music-generation/)**: Local music generation with ACE-Step 1.5
- **[music-source-separation](../music-source-separation/)**: Split a mixed recording into stems
- **[music-transcription](../music-transcription/)**: Transcribe recordings into musical notation
