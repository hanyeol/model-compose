# Text Classification + LoRA Model Trainer Example

This example demonstrates how to fine-tune a sequence classifier using model-compose's `model-trainer` component with the `text-classification` task on the HuggingFace driver. It trains BERT-base with LoRA adapters on GLUE SST-2 for binary sentiment classification (positive/negative).

## Overview

This workflow provides a declarative Classification+LoRA training loop that:

1. **HuggingFace Trainer**: Wraps `transformers.Trainer` with `TrainingArguments` and `AutoModelForSequenceClassification`
2. **LoRA Adapters**: Attaches rank-8 LoRA adapters to BERT's `query`/`value` projections
3. **Automatic Model Provisioning**: Downloads `bert-base-uncased` on first run
4. **GLUE SST-2 Dataset**: Loads the SST-2 sentiment dataset from GLUE and trains on the `sentence` column
5. **Safe Split Selection**: Automatically picks the `validation` split for evaluation (SST-2's `test` split has masked labels — the driver rejects it and falls through)
6. **Checkpoint Output**: Saves the trained adapter under `output_dir` and returns training metrics

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python environment with `torch`, `transformers`, `datasets`, `peft`, `accelerate` (managed automatically by the component's `_get_setup_requirements`)
- A GPU with **≥4 GB VRAM** is recommended, but this example is small enough to train on **CPU in ~30 minutes** for 3 epochs.
- **~1 GB disk** for BERT weights and SST-2 dataset cache

### Why Classification + LoRA

- **Sequence Classification** is the standard task for sentiment, topic, or intent labeling. `AutoModelForSequenceClassification` adds a linear classifier head on top of the base transformer.
- **LoRA** at rank 8 keeps only ~0.3% of BERT's parameters trainable while typically matching full-fine-tune accuracy on GLUE-scale tasks.
- **SST-2** is the standard binary sentiment benchmark (67k training examples). It converges within 1–3 epochs at batch size 32.

### Environment Configuration

Navigate to this example directory:
```bash
cd examples/model-training-tasks/text-classification/huggingface
```

No additional environment configuration required.

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
         "num_epochs": 3,
         "batch_size": 32,
         "learning_rate": 5e-5
       }
     }'
   ```

   **Using Web UI:**
   - Open http://localhost:8081
   - Adjust `num_epochs`, `batch_size`, `learning_rate` if desired
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   model-compose run --input '{"num_epochs": 3}'
   ```

3. **Inspect the trained adapter:**
   ```bash
   ls ./output/classification
   # adapter_config.json  adapter_model.safetensors  tokenizer_config.json  ...
   ```

## Component Details

### Model-Trainer Component (Default)

- **Type**: `model-trainer`
- **Task**: `classification`
- **Driver**: `huggingface`
- **Base Model**: `bert-base-uncased`
- **LoRA Config**:
  - rank: 8
  - alpha: 16
  - dropout: 0.05
  - target_modules: `query`, `value` (BERT self-attention names)
- **Label Names**: `[negative, positive]` (bakes `id2label` / `label2id` into the saved checkpoint)

### Model Information: bert-base-uncased

- **Developer**: Google Research
- **Parameters**: 110 million
- **Type**: Encoder-only bidirectional transformer
- **License**: Apache 2.0
- **Trainable parameters after LoRA**: ~300K (~0.3%)

## Workflow Details

### "Fine-tune BERT for SST-2 Sentiment Classification" Workflow (Default)

**Description**: Fine-tune BERT-base with LoRA adapters on GLUE SST-2 for binary sentiment classification, then return the checkpoint directory and training metrics.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `dataset` | string | No | `glue/sst2` | HuggingFace dataset name or local path |
| `num_epochs` | int | No | `3` | Number of training epochs |
| `batch_size` | int | No | `32` | Per-device train batch size |
| `learning_rate` | float | No | `5e-5` | AdamW initial learning rate |
| `output_dir` | string | No | `./output/classification` | Where the trained adapter is saved |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `output_dir` | string | Directory containing the saved LoRA adapter + tokenizer |
| `train_loss` | float | Final training loss |
| `metrics` | object | Full `Trainer.train()` metrics (train_runtime, samples_per_second, ...) |

## Label Handling

The driver resolves the label list in this priority order:

1. **Explicit `label_names` in the action config** (this example uses `[negative, positive]`)
2. **`ClassLabel.names` on the dataset's label feature** (SST-2 has this too)
3. **A scan of distinct values in the split**

The resolved `num_labels` and `id2label` / `label2id` mappings are passed to `AutoModelForSequenceClassification.from_pretrained` so the classifier head has the right output size and the saved checkpoint can decode predictions back to human-readable labels.

If your dataset's raw label values are non-contiguous (e.g. `{1, 2}` instead of `{0, 1}`), the driver automatically builds a `label_remap` and rewrites the labels before training. Non-integer labels (floats, strings, None) are rejected explicitly at training start rather than silently coerced.

## Split Handling

`_load_datasets` picks the evaluation split by trying `validation` → `eval` → `test` in that order. GLUE SST-2's `test` split has all labels masked to `-1`, so the driver detects this and falls through to `validation`. This means:

- With `dataset: glue/sst2` you get `train` for training and `validation` for evaluation automatically.
- If none of the candidates has usable labels, evaluation is skipped rather than falling back to an arbitrary split.

## System Requirements

### Minimum

- **CPU**: Any modern multi-core CPU
- **RAM**: 4 GB
- **Disk**: 2 GB
- **Training time**: ~30 minutes for 3 epochs on CPU (Apple Silicon: ~15 minutes)

### Recommended

- **GPU**: any CUDA GPU with ≥4 GB VRAM (this is a tiny workload)
- **Training time**: ~5 minutes for 3 epochs on RTX 3060

## Customization

### Use a different classification dataset

```yaml
action:
  dataset: glue/cola             # Grammatical acceptability (2 classes)
  text_column: sentence
  label_names: [unacceptable, acceptable]
```

Or a multi-class task:

```yaml
action:
  dataset: ag_news               # 4-class news topic
  text_column: text
  label_names: [world, sports, business, sci-tech]
```

### Use QLoRA (4-bit quantized base)

For a larger encoder like `deberta-v3-large`:

```yaml
component:
  type: model-trainer
  task: text-classification
  driver: huggingface
  model: microsoft/deberta-v3-large
  lora:
    rank: 8
    alpha: 16
    target_modules: [query_proj, value_proj]
  quantization:
    type: nf4
    compute_dtype: bfloat16
  action:
    dataset: glue/sst2
    text_column: sentence
    label_names: [negative, positive]
```

Note: quantization requires `lora` to be set (the driver rejects the combination otherwise).

### Chain with a datasets component

Pre-load and pre-shuffle a dataset in one job and pass it to the trainer:

```yaml
components:
  - id: sst2
    type: datasets
    driver: huggingface
    action:
      method: load
      path: glue
      name: sst2
      shuffle: true

  - id: trainer
    type: model-trainer
    task: text-classification
    driver: huggingface
    model: bert-base-uncased
    lora:
      rank: 8
      target_modules: [query, value]
    action:
      dataset: ${jobs.load-data.output}
      text_column: sentence
      label_names: [negative, positive]
      output_dir: ./output/classification

workflow:
  jobs:
    - id: load-data
      component: sst2
    - id: train
      component: trainer
      depends_on: [load-data]
```

## Troubleshooting

- **`num_labels` mismatch error**: your dataset has more (or fewer) distinct labels than declared. Remove `label_names` to let the driver auto-detect, or fix the list.
- **Non-integer label rejected**: the driver refuses float/bool/string labels because `int(0.8)` would silently collapse to 0. Bucket or cast your labels before training.
- **Slow training on CPU**: expected — CPU inference for BERT is fine but training at batch 32 is heavy. Reduce `batch_size` or use a GPU.
- **`datasets` version incompatibility**: the driver pins `datasets>=2.14,<4.0`. If you have a newer version globally, model-compose's isolated runtime installs the pinned version.

## Using the trained classifier

After training, load the adapter with a `model` component of task `text-classification`:

```yaml
component:
  type: model
  task: text-classification
  model: bert-base-uncased
  peft_adapters:
    - type: lora
      model: ./output/classification
  action:
    text: ${input.text}
```

Because the adapter checkpoint saved `id2label`, the output will already be `"positive"` / `"negative"` rather than `0` / `1`.

## Related Examples

- `examples/model-training-tasks/sft-lora/huggingface/` — TinyLlama SFT+LoRA on the Alpaca instruction dataset
- `examples/model-tasks/text-classification/` — using a pre-trained (or your fine-tuned) classifier for inference
