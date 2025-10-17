# 9. Model Training

> **⚠️ Development Status**: This feature is currently under development. The configuration schema is defined, but the training execution service is not yet implemented. Updates will be provided in future releases.

This chapter explains how to configure model training using model-compose.

---

## 9.1 Training Overview

### 9.1.1 Supported Training Tasks

model-compose provides configurations for the following training tasks:

- **SFT (Supervised Fine-Tuning)**: Supervised learning-based fine-tuning
- **Classification**: Classification model training

### 9.1.2 Training Component Structure

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft                      # or classification

    # LoRA configuration (optional)
    peft_adapter: lora
    lora_r: 8
    lora_alpha: 16

    # Training parameters
    learning_rate: 5e-5
    num_epochs: 3
    output_dir: ./trained-model
```

---

## 9.2 Dataset Preparation

### 9.2.1 Dataset Component Overview

The dataset component provides tools for preparing training data.

**Supported Features:**
- Load datasets from HuggingFace Hub
- Load datasets from local files
- Merge and transform datasets
- Row/column selection and filtering

### 9.2.2 Loading HuggingFace Datasets

**Basic Configuration:**

```yaml
components:
  - id: dataset-loader
    type: datasets
    provider: huggingface
    path: tatsu-lab/alpaca          # HuggingFace Hub path
    split: train                    # train, test, validation, etc.
    fraction: 1.0                   # Fraction of data (0.0 ~ 1.0)
```

**Advanced Configuration:**

```yaml
components:
  - id: dataset-loader
    type: datasets
    provider: huggingface
    path: tatsu-lab/alpaca
    name: default                   # Dataset configuration name
    split: train
    fraction: 0.1                   # Use only 10%
    streaming: false                # Streaming mode
    cache_dir: ./cache/datasets     # Cache directory
    revision: main                  # Model revision
    trust_remote_code: false        # Allow remote code execution
    token: ${env.HF_TOKEN}          # HuggingFace token
    shuffle: true                   # Shuffle data
```

**Workflow Example:**

```yaml
workflows:
  - id: load-training-data
    jobs:
      - id: load
        component: dataset-loader
        input:
          path: ${input.dataset | tatsu-lab/alpaca}
          split: train
          fraction: 1.0
        output: ${output}
```

### 9.2.3 Loading Local Datasets

**JSON Files:**

```yaml
components:
  - id: local-dataset
    type: datasets
    provider: local
    loader: json                    # json, csv, parquet, text
    data_files: ./data/train.json   # File path
```

**CSV Files:**

```yaml
components:
  - id: local-dataset
    type: datasets
    provider: local
    loader: csv
    data_files:
      - ./data/train.csv
      - ./data/validation.csv
```

**Directories:**

```yaml
components:
  - id: local-dataset
    type: datasets
    provider: local
    loader: json
    data_dir: ./data/training       # All JSON files in directory
```

### 9.2.4 Dataset Manipulation

**Merging Datasets:**

```yaml
workflows:
  - id: merge-datasets
    jobs:
      - id: load-first
        component: dataset-loader
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: load-second
        component: dataset-loader
        input:
          path: yahma/alpaca-cleaned
          split: train

      - id: concat
        component: dataset-ops
        method: concat
        input:
          datasets:
            - ${jobs.load-first.output}
            - ${jobs.load-second.output}
        depends_on: [ load-first, load-second ]
```

**Column Selection:**

```yaml
workflows:
  - id: select-columns
    jobs:
      - id: load
        component: dataset-loader
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: select
        component: dataset-ops
        method: select
        input:
          dataset: ${jobs.load.output}
          axis: columns
          columns: [ instruction, input, output ]
        depends_on: [ load ]
```

**Row Selection:**

```yaml
workflows:
  - id: select-rows
    jobs:
      - id: load
        component: dataset-loader
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: select
        component: dataset-ops
        method: select
        input:
          dataset: ${jobs.load.output}
          axis: rows
          indices: [ 0, 1, 2, 3, 4 ]    # First 5 rows
        depends_on: [ load ]
```

**Data Filtering:**

```yaml
components:
  - id: dataset-ops
    type: datasets
    method: filter
    dataset: ${input.dataset}
    condition: ${input.condition}    # Filter condition
```

**Data Mapping:**

```yaml
components:
  - id: dataset-ops
    type: datasets
    method: map
    dataset: ${input.dataset}
    template: ${input.template}      # Data transformation template
```

### 9.2.5 Dataset Formats

**Data Format for SFT Training:**

1. **Single Text Column:**
```json
{
  "text": "Complete training text here..."
}
```

2. **Prompt-Response Format:**
```json
{
  "prompt": "User question or instruction",
  "response": "Model's expected response"
}
```

3. **Instruction Format (Alpaca Style):**
```json
{
  "instruction": "Task instruction",
  "input": "Optional context",
  "output": "Expected output"
}
```

4. **Conversation Format:**
```json
{
  "system": "You are a helpful assistant",
  "prompt": "User message",
  "response": "Assistant response"
}
```

---

## 9.3 Training Configuration

### 9.3.1 Basic Training Configuration

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # Dataset
    dataset: ${input.dataset}

    # Learning rate and batch size
    learning_rate: 5e-5
    per_device_train_batch_size: 8
    per_device_eval_batch_size: 8
    num_epochs: 3

    # Output directory
    output_dir: ./output/model
```

### 9.3.2 Optimizer Configuration

**Supported Optimizers:**

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    optimizer: adamw_torch          # Default
```

**Optimizer Types:**

**AdamW Variants:**
- `adamw_torch`: PyTorch default AdamW
- `adamw_torch_fused`: Fused AdamW (faster)
- `adamw_8bit`: 8-bit AdamW (memory efficient)
- `adamw_bnb_8bit`: BitsAndBytes 8-bit AdamW

**Memory-Efficient Optimizers:**
- `adafactor`: Adafactor (memory efficient)
- `lomo`: LOMO (Low-Memory Optimization)
- `galore_adamw`: GaLore AdamW
- `galore_adamw_8bit`: GaLore AdamW 8-bit

**Advanced Optimizers:**
- `grokadamw`: Grok AdamW
- `stableadamw`: Stable AdamW
- `schedule_free_radamw`: Schedule-Free RAdamW

**Traditional Optimizers:**
- `sgd`: Stochastic Gradient Descent
- `adagrad`: Adagrad
- `rmsprop`: RMSprop

### 9.3.3 Learning Rate Scheduler

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    lr_scheduler_type: linear       # Default
    warmup_steps: 100
```

**Scheduler Types:**

- `linear`: Linear decay
- `cosine`: Cosine decay
- `cosine_with_restarts`: Cosine with restarts
- `polynomial`: Polynomial decay
- `constant`: Constant learning rate
- `constant_with_warmup`: Constant with warmup
- `inverse_sqrt`: Inverse square root decay
- `reduce_lr_on_plateau`: Reduce on plateau
- `cosine_with_min_lr`: Cosine with minimum learning rate
- `warmup_stable_decay`: Warmup-Stable-Decay

### 9.3.4 Optimization Settings

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # Weight decay (regularization)
    weight_decay: 0.01

    # Gradient clipping
    max_grad_norm: 1.0

    # Gradient accumulation
    gradient_accumulation_steps: 4
```

**Gradient Accumulation:**
- Effective batch size = `per_device_train_batch_size × gradient_accumulation_steps × num_gpus`
- When out of memory, reduce batch size and increase accumulation steps

### 9.3.5 Evaluation and Saving

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # Evaluation
    eval_steps: 500                 # Evaluate every 500 steps
    eval_dataset: ${input.eval_dataset}

    # Checkpoint saving
    save_steps: 500                 # Save every 500 steps

    # Logging
    logging_steps: 10               # Log every 10 steps
```

### 9.3.6 Memory Optimization

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # Gradient checkpointing
    gradient_checkpointing: true    # Save memory, reduce speed

    # Mixed precision
    fp16: true                      # FP16 (V100, RTX series)
    # or
    bf16: true                      # BF16 (recommended for A100, H100)
```

**Memory Optimization Options:**
- `gradient_checkpointing`: Saves ~30-40% memory, reduces speed by ~20%
- `fp16`: FP16 mixed precision, saves memory and improves speed
- `bf16`: BF16 mixed precision, better numerical stability (Ampere+ GPUs)

### 9.3.7 Reproducibility Settings

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft
    seed: 42                        # Random seed
```

---

## 9.4 Fine-Tuning

### 9.4.1 SFT (Supervised Fine-Tuning)

**Basic Configuration:**

```yaml
components:
  - id: sft-trainer
    type: model-trainer
    task: sft

    # Dataset
    dataset: ${input.dataset}
    eval_dataset: ${input.eval_dataset}

    # Data format
    text_column: text               # Single text column
    max_seq_length: 512

    # Training settings
    learning_rate: 5e-5
    num_epochs: 3
    per_device_train_batch_size: 4
    output_dir: ./output/sft-model
```

**Prompt-Response Format:**

```yaml
components:
  - id: sft-trainer
    type: model-trainer
    task: sft

    dataset: ${input.dataset}

    # Conversation format
    prompt_column: prompt
    response_column: response
    system_column: system           # Optional

    max_seq_length: 1024
```

**Data Validation:**
- Either `text_column` or `prompt_column` + `response_column` is required
- Error if both are specified

### 9.4.2 Sequence Packing

```yaml
components:
  - id: sft-trainer
    type: model-trainer
    task: sft

    dataset: ${input.dataset}
    text_column: text

    # Sequence packing
    packing: true                   # Combine short samples into one sequence
    max_seq_length: 512
```

**Packing Advantages:**
- Improves training efficiency with many short samples
- Increases GPU utilization
- Reduces training time

**Packing Disadvantages:**
- Sample boundaries may not be clear
- May reduce performance on some tasks

---

## 9.5 LoRA Training

### 9.5.1 LoRA Overview

LoRA (Low-Rank Adaptation) is an efficient technique for fine-tuning large models.

**Advantages:**
- Drastically reduces trainable parameters (<1%)
- Reduces memory usage
- Faster training
- Multiple LoRA adapters can be applied to one base model

### 9.5.2 Basic LoRA Configuration

```yaml
components:
  - id: lora-trainer
    type: model-trainer
    task: sft

    # Enable LoRA
    peft_adapter: lora

    # LoRA hyperparameters
    lora_r: 8                       # LoRA rank (lower = more memory savings)
    lora_alpha: 16                  # LoRA scaling (typically 2x of r)
    lora_dropout: 0.05              # Dropout rate

    # Dataset and training settings
    dataset: ${input.dataset}
    learning_rate: 1e-4             # LoRA typically uses higher learning rate
    num_epochs: 3
    output_dir: ./output/lora-adapter
```

### 9.5.3 Target Module Configuration

```yaml
components:
  - id: lora-trainer
    type: model-trainer
    task: sft
    peft_adapter: lora

    # Specify target modules
    lora_target_modules:
      - q_proj                      # Query projection
      - v_proj                      # Value projection
      - k_proj                      # Key projection
      - o_proj                      # Output projection

    lora_r: 16
    lora_alpha: 32
```

**Common Target Modules:**
- **Transformer Attention**: `q_proj`, `k_proj`, `v_proj`, `o_proj`
- **MLP**: `gate_proj`, `up_proj`, `down_proj`
- **Embedding**: `embed_tokens`, `lm_head`

**Target Module Selection Guide:**
- More modules: Better performance, more memory
- Attention only: Memory efficient, sufficient for most cases
- Attention + MLP: Better performance, more memory

### 9.5.4 LoRA Bias Configuration

```yaml
components:
  - id: lora-trainer
    type: model-trainer
    task: sft
    peft_adapter: lora

    lora_bias: none                 # none, all, lora_only
```

**Bias Options:**
- `none`: Don't train bias (default, memory efficient)
- `all`: Train all biases
- `lora_only`: Train only LoRA layer biases

### 9.5.5 QLoRA (Quantized LoRA)

QLoRA applies LoRA to a quantized base model for even more memory savings.

```yaml
components:
  - id: qlora-trainer
    type: model-trainer
    task: sft

    # LoRA settings
    peft_adapter: lora
    lora_r: 64
    lora_alpha: 16

    # 4-bit quantization
    quantization: nf4               # int4 or nf4
    bnb_4bit_compute_dtype: bfloat16
    bnb_4bit_use_double_quant: true

    # Dataset and training
    dataset: ${input.dataset}
    learning_rate: 2e-4
    num_epochs: 1
    per_device_train_batch_size: 4
    gradient_accumulation_steps: 4

    # Memory optimization
    gradient_checkpointing: true
    bf16: true
```

**Quantization Options:**
- `nf4`: NormalFloat 4-bit (recommended)
- `int4`: 4-bit integer quantization
- `int8`: 8-bit integer quantization

**QLoRA Recommended Settings:**
- Higher `lora_r` (64+)
- Higher learning rate (2e-4)
- BF16 mixed precision
- Gradient checkpointing

### 9.5.6 LoRA Hyperparameter Guide

| Parameter | Low Value | High Value | Recommended Use |
|---------|---------|---------|-----------|
| `lora_r` | 4-8 | 64-128 | Standard: 8-16, QLoRA: 64 |
| `lora_alpha` | 8-16 | 32-64 | Typically 2x of r |
| `lora_dropout` | 0.0 | 0.1 | Small datasets: 0.05-0.1 |
| `learning_rate` | 1e-5 | 5e-4 | Full FT: 5e-5, LoRA: 1e-4 |

---

## 9.6 Training Monitoring

### 9.6.1 Logging Configuration

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    # Logging
    logging_steps: 10               # Log output interval
    eval_steps: 100                 # Evaluation interval
```

**Expected Log Output:**
- Training loss
- Learning rate
- Gradient norm
- Training speed (samples/sec)

### 9.6.2 Evaluation Metrics

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    eval_dataset: ${input.eval_dataset}
    eval_steps: 500
```

**Expected Evaluation Metrics:**
- Evaluation loss
- Perplexity
- Task-specific metrics (classification accuracy, etc.)

### 9.6.3 TensorBoard Integration (Coming Soon)

TensorBoard integration will be added in future releases:

```bash
# Expected usage
tensorboard --logdir ./output/runs
```

---

## 9.7 Checkpoint Management

### 9.7.1 Checkpoint Saving

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    output_dir: ./output/checkpoints
    save_steps: 500                 # Save every 500 steps
```

**Expected Directory Structure:**
```
output/checkpoints/
  ├── checkpoint-500/
  │   ├── model.safetensors
  │   ├── config.json
  │   ├── training_args.bin
  │   └── optimizer.pt
  ├── checkpoint-1000/
  └── checkpoint-1500/
```

### 9.7.2 Resuming from Checkpoint

To be supported in future releases:

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    resume_from_checkpoint: ./output/checkpoints/checkpoint-1000
```

### 9.7.3 Saving Final Model

```yaml
components:
  - id: trainer
    type: model-trainer
    task: sft

    output_dir: ./output/final-model
```

**Expected Final Model Structure:**
```
output/final-model/
  ├── model.safetensors
  ├── config.json
  ├── tokenizer.json
  ├── tokenizer_config.json
  └── special_tokens_map.json
```

---

## 9.8 Practical Examples

### 9.8.1 Alpaca-Style Fine-Tuning

```yaml
components:
  - id: alpaca-loader
    type: datasets
    provider: huggingface
    path: tatsu-lab/alpaca
    split: train

  - id: alpaca-trainer
    type: model-trainer
    task: sft

    # LoRA settings
    peft_adapter: lora
    lora_r: 16
    lora_alpha: 32
    lora_dropout: 0.05
    lora_target_modules: [q_proj, v_proj]

    # Data settings
    dataset: ${input.dataset}
    prompt_column: instruction
    response_column: output
    max_seq_length: 512

    # Training settings
    learning_rate: 1e-4
    num_epochs: 3
    per_device_train_batch_size: 4
    gradient_accumulation_steps: 4

    # Optimization
    gradient_checkpointing: true
    fp16: true

    output_dir: ./output/alpaca-lora

workflows:
  - id: train-alpaca
    jobs:
      - id: load-data
        component: alpaca-loader

      - id: train
        component: alpaca-trainer
        input:
          dataset: ${jobs.load-data.output}
        depends_on: [load-data]
```

### 9.8.2 Training Large Models with QLoRA

```yaml
components:
  - id: qlora-trainer
    type: model-trainer
    task: sft

    # QLoRA settings
    peft_adapter: lora
    lora_r: 64
    lora_alpha: 16
    quantization: nf4
    bnb_4bit_compute_dtype: bfloat16

    # Data
    dataset: ${input.dataset}
    text_column: text
    max_seq_length: 2048
    packing: true

    # Training
    learning_rate: 2e-4
    num_epochs: 1
    per_device_train_batch_size: 1
    gradient_accumulation_steps: 16

    # Optimization
    optimizer: adamw_8bit
    gradient_checkpointing: true
    bf16: true

    output_dir: ./output/qlora-model
```

### 9.8.3 Custom Dataset Preparation and Training

```yaml
components:
  - id: local-data
    type: datasets
    provider: local
    loader: json
    data_files: ./data/custom_train.json

  - id: data-processor
    type: datasets
    method: map

  - id: custom-trainer
    type: model-trainer
    task: sft

    peft_adapter: lora
    lora_r: 8
    lora_alpha: 16

    dataset: ${input.dataset}
    prompt_column: user_input
    response_column: assistant_response

    learning_rate: 5e-5
    num_epochs: 5
    per_device_train_batch_size: 8

    output_dir: ./output/custom-model

workflows:
  - id: train-custom
    jobs:
      - id: load
        component: local-data

      - id: process
        component: data-processor
        input:
          dataset: ${jobs.load.output}
          template: ${input.template}
        depends_on: [load]

      - id: train
        component: custom-trainer
        input:
          dataset: ${jobs.process.output}
        depends_on: [process]
```

---

## Next Steps

After learning about dataset preparation:

- **Chapter 10**: External Service Integration - Utilizing API services
- **Chapter 8**: Using Local AI Models - Loading LoRA adapters and inference

Currently Available Features:
- Dataset loading and manipulation (HuggingFace, local files)
- Dataset merging, filtering, selection
- Inference with LoRA adapters (see Chapter 8)

Features to be Added:
- Model training execution
- Checkpoint management
- Training monitoring and visualization

---

**Next Chapter**: [10. External Service Integration](./10-external-service-integration.md)
