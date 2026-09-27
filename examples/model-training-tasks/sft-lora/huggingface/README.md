# SFT + LoRA Model Trainer Example

This example demonstrates how to fine-tune a causal language model using model-compose's `model-trainer` component with the `sft` task on the HuggingFace driver. It runs supervised fine-tuning (SFT) on TinyLlama-1.1B with LoRA adapters and the Alpaca instruction dataset.

## Overview

This workflow provides a declarative SFT+LoRA training loop that:

1. **HuggingFace Trainer**: Wraps `trl.SFTTrainer` with `SFTConfig` (TRL 0.12+ API)
2. **LoRA Adapters**: Attaches rank-16 LoRA adapters to `q_proj`/`k_proj`/`v_proj`/`o_proj` so only ~1% of parameters train
3. **Automatic Model Provisioning**: Downloads TinyLlama on first run and caches it under `~/.cache/huggingface/`
4. **Instruction Dataset**: Loads the `tatsu-lab/alpaca` dataset and trains on its `text` column (pre-flattened instruction/response prompts)
5. **Checkpoint Output**: Saves the trained LoRA adapter under `output_dir` and returns training metrics

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python environment with `torch`, `transformers`, `datasets`, `peft`, `trl`, `accelerate` (managed automatically by the component's `_get_setup_requirements`)
- A GPU with **≥8 GB VRAM** is recommended. CPU-only training works but takes hours per epoch on this dataset size.
- **~5 GB disk** for TinyLlama weights and dataset cache

### Why SFT + LoRA

- **SFT** (supervised fine-tuning) is the standard way to teach a base LM to follow instructions or adapt to a domain, using paired prompt/response text.
- **LoRA** (Low-Rank Adaptation) trains a small pair of matrices per attention projection instead of the full weight matrix. For TinyLlama-1.1B at rank 16, this reduces trainable parameters from 1.1B to ~4M while retaining most of the fine-tuning gains.

### Environment Configuration

Navigate to this example directory:
```bash
cd examples/model-training-tasks/sft-lora/huggingface
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
   ls ./output/sft-lora
   # adapter_config.json  adapter_model.safetensors  tokenizer.json  ...
   ```

## Component Details

### Model-Trainer Component (Default)

- **Type**: `model-trainer`
- **Task**: `sft`
- **Driver**: `huggingface`
- **Base Model**: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
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

### "Fine-tune TinyLlama with SFT + LoRA" Workflow (Default)

**Description**: Supervised fine-tune TinyLlama-1.1B on the Alpaca instruction dataset using LoRA adapters, then return the checkpoint directory and training metrics.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `dataset` | string | No | `tatsu-lab/alpaca` | HuggingFace dataset name or local path |
| `num_epochs` | int | No | `1` | Number of training epochs |
| `batch_size` | int | No | `4` | Per-device train batch size |
| `learning_rate` | float | No | `2e-4` | AdamW initial learning rate |
| `output_dir` | string | No | `./output/sft-lora` | Where the trained adapter is saved |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `output_dir` | string | Directory containing the saved LoRA adapter + tokenizer |
| `train_loss` | float | Final training loss |
| `metrics` | object | Full `Trainer.train()` metrics (train_runtime, samples_per_second, ...) |

## System Requirements

### Recommended

- **GPU**: NVIDIA GPU with ≥8 GB VRAM (RTX 3060 12GB, T4, A10, or better)
- **RAM**: 16 GB
- **Disk**: 10 GB for model + dataset cache + checkpoints
- **CUDA**: 11.8+ with matching PyTorch

### CPU-only

Training works but is impractically slow (~hours per epoch on this dataset). Use CPU only for smoke-testing the pipeline with `num_epochs: 1` and a small dataset slice.

## Customization

### Use QLoRA (4-bit quantized base)

For larger models on limited VRAM, add `quantization` to the component. Quantization requires `lora` to be set (the driver rejects the combination otherwise).

```yaml
component:
  type: model-trainer
  task: sft
  driver: huggingface
  model: mistralai/Mistral-7B-Instruct-v0.3
  lora:
    rank: 8
    alpha: 16
  quantization:
    type: nf4
    compute_dtype: bfloat16
    double_quant: true
  action:
    dataset: HuggingFaceH4/ultrachat_200k
    text_column: messages       # UltraChat ships conversational data
    output_dir: ./output/qlora
```

Note: the `messages` path requires the tokenizer to have a `chat_template`. Instruct-tuned checkpoints (`*-Instruct-*`, `*-chat`, `*-it`) ship one; raw base checkpoints do not, and the driver will reject them with a `ValueError` at training start.

### Use prompt/response columns

If your dataset has separate columns for prompt and response instead of a pre-flattened text field:

```yaml
action:
  dataset: my-org/my-dataset
  prompt_column: instruction
  response_column: output
  system_column: system         # optional
  output_dir: ./output/sft-lora
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
    driver: huggingface
    model: TinyLlama/TinyLlama-1.1B-Chat-v1.0
    lora:
      rank: 16
    action:
      dataset: ${jobs.load-data.output}
      text_column: text
      output_dir: ./output/sft-lora

workflow:
  jobs:
    - id: load-data
      component: alpaca
    - id: train
      component: trainer
      depends_on: [load-data]
```

## Troubleshooting

- **Out of Memory (CUDA OOM)**: reduce `batch_size` (try `1`), enable `gradient_checkpointing: true` (already on), or switch to QLoRA (`quantization.type: nf4`).
- **`chat_template is None` error**: switch to an instruct-tuned model or set `text_column` to a pre-flattened text field.
- **Slow first run**: TinyLlama (~2 GB) and Alpaca (~50 MB) download on first launch; subsequent runs reuse the cache.
- **`datasets` version incompatibility**: the driver pins `datasets>=2.14,<4.0` because TRL 0.13's conversational auto-detection breaks on datasets 4.0. If you have a newer version installed globally, model-compose's isolated runtime will install the pinned version.

## Related Examples

- `examples/model-training-tasks/text-classification/huggingface/` — BERT + LoRA on GLUE SST-2 for text classification
- `examples/model-tasks/chat-completion/huggingface/` — using a pre-trained (or your fine-tuned) chat model for inference
