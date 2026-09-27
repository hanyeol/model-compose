# SFT + LoRA Model Trainer Example (Unsloth)

This example demonstrates how to fine-tune a causal language model using model-compose's `model-trainer` component with the `sft` task on the **Unsloth** driver. It runs supervised fine-tuning (SFT) on TinyLlama-1.1B with LoRA adapters and the Alpaca instruction dataset, leveraging Unsloth's fused CUDA kernels for ~2× throughput and ~30-70% VRAM reduction versus the vanilla HuggingFace backend.

## Overview

This workflow provides a declarative SFT+LoRA training loop that:

1. **Unsloth Fast Kernels**: Loads the base model via `FastLanguageModel.from_pretrained`, which patches attention and MLP layers with hand-tuned Triton kernels
2. **LoRA Adapters via `FastLanguageModel.get_peft_model`**: The PEFT wrap is Unsloth-specific — standard `peft.get_peft_model` would bypass the fast kernels
3. **Automatic Model Provisioning**: Downloads TinyLlama on first run and caches it under `~/.cache/huggingface/`
4. **Instruction Dataset**: Loads the `tatsu-lab/alpaca` dataset and trains on its `text` column (pre-flattened instruction/response prompts)
5. **Checkpoint Output**: Saves the trained LoRA adapter under `output_dir` and returns training metrics

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- **CUDA-capable NVIDIA GPU** — Unsloth ships CUDA-only kernels (Triton + bitsandbytes + xformers). MPS and CPU are not supported.
- Compute Capability ≥ 7.0 (Turing / RTX 20xx or newer) recommended. Ampere+ (RTX 30xx, A100, H100) is required for bfloat16 mixed precision.
- Python environment with `torch`, `unsloth`, `trl`, `huggingface_hub` (managed automatically by the component's `_get_setup_requirements`)
- A GPU with **≥6 GB VRAM** is recommended for TinyLlama at rank 16. Unsloth's memory efficiency means 4-6 GB cards can also fit this workload.
- **~5 GB disk** for TinyLlama weights and dataset cache

### Why Unsloth

Unsloth is a drop-in acceleration layer for LoRA/QLoRA fine-tuning of decoder-only language models. Compared to the vanilla HuggingFace path:

- **~2× throughput** on Ampere+ GPUs via fused attention/MLP kernels
- **~30-70% VRAM reduction** via smart activation checkpointing and 4-bit weight compression
- **Same TRL API** for the trainer — `SFTTrainer` + `SFTConfig` are used unchanged; the acceleration lives in the model wrapping, not the training loop

Trade-offs:

- **CUDA-only**. No MPS, no CPU, no ROCm (upstream is adding ROCm support but it isn't stable yet).
- **LoRA/QLoRA required**. Full fine-tuning is not supported by the Unsloth backend — the component config rejects it at load time.
- **Rope scaling is baked in at load time** via the component-level `max_seq_length`. Action-level `max_seq_length` still controls per-batch truncation but cannot exceed the component value.
- **Model family support** is limited to decoder-only architectures (Llama, Mistral, Gemma, Qwen, Phi). Encoder models (BERT, DeBERTa) are supported for classification via the `FastModel` API but not by this SFT driver.

### Environment Configuration

Navigate to this example directory:
```bash
cd examples/model-training-tasks/sft-lora/unsloth
```

No additional environment configuration is required. Model and dataset are downloaded automatically on the first workflow run.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Trigger a training run:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "num_epochs": 1,
         "batch_size": 4,
         "learning_rate": 2e-4
       }
     }'
   ```

   **Using Web UI:**
   - Open http://localhost:8081
   - Adjust `num_epochs`, `batch_size`, `learning_rate` if desired
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{"num_epochs": 1}'
   ```

3. **Inspect the trained adapter:**
   ```bash
   ls ./output/sft-lora-unsloth
   # adapter_config.json  adapter_model.safetensors  tokenizer.json  ...
   ```

## Component Details

### Model-Trainer Component (Default)

- **Type**: `model-trainer`
- **Task**: `sft`
- **Driver**: `unsloth`
- **Base Model**: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
- **max_seq_length** (component-level): `2048` — baked into the model at load time via rope scaling
- **LoRA Config**:
  - rank: 16
  - alpha: 32
  - dropout: 0.05
  - target_modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`

### Model Information: TinyLlama-1.1B-Chat-v1.0

- **Developer**: TinyLlama project
- **Parameters**: 1.1 billion
- **Type**: Causal LM, chat-tuned
- **License**: Apache 2.0
- **Trainable parameters after LoRA**: ~4M (~0.4%)

## Workflow Details

### "Fine-tune TinyLlama with SFT + LoRA (Unsloth)" Workflow (Default)

**Description**: Supervised fine-tune TinyLlama-1.1B on the Alpaca instruction dataset using Unsloth's fast kernels with LoRA adapters, then return the checkpoint directory and training metrics.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `dataset_path` | string | No | `tatsu-lab/alpaca` | HuggingFace dataset repo id or local path |
| `dataset_split` | string | No | `train` | Which split of the dataset to load |
| `num_epochs` | int | No | `1` | Number of training epochs |
| `batch_size` | int | No | `4` | Per-device train batch size |
| `learning_rate` | float | No | `2e-4` | AdamW initial learning rate |
| `output_dir` | string | No | `./output/sft-lora-unsloth` | Where the trained adapter is saved |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `output_dir` | string | Directory containing the saved LoRA adapter + tokenizer |
| `train_loss` | float | Final training loss |
| `metrics` | object | Full `Trainer.train()` metrics (train_runtime, samples_per_second, ...) |

## `max_seq_length` semantics

Unsloth's `FastLanguageModel.from_pretrained` applies rope scaling at load time and bakes the maximum position embedding size into the patched model. This differs from the vanilla HuggingFace driver, where truncation is a per-batch tokenizer setting.

- **`trainer.max_seq_length` (component-level)**: determines the loaded model's positional capacity. Set it once to cover the longest sequence any downstream action will feed in.
- **`action.max_seq_length`**: still controls per-example truncation at the SFT config level. If unset, the tokenizer's `model_max_length` is used. This value must not exceed the component-level value.

For most instruction-tuned workloads a component-level value of `2048` or `4096` is a safe default.

## System Requirements

### Recommended

- **GPU**: NVIDIA GPU with ≥6 GB VRAM (RTX 3060 / T4 / A10 or better). Ampere+ (RTX 30xx, A100, H100) enables bfloat16 and gets the full speedup.
- **RAM**: 16 GB
- **Disk**: 10 GB for model + dataset cache + checkpoints
- **CUDA**: 11.8+ with matching PyTorch

### Minimum

- **GPU**: Turing (RTX 20xx / T4) with 4 GB VRAM. Use `quantization: nf4` and `batch_size: 1` to fit larger models on limited hardware.

## Customization

### Use QLoRA (4-bit quantized base)

Unsloth's biggest wins show up on 7B+ models with QLoRA. Add `quantization` to the component:

```yaml
component:
  type: model-trainer
  task: sft
  driver: unsloth
  model: mistralai/Mistral-7B-Instruct-v0.3
  max_seq_length: 2048
  lora:
    rank: 8
    alpha: 16
  quantization:
    type: nf4
    compute_dtype: bfloat16
  action:
    dataset: HuggingFaceH4/ultrachat_200k
    text_column: messages       # UltraChat ships conversational data
    output_dir: ./output/qlora
```

Under Unsloth `quantization.type: int8` maps to `load_in_8bit=True`, and `nf4`/`int4`/`fp4` all map to `load_in_4bit=True`. Compute dtype is inferred from `precision` and the GPU's bfloat16 support.

Note: the `messages` path requires the tokenizer to have a `chat_template`. Instruct-tuned checkpoints (`*-Instruct-*`, `*-chat`, `*-it`) ship one; raw base checkpoints do not, and the driver will reject them with a `ValueError` at training start.

### Use prompt/response columns

If your dataset has separate columns for prompt and response instead of a pre-flattened text field:

```yaml
action:
  dataset: my-org/my-dataset
  prompt_column: instruction
  response_column: output
  system_column: system         # optional
  output_dir: ./output/sft-lora-unsloth
```

The driver builds a canonical `messages` column via `dataset.map`, then routes through the tokenizer's chat template. Chat template is required for this path too.

### Chain with a datasets component

Pre-load a dataset in one job and pass it to the trainer:

```yaml
components:
  - id: alpaca
    type: datasets
    driver: huggingface
    action:
      method: load
      path: tatsu-lab/alpaca
      split: train

  - id: trainer
    type: model-trainer
    task: sft
    driver: unsloth
    model: TinyLlama/TinyLlama-1.1B-Chat-v1.0
    max_seq_length: 2048
    lora:
      rank: 16
    action:
      dataset: ${jobs.load-data.output}
      text_column: text
      output_dir: ./output/sft-lora-unsloth

workflow:
  jobs:
    - id: load-data
      component: alpaca
    - id: train
      component: trainer
      depends_on: [load-data]
```

## Troubleshooting

- **`Unsloth trainer requires 'lora' to be set`**: full fine-tuning is not supported on this backend. Add a `lora` block or switch to `driver: huggingface`.
- **`Unsloth trainer requires a CUDA device`**: `device` must be `cuda`, `cuda:N`, or `auto`. MPS and CPU are not supported.
- **Out of Memory (CUDA OOM)**: reduce `batch_size` (try `1`), reduce component-level `max_seq_length`, or add `quantization: {type: nf4, compute_dtype: bfloat16}`.
- **Triton compilation error on first run**: Unsloth JIT-compiles its Triton kernels for your GPU. Compilation output is cached under `~/.triton`; first launch may pause for 30-60 seconds.
- **Slow first run**: TinyLlama (~2 GB) and Alpaca (~50 MB) download on first launch; subsequent runs reuse the cache.
- **`chat_template is None` error**: switch to an instruct-tuned model or set `text_column` to a pre-flattened text field.

## Related Examples

- `examples/model-training-tasks/sft-lora/huggingface/` — the same workflow on the vanilla HuggingFace backend, useful for comparison on non-CUDA hardware
- `examples/model-training-tasks/text-classification/huggingface/` — BERT + LoRA on GLUE SST-2 for text classification
- `examples/model-tasks/chat-completion/huggingface/` — using a pre-trained (or your fine-tuned) chat model for inference
