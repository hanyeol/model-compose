# Tokenizer Component

The tokenizer component provides standalone tokenization capabilities for text processing. It loads a tokenizer model once at the component level and reuses it across actions, supporting encode, decode, and token counting operations.

## Basic Configuration

```yaml
component:
  type: tokenizer
  task: text
  model: gpt2
  action:
    method: encode
    text: ${input.text}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `tokenizer` |
| `task` | string | **required** | Tokenizer task type: `text` |
| `driver` | string | `huggingface` | Tokenizer driver |
| `model` | string/object | **required** | Model identifier or configuration object |
| `use_fast` | boolean | `true` | Whether to use the fast tokenizer if available |

### Model Source Configuration

You can specify models as a string or detailed configuration:

```yaml
# Simple string format
model: gpt2

# HuggingFace model with options
model:
  provider: huggingface
  repository: bert-base-uncased
  revision: main
  token: ${env.HUGGINGFACE_TOKEN}

# Local model
model: /path/to/tokenizer
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | string | `huggingface` | Model provider: `huggingface`, `local` |
| `repository` | string | **required** | HuggingFace model repository (when provider is `huggingface`) |
| `path` | string | **required** | Local model path (when provider is `local`) |
| `revision` | string | `null` | Model version or branch |
| `cache_dir` | string | `null` | Directory to cache model files |
| `local_files_only` | boolean | `false` | Force loading from local files only |
| `token` | string | `null` | HuggingFace access token for private models |

## Methods

### Encode

Tokenize text into token IDs:

```yaml
component:
  type: tokenizer
  task: text
  model: gpt2
  action:
    method: encode
    text: ${input.text}
    max_length: 512
    padding: true
    truncation: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `encode` |
| `text` | string | **required** | Input text to tokenize |
| `max_length` | integer | `null` | Maximum token length |
| `padding` | boolean | `false` | Whether to pad to max_length |
| `truncation` | boolean | `false` | Whether to truncate to max_length |

**Output:**
```json
{
  "input_ids": [15496, 995],
  "attention_mask": [1, 1]
}
```

### Decode

Convert token IDs back to text:

```yaml
component:
  type: tokenizer
  task: text
  model: gpt2
  action:
    method: decode
    token_ids: ${input.token_ids}
    skip_special_tokens: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `decode` |
| `token_ids` | array | **required** | Token IDs to decode |
| `skip_special_tokens` | boolean | `true` | Whether to skip special tokens in output |

**Output:**
```json
{
  "text": "Hello world"
}
```

### Count

Count the number of tokens in text:

```yaml
component:
  type: tokenizer
  task: text
  model: gpt2
  action:
    method: count
    text: ${input.text}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `count` |
| `text` | string | **required** | Input text to count tokens for |

**Output:**
```json
{
  "count": 5
}
```

## Multiple Actions

Define multiple actions for different tokenization operations:

```yaml
component:
  type: tokenizer
  task: text
  model: gpt2
  actions:
    - id: encode
      method: encode
      text: ${input.text}
      max_length: 512
      truncation: true

    - id: count
      method: count
      text: ${input.text}

    - id: decode
      method: decode
      token_ids: ${input.token_ids}
```

## Usage Examples

### Token Counting for Input Validation

```yaml
components:
  - id: token-counter
    type: tokenizer
    task: text
    model: gpt2
    action:
      method: count
      text: ${input.text}

workflows:
  - id: validate-input
    jobs:
      - id: count-tokens
        component: token-counter
        input:
          text: ${input.prompt}
        output:
          token_count: ${output.count}
```

### Preprocessing for Model Input

```yaml
components:
  - id: tokenizer
    type: tokenizer
    task: text
    model: bert-base-uncased
    action:
      method: encode
      text: ${input.text}
      max_length: 512
      padding: true
      truncation: true

  - id: classifier
    type: model
    task: text-classification
    model: bert-base-uncased
    action:
      text: ${input.text}
```

### Private Model with Authentication

```yaml
component:
  type: tokenizer
  task: text
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    token: ${env.HUGGINGFACE_TOKEN}
  action:
    method: count
    text: ${input.text}
```

### Offline Usage

```yaml
component:
  type: tokenizer
  task: text
  model:
    provider: huggingface
    repository: gpt2
    cache_dir: /data/tokenizer-cache
    local_files_only: true
  action:
    method: encode
    text: ${input.text}
```

## Variable Interpolation

Tokenizer components support dynamic configuration:

```yaml
component:
  type: tokenizer
  task: text
  model: ${env.TOKENIZER_MODEL | gpt2}
  action:
    method: encode
    text: ${input.text}
    max_length: ${input.max_length as integer | 512}
    truncation: ${input.truncation as boolean | true}
```

## Best Practices

1. **Reuse tokenizers**: The tokenizer is loaded once per component and reused across all action invocations
2. **Match tokenizer to model**: Use the same tokenizer model as your inference model for consistent results
3. **Use fast tokenizers**: Keep `use_fast: true` (default) for better performance
4. **Token counting**: Use the `count` method to validate input lengths before sending to models
5. **Caching**: Set `cache_dir` to persist downloaded tokenizer files

## Common Use Cases

- **Input validation**: Count tokens before sending to LLM APIs with token limits
- **Text preprocessing**: Encode text for custom model pipelines
- **Token analysis**: Analyze tokenization behavior across different models
- **Batch preparation**: Encode and pad texts for batch processing
