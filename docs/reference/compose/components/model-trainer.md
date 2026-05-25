# Model Trainer Component

> **Development Status**: The configuration schema is defined and stable, but the training execution backend is still under active development. Schema fields below reflect the current declarative interface; expect runtime support to land in upcoming releases.

The model-trainer component declares supervised fine-tuning (SFT) and classification training jobs. It supports LoRA adapters, quantization, optimizer and scheduler selection, mixed-precision training, and gradient checkpointing — all configured declaratively so the same workflow can target different hardware profiles by swapping a few fields.

## Basic Configuration

```yaml
component:
  type: model-trainer
  task: sft
  action:
    dataset: ${input.dataset}
    text_column: text
    learning_rate: 5e-5
    num_epochs: 3
    output_dir: ./output/model
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `model-trainer` |
| `task` | string | **required** | Training task: `sft`, `classification` |
| `lora` | object | `null` | LoRA adapter configuration |
| `quantization` | string/object | `null` | Model quantization configuration |

### LoRA Configuration

LoRA (Low-Rank Adaptation) trains a small set of adapter parameters instead of the full model, dramatically reducing memory and time requirements.

```yaml
component:
  type: model-trainer
  task: sft
  lora:
    rank: 8
    alpha: 16
    dropout: 0.05
    target_modules: ["q_proj", "v_proj"]
    bias: none
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rank` | integer | `8` | LoRA rank |
| `alpha` | integer | `16` | LoRA alpha for scaling |
| `dropout` | float | `0.05` | LoRA dropout rate |
| `target_modules` | array | `null` | Target modules for LoRA. Auto-detected when omitted |
| `bias` | string | `none` | Bias training strategy: `none`, `all`, `lora_only` |

### Quantization Configuration

Reduce memory footprint by loading the base model in lower precision. Provide a string shorthand or a full config object.

```yaml
# Shorthand
component:
  type: model-trainer
  task: sft
  quantization: 4bit

# Full object — same shape as the model component's quantization config
component:
  type: model-trainer
  task: sft
  quantization:
    type: 4bit
    # provider-specific fields
```

See [model.md](model.md) for the full quantization schema.

## Training Tasks

### SFT (Supervised Fine-Tuning)

Fine-tune a causal language model on instruction or chat data. The action requires either a `text_column` (pre-formatted text) or both `prompt_column` and `response_column` (chat-style data).

```yaml
component:
  type: model-trainer
  task: sft
  lora:
    rank: 8
    alpha: 16
  action:
    dataset: ${input.dataset}
    text_column: text
    max_seq_length: 1024
    packing: true
    learning_rate: 2e-4
    per_device_train_batch_size: 4
    gradient_accumulation_steps: 4
    num_epochs: 3
    output_dir: ./output/sft-model
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `dataset` | string | **required** | Training dataset reference |
| `eval_dataset` | string | `null` | Evaluation dataset reference |
| `text_column` | string | `null` | Column containing pre-formatted training text |
| `prompt_column` | string | `null` | Column containing chat prompts |
| `response_column` | string | `null` | Column containing chat responses |
| `system_column` | string | `null` | Column containing chat system prompts |
| `max_seq_length` | integer | `512` | Maximum sequence length for training |
| `packing` | boolean | `false` | Pack multiple short examples into one sequence for efficiency |

Either `text_column` or both `prompt_column` and `response_column` must be specified.

### Classification

Fine-tune a model for classification. The classification action shares all common training fields (no task-specific extras beyond the shared base).

```yaml
component:
  type: model-trainer
  task: classification
  action:
    dataset: ${input.dataset}
    eval_dataset: ${input.eval_dataset}
    learning_rate: 3e-5
    per_device_train_batch_size: 16
    num_epochs: 5
    output_dir: ./output/classifier
```

## Common Training Parameters

All training actions accept these shared parameters from `CommonModelTrainerActionConfig`:

### Essential

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `learning_rate` | float | `5e-5` | Learning rate for training |
| `per_device_train_batch_size` | integer | `8` | Training batch size per device |
| `per_device_eval_batch_size` | integer | `null` | Evaluation batch size per device. Falls back to train batch size |
| `num_epochs` | integer | `3` | Number of training epochs |

### Optimizer and Scheduler

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `optimizer` | string | `adamw_torch` | Optimizer (see list below) |
| `lr_scheduler_type` | string | `linear` | Learning rate scheduler type |

**Optimizer options:**

- AdamW variants: `adamw_torch`, `adamw_torch_fused`, `adamw_torch_xla`, `adamw_torch_npu_fused`, `adamw_apex_fused`, `adamw_anyprecision`, `adamw_bnb_8bit`, `adamw_8bit` (alias for `adamw_bnb_8bit`), `adamw_hf`
- Specialized: `adafactor`, `adalomo`, `lomo`
- Memory-efficient: `apollo_adamw`, `galore_adamw`, `galore_adamw_8bit`, `galore_adafactor`, `galore_adamw_layerwise`, `galore_adamw_8bit_layerwise`, `galore_adafactor_layerwise`
- Advanced: `grokadamw`, `schedule_free_radamw`, `stableadamw`
- Traditional: `sgd`, `adagrad`, `rmsprop`

**LR scheduler options:** `linear`, `cosine`, `cosine_with_restarts`, `polynomial`, `constant`, `constant_with_warmup`, `inverse_sqrt`, `reduce_lr_on_plateau`, `cosine_with_min_lr`, `warmup_stable_decay`

### Output and Logging

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `output_dir` | string | `./output` | Directory to save the trained model |
| `eval_steps` | integer | `500` | Steps between evaluations |
| `save_steps` | integer | `null` | Steps between model saves. Falls back to `eval_steps` |
| `logging_steps` | integer | `10` | Steps between logging |

### Optimization

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `weight_decay` | float | `0.01` | Weight decay for regularization |
| `warmup_steps` | integer | `100` | Number of warmup steps |
| `max_grad_norm` | float | `1.0` | Maximum gradient norm for gradient clipping |
| `gradient_accumulation_steps` | integer | `1` | Number of gradient accumulation steps |

### Memory and Precision

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `gradient_checkpointing` | boolean | `false` | Enable gradient checkpointing to save memory |
| `fp16` | boolean | `false` | Enable FP16 mixed precision training |
| `bf16` | boolean | `false` | Enable BF16 mixed precision training (recommended for A100/H100) |

### Reproducibility

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `seed` | integer | `null` | Random seed for reproducibility |

## Usage Examples

### LoRA Fine-Tuning on a Single GPU

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    lora:
      rank: 8
      alpha: 16
      dropout: 0.05
    quantization: 4bit
    action:
      dataset: ${input.dataset}
      text_column: text
      max_seq_length: 1024
      packing: true
      learning_rate: 2e-4
      per_device_train_batch_size: 4
      gradient_accumulation_steps: 4
      num_epochs: 3
      warmup_steps: 100
      logging_steps: 10
      eval_steps: 500
      bf16: true
      gradient_checkpointing: true
      output_dir: ./output/lora-model
```

### Chat-Style Training Data

When training data is split into separate prompt and response columns:

```yaml
component:
  type: model-trainer
  task: sft
  action:
    dataset: ${input.dataset}
    prompt_column: instruction
    response_column: output
    system_column: system
    max_seq_length: 2048
    learning_rate: 5e-5
    num_epochs: 3
    output_dir: ./output/chat-model
```

### Full Pipeline: Dataset + Trainer

```yaml
components:
  - id: dataset
    type: datasets
    actions:
      - id: load
        method: load
        provider: huggingface
        path: tatsu-lab/alpaca
        split: train

      - id: format
        method: map
        dataset: ${jobs.load.output}
        template: "### Instruction:\n{instruction}\n\n### Response:\n{output}"
        output_column: text
        remove_columns: ["instruction", "input", "output"]

  - id: trainer
    type: model-trainer
    task: sft
    lora:
      rank: 8
      alpha: 16
    action:
      dataset: ${input.dataset}
      text_column: text
      learning_rate: 2e-4
      num_epochs: 3
      output_dir: ./output/finetuned

workflows:
  - id: train
    jobs:
      - id: load
        component: dataset
        action: load

      - id: format
        component: dataset
        action: format
        input:
          dataset: ${jobs.load.output}
        depends_on: [load]

      - id: train
        component: trainer
        input:
          dataset: ${jobs.format.output}
        depends_on: [format]
```

### Classification

```yaml
component:
  type: model-trainer
  task: classification
  action:
    dataset: ${input.train_dataset}
    eval_dataset: ${input.eval_dataset}
    learning_rate: 3e-5
    per_device_train_batch_size: 16
    per_device_eval_batch_size: 32
    num_epochs: 5
    eval_steps: 200
    save_steps: 500
    output_dir: ./output/classifier
```

## Variable Interpolation

```yaml
component:
  type: model-trainer
  task: sft
  lora:
    rank: ${env.LORA_RANK as integer | 8}
    alpha: ${env.LORA_ALPHA as integer | 16}
  action:
    dataset: ${input.dataset}
    text_column: ${input.text_column | text}
    learning_rate: ${input.learning_rate as number | 5e-5}
    num_epochs: ${input.num_epochs as integer | 3}
    output_dir: ${env.OUTPUT_DIR | ./output}
    bf16: ${input.bf16 as boolean | true}
```

## Best Practices

1. **Start with LoRA**: Use LoRA before attempting full fine-tuning — it is faster, cheaper, and easier to recover from
2. **Match precision to hardware**: Use `bf16` on A100/H100; `fp16` on older GPUs; neither on CPUs
3. **Pair quantization with LoRA**: `quantization: 4bit` plus LoRA enables fine-tuning on consumer GPUs
4. **Tune `gradient_accumulation_steps`**: When VRAM forces a small `per_device_train_batch_size`, increase accumulation to keep the effective batch size large
5. **Pack short examples**: Set `packing: true` for SFT when most examples are short — significant throughput win
6. **Pin `seed`**: Set a seed for reproducible experiments
7. **Pre-format with `datasets`**: Use the [datasets.md](datasets.md) component's `map` method to produce a clean `text_column`

## Common Use Cases

- **Instruction tuning**: Fine-tune a base model on instruction-following data with LoRA + 4-bit quantization
- **Domain adaptation**: Continue training on domain-specific text to specialize a general model
- **Classification**: Fine-tune encoder models for sentiment, intent, or topic classification
- **Style transfer**: Train on writing samples to capture a tone or persona

## Related Components

- [datasets.md](datasets.md) — Prepare and format training data
- [model.md](model.md) — Inference for the resulting fine-tuned model
- [model-tokenizer.md](model-tokenizer.md) — Standalone tokenization for input validation
