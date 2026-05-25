# Datasets Component

The datasets component provides declarative dataset loading and transformation built on top of the HuggingFace `datasets` library. It supports loading from the HuggingFace Hub or local files, concatenating multiple datasets, selecting subsets by rows or columns, filtering, and mapping with templated formatting.

## Basic Configuration

```yaml
component:
  type: datasets
  action:
    method: load
    provider: huggingface
    path: tatsu-lab/alpaca
    split: train
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `datasets` |
| `actions` | array | `[]` | List of dataset operations (load, concat, select, filter, map) |

All dataset behavior is driven through actions; the component itself has no other top-level fields.

## Methods

### Load

Load a dataset from a provider. The provider determines the remaining fields.

```yaml
component:
  type: datasets
  action:
    method: load
    provider: huggingface
    path: tatsu-lab/alpaca
    split: train
    fraction: 0.1
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `load` |
| `provider` | string | **required** | Dataset provider: `huggingface`, `local` |
| `split` | string | `null` | Dataset split to load (e.g., `train`, `test`, `validation`) |
| `streaming` | boolean | `false` | Enable streaming mode for large datasets |
| `keep_in_memory` | boolean | `false` | Keep dataset in memory |
| `cache_dir` | string | `null` | Directory to cache downloaded files |
| `save_infos` | boolean | `false` | Save dataset info to cache |
| `fraction` | float | `null` | Fraction of dataset to load (0.0 ~ 1.0) |
| `shuffle` | boolean | `false` | Shuffle dataset before applying fraction selection |

**HuggingFace provider fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | **required** | HuggingFace dataset name or path |
| `name` | string | `null` | Dataset configuration name |
| `revision` | string | `null` | Dataset revision/version to load |
| `token` | string | `null` | Authentication token for private datasets |
| `trust_remote_code` | boolean | `false` | Allow executing remote code for dataset loading |

**Local provider fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `loader` | string | **required** | Loader type: `json`, `csv`, `parquet`, `text` |
| `data_files` | string/array/object | `null` | Path to data files (string, list, or split mapping) |
| `data_dir` | string | `null` | Directory containing data files |

### Concat

Concatenate multiple datasets.

```yaml
action:
  method: concat
  datasets:
    - ${jobs.load-first.output}
    - ${jobs.load-second.output}
  direction: vertical
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `concat` |
| `datasets` | array | **required** | List of datasets to concatenate |
| `direction` | string | `vertical` | `vertical` for rows, `horizontal` for columns |
| `info` | any | `null` | Dataset info to use for the concatenated dataset |
| `split` | string | `null` | Name of the split for the concatenated dataset |

### Select

Select a subset of rows by index or columns by name.

```yaml
# Select columns
action:
  method: select
  dataset: ${jobs.load.output}
  axis: columns
  columns: ["instruction", "output"]

# Select rows
action:
  method: select
  dataset: ${jobs.load.output}
  axis: rows
  indices: [0, 1, 2, 5, 10]
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `select` |
| `dataset` | string | **required** | Source dataset to select from |
| `axis` | string | `columns` | `rows` (by indices) or `columns` (by names) |
| `indices` | array | `null` | Row indices to select (when `axis: rows`) |
| `columns` | array | `null` | Column names to select (when `axis: columns`) |

### Filter

Filter rows in a dataset.

```yaml
action:
  method: filter
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `filter` |

### Map

Apply a template-based transformation to produce a new column from existing columns.

```yaml
action:
  method: map
  dataset: ${jobs.load.output}
  template: "Instruction: {instruction}\nResponse: {output}"
  output_column: text
  remove_columns: ["instruction", "output"]
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `map` |
| `dataset` | string | **required** | Source dataset to map |
| `template` | string | **required** | Template string with `{column_name}` placeholders |
| `output_column` | string | **required** | Name of the new column to create |
| `remove_columns` | array | `null` | Columns to remove after mapping |

## Multiple Actions

A single component can declare multiple dataset operations:

```yaml
component:
  type: datasets
  actions:
    - id: load
      method: load
      provider: huggingface
      path: ${input.path}
      split: ${input.split}
      fraction: ${input.fraction}

    - id: concat
      method: concat
      datasets: ${input.datasets}

    - id: select-columns
      method: select
      dataset: ${input.dataset}
      axis: columns
      columns: ${input.columns}

    - id: select-rows
      method: select
      dataset: ${input.dataset}
      axis: rows
      indices: ${input.indices}
```

## Usage Examples

### Load and Format for Training

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

workflows:
  - id: prepare-training-data
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
```

### Merge Two Datasets

```yaml
workflows:
  - id: concat-datasets
    jobs:
      - id: load-first
        component: dataset
        action: load
        input:
          path: tatsu-lab/alpaca
          split: train

      - id: load-second
        component: dataset
        action: load
        input:
          path: yahma/alpaca-cleaned
          split: train

      - id: concat
        component: dataset
        action: concat
        input:
          datasets:
            - ${jobs.load-first.output}
            - ${jobs.load-second.output}
        depends_on: [load-first, load-second]
```

### Local Dataset Loading

```yaml
component:
  type: datasets
  action:
    method: load
    provider: local
    loader: json
    data_files: ./data/training-set.jsonl
```

```yaml
component:
  type: datasets
  action:
    method: load
    provider: local
    loader: csv
    data_files:
      train: ./data/train.csv
      test: ./data/test.csv
    split: train
```

### Private Dataset with Authentication

```yaml
component:
  type: datasets
  action:
    method: load
    provider: huggingface
    path: my-org/private-dataset
    token: ${env.HUGGINGFACE_TOKEN}
    split: train
```

## Variable Interpolation

```yaml
component:
  type: datasets
  action:
    method: load
    provider: huggingface
    path: ${env.DATASET_PATH | tatsu-lab/alpaca}
    split: ${input.split | train}
    fraction: ${input.fraction as number | 1.0}
    streaming: ${input.streaming as boolean | false}
```

## Best Practices

1. **Use `fraction` for iteration**: Load a small fraction during development to keep workflows snappy
2. **Cache locally**: Set `cache_dir` to avoid re-downloading large datasets on every run
3. **Stream for huge datasets**: Enable `streaming: true` when the dataset does not fit in memory
4. **Format with `map`**: Use the `map` method to build the exact text column shape your trainer expects
5. **Pin revisions**: Set `revision:` for reproducible training runs

## Common Use Cases

- **Training data preparation**: Combine with [model-trainer.md](model-trainer.md) to feed fine-tuning jobs
- **Evaluation set assembly**: Load test/validation splits and forward to evaluators
- **Dataset transformation**: Pre-process before vectorization for [vector-store.md](vector-store.md)
- **Sample inspection**: Use `select` with `axis: rows` to extract small samples for debugging
