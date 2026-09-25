# Model Component

The model component enables loading and running AI/ML models locally using HuggingFace transformers. It supports various tasks including text generation (causal LM), chat completion, text-to-text transforms (seq2seq for translation/summarization), text embedding, classification, image-to-text processing, and text-to-speech synthesis.

## Basic Configuration

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  action:
    prompt: ${input.prompt}
    params:
      max_output_length: 1024
      temperature: 0.7
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `model` |
| `task` | string | **required** | Model task type: `text-generation`, `chat-completion`, `text-to-text`, `text-embedding`, `text-classification`, `text-reranking`, `image-to-text`, `image-text-to-text`, `image-embedding`, `video-embedding`, `text-to-speech`, `speech-to-text`, `speaker-diarization`, `voice-activity-detection`, `image-generation`, `image-upscale`, `text-to-video`, `image-to-video`, `video-to-video`, `image-to-3d`, `talking-head`, `lip-sync`, `face-detection`, `face-tracking`, `pose-detection`, `face-embedding`, `shot-boundary-detection`, `music-generation`, `music-source-separation`, `music-transcription`, `music-beat-tracking` |
| `driver` | string | `huggingface` | Inference framework: `huggingface`, `unsloth`, `vllm`, `llamacpp`, `custom` (availability depends on task) |
| `model` | string/object | **required** | Model identifier or configuration object (see below) |
| `device_mode` | string | `auto` | Device allocation mode: `auto`, `single` |
| `device` | string | `cpu` | Computation device: `cpu`, `cuda`, `cuda:0`, etc. |
| `precision` | string | `null` | Numerical precision: `auto`, `float32`, `float16`, `bfloat16` |
| `quantization` | string/object | `null` | Quantization type shorthand (`int8`, `int4`, `fp4`, `nf4`) or `{ type, compute_dtype?, double_quant? }` |
| `low_cpu_mem_usage` | boolean | `false` | Load model with minimal CPU RAM usage |
| `peft_adapters` | array | `null` | PEFT adapters (e.g. LoRA) to load on top of the base model |
| `preload` | boolean | `true` | Load the model at startup |
| `on_demand` | boolean/object | `false` | Enable on-demand loading; `true` uses defaults, or `{ priority, idle_timeout }` |
| `runtime_spec` | object | `null` | Runtime hints — `{ vram, ram }` in MB |
| `fast_tokenizer` | boolean | `true` | Use fast tokenizer if available (language-model tasks only) |
| `max_seq_length` | integer | `2048` | Maximum sequence length (language-model tasks only) |

### Model Source Configuration

You can specify models as a string or detailed configuration. A string that looks like a local path is auto-inflated to `{ provider: local, path: <string> }`; otherwise it becomes `{ provider: huggingface, repository: <string> }`.

```yaml
# Simple string format (auto-resolved to HuggingFace)
model: microsoft/DialoGPT-medium

# Detailed HuggingFace configuration
model:
  provider: huggingface
  repository: microsoft/DialoGPT-medium
  revision: main
  filename: pytorch_model.bin
  cache_dir: ./models_cache
  local_files_only: false
  token: ${env.HUGGINGFACE_TOKEN}

# Detailed local configuration
model:
  provider: local
  path: ./local_models/my-model
  format: pytorch  # pytorch | safetensors | onnx | gguf | tensorrt
```

**HuggingFace source (`provider: huggingface`):**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `repository` | string | **required** | HuggingFace model repository |
| `filename` | string | `null` | Specific file within the repository |
| `revision` | string | `null` | Model version or branch |
| `cache_dir` | string | `null` | Directory to cache the model files |
| `local_files_only` | boolean | `false` | Force loading from local files only |
| `token` | string | `null` | HuggingFace access token for private models |

**Local source (`provider: local`):**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | **required** | Filesystem path to the model |
| `format` | string | `pytorch` | Model file format: `pytorch`, `safetensors`, `onnx`, `gguf`, `tensorrt` |

## Task Types and Examples

### Text Generation

Generate text from prompts using language models:

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  action:
    prompt: ${input.prompt}
    max_output_length: 2048
    num_return_sequences: 1
    params:
      temperature: 0.8
      top_p: 0.9
      top_k: 50
      do_sample: true
    output:
      generated_text: ${response.generated_text}
```

**Text Generation Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_output_length` | integer | `1024` | Maximum tokens to generate |
| `min_output_length` | integer | `1` | Minimum tokens to generate |
| `num_return_sequences` | integer | `1` | Number of generated sequences to return |
| `stop_sequences` | array | `null` | Stop generation sequences |
| `batch_size` | integer | `1` | Batch processing size |
| `params.temperature` | float | `1.0` | Sampling temperature (creativity) |
| `params.top_p` | float | `0.9` | Nucleus sampling threshold |
| `params.top_k` | integer | `50` | Top-K sampling limit |
| `params.num_beams` | integer | `1` | Beam search width |
| `params.do_sample` | boolean | `true` | Enable sampling vs greedy |

### Chat Completion

Generate conversational responses using chat models:

```yaml
component:
  type: model
  task: chat-completion
  model: HuggingFaceTB/SmolLM3-3B
  action:
    messages:
      - role: system
        content: ${input.system_prompt}
      - role: user
        content: ${input.user_message}
    params:
      max_output_length: 1024
      temperature: 0.7
      top_p: 0.9
    output:
      response: ${response.message.content}
```

**Message Format:**

```yaml
messages:
  - role: system
    content: You are a helpful assistant.
  - role: user 
    content: What is machine learning?
  - role: assistant
    content: Machine learning is...
  - role: tool
    call_id: call_123
    name: search_web
    content: Search results...
```

**Chat Completion Component Options:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `chat_template` | string | `null` | Inline Jinja chat template string, overriding the tokenizer default. Applies to `huggingface`, `vllm`, and `llamacpp` drivers. |
| `tools` | array | `null` | Catalog of tools this component exposes for tool calling. |
| `reasoning_parser` | object | `null` | Rules for extracting reasoning spans (e.g. `<think>...</think>`) from raw model output. Applied before `tool_call_parser`. See below. |
| `tool_call_parser` | object | `null` | Rules for extracting tool calls from raw model output. See below. |

**`reasoning_parser` Fields:**

Extracts reasoning spans (chain-of-thought text the model emits before its actual answer) into `reasoning` blocks so downstream consumers can log or hide them separately. Runs before `tool_call_parser`; anything inside a reasoning span is opaque and is not scanned for tool calls. Unclosed reasoning spans are dropped silently (non-streaming) or trimmed at flush (streaming).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `start_tag` | string | `null` | Literal marker that opens a reasoning span (e.g., `<think>`). Omit for models that begin thinking at the start of the response (e.g., Qwen3 thinking mode) — everything up to `end_tag` is treated as reasoning. |
| `end_tag` | string | (required) | Literal marker that closes a reasoning span (e.g., `</think>`). |

Examples:

```yaml
# DeepSeek-R1 / GLM-Z1 / Kimi-K1.5: <think>...</think>
reasoning_parser:
  start_tag: '<think>'
  end_tag:   '</think>'

# Qwen3 thinking mode: response begins inside the reasoning span; only the close marker separates it
reasoning_parser:
  end_tag: '</think>'
```

**`tool_call_parser` Fields:**

Declares where tool calls appear in the model's text and how to parse them. The parser scans left-to-right; text outside a matched call is preserved as a `text` block, and everything inside is emitted as `tool_call` blocks in the message's `content`. Malformed bodies (invalid JSON, missing keys, incomplete pythonic call) are treated as text so a single bad output cannot swallow the rest of the response.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `batch_start_tag` | string | `null` | Outer marker that opens a batch of tool calls (e.g., DeepSeek's `<｜tool_calls_begin｜>`). Must be paired with `batch_end_tag`. |
| `batch_end_tag` | string | `null` | Outer marker that closes a batch of tool calls. |
| `start_tag` | string | (required) | Literal marker that opens a single tool call (e.g., `<tool_call>`, `<\|python_tag\|>`, `[TOOL_CALLS]`). |
| `end_tag` | string | `null` | Literal marker that closes a single tool call. Omit to consume exactly one JSON or pythonic value after `start_tag`. |
| `format` | string | `json` | Body syntax: `json` or `pythonic`. |
| `name_key` | string | `name` | JSON field holding the tool name. Ignored when `name_marker` is set. |
| `arguments_key` | string | `arguments` | JSON field holding the tool arguments. Ignored when `arguments_marker` is set. |
| `name_marker` | object | `null` | Locate the tool name as a literal between two markers inside the body (instead of as a JSON field). Fields: `prefix`, `suffix`. |
| `arguments_marker` | object | `null` | Locate the arguments payload inside a wrapper (e.g., a fenced code block) inside the body. Fields: `open`, `close`. The extracted region is parsed as JSON. |

Examples:

```yaml
# Hermes / Qwen style: <tool_call>{...}</tool_call>
tool_call_parser:
  start_tag: '<tool_call>'
  end_tag: '</tool_call>'

# Llama 3.1: <|python_tag|>{...}   (no closing marker; "parameters" instead of "arguments")
tool_call_parser:
  start_tag: '<|python_tag|>'
  arguments_key: parameters

# Mistral: [TOOL_CALLS][{...}, {...}]   (single tag, body may hold multiple calls)
tool_call_parser:
  start_tag: '[TOOL_CALLS]'

# Llama 3.2 pythonic: <|python_tag|>[foo(x="v"), bar(y=1)]
tool_call_parser:
  start_tag: '<|python_tag|>'
  format: pythonic

# DeepSeek V3 / R1: nested batch envelope, name as body literal, arguments in a fenced JSON block
tool_call_parser:
  batch_start_tag: '<｜tool_calls_begin｜>'
  batch_end_tag:   '<｜tool_calls_end｜>'
  start_tag:       '<｜tool_call_begin｜>'
  end_tag:         '<｜tool_call_end｜>'
  name_marker:
    prefix: 'function<｜tool_sep｜>'
    suffix: "\n"
  arguments_marker:
    open:  "```json\n"
    close: "\n```"
```

Each emitted tool call carries a generated `id` (`call_<ulid>`) so downstream `tool` messages can reference it via `tool_call_id`.

**vLLM Driver Options:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `options` | object | `null` | Engine options forwarded to vLLM when loading the model (see `AsyncEngineArgs`). |

Example:

```yaml
component:
  type: model
  task: chat-completion
  driver: vllm
  model: mistralai/Mistral-7B-Instruct-v0.3
  chat_template: |
    {%- for message in messages %}
    <|{{ message.role }}|>
    {{ message.content }}</s>
    {%- endfor %}
  options:
    dtype: bfloat16
    gpu_memory_utilization: 0.9
```

### Text Embedding

Generate vector embeddings for text:

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
  action:
    text: ${input.text}
    output:
      embedding: ${response.embedding}
      dimensions: ${response.embedding | length}
```

### Text Classification

Classify text into predefined categories:

```yaml
component:
  type: model
  task: text-classification
  model: cardiffnlp/twitter-roberta-base-sentiment-latest
  labels: [ positive, negative, neutral ]
  action:
    text: ${input.text}
    output:
      predicted_label: ${response.label}
      confidence: ${response.score}
      all_scores: ${response.scores}
```

### Text Reranking

Rerank a set of candidate documents against a query using a cross-encoder model. This is the typical second stage of a retrieval pipeline: a vector store (bi-encoder) fetches a broad candidate set with high recall, then a cross-encoder rescores each (query, document) pair for higher precision.

```yaml
component:
  type: model
  task: text-reranking
  model: BAAI/bge-reranker-v2-m3
  action:
    query: ${input.query}
    documents: ${input.candidates}
    top_k: 5
    output:
      results: ${result}
```

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string \| list | **required** | Query text to rank documents against. A list runs one independent reranking job per query. |
| `documents` | list | **required** | Candidate documents. Each item is a string, or an object when `document_field` is set. When `query` is a list, this must be a list-of-lists (one candidate list per query). |
| `document_field` | string | `null` | Field name to read the text from when documents are objects. Required for object documents; ignored for strings. |
| `top_k` | integer | `null` | Keep only the top K results per query after scoring. |
| `score_threshold` | float | `null` | Drop any result whose score is below this threshold. |
| `return_documents` | bool | `true` | Include the original document under `document` in each result. Set to `false` to return only `index` and `score`. |
| `batch_size` | integer | `32` | Number of (query, document) pairs the driver scores in a single forward pass. |
| `max_input_length` | integer | `null` | Maximum tokens per (query, document) pair; longer pairs are truncated. Defaults to the tokenizer's `model_max_length`. |
| `params.normalize` | bool | `true` | Apply sigmoid to raw logits so scores are in `[0, 1]`. Set to `false` to return raw logits. |

**Result Shape:**

Each result is a list of ranked items, sorted by score descending:

```yaml
- index: 3          # position in the original documents list
  score: 0.94       # relevance score (sigmoid-normalized by default)
  document: { ... } # original document (string or object), omitted when return_documents is false
```

**Example — Rerank vector-store search results:**

```yaml
components:
  - id: embedder
    type: model
    task: text-embedding
    model: BAAI/bge-m3

  - id: vec-store
    type: vector-store
    driver: qdrant
    endpoint: http://localhost:6333
    actions:
      - id: search
        method: search
        collection: docs
        query: ${input.vector}
        top_k: 50
        output_fields: [ text, source ]

  - id: reranker
    type: model
    task: text-reranking
    model: BAAI/bge-reranker-v2-m3
    action:
      query: ${input.query}
      documents: ${input.candidates}
      document_field: text
      top_k: 5

workflows:
  - id: rag-search
    jobs:
      - id: embed
        component: embedder
        input: { text: ${input.query} }
      - id: retrieve
        component: vec-store
        action: search
        input: { vector: ${jobs.embed.output} }
        depends_on: [ embed ]
      - id: rerank
        component: reranker
        input:
          query: ${input.query}
          candidates: ${jobs.retrieve.output}
        depends_on: [ retrieve ]
```

**Example — Batch reranking (multiple independent queries):**

```yaml
action:
  query: ${input.queries}       # list of queries
  documents: ${input.candidates}  # list-of-lists, one per query
  top_k: 3
```

The output is a list of ranked-result lists, one per query.

### Typed Decision

Answer a set of typed questions about a piece of text in a single forward pass. Each question is one of `noul` (yes/no), `choice` (one of N named options), or `score` (an ordered rating scale). The scorer reads candidate-answer logits directly, so the answer is always one of the values the schema allows — no free-form generation, no JSON parsing, no schema drift.

Runs on `driver: custom` with one of three families: `laya`, `kev`, or `nimble`. Pick one per component; run two components if you need to combine them.

```yaml
component:
  type: model
  task: typed-decision
  driver: custom
  family: laya                        # 'laya' | 'kev' | 'nimble'
  preset: multilingual                # laya-only: 'english' | 'multilingual' (default) | 'typed-decisions'
  action:
    text: ${input.text}
    schema: ${input.schema}
    return_probabilities: true
```

**Component Settings** (common to all families):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `family` | enum | **required** | `laya`, `kev`, or `nimble`. Picks the scoring backend. |
| `model` | string \| object | family default | HuggingFace repo id or local checkpoint directory. Optional for `laya` (defaults to the `convaiinnovations/laya` bundle repo). Required for `kev` and `nimble`. |

**Family-specific settings:**

`laya`:
- `preset` (enum, default `multilingual`) — checkpoint to load from the bundle repo: `english` (ModernBERT-large, 512-token context), `multilingual` (mmBERT-base, 100+ languages, up to 1024 tokens, extendable to 8192 via `max_seq_length`), or `typed-decisions` (fine-tuned on the four typed-decisions workflows).
- `max_seq_length` (int, optional) — override per-call encoder token budget.
- `max_head_length` (int, optional) — override per-call per-question head token budget.
- `fast` (bool, default `false`) — enable the TileLang CUDA fast path (Linux+x86_64 with a supported NVIDIA GPU; the driver installs `tilelang` automatically).

`kev`:
- `backend` (enum, default `auto`) — `auto`, `torch`, or `mlx`. `auto` picks MLX on Apple Silicon with hybrid Qwen3.5 bases and Torch elsewhere.
- `max_state_length` (int, default `8192`) — tokens allotted to the shared state (context) portion.
- `max_branch_length` (int, default `8192`) — tokens allotted to per-question branches.

`nimble`:
- `base_model` (string, default `Qwen/Qwen3.5-9B`) — base model the adapter is merged onto. The driver merges the adapter once on first startup and caches the merged snapshot.
- `max_seq_length` (int, default `4096`) — maximum sequence length the scorer accepts.

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `text` | string \| list | **required** | Unstructured text the scorer judges. A list scores many inputs against the same schema in one call. |
| `schema` | object | **required** | Map of question id to a question spec (see below). |
| `batch_size` | integer | `1` | Number of texts the driver scores in a single forward pass when `text` is a list. |
| `return_probabilities` | bool | `false` | Include per-candidate scores per question in `fields[qid].scores`. |
| `return_logits` | bool | `false` | Include raw pre-softmax logits per question. Only `nimble` surfaces logits at the API level. |

**Question specs** (values in `schema`):

| Question type | Required fields | Optional fields | Answer type |
|---------------|-----------------|-----------------|-------------|
| `noul` (yes/no) | `type`, `instructions` | `criteria: {true?: description, false?: description}` | boolean (`p(true) >= 0.5`) |
| `choice` | `type`, `instructions`, `criteria: {name: description, ...}` | — | winning option name |
| `score` | `type`, `instructions`, `criteria: [level0, level1, ...]` | — | expected level (float, averaged over the softmax across levels) |

**Result Shape:**

```yaml
decision:
  urgent: true                    # noul → boolean
  category: infra                 # choice → option name
  severity: 4.6                   # score → expected level (float)
fields:                           # present only when return_probabilities is true
  urgent:   { scores: { true: 0.94, false: 0.06 } }
  category: { scores: { payments: 0.31, infra: 0.58, product: 0.11 } }
  severity: { scores: { "0": 0.01, "1": 0.03, "2": 0.09, "3": 0.24, "4": 0.63 } }
```

**Example — Support-ticket triage with `laya` (multilingual):**

```yaml
component:
  type: model
  task: typed-decision
  driver: custom
  family: laya
  preset: multilingual
  action:
    text: ${input.text}
    schema:
      urgent:
        type: noul
        instructions: Is this an urgent operational incident?
        criteria:
          true:  A production system is currently unavailable to real users.
          false: Non-blocking issue, question, or feature request.
      category:
        type: choice
        instructions: Which team owns this?
        criteria:
          payments: Billing, checkout, or payment processing.
          infra:    Servers, deployment, or platform outages.
          product:  UX, feature behavior, or product feedback.
      severity:
        type: score
        instructions: Rate business impact from 1 (trivial) to 5 (critical).
        criteria:
          - trivial:  cosmetic or single-user issue
          - low:      minor inconvenience for a few users
          - medium:   measurable revenue or productivity loss
          - high:     broad customer impact, some workaround exists
          - critical: total outage with no workaround
    return_probabilities: true
```

Full examples: [`typed-decision-laya`](../../../../examples/model-tasks/typed-decision-laya), [`typed-decision-kev`](../../../../examples/model-tasks/typed-decision-kev), [`typed-decision-nimble`](../../../../examples/model-tasks/typed-decision-nimble).

### Text to Text (Translation, Summarization, and other seq2seq tasks)

Transform a source text with an encoder-decoder (seq2seq) model. This one task covers translation, summarization, and any other paraphrasing/rewriting workload that a seq2seq model can perform. Task selection with T5-family models is done by prefixing the source text (e.g. `"translate English to German: ..."`, `"summarize: ..."`); BART/MarianMT/Pegasus models are usually fine-tuned to a single task and don't need a prefix.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `text-to-text` |
| `driver` | string | `huggingface` | Model inference framework: `huggingface`, `custom` |
| `architecture` | string | `auto` | HuggingFace model architecture: `auto`, `t5`, `bart`, `marian`, `pegasus`, `mbart` |

**Example — Translation with MarianMT:**

```yaml
component:
  type: model
  task: text-to-text
  driver: huggingface
  model: Helsinki-NLP/opus-mt-en-fr
  action:
    text: ${input.text}
    output:
      translated_text: ${result}
```

**Example — Summarization with BART:**

```yaml
component:
  type: model
  task: text-to-text
  driver: huggingface
  architecture: bart
  model: facebook/bart-large-cnn
  action:
    text: ${input.article_text}
    max_input_length: 1024
    params:
      do_sample: false
      num_beams: 4
    output:
      summary: ${result}
```

**Example — T5 with a task prefix:**

```yaml
component:
  type: model
  task: text-to-text
  driver: huggingface
  architecture: t5
  model: google/flan-t5-base
  action:
    text: "translate English to German: ${input.text}"
```

**Text-to-Text Parameters:**

Same generation parameter shape as text-generation, but defaults favor deterministic beam search:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_output_length` | integer | `null` | Maximum tokens to generate |
| `min_output_length` | integer | `1` | Minimum tokens to generate |
| `num_return_sequences` | integer | `1` | Number of generated sequences to return |
| `stop_sequences` | array | `null` | Stop generation sequences |
| `params.num_beams` | integer | `4` | Beam search width |
| `params.length_penalty` | float | `1.0` | Length penalty for beam search |
| `params.early_stopping` | boolean | `true` | Stop when all beams finish |
| `params.do_sample` | boolean | `false` | Enable sampling (turn on for creative rewriting) |
| `params.temperature`/`params.top_k`/`params.top_p` | — | — | Only used when `params.do_sample: true` |

### Image-to-Text

Generate text descriptions from images:

```yaml
component:
  type: model
  task: image-to-text
  model: Salesforce/blip-image-captioning-base
  action:
    image: ${input.image_url}
    output:
      caption: ${response.generated_text}
```

### Image-Text-to-Text

Answer a text prompt about one or more images with a vision-language model (VLM). Suitable for visual question answering, image-conditioned instruction following (e.g. document OCR, chart understanding), and single-turn multimodal reasoning. For multi-turn chat, use [`chat-completion`](#chat-completion) with a vision-capable model instead.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `image-text-to-text` |
| `driver` | string | `huggingface` | Model inference framework: `huggingface`, `vllm` |
| `architecture` | string | `auto` | HuggingFace model architecture: `auto`, `qwen2-vl`, `qwen2.5-vl`, `llava`, `llava-next`, `idefics3`, `internvl` |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | string/array | **required** | Text prompt; a list is treated as a batch of prompts |
| `image` | string/array | **required** | Image or images for the prompt; use a list-of-lists to pass multiple images per prompt in a batch |
| `system_prompt` | string | `null` | System instruction prepended before the user prompt |
| `max_input_length` | integer | `null` | Maximum tokens accepted per input prompt |
| `max_output_length` | integer | `null` | Maximum tokens to generate |
| `min_output_length` | integer | `1` | Minimum tokens to generate before generation may stop |
| `num_return_sequences` | integer | `1` | Number of generated sequences to return per input |
| `stop_sequences` | string/array | `null` | Sequences that terminate generation when produced |
| `batch_size` | integer | `1` | Number of prompts processed per batch |
| `streaming` | boolean | `false` | Emit generated tokens incrementally as they are produced |
| `params.do_sample` | boolean | `true` | Enable sampling; disable for deterministic beam/greedy decoding |
| `params.temperature` | float | `1.0` | Sampling temperature (used when `params.do_sample: true`) |
| `params.top_k` | integer | `50` | Top-K sampling cutoff (used when `params.do_sample: true`) |
| `params.top_p` | float | `0.9` | Nucleus sampling threshold (used when `params.do_sample: true`) |
| `params.num_beams` | integer | `1` | Beam search width |
| `params.length_penalty` | float | `1.0` | Length penalty applied during beam search |
| `params.early_stopping` | boolean | `true` | Stop when all beams finish generating |

**Example — Visual question answering with Qwen2.5-VL (HuggingFace):**

```yaml
component:
  type: model
  task: image-text-to-text
  driver: huggingface
  architecture: qwen2.5-vl
  model: Qwen/Qwen2.5-VL-3B-Instruct
  action:
    image: ${input.image as image}
    prompt: ${input.prompt as text}
    max_output_length: 512
    params:
      do_sample: false
    output:
      answer: ${result}
```

**Example — Multiple images in one prompt:**

```yaml
component:
  type: model
  task: image-text-to-text
  driver: huggingface
  architecture: qwen2.5-vl
  model: Qwen/Qwen2.5-VL-3B-Instruct
  action:
    image:
      - ${input.image_a as image}
      - ${input.image_b as image}
    prompt: "Compare the two images and describe the differences."
    max_output_length: 512
```

**Example — Document OCR with olmOCR (vLLM):**

```yaml
component:
  type: model
  task: image-text-to-text
  driver: vllm
  model: allenai/olmOCR-2-7B-1025-FP8
  options:
    max_model_len: 16384
    gpu_memory_utilization: 0.9
  action:
    image: ${input.image as image}
    prompt: |-
      Attached is one page of a document. Return the plain text as markdown,
      converting equations to LaTeX and tables to markdown.
    max_output_length: 8000
    params:
      do_sample: false
    output:
      markdown: ${result}
```

### Image Embedding

Generate vector embeddings for images. Use this for visual similarity search, image-based dedup/clustering, or building a retrieval index over local image folders. Bi-encoder style: encode once, compare with cosine similarity downstream.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `image-embedding` |
| `driver` | string | `huggingface` | Model inference framework: `huggingface`, `custom` |
| `architecture` | string | `auto` | HuggingFace model architecture: `auto`, `clip`, `siglip`, `dinov2` |

**Architecture notes:**

- `auto` — Loads with `AutoModel` + `AutoImageProcessor`. If the loaded model exposes `get_image_features` (CLIP/SigLIP family), that path is used; otherwise the encoder's `last_hidden_state` is pooled per `params.pooling`.
- `clip` — Explicit `CLIPModel.get_image_features()`. `params.pooling` is ignored (the model has a built-in projection head).
- `siglip` — Explicit `SiglipModel.get_image_features()`. `params.pooling` is ignored.
- `dinov2` — Runs `AutoModel` and pools `last_hidden_state` per `params.pooling` (default `cls`).

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | string \| list \| stream | **required** | Input image (path, URL, or base64), a list of images, or an async stream. |
| `batch_size` | integer | `8` | Number of images per forward pass. |
| `params.pooling` | string | `cls` | Pooling strategy over patch embeddings: `cls`, `mean`, `max`. Ignored by architectures with a built-in pooler (CLIP/SigLIP). |
| `params.normalize` | bool | `true` | L2-normalize output embeddings so cosine similarity reduces to a dot product downstream. |

**Result Shape:**

Single image input → a single flat vector (`List[float]`). List input → a list of vectors (`List[List[float]]`). Stream input → an async iterator that yields one vector per image.

**Example — CLIP for image similarity search:**

```yaml
component:
  type: model
  task: image-embedding
  driver: huggingface
  architecture: clip
  model: openai/clip-vit-base-patch32
  action:
    image: ${input.paths}
    batch_size: 16
```

**Example — DINOv2 with mean pooling:**

```yaml
component:
  type: model
  task: image-embedding
  driver: huggingface
  architecture: dinov2
  model: facebook/dinov2-base
  action:
    image: ${input.image}
    params:
      pooling: mean
      normalize: true
```

**Example — Persist image vectors to a vector store:**

```yaml
components:
  - id: embedder
    type: model
    task: image-embedding
    driver: huggingface
    architecture: clip
    model: openai/clip-vit-base-patch32

  - id: vec-store
    type: vector-store
    driver: qdrant
    endpoint: http://localhost:6333
    actions:
      - id: insert
        method: insert
        collection: images
        vector: ${input.vector}
        vector_id: ${input.id}

workflows:
  - id: index-images
    jobs:
      - id: embed
        component: embedder
        input: { image: ${input.path} }
      - id: store
        component: vec-store
        action: insert
        input:
          id: ${input.id}
          vector: ${jobs.embed.output}
        depends_on: [ embed ]
```

### Video Embedding

Compute a fixed-length vector embedding for a video. The action accepts a sampled sequence of frames (as PIL images or paths); the model produces a single vector per video, suitable for semantic video search, dedup, or clustering. Use the `video-frame-extractor` component to produce the frame list, or pass frames yielded by another component.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `video-embedding` |
| `driver` | string | `huggingface` | Inference framework (currently `huggingface`) |
| `architecture` | string | `auto` | Model architecture: `auto`, `xclip`, `videomae`. `auto` infers from the model config |
| `model` | string / config | **required** | Model source (HuggingFace repo ID such as `microsoft/xclip-base-patch32`, or a local path) |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | image / list | **required** | Frame images for a single video, a list of frames, a list of per-video frame batches, or a stream of batches |
| `batch_size` | int | `1` | Number of videos processed per batch |
| `params.normalize` | bool | `true` | L2-normalize the output vector |

**Example:**

```yaml
component:
  id: video-embed
  type: model
  task: video-embedding
  model: microsoft/xclip-base-patch32
  action:
    frames: ${input.frames}
    params:
      normalize: true
    output: ${result}
```

**Result Shape:**

A single vector per video (list of floats). When the input is a list of per-video frame batches, the action returns a list of vectors.

```json
[0.021, -0.114, 0.087, ...]
```

**Supported architectures:**
- `xclip` — Microsoft X-CLIP (video-text contrastive; e.g., `microsoft/xclip-base-patch32`).
- `videomae` — VideoMAE (masked autoencoder for video; e.g., `MCG-NJU/videomae-base`).

Typical pairing: chain `video-frame-extractor` to sample frames from a source video, feed those frames into `video-embedding`, then insert the vector into a `vector-store`.

### Face Detection

Detect faces in an image and return bounding boxes (with optional facial landmarks). This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `face-detection` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family: `blazeface` or `insightface` |
| `model` | string/object | family-dependent | Model source. For `blazeface`, a MediaPipe `.tflite` file (auto-downloads BlazeFace short-range to `~/.cache/models/mediapipe/` when omitted). For `insightface`, a HuggingFace-style identifier or a local path to an InsightFace model pack (auto-downloads `antelopev2` to `~/.cache/models/insightface/` when omitted). |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | image/array | **required** | Input image, list of images, or async stream of images |
| `return_landmarks` | bool | `false` | Include facial keypoints in the result (6 for BlazeFace, up to 106 for InsightFace `antelopev2`). |
| `bounding_box_padding` | float | `0.0` | Grow each returned bounding box by this fraction of its width/height on every side, then clip to the image (e.g. `0.2` = +20%). Useful when downstream consumers crop the box and need extra context (hair, chin). |
| `batch_size` | int | `1` | Number of images to process per batch |
| `params.min_confidence` | float | `0.5` | Minimum detection confidence threshold (0.0 - 1.0). Passed to the InsightFace detector as `det_thresh`. |

**Family-Specific Fields (`insightface`):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.detection_size` | [int, int] | `[640, 640]` | Detector input size in pixels. Larger sizes improve recall on small faces at the cost of throughput. |
| `params.max_num_faces` | int | `0` | Maximum number of faces returned per image. `0` disables the limit. Applied at detection time (before embedding-style postprocessing). |

**Example — BlazeFace:**

```yaml
component:
  type: model
  task: face-detection
  driver: custom
  family: blazeface
  action:
    image: ${input.image as image}
    return_landmarks: true
    params:
      min_confidence: 0.6
    output:
      faces: ${result.faces}
```

**Example — InsightFace:**

```yaml
component:
  type: model
  task: face-detection
  driver: custom
  family: insightface
  model:
    provider: local
  action:
    image: ${input.image as image}
    params:
      min_confidence: 0.5
      detection_size: [ 960, 960 ]
    output:
      faces: ${result.faces}
```

**Result Shape:**

```json
{
  "faces": [
    {
      "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 280 },
      "score": 0.97,
      "landmarks": [{ "x": 123, "y": 45 }, ...]
    }
  ],
  "width": 1280,
  "height": 720
}
```

When the input is a list, the action returns a list of result dicts. When the input is an async stream, the action returns an async iterator that yields per-frame result dicts.

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `blazeface` | [MediaPipe Tasks (Face Detector)](https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector) (pip) | Lightweight, optimised for close-up frontal faces (webcam / selfie distance). Fast on CPU but misses profile / small / heavily occluded faces at typical video distances. |
| `insightface` | [deepinsight/insightface](https://github.com/deepinsight/insightface) (pip) | SCRFD detector from an InsightFace model pack (e.g. `antelopev2`). Handles small, profile, and off-frontal faces far better than BlazeFace. Uses `onnxruntime`; prefers CUDA/CoreML/DirectML/ROCm providers when available. |

### Face Tracking

Track faces across a sequence of video frames. Per-frame detections are grouped into identity tracks by cosine similarity on the face embedding, and consecutive hits for the same identity are merged into timecoded segments. Accepts a single frame sequence, a list of sequences, or an async stream of frame batches; runs the tracker lazily on streamed input without buffering the whole video. This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `face-tracking` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `insightface`) |
| `model` | string/object | **required** | Model pack. For `insightface`, either a HuggingFace-style identifier or a local path to an InsightFace model pack directory (e.g. `antelopev2` layout with `.onnx` files). |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | image/array | **required** | Frame images to analyze. May be a single frame, a flat list, a list of batches, or a stream of batches. |
| `frame_rate` | float | **required** | Frames per second of the sampled sequence, used to derive per-frame timestamps. |
| `time_offset` | float/list | `0.0` | Timestamp offset in seconds for the first frame of each batch. Scalar is broadcast; a list is paired per batch. |
| `return_tracks` | bool | `true` | Include the per-identity track list (`tracks[]`) in the result. |
| `return_embedding` | bool | `false` | Include the track's L2-normalized identity centroid embedding in the result. |
| `return_track_image` | bool | `false` | Include one representative face crop per segment (highest-scoring frame in the segment, cropped at the detected bounding box in the frame's native resolution). |
| `return_detections` | bool | `false` | Include a frame-centric view (`detections[]`) alongside tracks, tagging each face with its `track_id`. |
| `return_frame_image` | bool | `false` | Include the source frame image on each per-frame detection entry. Requires `return_detections: true`. |
| `return_metadata` | bool | `false` | Include processing metadata (`frame_count`, ...) in the result. In streaming mode, appended as a terminal `metadata` chunk. |
| `bounding_box_padding` | float | `0.0` | Padding ratio applied when cropping the returned face image. Grows the box by this fraction of its width/height on each side (e.g. `0.2` = +20% on each side). Only affects `segment.image`; embeddings and clustering still use the un-padded box. |
| `batch_size` | int | `1` | Number of frame batches per iteration. |
| `streaming` | bool | `false` | Emit per-frame detections and confirmed track/segment events incrementally as an event stream instead of a single result dict. See [Streaming chunks](#streaming-chunks-face-tracking) below. |
| `params.similarity_threshold` | float | `0.4` | Cosine similarity above which two faces are grouped into the same track. |
| `params.min_face_size` | int | `0` | Minimum face bounding box size in pixels. `0` disables the filter. |
| `params.min_frame_count` | int | `1` | Discard tracks that appear in fewer than this many frames. |
| `params.max_face_count_per_frame` | int | `0` | Maximum number of faces to keep per frame. `0` disables the limit. |
| `params.merge_gap` | float | `0.5` | Extra seconds a person may be undetected before their segment is split; consecutive frames always merge. |
| `params.max_track_distance` | float | `1.5` | Maximum distance a track may move between consecutive detections, as a multiple of the face size. `0` disables the check. |

At least one of `return_tracks` or `return_detections` must be `true`. `return_frame_image` requires `return_detections: true`.

**Family-Specific Fields (`insightface`):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `return_gender_age` | bool | `false` | Include the track's `gender` and `age` from its highest-scoring frame. Requires a model pack that ships gender/age submodels (e.g. `antelopev2`, `buffalo_l`). |
| `params.detection_threshold` | float | `0.5` | Face detection confidence threshold passed to the InsightFace detector (0.0 - 1.0). |
| `params.detection_size` | [int, int] | `[640, 640]` | Detector input size in pixels. Larger sizes improve recall on small faces at the cost of throughput. |

**Example:**

```yaml
component:
  type: model
  task: face-tracking
  driver: custom
  family: insightface
  model:
    provider: local
    path: ./.models/antelopev2
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    time_offset: 0.0
    return_track_image: true
    return_embedding: false
    params:
      similarity_threshold: 0.4
      min_face_size: 40
      min_frame_count: 2
      merge_gap: 1.0
    output:
      tracks: ${result.tracks}
```

**Result Shape:**

```json
{
  "tracks": [
    {
      "track_id": 1,
      "segments": [
        { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "duration": "0:00:06.500", "score": 0.94 },
        { "start_time": "0:00:14.000", "end_time": "0:00:17.000", "duration": "0:00:03.000", "score": 0.88 }
      ],
      "frame_count": 21,
      "score": 0.94,
      "gender": "female",
      "age": 32,
      "embedding": [0.012, -0.045, ...]
    }
  ],
  "detections": [
    {
      "number": 60,
      "timestamp": "0:00:02.000",
      "faces": [
        { "track_id": 1, "bounding_box": { "x": 812, "y": 240, "width": 168, "height": 210 }, "score": 0.94 }
      ]
    }
  ],
  "frame_count": 40
}
```

- `tracks[i].track_id` is stable across the whole video for one identity; the same id can span multiple segments if the person leaves and re-enters the frame.
- `tracks[i].score` is the highest detection confidence across all frames in the track. Useful for ranking or filtering tracks.
- `tracks[i].segments[j].score` is the detection confidence of the representative frame for that segment (the highest-scoring frame within the segment; the same frame `image` is cropped from when `return_track_image` is enabled).
- `tracks[i].embedding` is present only when `return_embedding` is enabled — a 512-d L2-normalized centroid (for antelopev2) suitable for cosine matching against an identity DB or for merging tracks that turn out to be the same person.
- `tracks[i].segments[j].image` is present only when `return_track_image` is enabled — the highest-scoring frame in that segment, cropped at the detected bounding box in the frame's native resolution.
- `tracks[i].gender` (`"male"` / `"female"`) and `tracks[i].age` (integer) are present only when `return_gender_age` is enabled — taken from the track's highest-scoring frame. Absent if the model pack doesn't ship gender/age submodels.
- `detections[]` is present only when `return_detections` is enabled — one entry per analyzed frame, each with `number`, `timestamp`, and a `faces[]` list of per-frame detections tagged by `track_id`. When `return_frame_image` is enabled, each entry also carries the source frame `image`.
- `detections[i].faces[j].interpolated: true` appears when the face was filled in for a gap between real detections in the same track. Interpolated entries have no `image` even under `return_track_image`.
- `frame_count` at the top level is the total number of sampled frames analyzed. Only present when `return_metadata: true`.

When `frames` is a list of sequences, the action returns a list of result dicts (one per sequence). When it is an async stream of frame batches, the action returns an async iterator that yields one result dict per batch.

<a id="streaming-chunks-face-tracking"></a>

**Streaming chunks (`streaming: true`):**

Instead of a single result dict, the action returns an async iterator of chunks. Each chunk has a `type` field discriminating four kinds:

| `type` | When emitted | Payload shape |
|--------|--------------|---------------|
| `"detection"` | Once per analyzed frame, after `merge_gap` has passed since the frame. Suppressed when `return_detections: false`. | `{ type, number, timestamp, faces: [...], image? }` |
| `"segment"` | Whenever a track's ongoing segment is sealed (either the track went idle past `merge_gap` or the stream ended). Suppressed when `return_tracks: false`. | `{ type, track_id, start_time, end_time, duration, frame_count, score, image?, gender?, age? }` |
| `"track"` | Whenever a track goes idle past `merge_gap` (may re-emit if the same `track_id` becomes active again). Suppressed when `return_tracks: false`. | `{ type, track_id, segment_count, frame_count, score, embedding?, gender?, age? }` |
| `"metadata"` | Once at the end of the stream, only when `return_metadata: true`. | `{ type: "metadata", frame_count }` |

Downstream consumers should treat the latest `track` chunk for a given `track_id` as canonical — if the same id emits multiple `track` chunks (identity re-entered the frame), each supersedes the previous.

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `insightface` | [deepinsight/insightface](https://github.com/deepinsight/insightface) (pip) | Detection + 512-d ArcFace embedding. Requires an InsightFace model pack (e.g. `antelopev2`). Uses `onnxruntime`; prefers CUDA/CoreML/DirectML/ROCm providers when available. |

### Pose Detection

Detect human bodies in an image and return per-pose keypoints (2D, optionally 3D, optionally with segmentation mask). This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `pose-detection` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family: `blazepose` or `yolo` |
| `model` | string | `__default__` | Path or URL of the model checkpoint. `__default__` auto-downloads the family-specific default (BlazePose Lite `.task` for `blazepose`, YOLOv8n-pose `.pt` for `yolo`). |

**Common Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | image/array | **required** | Input image, list of images, or async stream of images |
| `max_pose_count` | int | `1` | Maximum number of poses to detect per image (>= 1) |
| `return_keypoints` | bool | `true` | Include 2D pose keypoints (pixel coordinates) in the result |
| `batch_size` | int | `1` | Number of images to process per batch |
| `params.min_confidence` | float | `0.5` | Minimum pose-detection confidence threshold (0.0 - 1.0) |

**Family-Specific Fields:**

| Field | `blazepose` | `yolo` | Description |
|-------|:-----------:|:------:|-------------|
| `params.min_presence_confidence` | ✓ | – | Minimum keypoint-presence confidence (0.0 - 1.0) |
| `params.min_tracking_confidence` | ✓ | – | Minimum tracking confidence. Reserved for future video running mode. |
| `return_keypoints_3d` | ✓ | – | Include real-world 3D keypoints in meters (hip-centered) |
| `return_segmentation_mask` | ✓ | – | Include per-pose grayscale segmentation mask (PIL image) |

Fields marked `–` are silently ignored by families that don't support them.

**Example — BlazePose:**

```yaml
component:
  type: model
  task: pose-detection
  driver: custom
  family: blazepose
  action:
    image: ${input.image as image}
    max_pose_count: 2
    return_keypoints_3d: true
    params:
      min_confidence: 0.6
    output:
      poses: ${result.poses}
```

**Example — YOLO:**

```yaml
component:
  type: model
  task: pose-detection
  driver: custom
  family: yolo
  action:
    image: ${input.image as image}
    max_pose_count: 5
    params:
      min_confidence: 0.4
    output:
      poses: ${result.poses}
```

**Result Shape (BlazePose):**

```json
{
  "poses": [
    {
      "keypoints": [
        { "x": 320, "y": 240, "z": -0.12, "visibility": 0.99, "presence": 0.98 },
        ...
      ],
      "keypoints_3d": [
        { "x": 0.05, "y": -0.10, "z": -0.20, "visibility": 0.99, "presence": 0.98 },
        ...
      ],
      "segmentation_mask": "<PIL grayscale image>"
    }
  ],
  "width": 1280,
  "height": 720
}
```

BlazePose returns **33 keypoints** per detected pose (see [MediaPipe pose landmark diagram](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker#pose_landmarker_model)). `keypoints_3d` and `segmentation_mask` are only present when explicitly enabled.

**Result Shape (YOLO):**

```json
{
  "poses": [
    {
      "keypoints": [
        { "x": 320, "y": 240, "visibility": 0.94 },
        ...
      ]
    }
  ],
  "width": 1280,
  "height": 720
}
```

YOLOv8-pose returns **17 COCO keypoints** per detected pose (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles). `visibility` is the per-keypoint confidence score. YOLO does not produce 3D keypoints or segmentation masks.

List and async-stream inputs behave the same way as face detection.

### Pose Tracking

Track people (as poses) across a sequence of video frames. Per-frame pose detections are grouped into tracks by the underlying tracker's persistent `track_id`, and consecutive hits for the same track are merged into timecoded segments with optional interpolation across small gaps. Accepts a single frame sequence, a list of sequences, or an async stream of frame batches; runs lazily on streamed input without buffering the whole video. This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `pose-tracking` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `yolo`) |
| `model` | string | `__default__` | Path or URL of the model checkpoint. `__default__` auto-downloads the family default (YOLOv8n-pose `.pt` for `yolo`). |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | image/array | **required** | Frame images to analyze. May be a single frame, a flat list, a list of batches, or a stream of batches. |
| `frame_rate` | float | **required** | Frames per second of the sampled sequence, used to derive per-frame timestamps. |
| `time_offset` | float/list | `0.0` | Timestamp offset in seconds for the first frame of each batch. Scalar is broadcast; a list is paired per batch. |
| `skeleton_format` | string | `"natural"` | Layout used when rendering the skeleton image. One of `"natural"` or `"openpose"`. |
| `skeleton_background` | color/null | `null` | Skeleton canvas background: `null` yields a transparent RGBA PNG; a color (e.g. `"#000000"`) flattens to that solid RGB fill. |
| `return_tracks` | bool | `true` | Include the per-person track list (`tracks[]`) in the result. |
| `return_keypoints` | bool | `true` | Include natural-layout 2D keypoints on each pose. Also emitted per-frame when `return_detections` is enabled. |
| `return_openpose_keypoints` | bool | `false` | Include OpenPose BODY_18 keypoints on each pose. Also emitted per-frame when `return_detections` is enabled. |
| `return_skeleton_image` | bool | `false` | Include a rendered skeleton image on each pose (see `skeleton_format` / `skeleton_background`). Also emitted per-frame when `return_detections` is enabled. |
| `return_track_image` | bool | `false` | Include one representative body crop per segment (highest-scoring frame in the segment, cropped at the detected bounding box in the frame's native resolution). |
| `return_detections` | bool | `false` | Include a frame-centric view (`detections[]`) alongside tracks, tagging each pose with its `track_id`. |
| `return_frame_image` | bool | `false` | Include the source frame image on each per-frame detection entry. Requires `return_detections: true`. |
| `return_metadata` | bool | `false` | Include processing metadata (`frame_count`, ...) in the result. In streaming mode, appended as a terminal `metadata` chunk. |
| `bounding_box_padding` | float | `0.0` | Padding ratio applied when cropping the returned body image. Grows the box by this fraction of its width/height on each side. |
| `batch_size` | int | `1` | Number of frame batches per iteration. |
| `streaming` | bool | `false` | Emit per-frame detections and confirmed track/segment events incrementally as an event stream. See [Streaming chunks](#streaming-chunks-pose-tracking) below. |
| `params.min_confidence` | float | `0.5` | Minimum detection confidence a pose must reach. |
| `params.min_presence_confidence` | float | `0.5` | Minimum presence confidence a keypoint must reach to be kept. |
| `params.min_pose_size` | int | `0` | Minimum pose bounding box size in pixels. `0` disables the filter. |
| `params.min_frame_count` | int | `1` | Discard tracks that appear in fewer than this many frames. |
| `params.max_pose_count_per_frame` | int | `0` | Maximum number of poses to keep per frame. `0` disables the limit. |
| `params.merge_gap` | float | `0.5` | Extra seconds a person may be undetected before their segment is split; consecutive frames always merge. |

At least one of `return_tracks` or `return_detections` must be `true`. `return_frame_image` requires `return_detections: true`.

**Family-Specific Fields (`yolo`):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.tracker` | string | `"bytetrack"` | Underlying Ultralytics tracker used for association. One of `"bytetrack"` or `"botsort"`. |

**Example:**

```yaml
component:
  type: model
  task: pose-tracking
  driver: custom
  family: yolo
  model: __default__
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    time_offset: 0.0
    skeleton_format: openpose
    return_track_image: true
    return_skeleton_image: true
    params:
      min_confidence: 0.5
      min_frame_count: 3
      merge_gap: 0.5
      tracker: bytetrack
    output:
      tracks: ${result.tracks}
```

**Result Shape:**

```json
{
  "tracks": [
    {
      "track_id": 3,
      "segments": [
        { "start_time": "0:00:01.500", "end_time": "0:00:07.200", "duration": "0:00:05.700", "frame_count": 172, "score": 0.91, "bounding_box": { "x": 440, "y": 120, "width": 260, "height": 640 } }
      ],
      "frame_count": 172,
      "score": 0.91
    }
  ],
  "detections": [
    {
      "number": 45,
      "timestamp": "0:00:01.500",
      "poses": [
        { "track_id": 3, "bounding_box": { "x": 440, "y": 120, "width": 260, "height": 640 }, "score": 0.91 }
      ]
    }
  ],
  "frame_count": 210
}
```

- `tracks[i].track_id` is the tracker's persistent id — stable across a segment; the same id can span multiple segments if the person leaves and re-enters the frame.
- `tracks[i].score` is the highest detection confidence across all frames in the track.
- `tracks[i].segments[j].keypoints` / `openpose_keypoints` / `skeleton_image` are present only when the corresponding `return_*` flag is enabled — taken from the highest-scoring frame in the segment.
- `tracks[i].segments[j].image` is present only when `return_track_image` is enabled.
- `detections[]` is present only when `return_detections` is enabled — one entry per analyzed frame, each with a `poses[]` list tagged by `track_id`. Each pose carries the same optional fields (`keypoints`, `openpose_keypoints`, `skeleton_image`, `image`) as track segments.
- `detections[i].poses[j].interpolated: true` appears when the pose was filled in for a gap between real detections in the same track. Interpolated entries have no `image` even under `return_track_image`.
- `frame_count` at the top level is the total number of sampled frames analyzed. Only present when `return_metadata: true`.

When `frames` is a list of sequences, the action returns a list of result dicts (one per sequence). When it is an async stream of frame batches, the action returns an async iterator that yields one result dict per batch.

<a id="streaming-chunks-pose-tracking"></a>

**Streaming chunks (`streaming: true`):**

Instead of a single result dict, the action returns an async iterator of chunks. Each chunk has a `type` field discriminating four kinds:

| `type` | When emitted | Payload shape |
|--------|--------------|---------------|
| `"detection"` | Once per analyzed frame, after `merge_gap` has passed. Suppressed when `return_detections: false`. | `{ type, number, timestamp, poses: [...], image? }` |
| `"segment"` | When a track's ongoing segment is sealed. Suppressed when `return_tracks: false`. | `{ type, track_id, start_time, end_time, duration, frame_count, score, bounding_box, keypoints?, openpose_keypoints?, skeleton_image?, image? }` |
| `"track"` | When a track goes idle past `merge_gap` (may re-emit for the same `track_id` if it reactivates). Suppressed when `return_tracks: false`. | `{ type, track_id, segment_count, frame_count, score }` |
| `"metadata"` | Once at the end of the stream, only when `return_metadata: true`. | `{ type: "metadata", frame_count }` |

Downstream consumers should treat the latest `track` chunk for a given `track_id` as canonical.

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `yolo` | [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) (pip: `ultralytics`, `lap`) | YOLOv8-pose weights. Uses Ultralytics' built-in tracker (ByteTrack or BoT-SORT) for id association. 17 COCO keypoints natively; converted to OpenPose BODY_18 when requested. |

### Object Detection

Detect objects in an image and return per-object bounding boxes with class labels and confidence scores. This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `object-detection` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `yolo`) |
| `model` | string | `__default__` | Path or URL of the model checkpoint. `__default__` auto-downloads YOLOv11n (`yolo11n.pt`) to `~/.cache/models/ultralytics/`. Any Ultralytics YOLO detection or segmentation checkpoint (`.pt`) is accepted; masks from segmentation checkpoints are ignored. |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | image/array | **required** | Input image, list of images, or async stream of images |
| `labels` | list[str] | `null` | Restrict detections to these class labels. Unknown labels raise an error listing available labels. If omitted, all classes are returned |
| `max_object_count` | int | `300` | Maximum detections per image (>= 1) |
| `bounding_box_padding` | float | `0.0` | Expand each output bounding box outward by this ratio of its width/height on every side (e.g. `0.1` = 10%). Clamped to image bounds. Useful when feeding boxes downstream to crop or SAM box prompts |
| `batch_size` | int | `1` | Number of images to process per batch |
| `params.min_confidence` | float | `0.25` | Minimum detection confidence threshold (0.0 - 1.0) |
| `params.iou_threshold` | float | `0.7` | IoU threshold for non-maximum suppression (0.0 - 1.0) |
| `params.agnostic_nms` | bool | `false` | Perform class-agnostic NMS across all labels |

**Example:**

```yaml
component:
  type: model
  task: object-detection
  driver: custom
  family: yolo
  action:
    image: ${input.image as image}
    labels: [ person, dog ]
    bounding_box_padding: 0.05
    params:
      min_confidence: 0.4
    output:
      objects: ${result.objects}
```

**Result Shape:**

```json
{
  "objects": [
    {
      "label": "person",
      "label_id": 0,
      "score": 0.87,
      "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 460 }
    }
  ],
  "width": 1920,
  "height": 1080
}
```

`bounding_box` uses top-left origin as `{x, y, width, height}` in pixel coordinates. When `bounding_box_padding > 0`, boxes are expanded before clamping to image bounds. List and async-stream inputs behave the same way as face detection.

### Object Tracking

Track objects across a sequence of video frames. Per-frame detections are grouped into tracks by the underlying tracker's persistent `track_id`, and consecutive hits for the same track are merged into timecoded segments with optional interpolation across small gaps. Accepts a single frame sequence, a list of sequences, or an async stream of frame batches; runs lazily on streamed input without buffering the whole video. This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `object-tracking` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `yolo`) |
| `model` | string | `__default__` | Path or URL of the model checkpoint. `__default__` auto-downloads the family default (YOLOv8n `.pt` for `yolo`). |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | image/array | **required** | Frame images to analyze. May be a single frame, a flat list, a list of batches, or a stream of batches. |
| `frame_rate` | float | **required** | Frames per second of the sampled sequence, used to derive per-frame timestamps. |
| `time_offset` | float/list | `0.0` | Timestamp offset in seconds for the first frame of each batch. Scalar is broadcast; a list is paired per batch. |
| `labels` | string[]/null | `null` | Class labels detections are restricted to. Unset returns all classes. |
| `return_tracks` | bool | `true` | Include the per-object track list (`tracks[]`) in the result. |
| `return_track_image` | bool | `false` | Include one representative object crop per segment (highest-scoring frame in the segment, cropped at the detected bounding box in the frame's native resolution). |
| `return_detections` | bool | `false` | Include a frame-centric view (`detections[]`) alongside tracks, tagging each object with its `track_id`. |
| `return_frame_image` | bool | `false` | Include the source frame image on each per-frame detection entry. Requires `return_detections: true`. |
| `return_metadata` | bool | `false` | Include processing metadata (`frame_count`, ...) in the result. In streaming mode, appended as a terminal `metadata` chunk. |
| `bounding_box_padding` | float | `0.0` | Padding ratio applied when cropping the returned object image. Grows the box by this fraction of its width/height on each side. |
| `batch_size` | int | `1` | Number of frame batches per iteration. |
| `streaming` | bool | `false` | Emit per-frame detections and confirmed track/segment events incrementally as an event stream. See [Streaming chunks](#streaming-chunks-object-tracking) below. |
| `params.min_confidence` | float | `0.25` | Minimum detection confidence an object must reach. |
| `params.iou_threshold` | float | `0.7` | IoU threshold used by non-maximum suppression. |
| `params.agnostic_nms` | bool | `false` | Whether NMS is applied across classes rather than per class. |
| `params.min_object_size` | int | `0` | Minimum object bounding box size in pixels. `0` disables the filter. |
| `params.min_frame_count` | int | `1` | Discard tracks that appear in fewer than this many frames. |
| `params.max_object_count_per_frame` | int | `0` | Maximum number of objects to keep per frame. `0` disables the limit. |
| `params.merge_gap` | float | `0.5` | Extra seconds an object may be undetected before its segment is split; consecutive frames always merge. |

At least one of `return_tracks` or `return_detections` must be `true`. `return_frame_image` requires `return_detections: true`.

**Family-Specific Fields (`yolo`):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.tracker` | string | `"bytetrack"` | Underlying Ultralytics tracker used for association. One of `"bytetrack"` or `"botsort"`. |

**Example:**

```yaml
component:
  type: model
  task: object-tracking
  driver: custom
  family: yolo
  model: __default__
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    time_offset: 0.0
    labels: [person, car]
    return_track_image: true
    params:
      min_confidence: 0.3
      min_object_size: 40
      min_frame_count: 3
      merge_gap: 0.5
      tracker: bytetrack
    output:
      tracks: ${result.tracks}
```

**Result Shape:**

```json
{
  "tracks": [
    {
      "track_id": 7,
      "label": "car",
      "label_id": 2,
      "segments": [
        { "start_time": "0:00:04.100", "end_time": "0:00:09.800", "duration": "0:00:05.700", "frame_count": 172, "label": "car", "label_id": 2, "score": 0.89, "bounding_box": { "x": 220, "y": 380, "width": 340, "height": 180 } }
      ],
      "frame_count": 172,
      "score": 0.89
    }
  ],
  "detections": [
    {
      "number": 123,
      "timestamp": "0:00:04.100",
      "objects": [
        { "track_id": 7, "label": "car", "label_id": 2, "bounding_box": { "x": 220, "y": 380, "width": 340, "height": 180 }, "score": 0.89 }
      ]
    }
  ],
  "frame_count": 300
}
```

- `tracks[i].track_id` is the tracker's persistent id — stable across a segment; the same id can span multiple segments if the object leaves and re-enters the frame.
- `tracks[i].label` / `label_id` are taken from the highest-scoring frame in the track.
- `tracks[i].score` is the highest detection confidence across all frames in the track.
- `tracks[i].segments[j].image` is present only when `return_track_image` is enabled — the highest-scoring frame in that segment, cropped at the detected bounding box (with `bounding_box_padding` applied).
- `detections[]` is present only when `return_detections` is enabled — one entry per analyzed frame, each with an `objects[]` list tagged by `track_id`.
- `detections[i].objects[j].interpolated: true` appears when the object was filled in for a gap between real detections in the same track. Interpolated entries have no `image` even under `return_track_image`.
- `frame_count` at the top level is the total number of sampled frames analyzed. Only present when `return_metadata: true`.

When `frames` is a list of sequences, the action returns a list of result dicts (one per sequence). When it is an async stream of frame batches, the action returns an async iterator that yields one result dict per batch.

<a id="streaming-chunks-object-tracking"></a>

**Streaming chunks (`streaming: true`):**

Instead of a single result dict, the action returns an async iterator of chunks. Each chunk has a `type` field discriminating four kinds:

| `type` | When emitted | Payload shape |
|--------|--------------|---------------|
| `"detection"` | Once per analyzed frame, after `merge_gap` has passed. Suppressed when `return_detections: false`. | `{ type, number, timestamp, objects: [...], image? }` |
| `"segment"` | When a track's ongoing segment is sealed. Suppressed when `return_tracks: false`. | `{ type, track_id, start_time, end_time, duration, frame_count, label, label_id, score, bounding_box, image? }` |
| `"track"` | When a track goes idle past `merge_gap` (may re-emit for the same `track_id` if it reactivates). Suppressed when `return_tracks: false`. | `{ type, track_id, label, label_id, segment_count, frame_count, score }` |
| `"metadata"` | Once at the end of the stream, only when `return_metadata: true`. | `{ type: "metadata", frame_count }` |

Downstream consumers should treat the latest `track` chunk for a given `track_id` as canonical.

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `yolo` | [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) (pip: `ultralytics`, `lap`) | YOLOv8 detection weights. Uses Ultralytics' built-in tracker (ByteTrack or BoT-SORT) for id association. |

### Image Segmentation

Generate per-region binary segmentation masks from an image. Supports **automatic mode** (masks every distinct region) and **box-prompted mode** (refines masks around user-supplied bounding boxes, e.g. from an object-detection component). This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `image-segmentation` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `sam` — Meta's Segment Anything Model via Ultralytics) |
| `model` | string | `__default__` | Path or URL of the model checkpoint. `__default__` auto-downloads `sam2_b.pt` to `~/.cache/models/ultralytics/`. Any Ultralytics SAM checkpoint (`sam_b.pt`, `sam_l.pt`, `sam2_t.pt`, `sam2_b.pt`, `sam2_l.pt`, `sam2.1_*.pt`, `mobile_sam.pt`) is accepted |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | image/array | **required** | Input image, list of images, or async stream of images |
| `box_prompt` | object or list | `null` | Bounding-box prompt(s) that constrain segmentation as `{x, y, width, height}` (single) or `[{...}, ...]` (multiple). Same shape as detection components' `bounding_box` outputs. If omitted, the task runs in automatic mode |
| `max_segment_count` | int | `100` | Maximum segments per image (>= 1). Extra segments are dropped after sorting by score |
| `return_mask` | bool | `true` | Include the per-segment binary mask (grayscale PNG: background `0`, segment `255`) in the result |
| `batch_size` | int | `1` | Number of images to process per batch |
| `params.min_confidence` | float | `0.5` | Minimum per-segment confidence (0.0 - 1.0) |
| `params.min_area` | int | `null` | Minimum mask area in pixels. Smaller masks are filtered out. If omitted, no area filter is applied |

**Example — automatic mode:**

```yaml
component:
  type: model
  task: image-segmentation
  driver: custom
  family: sam
  action:
    image: ${input.image as image}
    max_segment_count: 20
    params:
      min_confidence: 0.6
    output:
      segments: ${result.segments}
```

**Example — box-prompted (fed from object-detection):**

```yaml
jobs:
  - id: detect
    component: yolo-detector
    action:
      image: ${input.image as image}
      bounding_box_padding: 0.1
  - id: segment
    component: sam-segmenter
    action:
      image: ${input.image as image}
      box_prompt: ${detect.output.objects[*].bounding_box}
```

**Result Shape (automatic mode):**

```json
{
  "segments": [
    {
      "score": 0.92,
      "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 460 },
      "area": 12345,
      "mask": "<PNG>"
    }
  ],
  "width": 1920,
  "height": 1080
}
```

**Result Shape (box-prompted mode)** adds a `prompt_index` field per segment:

```json
{
  "segments": [
    {
      "score": 0.87,
      "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 460 },
      "area": 12345,
      "mask": "<PNG>",
      "prompt_index": 0
    }
  ],
  "width": 1920,
  "height": 1080
}
```

- `bounding_box` — `{x, y, width, height}` derived from the returned mask, top-left origin.
- `area` — Mask area in pixels.
- `mask` — Binary mask as a grayscale PNG (omitted when `return_mask: false`).
- `prompt_index` — Index into the input `box_prompt` list that this segment corresponds to (only in box-prompted mode).

Segments are sorted by `score` in descending order and truncated to `max_segment_count`. List and async-stream inputs behave the same way as face detection.

### Text to Video

Generate a short video clip from a text prompt. This task uses `driver: custom` with a `family` field to select the model family and a `preset` field to select the checkpoint variant.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `text-to-video` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `wan`) |
| `preset` | string | `t2v-a14b` | Checkpoint preset (`t2v-a14b`, `ti2v-5b`) |
| `model` | string | **required** | Model identifier — a HuggingFace repo ID or a local checkpoint directory |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | string/array | **required** | Text description of the video to generate |
| `negative_prompt` | string/array | `null` | Text describing content to avoid |
| `seed` | int | `null` | Random seed for reproducible generation |
| `batch_size` | int | `1` | Number of prompts processed per batch |
| `params.num_frames` | int | `81` | Number of frames to generate |
| `params.fps` | int | `24` | Output video frame rate |
| `params.width` | int | `1280` | Output video width in pixels |
| `params.height` | int | `720` | Output video height in pixels |
| `params.inference_steps` | int | `50` | Number of diffusion inference steps |
| `params.guidance_scale` | float | `5.0` | Classifier-free guidance scale |
| `params.shift` | float | `5.0` | Flow-matching timestep shift applied to the scheduler |

**Example:**

```yaml
component:
  type: model
  task: text-to-video
  driver: custom
  family: wan
  preset: t2v-a14b
  model: Wan-AI/Wan2.2-T2V-A14B
  device: cuda:0
  action:
    prompt: ${input.prompt as text}
    params:
      num_frames: 81
      fps: 24
      width: 1280
      height: 720
      inference_steps: 50
      guidance_scale: 5.0
```

#### Supported families

| Family | Preset | Notes |
|--------|--------|-------|
| `wan` | `t2v-a14b` | Wan2.2 T2V, 27B parameters (14B active). Requires ~80GB+ VRAM on a single GPU. |
| `wan` | `ti2v-5b` | Wan2.2 hybrid text-and-image-to-video, 5B parameters. Runs on a single 24GB GPU (e.g. RTX 4090). |

**Result Shape:**

Returns a single mp4 stream (or a list of streams for batched prompts). Each stream carries `format: "mp4"` and an `fps` attribute matching the requested frame rate.

### Image to Video

Generate a short video clip that animates an input image, optionally guided by a text prompt.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `image-to-video` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `wan`) |
| `preset` | string | `i2v-a14b` | Checkpoint preset (`i2v-a14b`, `ti2v-5b`) |
| `model` | string | **required** | Model identifier — a HuggingFace repo ID or a local checkpoint directory |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | image/array | **required** | Input image (or list/stream of images) used as the first frame |
| `prompt` | string/array | `null` | Text prompt guiding motion and content |
| `negative_prompt` | string/array | `null` | Text describing content to avoid |
| `seed` | int | `null` | Random seed for reproducible generation |
| `batch_size` | int | `1` | Number of inputs processed per batch |
| `params.num_frames` | int | `81` | Number of frames to generate |
| `params.fps` | int | `24` | Output video frame rate |
| `params.width` | int | `null` | Output video width in pixels; defaults to the input image width |
| `params.height` | int | `null` | Output video height in pixels; defaults to the input image height |
| `params.inference_steps` | int | `40` | Number of diffusion inference steps |
| `params.guidance_scale` | float | `5.0` | Classifier-free guidance scale |
| `params.shift` | float | `5.0` | Flow-matching timestep shift applied to the scheduler |

**Example:**

```yaml
component:
  type: model
  task: image-to-video
  driver: custom
  family: wan
  preset: i2v-a14b
  model: Wan-AI/Wan2.2-I2V-A14B
  device: cuda:0
  action:
    image: ${input.image as image}
    prompt: ${input.prompt | ""}
    params:
      num_frames: 81
      fps: 24
      inference_steps: 40
      guidance_scale: 5.0
```

#### Supported families

| Family | Preset | Notes |
|--------|--------|-------|
| `wan` | `i2v-a14b` | Wan2.2 I2V, 27B parameters (14B active). Requires ~80GB+ VRAM on a single GPU. |
| `wan` | `ti2v-5b` | Wan2.2 hybrid text-and-image-to-video, 5B parameters. Runs on a single 24GB GPU. |

**Result Shape:**

Returns a single mp4 stream (or a list of streams for batched inputs), each with `format: "mp4"` and an `fps` attribute matching the requested frame rate.

### Image to 3D

Generate a 3D GLB asset from a single image. This task uses `driver: custom` with a `family` field to select the model family — `pixal3d` produces a single textured GLB, while `anigen` produces a rigged mesh plus a separate skeleton visualization.

**Common Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `image-to-3d` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (`pixal3d` or `anigen`) |
| `model` | string | **required** | Model identifier — a HuggingFace repo ID or a local checkpoint directory |

**Common Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | image/array | **required** | Input image (or list/stream of images) used as the sole conditioning input |
| `seed` | int | `null` | Random seed for reproducible generation |
| `batch_size` | int | `1` | Number of inputs processed per batch |
| `params.mesh_scale` | float | `1.0` | Target mesh scale used for camera-distance computation |
| `params.image_resolution` | int | `512` | Working image resolution used during camera estimation |

#### Family: pixal3d

Chains sparse-structure, shape, and texture flow-matching stages to produce a mesh with baked PBR maps.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `low_vram` | boolean | `false` | Keep stage models on CPU and page each to GPU per stage; reduces peak VRAM at the cost of slower inference |
| `resolution` | integer | `null` | Pipeline grid resolution (`1024` or `1536`); unset defaults to `1024` in low-VRAM mode, else `1536` |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.manual_fov` | float | `null` | Manual camera horizontal FOV in radians; unset triggers MoGe-based auto-estimation |
| `params.ss_sampling_steps` | int | `12` | Sparse-structure diffusion sampling steps |
| `params.ss_guidance_strength` | float | `7.5` | Sparse-structure classifier-free guidance strength |
| `params.ss_guidance_rescale` | float | `0.7` | Sparse-structure guidance rescale factor |
| `params.ss_rescale_t` | float | `5.0` | Sparse-structure timestep rescale factor |
| `params.shape_slat_sampling_steps` | int | `12` | Shape structured-latent sampling steps |
| `params.shape_slat_guidance_strength` | float | `7.5` | Shape structured-latent classifier-free guidance strength |
| `params.shape_slat_guidance_rescale` | float | `0.5` | Shape structured-latent guidance rescale factor |
| `params.shape_slat_rescale_t` | float | `3.0` | Shape structured-latent timestep rescale factor |
| `params.tex_slat_sampling_steps` | int | `12` | Texture structured-latent sampling steps |
| `params.tex_slat_guidance_strength` | float | `1.0` | Texture structured-latent classifier-free guidance strength |
| `params.tex_slat_guidance_rescale` | float | `0.0` | Texture structured-latent guidance rescale factor |
| `params.tex_slat_rescale_t` | float | `3.0` | Texture structured-latent timestep rescale factor |
| `params.max_num_tokens` | int | `49152` | Maximum sparse-token budget per stage |
| `params.texture_size` | int | `4096` | Baked texture size in pixels applied when exporting the GLB |
| `params.decimation_target` | int | `1000000` | Target face count applied during mesh decimation before GLB export |

**Example:**

```yaml
component:
  type: model
  task: image-to-3d
  driver: custom
  family: pixal3d
  device: cuda
  model:
    provider: huggingface
    repository: TencentARC/Pixal3D
  low_vram: false
  action:
    image: ${input.image as image}
    seed: ${input.seed as integer}
    params:
      texture_size: 4096
      shape_slat_sampling_steps: 12
      tex_slat_sampling_steps: 12
```

#### Family: anigen

Runs AniGen's SS-Flow and SLAT-Flow stages end-to-end to produce a rigged mesh (bones, hierarchical parents, and per-vertex skin weights baked into a standard glTF skinned-mesh) plus a stand-alone skeleton visualization.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ss_variant` | string | `solo` | SS-Flow checkpoint variant (`solo`, `epic`, `duet`) |
| `slat_variant` | string | `auto` | SLAT-Flow checkpoint variant (`auto`, `control`) |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `return_mesh` | bool | `true` | Include the rigged mesh GLB in the result |
| `return_skeleton` | bool | `true` | Include the skeleton visualization GLB in the result |
| `return_image` | bool | `false` | Include the background-removed conditioning image in the result |
| `params.cfg_scale_ss` | float | `7.5` | Sparse-structure classifier-free guidance scale |
| `params.cfg_scale_slat` | float | `3.0` | Structured-latent classifier-free guidance scale |
| `params.ss_steps` | int | `25` | Sparse-structure flow-matching sampling steps |
| `params.slat_steps` | int | `25` | Structured-latent flow-matching sampling steps |
| `params.joints_density` | int | `1` | Joint density level (0-4) — only used by `slat_variant: control` |
| `params.simplify_ratio` | float | `0.95` | Mesh simplification ratio applied during postprocessing |
| `params.fill_holes` | bool | `true` | Fill holes during mesh postprocessing |
| `params.no_smooth_skin_weights` | bool | `false` | Disable skin-weight smoothing |
| `params.smooth_skin_weights_iters` | int | `100` | Skin-weight smoothing iterations |
| `params.smooth_skin_weights_alpha` | float | `1.0` | Skin-weight smoothing alpha |
| `params.no_filter_skin_weights` | bool | `false` | Disable geodesic filtering of mesh skinning weights |
| `params.texture_size` | int | `1024` | Baked texture size (pixels); `0` disables texture baking |

**Example:**

```yaml
component:
  type: model
  task: image-to-3d
  driver: custom
  family: anigen
  device: cuda
  model:
    provider: huggingface
    repository: VAST-AI/AniGen
  ss_variant: solo
  slat_variant: auto
  action:
    image: ${input.image as image}
    seed: ${input.seed as integer}
    params:
      ss_steps: 25
      slat_steps: 25
      texture_size: 1024
```

#### Supported families

| Family | Notes |
|--------|-------|
| `pixal3d` | Pixal3D, single-image to textured GLB. Requires a CUDA GPU (~18 GB VRAM at 1536 resolution, or ~10-12 GB with `low_vram: true` at 1024 resolution). |
| `anigen` | AniGen, single-image to rigged GLB plus skeleton visualization. Requires a CUDA GPU with at least 18 GB VRAM (Linux only; CUDA 11.8 or 12.x). |

**Result Shape:**

- `pixal3d` returns a single GLB stream (or a list of streams for batched inputs). Each stream carries `format: "glb"` with content type `model/gltf-binary`, so any glTF-compatible viewer can load it directly.
- `anigen` returns a dict per input with `mesh`, `skeleton`, and optionally `image` fields, gated by the corresponding `return_*` flags. `mesh` and `skeleton` are GLB streams (`model/gltf-binary`); `image` is a PNG of the background-removed conditioning image.

### Video to Video

Transform an existing video clip. Two driver families are supported: `huggingface` layers AnimateDiff over an SD 1.5 checkpoint to restyle the clip with a text prompt while preserving motion, and `custom` runs Wan-Animate to drive a reference character with the pose/expression of the input video.

**Common Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | video/array | one of `video`/`frames` **required** | Source video (or list/stream of videos) whose motion is preserved |
| `frames` | image-array | one of `video`/`frames` **required** | Source frames used as the motion source, as an alternative to `video` |
| `prompt` | string/array | `null` | Text prompt guiding the output |
| `negative_prompt` | string/array | `null` | Text describing content to avoid |
| `reference_image` | image | `null` | Reference image; usage depends on the driver — appearance IP-Adapter conditioning for `huggingface`, target character for `custom` (**required** on Wan-Animate) |
| `seed` | int | `null` | Random seed for reproducible generation |
| `batch_size` | int | `1` | Number of inputs processed per batch |
| `params.num_frames` | int | `null` | Frames sampled from the input; unset consumes every input frame |
| `params.fps` | int | `null` | Output video frame rate; unset inherits the input clip's native fps |
| `params.width` | int | `null` | Output video width in pixels; defaults to the input width |
| `params.height` | int | `null` | Output video height in pixels; defaults to the input height |

#### Driver: huggingface (AnimateDiff)

Restyle the source clip with a text prompt while preserving its motion.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `video-to-video` |
| `driver` | string | **required** | Must be `huggingface` |
| `architecture` | string | **required** | Currently `animatediff` |
| `model` | model | **required** | Base SD 1.5 style checkpoint (HuggingFace repo or local path); any SD 1.5 fine-tune works |
| `motion_adapter` | model | **required** | AnimateDiff motion adapter matching the base architecture |
| `ip_adapter` | model | `null` | Optional IP-Adapter weights used when actions supply a `reference_image`. Set `filename` to `<sub_dir>/<weight_name>` (e.g. `models/ip-adapter_sd15.bin`) |

**Action Fields (in addition to the common fields):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.inference_steps` | int | `25` | Number of diffusion inference steps per frame |
| `params.guidance_scale` | float | `7.5` | Classifier-free guidance scale |
| `params.denoise_strength` | float | `0.5` | Denoising strength — higher values follow the prompt more, lower values preserve the input video's appearance |
| `params.ip_adapter_scale` | float | `0.6` | IP-Adapter influence when `reference_image` is supplied; ignored otherwise. `0` disables, `1` fully follows the reference |

**Example:**

```yaml
component:
  type: model
  task: video-to-video
  driver: huggingface
  architecture: animatediff
  model:
    provider: huggingface
    repository: SG161222/Realistic_Vision_V5.1_noVAE
  motion_adapter:
    provider: huggingface
    repository: guoyww/animatediff-motion-adapter-v1-5-3
  ip_adapter:
    provider: huggingface
    repository: h94/IP-Adapter
    filename: models/ip-adapter_sd15.bin
  device: cuda
  action:
    video: ${input.video as video}
    prompt: ${input.prompt}
    reference_image: ${input.reference_image as image?}
    params:
      denoise_strength: 0.5
      guidance_scale: 7.5
      inference_steps: 25
      ip_adapter_scale: 0.6
```

**Supported architectures:**

| Architecture | Notes |
|--------------|-------|
| `animatediff` | Stable Diffusion 1.5 checkpoint + AnimateDiff motion adapter. Trained on ~16-frame windows — split long inputs into short segments upstream (e.g. with `video-clipper`) and stitch the results downstream. |

#### Driver: custom (Wan-Animate)

Transfer the pose and expression of a driving video onto a reference character. Requires CUDA and preprocessing checkpoints (pose detection, person detection, and — for the optional replacement and pose-retargeting features — SAM2 and FLUX.1-Kontext).

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `video-to-video` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `wan`) |
| `preset` | string | `animate-14b` | Checkpoint preset (`animate-14b`) |
| `model` | model | **required** | Wan-Animate checkpoint (HuggingFace repo or local checkpoint directory) |
| `pose2d_model` | model | **required** | ViTPose whole-body ONNX checkpoint used to extract driving poses |
| `det_model` | model | **required** | Person detector ONNX checkpoint (e.g. YOLOv10) used by the pose extractor |
| `sam2_model` | model | `null` | SAM2 checkpoint; required only when an action uses `params.replace_flag` |
| `flux_kontext_model` | model | `null` | FLUX.1-Kontext model; required only when an action uses `params.use_flux` with pose retargeting |
| `cpu_offload` | boolean | `false` | Offload submodules to CPU during generation to save VRAM |

**Action Fields (in addition to the common fields):**

`reference_image` is **required** on this driver — it supplies the target character animated to match the driving video.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.inference_steps` | int | `20` | Number of diffusion sampling steps |
| `params.guidance_scale` | float | `1.0` | Classifier-free guidance scale used for expression control |
| `params.shift` | float | `5.0` | Flow-matching timestep shift applied to the scheduler |
| `params.clip_len` | int | `77` | Frames generated per clip; must satisfy `4n+1` |
| `params.refert_num` | int | `1` | Frames used as temporal guidance between clips; `1` or `5` |
| `params.preprocess_fps` | int | `30` | Target fps when sampling the driving video during preprocessing; `-1` keeps the video's native fps |
| `params.resolution_width` | int | `1280` | Preprocessing resolution width; the driving video is resized to preserve aspect ratio within `width * height` area |
| `params.resolution_height` | int | `720` | Preprocessing resolution height; paired with `resolution_width` to define the target area |
| `params.retarget_flag` | boolean | `false` | Enable pose retargeting during preprocessing |
| `params.use_flux` | boolean | `false` | Use FLUX.1-Kontext image editing during pose retargeting; requires `retarget_flag` and the component's `flux_kontext_model` |
| `params.replace_flag` | boolean | `false` | Enable character replacement mode; requires the component's `sam2_model` to be configured |
| `params.mask_iterations` | int | `3` | Mask dilation iterations used in replacement mode |
| `params.mask_kernel_size` | int | `7` | Mask dilation kernel size used in replacement mode |
| `params.mask_w_len` | int | `1` | Grid subdivisions along the width axis used to refine the replacement mask contour |
| `params.mask_h_len` | int | `1` | Grid subdivisions along the height axis used to refine the replacement mask contour |

**Example:**

```yaml
component:
  type: model
  task: video-to-video
  driver: custom
  family: wan
  preset: animate-14b
  model: Wan-AI/Wan2.2-Animate-14B
  pose2d_model: Wan-AI/Wan2.2-Animate-14B/process_checkpoint/pose2d/vitpose_h_wholebody.onnx
  det_model: Wan-AI/Wan2.2-Animate-14B/process_checkpoint/det/yolov10m.onnx
  # Optional — enable replacement mode / pose retargeting with image editing.
  sam2_model: Wan-AI/Wan2.2-Animate-14B/process_checkpoint/sam2/sam2_hiera_large.pt
  flux_kontext_model: black-forest-labs/FLUX.1-Kontext-dev
  cpu_offload: false
  device: cuda:0
  action:
    video: ${input.driving_video as video}
    reference_image: ${input.reference_image as image}
    prompt: ${input.prompt | ""}
    params:
      clip_len: 77
      refert_num: 1
      inference_steps: 20
      guidance_scale: 1.0
      resolution_width: 1280
      resolution_height: 720
      preprocess_fps: 30
```

**Supported families:**

| Family | Preset | Notes |
|--------|--------|-------|
| `wan` | `animate-14b` | Wan2.2 Animate 14B. Requires CUDA. Preprocessing pulls in `pose2d`/`det` (always), `sam2` (replacement mode), and `FLUX.1-Kontext` (retargeting with image editing). |

**Result Shape:**

Returns a single mp4 stream (or a list of streams for batched inputs), each with `format: "mp4"` and an `fps` attribute matching the output frame rate.

### Text to Speech

Generate speech audio from text. This task uses `driver: custom` with a `family` field to select the model family, and a `method` field on the action to select the generation method. Supported families: `qwen`, `kokoro`, `chatterbox`, `luxtts`, `tada`, `cosyvoice`, `fireredtts3`.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `text-to-speech` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family: `qwen`, `kokoro`, `chatterbox`, `luxtts`, `tada`, `cosyvoice`, `fireredtts3` |
| `model` | string / config | **required** | Model source (HuggingFace repo, local path, or named model) |

Each family may add its own component-level fields (e.g. `preset`, CUDA acceleration flags). See the family sections below.

**Common Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | TTS generation method — one of `generate`, `clone`, `design`, `edit`. Availability depends on the family. |
| `text` | string / array | **required** | Text (or list of texts) to synthesize |
| `language` | string | `null` | Text language as an ISO 639-1 or BCP 47 code (see [language codes](../language-codes.md)). Only used by families that condition on language. |
| `batch_size` | int | `1` | Number of input texts processed per batch |

**Method Availability by Family:**

| Family | `generate` | `clone` | `design` | `edit` |
|--------|:---:|:---:|:---:|:---:|
| `qwen` | ✅ | ✅ | ✅ | — |
| `kokoro` | ✅ | — | — | — |
| `chatterbox` | ✅ | ✅ | — | — |
| `luxtts` | — | ✅ | — | — |
| `tada` | — | ✅ | — | — |
| `cosyvoice` | ✅ | ✅ | ✅ | — |
| `fireredtts3` | — | ✅ | ✅ | ✅ |

#### Family: `qwen`

Alibaba Qwen3-TTS. Supports built-in voices, cloning, and voice design from natural-language descriptions.

**Component fields:** inherits common model fields only.

**Method: `generate`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice | vivian}
    instructions: ${input.instructions | ""}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `voice` | string | `vivian` | Built-in Qwen voice name |
| `instructions` | string | `""` | Emotion/style instructions for the voice |

**Method: `clone`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-Base
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text as text}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reference_audio` | string | **required** | Reference audio to clone the voice from |
| `reference_text` | string | **required** | Transcript of the reference audio |

**Method: `design`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
  device: cuda:0
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `instructions` | string | **required** | Natural-language description of the desired voice |

**Suggested checkpoints:**

| Model | Method | Description |
|-------|--------|-------------|
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | `generate` | Built-in voices with style control |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | `clone` | Voice cloning from reference audio |
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | `design` | Voice design from text description |

Languages: English, Chinese, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian (resolved from the ISO 639-1 prefix of `language`).

#### Family: `kokoro`

Kokoro TTS. Lightweight synthesis with preset voices. `generate` only.

**Component fields:** inherits common model fields only.

**Method: `generate`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: kokoro
  model: hexgrad/Kokoro-82M
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice | af_heart}
    speed: ${input.speed | 1.0}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `voice` | string | `af_heart` | Kokoro voice ID (e.g. `af_heart`, `af_bella`, `am_michael`) |
| `speed` | float | `1.0` | Speech speed multiplier; `1.0` is natural |

Languages: American English (`en`), British English (`en-GB`), Japanese (`ja`), Mandarin Chinese (`zh`), Spanish (`es`), French (`fr`), Hindi (`hi`), Italian (`it`), Brazilian Portuguese (`pt-BR`). Output sample rate: 24 kHz.

#### Family: `chatterbox`

Resemble AI Chatterbox. Supports preset synthesis and zero-shot cloning with emotion controls.

**Component fields:** inherits common model fields only.

**Method: `generate`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: chatterbox
  model: ResembleAI/chatterbox
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    exaggeration: ${input.exaggeration | 0.5}
    cfg_weight: ${input.cfg_weight | 0.5}
    temperature: ${input.temperature | 0.8}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `exaggeration` | float | — | Emotional exaggeration; `0.0` monotone, `1.0` dramatic |
| `cfg_weight` | float | — | Classifier-free guidance weight |
| `temperature` | float | — | Sampling temperature |

**Method: `clone`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: chatterbox
  model: ResembleAI/chatterbox
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reference_audio` | string | **required** | Reference audio (5 s+ recommended) |
| `exaggeration` | float | — | Emotional exaggeration |
| `cfg_weight` | float | — | Classifier-free guidance weight |
| `temperature` | float | — | Sampling temperature |

#### Family: `luxtts`

LuxTTS. Zero-shot cloning with fine-grained flow-matching controls. `clone` only.

**Component fields:** inherits common model fields only.

**Method: `clone`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: luxtts
  model: BeaverAI/luxtts-v1
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    num_steps: 4
    guidance_scale: 3.0
    speed: 1.0
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reference_audio` | string | **required** | Reference audio for zero-shot voice cloning |
| `reference_duration` | int | `5` | Reference clip duration in seconds |
| `reference_rms` | float | `0.01` | Target RMS normalization for the reference clip |
| `num_steps` | int | `4` | Flow-matching solver steps; higher = better quality, slower |
| `guidance_scale` | float | `3.0` | Classifier-free guidance scale |
| `t_shift` | float | `0.5` | Flow-matching time shift |
| `speed` | float | `1.0` | Speech speed multiplier |
| `seed` | int | — | Random seed for reproducibility |

Output sample rate: 48 kHz. On CPU, thread count is auto-clamped to `min(cpu_count, 8)`.

#### Family: `tada`

Hume TADA. Zero-shot cloning with an optional built-in ASR (English only) when the reference transcript is omitted. `clone` only.

**Component fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tokenizer` | string | `unsloth/Llama-3.2-1B` | HuggingFace repo ID for the tokenizer (ungated Llama-3.2-1B mirror) |

**Method: `clone`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: tada
  model:
    repository: HumeAI/tada-v0.1
    allow_patterns: ["*.safetensors", "*.json", "*.txt", "*.bin", "*.model"]
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text | ""}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reference_audio` | string | **required** | Reference audio for voice cloning |
| `reference_text` | string | — | Transcript of the reference audio; omit to use TADA's built-in English ASR |
| `seed` | int | — | Random seed for reproducibility |

Output sample rate: 24 kHz. On CUDA/XPU the model uses bfloat16 when supported; MPS falls back to CPU due to flow-matching instability on Apple Silicon.

#### Family: `cosyvoice`

FunAudioLLM CosyVoice / CosyVoice2 / CosyVoice3. AutoModel picks the version by inspecting `cosyvoice{,2,3}.yaml` inside the model directory.

The runtime downloads and installs the `cosyvoice` and `matcha` packages from GitHub on first startup (pinned commits). No `git` CLI is required.

**Component fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `load_jit` | bool | `false` | Load JIT-compiled modules (CUDA only; silently ignored on CPU) |
| `load_trt` | bool | `false` | Load TensorRT engines (CUDA only) |
| `load_vllm` | bool | `false` | Load vLLM runtime for the LLM stage (CosyVoice2/3 on CUDA only) |
| `fp16` | bool | `false` | Run inference in fp16 precision (CUDA only) |

**Method: `generate`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/CosyVoice-300M-SFT
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice}
    speed: 1.0
    text_frontend: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `voice` | string | **required** | Built-in speaker ID (SFT), or a pre-registered zero-shot speaker on CosyVoice2/3 |
| `speed` | float | `1.0` | Speech speed multiplier |
| `text_frontend` | bool | `true` | Run CosyVoice's text-normalization frontend |

**Method: `clone`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/CosyVoice2-0.5B
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text | ""}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reference_audio` | string | **required** | Reference audio for zero-shot voice cloning |
| `reference_text` | string | — | Transcript of the reference audio; when provided uses zero-shot inference, otherwise cross-lingual |
| `speed` | float | `1.0` | Speech speed multiplier |
| `text_frontend` | bool | `true` | Run text-normalization frontend |

**Method: `design`**

CosyVoice2/3 only. `inference_instruct2` under the hood.

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/CosyVoice2-0.5B
  device: cuda:0
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
    reference_audio: ${input.reference_audio as audio}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `instructions` | string | **required** | Natural-language instruction for style, dialect, or emotion |
| `reference_audio` | string | **required** | Prompt audio for voice conditioning |
| `speed` | float | `1.0` | Speech speed multiplier |
| `text_frontend` | bool | `true` | Run text-normalization frontend |

Output sample rate: 24 kHz (model default). Calling `design` on CosyVoice1 raises a runtime error.

#### Family: `fireredtts3`

FireRedTeam FireRedTTS3. Two presets share the family: `base` for cloning, `instruct` for cloning plus voice design and audio editing.

The runtime downloads and installs the `fireredtts3` package from GitHub on first startup (pinned commit).

**Component fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `preset` | string | `base` | `base` (FireRedTTS3 checkpoint) or `instruct` (FireRedTTS3-Instruct). `design` and `edit` require `instruct`. |

**Method: `clone`**

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: fireredtts3
  preset: base
  model: FireRedTeam/FireRedTTS3
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text | ""}
    language: ${input.language | en}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reference_audio` | string | **required** | Reference audio for zero-shot voice cloning |
| `reference_text` | string | — | Transcript of the reference audio; recommended for best speaker similarity |
| `text_frontend` | bool | `true` | Run FireRedTTS3's text-normalization frontend |

The `language` common field is honored on the `base` preset and ignored on `instruct`.

**Method: `design`** (Instruct only)

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: fireredtts3
  preset: instruct
  model: FireRedTeam/FireRedTTS3-Instruct
  device: cuda:0
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `instructions` | string | **required** | Natural-language description of the target voice (gender, age, timbre, emotion, pace, accent) |

**Method: `edit`** (Instruct only)

Rewrites audio directly from the instruction — the `text` field is ignored.

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: fireredtts3
  preset: instruct
  model: FireRedTeam/FireRedTTS3-Instruct
  device: cuda:0
  action:
    method: edit
    reference_audio: ${input.reference_audio as audio}
    instructions: ${input.instructions as text}
    mode: ${input.mode | semantic}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reference_audio` | string | **required** | Input audio to edit |
| `instructions` | string | **required** | Edit instruction (free-form for `semantic`, template-like for `acoustic`, e.g. `adjust the speed to 1.2`) |
| `mode` | string | `semantic` | `semantic` (content edit) or `acoustic` (speed/pitch/volume edit) |

Output sample rate: 24 kHz (both presets). Calling `design` or `edit` on the `base` preset raises a runtime error.

### Speech to Text

Transcribe audio into text, optionally with per-segment or per-word timestamps. Supports both the HuggingFace transformers backend (Whisper family) and several `custom` families (faster-whisper, crisper-whisper, fun-asr, vibevoice).

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `speech-to-text` |
| `driver` | string | `huggingface` | Inference framework: `huggingface` or `custom` |
| `architecture` | string | `auto` | (huggingface) Model architecture: `auto`, `whisper` |
| `family` | string | — | (custom) Model family: `faster-whisper`, `crisper-whisper`, `fun-asr`, `vibevoice` |
| `model` | string / config | varies | Model source; each family has its own default |

**Action Fields (common):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | audio | **required** | Input audio file, list of audios, or async stream |
| `language` | string | `null` | Language code (`en`, `ko`, etc.); unset triggers auto-detection where supported |
| `return_timestamps` | bool | `false` | Include per-segment timestamps in the result |
| `timestamp_level` | string | `segment` | `segment` or `word` (word-level requires backend support) |
| `time_offset` | time / list | `null` | Offset added to every segment's start/end times; scalars broadcast, lists pair per audio |
| `batch_size` | int | `1` | Number of audios processed per batch |
| `streaming` | bool | `false` | Emit transcribed chunks incrementally as decoded |

**Family-specific action fields:**

- `faster-whisper` / `huggingface` (Whisper): `task` (`transcribe` \| `translate`), `chunk_length`, and `params` (`num_beams`, `temperature`, `compression_ratio_threshold`, `log_prob_threshold`, `no_speech_threshold`).
- `crisper-whisper`: `mode` (`verbatim` \| `intended`), `hotwords`, `longform_strategy`, `speculative_decoding`, `hallucination_mitigation`, `temperature_fallback`, and `params.{chunk_duration,stride,context_words,drop_words,max_output_length}`.
- `vibevoice`: `context_info`, `max_output_length`, `temperature`, `top_p`, `num_beams`.
- `fun-asr`: uses the common fields only; VAD and punctuation are configured on the component (`voice_activity_detection`, `punctuation`).

**Example (custom / faster-whisper):**

```yaml
component:
  id: transcriber
  type: model
  task: speech-to-text
  driver: custom
  family: faster-whisper
  model:
    provider: huggingface
    repository: Systran/faster-whisper-large-v3
  compute_type: float16
  action:
    audio: ${input.audio as audio}
    language: en
    return_timestamps: true
    timestamp_level: word
    output: ${result as json}
```

**Result Shape:**

Plain-text mode (`return_timestamps: false`) returns a string per input:

```json
"Hello world, this is a test."
```

Timestamped mode returns a list of segments:

```json
[
  { "text": "Hello world,", "start_time": 0.12, "end_time": 1.03 },
  { "text": "this is a test.", "start_time": 1.05, "end_time": 2.44 }
]
```

Word-level timestamps add a `words` array to each segment:

```json
[
  {
    "text": "Hello world",
    "start_time": 0.12,
    "end_time": 1.03,
    "words": [
      { "text": "Hello", "start_time": 0.12, "end_time": 0.44 },
      { "text": "world", "start_time": 0.46, "end_time": 1.03 }
    ]
  }
]
```

When `streaming: true`, per-input results are async iterators. Whisper-family backends emit token-level chunks (a plain string per chunk when timestamps are off, one segment dict per chunk when on). Timestamped segment chunks carry a `"type": "segment"` field alongside the segment fields. VibeVoice ASR *streaming* checkpoints stream per-chunk transcript text; offline checkpoints fall back to yielding the collected result as a single chunk (segments carry `"type": "segment"`; plain-text checkpoints yield the whole transcript as one string chunk).

#### Supported Families

| Family | Backend | Notes |
|--------|---------|-------|
| `faster-whisper` | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2-based Whisper runtime; supports beam search, VAD, chunked long-form |
| `crisper-whisper` | [nyralabs/crisperwhisper](https://pypi.org/project/crisperwhisper/) | Word-precise Whisper variant; picks `ct2` when available, else `transformers`. Model shorthands (`large`, `turbo`, `medium`, `small`, and `*_pro`) are resolved to `nyralabs/CrisperWhisper2.0_<size>` |
| `fun-asr` | [FunAudioLLM/FunASR](https://github.com/modelscope/FunASR) | Chinese-first multi-language ASR; ships with optional VAD and punctuation stages. Default model: `FunAudioLLM/Fun-ASR-MLT-Nano-2512` |
| `vibevoice` | [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) | Streaming + offline ASR checkpoints. Default: `microsoft/VibeVoice-ASR-Streaming-1.5B`. Language is auto-detected across 10 languages |

The HuggingFace `whisper` driver runs stock Whisper checkpoints via `transformers`; use it when you want the transformers ecosystem (LoRA adapters, quantization) rather than the CT2-backed `faster-whisper` fast path.

### Speaker Diarization

Segment an audio file by speaker — return per-speaker turns with start/end times and a speaker label. Runs the pyannote.audio speaker-diarization pipeline. This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `speaker-diarization` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `pyannote`) |
| `model` | string / config | `pyannote/speaker-diarization-3.1` | Pyannote pipeline identifier (HuggingFace repo or local path). Access to the gated repo requires a HuggingFace token on the model config |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | audio | **required** | Input audio file, list of audios, or async stream |
| `speaker_count` | int | `null` | Exact number of speakers when known; otherwise leave unset and use the min/max hints |
| `min_speaker_count` | int | `null` | Minimum number of speakers considered by the pipeline |
| `max_speaker_count` | int | `null` | Maximum number of speakers considered by the pipeline |
| `batch_size` | int | `1` | Number of audios processed per batch |
| `streaming` | bool | `false` | Emit per-speaker turns as an async iterator (fake stream: pipeline needs the whole audio, then re-emits) |
| `params.min_segment_duration` | duration | `"0s"` | Discard turns shorter than this (e.g., `250ms`) |
| `params.merge_gap` | duration | `"0s"` | Merge adjacent same-speaker turns separated by no more than this gap (e.g., `500ms`) |

Duration fields accept values like `"250ms"`, `"0.5s"`, or bare numeric seconds.

**Example:**

```yaml
component:
  id: diarizer
  type: model
  task: speaker-diarization
  driver: custom
  family: pyannote
  model:
    provider: huggingface
    repository: pyannote/speaker-diarization-3.1
    token: ${env.HUGGINGFACE_TOKEN}
  action:
    audio: ${input.audio as audio}
    min_speaker_count: 2
    max_speaker_count: 4
    params:
      min_segment_duration: 250ms
      merge_gap: 500ms
    output: ${result as json}
```

**Result Shape:**

```json
{
  "segments": [
    { "speaker": "SPEAKER_00", "start_time": 0.48,  "end_time": 3.72,  "confidence": 1.0 },
    { "speaker": "SPEAKER_01", "start_time": 3.90,  "end_time": 7.16,  "confidence": 1.0 },
    { "speaker": "SPEAKER_00", "start_time": 7.44,  "end_time": 12.02, "confidence": 1.0 }
  ]
}
```

`confidence` is reported as `1.0` for pyannote (the pipeline does not expose per-turn confidence). Segments are sorted by `start_time` after filtering and merging.

Pyannote diarization is not truly streamable — the pipeline needs the full audio before producing turns. With `streaming: true` the same turns are re-emitted one-by-one to preserve the `AsyncIterator` contract expected by downstream jobs. Each streamed chunk carries `"type": "segment"` alongside the segment fields.

#### Supported Families

| Family | Backend | Notes |
|--------|---------|-------|
| `pyannote` | [pyannote/pyannote-audio](https://github.com/pyannote/pyannote-audio) | Runs any `pyannote.audio` speaker-diarization pipeline. Requires accepting the model license on HuggingFace and providing a token |

### Voice Activity Detection

Detect speech segments in an audio file and return their start/end timestamps with a confidence score. Silent regions are omitted from the result. This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `voice-activity-detection` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `silero`) |
| `model` | string / config | `null` | Optional and ignored for `silero`; the model ships inside the `silero-vad` pip package |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | audio | **required** | Input audio file, list of audio inputs, or async stream |
| `sample_rate` | int | `16000` | Target sample rate (16000 or 8000); input is resampled if needed |
| `batch_size` | int | `1` | Number of audio inputs to process per batch |
| `streaming` | bool | `false` | Emit each detected segment as it is confirmed (per-input stream) |
| `params.threshold` | float | `0.5` | Speech probability threshold (0.0 - 1.0); higher = stricter |
| `params.min_speech_duration` | duration | `"250ms"` | Minimum speech chunk duration; shorter chunks are discarded |
| `params.min_silence_duration` | duration | `"500ms"` | Silence required to split adjacent speech chunks |
| `params.speech_padding_time` | duration | `"100ms"` | Padding added to both sides of each detected chunk |

Duration fields accept values like `"250ms"`, `"0.5s"`, or bare numeric seconds.

**Example:**

```yaml
component:
  type: model
  task: voice-activity-detection
  driver: custom
  family: silero
  device: cpu
  action:
    audio: ${input.audio as audio}
    sample_rate: 16000
    params:
      threshold: 0.5
      min_speech_duration: 250ms
      min_silence_duration: 500ms
      speech_padding_time: 100ms
```

**Result Shape:**

```json
{
  "segments": [
    { "start_time": 0.124, "end_time": 44.58,  "confidence": 0.916 },
    { "start_time": 47.07, "end_time": 150.02, "confidence": 0.937 },
    { "start_time": 151.10, "end_time": 175.24, "confidence": 0.949 }
  ]
}
```

When the input is a list, the action returns a list of per-audio result dicts. When `streaming: true`, per-input results are async iterators that yield one segment chunk at a time as speech regions are confirmed; each chunk carries `"type": "segment"` alongside the segment fields.

#### Supported Families

| Family | Backend | Notes |
|--------|---------|-------|
| `silero` | [snakers4/silero-vad](https://github.com/snakers4/silero-vad) (pip) | Lightweight CNN (~1MB), 16 kHz and 8 kHz supported, frame size 32 ms @ 16 kHz |

### Shot Boundary Detection

Detect shot boundaries (hard cuts and transitions) in a video and return per-shot start/end timecodes and frame indices. This task uses `driver: custom` with a `family` field to select the model family. Unlike `video-scene-detector` (which groups semantically similar frames into scenes using classical CV), shot boundary detection uses a deep learning model to identify precise cut points frame-by-frame.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `shot-boundary-detection` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `transnetv2`) |
| `model` | string / config | **required** | Model source (local path or HuggingFace repo containing the checkpoint) |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | video | **required** | Input video file, list of videos, or async stream |
| `start_time` | time | `null` | Time in the source at which detection begins (e.g., `00:01:00`, `60s`) |
| `end_time` | time | `null` | Time in the source at which detection stops (e.g., `00:05:00`, `300s`) |
| `batch_size` | int | `1` | Number of videos processed per batch |
| `streaming` | bool | `false` | Emit each detected shot as it is confirmed (per-input stream) |
| `params.threshold` | float | `0.5` | Confidence threshold above which a frame is treated as a shot boundary (0.0 - 1.0); higher = fewer boundaries |

**Example:**

```yaml
component:
  id: shot-detector
  type: model
  task: shot-boundary-detection
  driver: custom
  family: transnetv2
  model:
    provider: local
    path: ./models/transnetv2-weights
  max_concurrent_count: 1
  action:
    video: ${input.video as file}
    params:
      threshold: 0.5
    output: ${result as json}
```

**Result Shape:**

```json
{
  "shots": [
    {
      "index": 0,
      "start_time": "00:00:00.000",
      "end_time": "00:00:12.345",
      "start_frame": 0,
      "end_frame": 370,
      "duration": "00:00:12.345"
    },
    {
      "index": 1,
      "start_time": "00:00:12.345",
      "end_time": "00:00:28.678",
      "start_frame": 370,
      "end_frame": 860,
      "duration": "00:00:16.333"
    }
  ]
}
```

When the input is a list, the action returns a list of per-video result dicts. When `streaming: true`, per-input results are async iterators that yield one shot chunk at a time as boundaries are detected; each chunk carries `"type": "shot"` alongside the shot fields.

#### Supported Families

| Family | Backend | Notes |
|--------|---------|-------|
| `transnetv2` | [soCzech/TransNetV2](https://github.com/soCzech/TransNetV2) | Deep learning shot detector; GPU-accelerated (TensorFlow). Point `model.path` at the SavedModel folder containing `saved_model.pb` and `variables/` |

### Music Generation

Generate or edit music audio. The action selects an operation via the `method` field — from scratch generation, cover of an existing track, in-place region rewrite, continuation past the end, adding a new instrument layer, generating accompaniment for a vocal-only stem, or synthesizing a MIDI file with a specific instrument voice. This task uses `driver: custom` with a `family` field to select the model family; ACE-Step also takes a `preset` field to pick the checkpoint variant.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `music-generation` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (`ace-step`, `midi-ddsp`, `yue2`) |
| `preset` | string | `acestep-v15-turbo` | Checkpoint preset (`ace-step` only: `acestep-v15-turbo`, `acestep-v15-base`, `acestep-v15-sft`) |
| `expression_generator_weights` | string | `<model>/expression_generator/5000` | Path to the expression generator checkpoint (`midi-ddsp` only) |
| `vae` | string/object | family-specific | VAE decoder model (`yue2` only). See the YuE2 family section |
| `backend` | string | `torch` | Inference backend for the AR model (`yue2` only: `torch`, `torch-eager`, `vllm`) |
| `quantization` | object | `null` | AR-model quantization (`yue2` only: `type: fp8`) |
| `memory_budget_gib` | float | `24` | GPU memory budget in GiB reserved for generation (`yue2` only) |
| `cpu_offload` | string/array | `null` | Submodules to run on CPU (`yue2` only): `ar` moves the AR model during NAR synthesis, `vae` runs the VAE decoder on CPU. Accepts a single value or a list |
| `verify_hashes` | bool | `true` | Verify model file checksums on load (`yue2` only) |
| `model` | string | **required** | Local checkpoint directory (`ace-step`, `midi-ddsp`) or HuggingFace repo / local path (`yue2`) |

**Common Action Fields:**

Every method shares these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Operation: `generate` (all families), `cover` (`ace-step`, `yue2`), `rewrite`, `extend`, `layer`, `accompany` (`ace-step` only), `score` (`yue2` only) |
| `seed` | int | `null` | Random seed for reproducible generation |
| `batch_size` | int | `1` | Number of inputs processed per batch |
| `params.duration` | int | `30` | Duration of the generated music in seconds |
| `params.bpm` | int | `120` | Target tempo in beats per minute |
| `params.key_scale` | string | `null` | Musical key of the generated music (e.g., `C`, `D`, `Em`) |
| `params.time_signature` | string | `4/4` | Musical time signature (`ace-step` only; e.g., `4/4`, `3/4`) |
| `params.inference_steps` | int | `8` | Number of diffusion inference steps (`ace-step` only; turbo: `8`, base: `32`, sft: `50`) |
| `params.guidance_scale` | float | `5.0` | Classifier-free guidance scale applied during sampling (`ace-step` only) |

#### `method: generate`

Generate music from scratch. Optionally condition on a reference audio to nudge timbre and performance style toward it.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt` | string/array | **required** | Text description of the music style, genre, mood, and instrumentation |
| `lyrics` | string/array | `null` | Song lyrics used for vocal generation |
| `reference_audio` | string | `null` | Optional reference audio guiding timbre, mixing, and performance style |

```yaml
action:
  method: generate
  prompt: ${input.prompt as text}
  lyrics: ${input.lyrics | ""}
  params:
    duration: 30
    bpm: 120
```

#### `method: cover`

Cover an existing track in a new style described by `prompt`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string | **required** | Path or URL of the source audio to create a cover from |
| `prompt` | string/array | **required** | Text description of the target cover style |
| `lyrics` | string/array | `null` | Optional lyrics to sing in the cover |

```yaml
action:
  method: cover
  source: ${input.source}
  prompt: "acoustic folk arrangement, warm and intimate"
```

#### `method: rewrite`

Regenerate a specific `[start_time, end_time]` region of the source while keeping the rest intact.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string | **required** | Path or URL of the source audio containing the region to rewrite |
| `start_time` | float | **required** | Start time in seconds of the region to regenerate |
| `end_time` | float | **required** | End time in seconds of the region to regenerate |
| `prompt` | string/array | **required** | Text description guiding the rewritten region |
| `lyrics` | string/array | `null` | Optional lyrics for the rewritten region |

```yaml
action:
  method: rewrite
  source: ${input.source}
  start_time: 32.0
  end_time: 48.0
  prompt: "add a saxophone solo over the existing chord progression"
```

#### `method: extend`

Continue the source audio past its natural end.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string | **required** | Path or URL of the source audio to continue past its end |
| `prompt` | string/array | **required** | Text description of the continuation style |
| `lyrics` | string/array | `null` | Optional lyrics for the continuation |

```yaml
action:
  method: extend
  source: ${input.source}
  prompt: "outro fading into ambient pads"
  params:
    duration: 20
```

#### `method: layer`

Add a new instrument or part on top of the source, keeping the existing mix underneath. `track_class` selects which stem to generate.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string | **required** | Path or URL of the source audio to layer a new track on top of |
| `track_class` | string | **required** | Stem to generate on top of the source (see stem values below) |
| `prompt` | string/array | `null` | Text description guiding the added layer |
| `lyrics` | string/array | `null` | Optional lyrics when the added layer is vocals |

```yaml
action:
  method: layer
  source: ${input.source}
  track_class: drums
  prompt: "punchy 808 kick and hi-hat pattern"
```

#### `method: accompany`

Generate an instrumental accompaniment that matches a vocal-only source. `track_classes` lists which stems to fill in.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vocal` | string | **required** | Path or URL of the vocal-only audio to generate accompaniment for |
| `track_classes` | string[] | **required** | Stem classes to fill in as accompaniment (min length 1; see stem values below) |
| `prompt` | string/array | `null` | Text description of the desired accompaniment style |

```yaml
action:
  method: accompany
  vocal: ${input.vocal}
  track_classes: [ keyboard, bass, drums ]
  prompt: "sparse piano ballad, matches the vocal phrasing"
```

**Stem values (`track_class` / `track_classes`):**

`woodwinds`, `brass`, `fx`, `synth`, `strings`, `percussion`, `keyboard`, `guitar`, `bass`, `drums`, `backing-vocals`, `vocals`.

**Full Example:**

```yaml
component:
  type: model
  task: music-generation
  driver: custom
  family: ace-step
  preset: acestep-v15-turbo
  model: /path/to/ace-step-checkpoints
  device: cuda:0
  action:
    method: generate
    prompt: ${input.prompt as text}
    lyrics: ${input.lyrics | ""}
    params:
      duration: 30
      bpm: 120
      key_scale: C
      time_signature: 4/4
      inference_steps: 8
      guidance_scale: 5.0
```

#### Supported families

| Family | Preset | Notes |
|--------|--------|-------|
| `ace-step` | `acestep-v15-turbo` | Fast turbo variant; default `inference_steps: 8`. |
| `ace-step` | `acestep-v15-base` | Base variant; recommended `inference_steps: 32`. |
| `ace-step` | `acestep-v15-sft` | SFT variant; recommended `inference_steps: 50`. |
| `midi-ddsp` | — | Google Magenta MIDI-DDSP. Synthesizes a monophonic MIDI file with a specific URMP instrument voice. |
| `yue2` | — | M·A·P YuE2. Full-song generation with editable ABC score planning; renders 48 kHz stereo audio. |

#### `family: midi-ddsp`

Synthesize a MIDI file into 16 kHz mono audio using Google Magenta's [MIDI-DDSP](https://github.com/magenta/midi-ddsp). The model was trained on the URMP dataset and only supports monophonic tracks (a single note at any given time); polyphonic input is rejected. `method` is always `generate`.

**Runtime requirement:** MIDI-DDSP pins TensorFlow 2.11 and cannot coexist with the host mindor stack. The component must run under an isolated runtime — `virtualenv`, `docker`, or `apple-container`. Native / embedded / process runtimes are rejected at load time.

**Supported instruments:** `violin`, `viola`, `cello`, `double-bass`, `flute`, `oboe`, `clarinet`, `saxophone`, `bassoon`, `trumpet`, `horn`, `trombone`, `tuba`. The user-selected `instrument` always wins — MIDI program numbers embedded in the file are ignored.

**Action Fields (`method: generate`):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `midi` | string | **required** | Path or URL of the monophonic MIDI file to synthesize |
| `instrument` | string | **required** | Instrument voice used to synthesize every track in the MIDI file |
| `params.pitch_offset` | int | `0` | Semitones to transpose the input MIDI before synthesis |
| `params.speed_rate` | float | `1.0` | Playback speed multiplier applied to the MIDI sequence |
| `params.vibrato_extent` | float | `null` | Global override for the vibrato extent expression control (0.0-1.0) |
| `params.vibrato_attack` | float | `null` | Global override for the vibrato attack expression control (0.0-1.0) |
| `params.brightness` | float | `null` | Global override for the brightness expression control (0.0-1.0) |
| `params.attack_noise` | float | `null` | Global override for the attack noise expression control (0.0-1.0) |
| `params.volume` | float | `null` | Global override for the volume expression control (0.0-1.0) |
| `params.volume_fluctuation` | float | `null` | Global override for the volume fluctuation expression control (0.0-1.0) |

```yaml
component:
  type: model
  task: music-generation
  driver: custom
  family: midi-ddsp
  runtime:
    type: virtualenv
    driver: pyenv
    python: "3.10.14"
  model: /path/to/midi_ddsp_model_weights_urmp_9_10
  action:
    method: generate
    midi: ${input.midi}
    instrument: violin
    params:
      vibrato_extent: 0.6
      brightness: 0.7
```

#### `family: yue2`

M·A·P [YuE2](https://map-yue2.github.io/) full-song generation. A single AR–NAR Mixture-of-Transformers plans an editable ABC score, generates semantic tokens, and hands off to a flow-matching NAR + VAE decoder that renders 48 kHz stereo audio. `model` accepts either a HuggingFace repo ID (e.g. `m-a-p/YuE2-3B`) or a local checkpoint directory.

**Runtime requirement:** the unquantized preset needs a CUDA GPU with BF16 support and ≥24 GB VRAM. Reduce the footprint with `quantization.type: fp8`, `cpu_offload: ar`, and a smaller `vae.tile_size`. On macOS < 15.1 the MPS backend cannot execute the VAE's oversized Conv1d layers, so set `cpu_offload: vae` (or `cpu_offload: [ar, vae]`) to keep the decoder on CPU. The `vllm` backend additionally requires the model's optional `[fast]` extras, which model-compose installs automatically when `backend: vllm` is selected.

**Component Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vae` | string/object | `m-a-p/YuE2-Vae` | VAE decoder model. String shorthand expands to `{ model: <value> }` |
| `vae.model` | string/object | `m-a-p/YuE2-Vae` | VAE model identifier — HuggingFace repo ID or local path |
| `vae.tile_size` | int | family-default | VAE decode tile size in frames; `512` for ≤12 GiB budgets, `1024` otherwise |
| `backend` | string | `torch` | AR backend (`torch`, `torch-eager`, `vllm`). `vllm` requires the model's optional `[fast]` extras |
| `quantization.type` | string | — | Only `fp8` is supported; halves AR VRAM at a small quality cost |
| `memory_budget_gib` | float | `24` | GPU memory budget reserved for generation |
| `cpu_offload` | string/array | `null` | Submodules to run on CPU. `ar` moves the AR model to CPU during NAR synthesis to free VRAM. `vae` wraps the VAE decoder to run on CPU (workaround for MPS Conv1d `out_channels > 65536` on macOS < 15.1). Accepts a single value or a list of both |
| `verify_hashes` | bool | `true` | Verify model file checksums on load |

**Common Action Fields:**

Every YuE2 method shares these fields (in addition to the top-level `seed` and `batch_size`):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.cot_mode` | string | `full` | Chain-of-thought mode: `full` (score with chord symbols), `melody` (melody-only score, best for covers), `off` (direct generation) |
| `params.cfg_scale` | float | model default | Classifier-free guidance scale in `[0, 20]` |
| `params.abc_sampling` | object | `null` | Sampling overrides for ABC score generation (`temperature`, `top_p`, `top_k`, `repetition_penalty`, `penalty_window`, `min_tokens`, `max_tokens`) |
| `params.semantic_sampling` | object | `null` | Sampling overrides for semantic-token generation (same fields as `abc_sampling`) |

##### `method: generate`

Compose a new song from a style description and lyrics.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `style` | string | **required** | Text description of the music style, genre, mood, and instrumentation |
| `lyrics` | string | **required** | Song lyrics used for vocal generation |

```yaml
action:
  method: generate
  style: ${input.style as text}
  lyrics: ${input.lyrics as text}
  params:
    cot_mode: full
    cfg_scale: 1.5
```

##### `method: cover`

Reinterpret a supplied ABC score in a new style. Requires `cot_mode` to be `melody` or `full`; `off` is rejected because it cannot consume an external score.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `style` | string | **required** | Text description of the target cover style |
| `lyrics` | string | **required** | Lyrics to sing over the covered score |
| `abc` | string | **required** | ABC score conditioning the cover (typically a melody transcription without chord symbols) |

```yaml
action:
  method: cover
  style: "English, jazz-funk, warm lead vocal, Rhodes, bass and drums"
  lyrics: ${input.lyrics as text}
  abc: ${input.abc as text}
  params:
    cot_mode: melody
```

##### `method: score`

Plan an editable ABC score without rendering audio. Returns `{ abc: string, truncated: bool }`. Requires `cot_mode: melody` or `full`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `style` | string | **required** | Style description used to plan the score |
| `lyrics` | string | **required** | Lyrics that shape the planned score |

```yaml
action:
  method: score
  style: ${input.style as text}
  lyrics: ${input.lyrics as text}
  params:
    cot_mode: full
```

**Full Example:**

```yaml
component:
  type: model
  task: music-generation
  driver: custom
  family: yue2
  model: m-a-p/YuE2-3B
  device: cuda
  quantization:
    type: fp8
  cpu_offload: ar
  vae:
    model: m-a-p/YuE2-Vae
    tile_size: 512
  actions:
    - id: generate
      method: generate
      style: ${input.style as text}
      lyrics: ${input.lyrics as text}
      seed: 831001
      params:
        cot_mode: full
```

**Result Shape:**

Audio-producing methods (`generate`, `cover` on all families; `layer`, `accompany`, `rewrite`, `extend` on `ace-step`) return a single PCM audio stream (or a list of streams for batched inputs). Each stream carries `sample_rate`, `channels`, and `bit_depth` attributes. `yue2`'s `score` method returns `{ abc: string, truncated: bool }` instead.

### Music Source Separation

Split a mixed music recording into individual stems (vocals, drums, bass, other). This task uses `driver: custom` with a `family` field to select the model backend.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `music-source-separation` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model backend (`demucs`, `mdx-net`, `bs-roformer`, `mel-band-roformer`) |
| `model` | string/object | family-specific | Named checkpoint (Demucs) or a HuggingFace repo / local file (MDX-Net ONNX, RoFormer `.ckpt`/`.safetensors`) |
| `stems` | array | family-default | Names of the stems this checkpoint produces, in output order (RoFormer families); falls back to `stem_0`, `stem_1`, ... when omitted |
| `params` | object | family-default | Architecture hyperparameters passed to the model constructor (RoFormer families) — must match the checkpoint |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | string/array | **required** | Input audio path, URL, or list of audio inputs to separate |
| `batch_size` | int | `1` | Number of audio inputs processed per batch |
| `params.stems` | array/string | all stems | Stems returned in the result (e.g., `vocals`, `drums`, `bass`, `other`); when omitted, every stem the model produces is returned |
| `params.sample_rate` | int | model-native | Sample rate in Hz of the returned stems |
| `params.overlap` | float | family-default | Overlap ratio between chunks (0.0-0.99); higher = cleaner but slower |
| `params.shifts` | int | family-default | Number of random shifts for equivariant stabilization (Demucs only); higher = cleaner but slower |
| `params.chunk_duration` | float | `8.0` | Chunk length in seconds fed to the transformer (RoFormer families only); defaults to ~8 seconds at the model's sample rate |

#### `family: demucs`

Meta AI's Hybrid Transformer Demucs. Four-stem model (`vocals`, `drums`, `bass`, `other`) by default; six-stem variants add `guitar` and `piano`.

```yaml
component:
  type: model
  task: music-source-separation
  driver: custom
  family: demucs
  model: htdemucs_ft
  device: cpu   # MPS is unsupported for htdemucs_ft; use cpu or cuda
  action:
    audio: ${input.audio as audio}
    params:
      stems: [ vocals ]   # omit to return all stems the model produces
      overlap: 0.25
      shifts: 1
```

`htdemucs_ft` is a bagged ensemble whose internal conv widths exceed the MPS backend limit in PyTorch — keep `device: cpu` on Apple Silicon or switch the model to `htdemucs` (single-model variant) if you want MPS.

#### `family: mdx-net`

UVR MDX-Net vocal separator via ONNX Runtime. Produces a `vocals` stem; the complementary `instrumental` stem is derived by subtracting the estimated vocals from the original mix.

```yaml
component:
  type: model
  task: music-source-separation
  driver: custom
  family: mdx-net
  model:
    provider: huggingface
    repository: seanghay/uvr_models
    filename: UVR-MDX-NET-Voc_FT.onnx
  device: auto
  action:
    audio: ${input.audio as audio}
    params:
      stems: [ vocals ]   # or [vocals, instrumental]; omit to return both
```

#### `family: bs-roformer`

[lucidrains' BS-RoFormer](https://github.com/lucidrains/BS-RoFormer) — a band-split rotary transformer separator. The Python package only ships the architecture, so you point `model` at a pretrained checkpoint (typically the ZFTurbo `.ckpt`/`.safetensors` releases) and set `params` to the architecture hyperparameters the checkpoint was trained with. `stems` names the model's output channels so you can select them by name from action-side `params.stems`.

```yaml
component:
  type: model
  task: music-source-separation
  driver: custom
  family: bs-roformer
  model:
    provider: huggingface
    repository: ZFTurbo/Music-Source-Separation-Training
    filename: model_bs_roformer_ep_368_sdr_12.9628.ckpt
  stems: [ vocals ]
  params:
    dim: 384
    depth: 12
    stereo: true
    num_stems: 1
  device: auto
  action:
    audio: ${input.audio as audio}
    params:
      overlap: 0.25
      chunk_duration: 8.0
```

`params` fields (all optional except `dim` / `depth`) mirror `bs_roformer.BSRoformer(...)`: `dim`, `depth`, `stereo`, `num_stems`, `time_transformer_depth`, `freq_transformer_depth`, `heads`, `dim_head`, `stft_n_fft`, `stft_hop_length`, `stft_win_length`, `flash_attn`, plus `freqs_per_bands` (tuple summing to the STFT bin count).

#### `family: mel-band-roformer`

[lucidrains' Mel-Band RoFormer](https://github.com/lucidrains/BS-RoFormer) — the mel-band variant that shares the same wrapper as `bs-roformer` but builds its band split from a mel filter bank. `params.sample_rate` is required because the mel filter bank is baked in at construction time; audio is resampled to match.

```yaml
component:
  type: model
  task: music-source-separation
  driver: custom
  family: mel-band-roformer
  model:
    provider: huggingface
    repository: ZFTurbo/Music-Source-Separation-Training
    filename: model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt
  stems: [ vocals ]
  params:
    dim: 384
    depth: 12
    stereo: true
    num_stems: 1
    num_bands: 60
    sample_rate: 44100
  device: auto
  action:
    audio: ${input.audio as audio}
    params:
      overlap: 0.25
```

`params` accepts everything from `bs-roformer` plus `num_bands` and `sample_rate`. Match these to the checkpoint — a mismatch in `num_bands` or `sample_rate` produces a shape error at load time.

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `demucs` | [Demucs v4](https://github.com/facebookresearch/demucs) | Hybrid Transformer (spectrogram + waveform). Four-stem or six-stem checkpoints. |
| `mdx-net` | [UVR MDX-Net](https://github.com/Anjok07/ultimatevocalremovergui) | Vocal-focused; runs on ONNX Runtime. Instrumental stem derived by subtraction. |
| `bs-roformer` | [lucidrains BS-RoFormer](https://github.com/lucidrains/BS-RoFormer) | Band-split rotary transformer. Architecture-only package; pair with a community checkpoint. |
| `mel-band-roformer` | [lucidrains BS-RoFormer](https://github.com/lucidrains/BS-RoFormer) | Mel-band variant of BS-RoFormer. `params.sample_rate` must match the checkpoint. |

**Result Shape:**

When a single stem is requested, returns a single PCM audio stream (or a list of streams for batched inputs). When multiple stems are requested — or when `stems` is omitted so every stem the model produces is returned — the result is a `{ "<stem_name>": <PcmStreamResource>, ... }` map instead. Each stream carries `sample_rate`, `channels`, and `bit_depth` attributes.

### Music Transcription

Transcribe recorded audio into a MIDI file and a JSON list of note events (onset, offset, pitch, velocity). This task uses `driver: custom` with a `family` field to select the model backend.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `music-transcription` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model backend (`basic-pitch`, `piano-transcription`) |
| `model` | string | family-specific | Named checkpoint (see the per-family sections below) |

**Common Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | string/array | **required** | Input audio path, URL, or list of audio inputs |
| `batch_size` | int | `1` | Number of audio inputs processed per batch |
| `params.onset_threshold` | float | family-default | Confidence threshold for detecting a note onset (0.0-1.0); higher = fewer, more confident notes |
| `params.frame_threshold` | float | family-default | Confidence threshold for sustaining a note across frames (0.0-1.0) |

#### `family: basic-pitch`

Spotify's polyphonic, instrument-agnostic note transcriber. Runs on CPU via ONNX Runtime; the ICASSP-2022 checkpoint ships inside the `basic-pitch` package.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `return_pitch_bends` | bool | `false` | Whether per-note pitch bend events are written into the MIDI and included as a `pitch_bends` array on each note |
| `params.minimum_note_length` | float | `58.0` | Minimum note duration in milliseconds; shorter detections are discarded |
| `params.minimum_frequency` | float | `null` | Lower bound of detected pitch in Hz |
| `params.maximum_frequency` | float | `null` | Upper bound of detected pitch in Hz |
| `params.midi_tempo` | float | `120` | Tempo (BPM) written into the MIDI header; does not affect detected timings |

```yaml
component:
  type: model
  task: music-transcription
  driver: custom
  family: basic-pitch
  device: auto
  action:
    audio: ${input.audio as audio}
    return_pitch_bends: false
    params:
      onset_threshold: 0.5
      frame_threshold: 0.3
      minimum_note_length: 58.0
```

#### `family: piano-transcription`

ByteDance's 88-key piano transcriber with sustain-pedal event detection. Downloads its ~180 MB checkpoint into `~/piano_transcription_inference_data/` on first use.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.offset_threshold` | float | `0.3` | Confidence threshold for detecting a note offset (0.0-1.0) |
| `params.pedal_offset_threshold` | float | `0.2` | Confidence threshold for detecting sustain-pedal release events (0.0-1.0) |

```yaml
component:
  type: model
  task: music-transcription
  driver: custom
  family: piano-transcription
  device: auto
  action:
    audio: ${input.audio as audio}
    params:
      onset_threshold:        0.3
      offset_threshold:       0.3
      frame_threshold:        0.1
      pedal_offset_threshold: 0.2
```

`minimum_note_length`, `minimum_frequency`, `maximum_frequency`, `return_pitch_bends`, and `midi_tempo` do not apply — the model is fixed to 88-key piano and writes pedal events into the MIDI instead of pitch bends.

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `basic-pitch` | [Spotify Basic Pitch](https://github.com/spotify/basic-pitch) (ICASSP-2022) | Polyphonic, instrument-agnostic. Runs on CPU via ONNX. Checkpoint ships inside the wheel. |
| `piano-transcription` | [ByteDance Piano Transcription](https://github.com/bytedance/piano_transcription) | 88-key piano only. Detects sustain-pedal events. Auto-downloads checkpoint on first use. |

**Result Shape:**

Returns a dict with two fields per input (or a list of dicts for batched inputs):

- `midi` — a MIDI file suitable for saving to `.mid` or feeding into a score renderer.
- `notes` — a list of `{ "start_time", "end_time", "pitch", "velocity" }` objects (times in seconds, `pitch` as MIDI note number, `velocity` in 0.0-1.0). Basic Pitch adds a `pitch_bends` array on each note when `return_pitch_bends` is enabled.

### Music Beat Tracking

Detect beat and downbeat positions in a music recording. Each detected beat carries its measure-relative position. Uses `driver: custom` with a `family` field to select the model backend.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `music-beat-tracking` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model backend (`beat-this`) |
| `model` | string | family-specific | Named checkpoint (see the per-family section below) |

**Common Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | string/array | **required** | Input audio path, URL, or list of audio inputs |
| `batch_size` | int | `1` | Number of audio inputs processed per batch |
| `return_metadata` | bool | `true` | Whether processing metadata (`duration`, ...) is included in the result |

#### `family: beat-this`

CPJKU Beat This! — transformer-based joint beat and downbeat estimator (ISMIR 2024). Checkpoints auto-download from HuggingFace on first use.

**Component-level fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | `final0` | Beat This! checkpoint name (`final0/1/2`, `small0/1/2`) |
| `dbn` | bool | `false` | Apply madmom DBN post-processing to refine beats (requires `madmom` installed separately) |
| `precision` | string | `auto` | Numeric precision (`auto`, `float32`, `float16`); `float16` speeds up CUDA inference |

```yaml
component:
  type: model
  task: music-beat-tracking
  driver: custom
  family: beat-this
  device: auto
  model: final0
  dbn: false
  action:
    audio: ${input.audio as audio}
    return_metadata: true
```

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `beat-this` | [CPJKU Beat This!](https://github.com/CPJKU/beat_this) (ISMIR 2024) | Transformer-based; joint beat + downbeat prediction. Optional madmom DBN post-processing via `dbn: true`. |

**Result Shape:**

Returns a dict per input (or a list of dicts for batched inputs):

- `beats` — a list of `{ "time", "is_downbeat", "beat_number" }` objects. `time` is the beat timestamp in seconds; `is_downbeat` is `true` when the beat starts a new measure; `beat_number` is the beat's position within its measure, 1-indexed from the most recent downbeat (`1` on downbeats, `2`, `3`, ... on subsequent beats). Beats occurring before the first detected downbeat (pickup notes / anacrusis) carry `beat_number: null`.
- `duration` — the input audio duration in seconds (included when `return_metadata: true`).

### Talking Head

Animates a still portrait so it lip-syncs (and moves the head) to a driving audio clip. In contrast to `lip-sync` — which edits the mouth of an existing video — `talking-head` synthesises head motion and expression from a single image. Uses `driver: custom` with a `family` field to select the model backend.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `talking-head` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family: `sadtalker`, `hallo2`, `hallo3`, `sonic`, `echomimic`, or `float` |
| `preset` | string | family default | Checkpoint variant — see per-family tables below |
| `model` | string/object | **required** | Model identifier — a HuggingFace repo ID or a local checkpoint directory |

**Common Action Fields** (available on every family):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | image/array | **required** | Input portrait image (or list/stream of images) used as the source face |
| `audio` | audio/array | **required** | Input audio (or list of audios) driving the lip sync |
| `seed` | int | `null` | Random seed for reproducible generation |
| `batch_size` | int | `1` | Number of `(image, audio)` pairs processed per batch |
| `params.fps` | int | `25` | Output video frame rate |

#### Family: `sadtalker`

OpenTalker/SadTalker — Audio2Coeff + face renderer. Classical, fastest of the six; runs on a single mid-range GPU.

**Component-level fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `preset` | string | `v0.0.2-256` | Checkpoint variant: `v0.0.2-256` or `v0.0.2-512` |
| `preprocessor` | string | `crop` | Face preprocessor mode: `crop`, `extcrop`, `resize`, `full`, `extfull`. Determines which mapping checkpoint is loaded and cannot vary per action |

**Family-specific Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.ref_eyeblink` | string/array | `null` | Reference video whose eye-blink motion is transferred onto the output |
| `params.ref_pose` | string/array | `null` | Reference video whose head-pose motion is transferred onto the output |
| `params.pose_style` | int | `0` | Head-pose style index in `[0, 46]` |
| `params.expression_scale` | float | `1.0` | Multiplier applied to facial expression intensity |
| `params.input_yaw` / `input_pitch` / `input_roll` | list[int] | `null` | Manual head-rotation keyframes (degrees); override predicted rotation |
| `params.still` | bool | `false` | Keep the head still (only mouth moves); recommended with `preprocessor: full` |
| `params.enhancer` | string | `null` | Per-frame face enhancer: `gfpgan` or `RestoreFormer` |
| `params.background_enhancer` | string | `null` | Background super-resolution enhancer: `realesrgan` |
| `params.face3dvis` | bool | `false` | Render an additional 3D face visualization video alongside the output |
| `params.size` | int | `256` | Face renderer resolution; must match the loaded preset (256 or 512) |
| `params.facerender_batch_size` | int | `2` | Batch size used by the face renderer inference loop |

**Example:**

```yaml
component:
  type: model
  task: talking-head
  driver: custom
  family: sadtalker
  preset: v0.0.2-256
  preprocessor: full
  model: vinthony/SadTalker
  device: cuda:0
  action:
    image: ${input.image as image}
    audio: ${input.audio as audio}
    params:
      still: true
      enhancer: gfpgan
      expression_scale: 1.0
```

#### Family: `hallo2`

fudan-generative-vision/hallo2 — diffusion-based portrait animator with long-video chunk-and-blend and optional built-in super-resolution.

**Family-specific Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.pose_weight` | float | `1.1` | Weight applied to the driving pose signal during motion module conditioning |
| `params.face_weight` | float | `1.1` | Weight applied to the driving face signal during motion module conditioning |
| `params.lip_weight` | float | `1.1` | Weight applied to the driving lip signal during motion module conditioning |
| `params.face_expand_ratio` | float | `1.2` | Face crop expansion ratio around the detected face box |
| `params.inference_steps` | int | `40` | Number of diffusion inference steps per denoising loop |
| `params.cfg_scale` | float | `3.5` | Classifier-free guidance scale |
| `params.motion_module_frames` | int | `16` | Number of frames processed per motion module window |
| `params.long_video` | bool | `true` | Enable long-video mode (chunk-and-blend) for audio longer than one window |
| `params.high_resolution` | bool | `false` | Run the built-in super-resolution pass to produce a higher-resolution output |

#### Family: `hallo3`

fudan-generative-vision/hallo3 — newer DiT-based portrait video generator with optional text prompt guidance.

**Family-specific Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.prompt` | string/array | `null` | Optional text prompt guiding scene, style, or motion |
| `params.negative_prompt` | string/array | `null` | Text describing content to avoid |
| `params.inference_steps` | int | `50` | Number of DiT inference steps |
| `params.guidance_scale` | float | `6.0` | Classifier-free guidance scale for text conditioning |
| `params.audio_guidance_scale` | float | `3.0` | Guidance scale applied to the audio conditioning branch |
| `params.resolution` | int | `480` | Output frame resolution (short-side length in pixels) |
| `params.num_frames` | int | `97` | Number of frames generated per DiT window |
| `params.shift` | float | `5.0` | Flow-matching timestep shift applied to the scheduler |
| `params.long_video` | bool | `true` | Enable long-video mode (window-and-blend) for audio longer than one DiT window |

#### Family: `sonic`

LeonJoe13/Sonic — SVD-XT backbone with whisper-tiny audio embedding; produces expressive head motion. Downloads the SVD-XT and whisper-tiny snapshots into the installed package on first pipeline load.

**Family-specific Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.dynamic_scale` | float | `1.0` | Motion-dynamics scale; larger values produce more expressive head/facial motion |
| `params.inference_steps` | int | `25` | Number of diffusion inference steps |
| `params.min_resolution` | int | `512` | Minimum short-side resolution the face crop is resized to before rendering |
| `params.keep_resolution` | bool | `false` | Preserve the input portrait's original resolution instead of resizing to `min_resolution` |

**Example:**

```yaml
component:
  type: model
  task: talking-head
  driver: custom
  family: sonic
  model: LeonJoe13/Sonic
  device: cuda:0
  action:
    image: ${input.image as image}
    audio: ${input.audio as audio}
    params:
      dynamic_scale: 1.0
      inference_steps: 25
```

#### Family: `echomimic`

AntGroup EchoMimic — v1 for portrait framing, v2 for half-body with optional motion-sync reference video.

**Component-level fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `preset` | string | `v1` | EchoMimic release: `v1` (portrait) or `v2` (half-body) |

**Family-specific Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.pose` | string/array | `null` | Optional reference video/pose sequence driving head or half-body motion (v2 uses this for half-body) |
| `params.width` | int | `512` | Output frame width in pixels |
| `params.height` | int | `512` | Output frame height in pixels |
| `params.inference_steps` | int | `30` | Number of diffusion inference steps |
| `params.cfg_scale` | float | `2.5` | Classifier-free guidance scale |
| `params.context_frames` | int | `12` | Number of frames processed per temporal context window |
| `params.context_overlap` | int | `3` | Frame overlap between consecutive temporal windows |
| `params.motion_sync` | bool | `false` | Enable motion-sync mode which extracts motion cues from the reference `pose` video |
| `params.sample_rate` | int | `16000` | Audio sample rate the model expects; resampling is applied if the input differs |

#### Family: `float`

Flow-matching portrait animator with per-emotion conditioning; the fastest of the diffusion-family options at 10 default steps.

**Family-specific Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.emotion` | string | `null` | Optional emotion label conditioning the output (e.g. `happy`, `sad`, `angry`) |
| `params.emotion_scale` | float | `1.0` | Multiplier applied to the emotion conditioning strength |
| `params.inference_steps` | int | `10` | Number of flow-matching inference steps |
| `params.cfg_scale` | float | `2.0` | Classifier-free guidance scale |
| `params.a_cfg_scale` | float | `2.0` | Guidance scale applied to the audio conditioning branch |
| `params.e_cfg_scale` | float | `1.0` | Guidance scale applied to the emotion conditioning branch |
| `params.crop` | bool | `true` | Crop the source portrait to the detected face before rendering; disable to render the full frame |

**Result Shape:**

Every family returns a single mp4 stream (or a list of streams for batched inputs), each with `format: "mp4"` and an `fps` attribute matching the requested frame rate.

### Lip Sync

Re-syncs a face video's mouth movements to a driving audio clip. Only the mouth region is regenerated; identity, expression, head pose, and background come straight from the source video. Uses `driver: custom` with a `family` field to select the model backend.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `lip-sync` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family: `wav2lip`, `musetalk`, or `latentsync` |
| `preset` | string | family default | Checkpoint variant — see per-family tables below |
| `model` | string/object | (from preset) | Model identifier. Leave unset to auto-fetch the preset's checkpoint |

**Common Action Fields** (available on every family):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | video/array | **required** | Source face video (or list/stream of videos) whose mouth region is re-synced |
| `audio` | audio/array | **required** | Driving audio clip (or list of clips) whose speech the mouth follows |
| `seed` | int | `null` | Random seed for reproducible generation |
| `batch_size` | int | `1` | Number of `(video, audio)` pairs processed per batch |
| `params.fps` | int | source fps | Output video frame rate; defaults to the source video's frame rate when unset |

#### Family: `wav2lip`

Classical GAN-based lip-sync (Rudrabha/Wav2Lip, justinjohn0306 fork). Smallest VRAM footprint, fastest inference, most permissive with awkward footage. Auto-fetches the preset checkpoint from the Easy-Wav2Lip release mirror on first run; the S3FD face detector weights are dropped into the installed package on first pipeline load.

**Presets:**

| Preset | Notes |
|--------|-------|
| `wav2lip` | Accuracy-tuned generator; smoother mouth shape, slightly softer |
| `wav2lip-gan` | GAN-tuned generator (default); sharper faces at the cost of occasional artefacts |

**Family-specific Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.face_bounding_box` | box | `null` | Fixed face box `(left, top, right, bottom)` in pixels; bypasses face detection |
| `params.face_bounding_box_padding` | box | `[0, 0, 0, 10]` | Pixel padding `(left, top, right, bottom)` added around each detected face box |
| `params.frame_crop_box` | box | `null` | Manual crop rectangle applied to input frames; `null` on any edge keeps the frame edge |
| `params.resize_factor` | int | `1` | Downscale factor applied to input frames before inference; higher trades quality for speed |
| `params.face_smoothing` | bool | `true` | Whether to apply temporal smoothing to face detections across frames |
| `params.face_detection_batch_size` | int | `16` | Number of frames processed per S3FD face-detection batch |
| `params.generator_batch_size` | int | `128` | Number of samples processed per Wav2Lip generator batch |
| `params.static` | bool | `false` | Reuse the first frame as a still image for the entire audio |

**Example:**

```yaml
component:
  type: model
  task: lip-sync
  driver: custom
  family: wav2lip
  preset: wav2lip-gan
  device: cuda:0
  action:
    video: ${input.video as video}
    audio: ${input.audio as audio}
    params:
      face_bounding_box_padding: [0, 0, 0, 10]
      resize_factor: 1
      face_smoothing: true
```

If audio outlasts the video, source frames are forward-repeated to fill the timeline.

#### Family: `musetalk`

TMElyralab/MuseTalk latent VAE+UNet with InsightFace + Whisper front-end. Higher quality than Wav2Lip at moderate VRAM cost. Auto-fetches the MuseTalk UNet from `TMElyralab/MuseTalk`; sd-vae-ft-mse, whisper-tiny, DWPose, and face-parse-bisent snapshots are downloaded into the installed package's `models/` directory on first pipeline load.

**Presets:**

| Preset | Notes |
|--------|-------|
| `v1` | Original release; exposes `bbox_shift` for manual mouth region tuning |
| `v15` | Default; parsing-mask blending for softer edges, `extra_margin`/`parsing_mode`/`cheek_width` params |

**Family-specific Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.bbox_shift` | int | `0` | Vertical shift (pixels) applied to the detected face bounding box (v1 only) |
| `params.extra_margin` | int | `10` | Extra chin margin (pixels) added to the face region before blending (v15 only) |
| `params.parsing_mode` | string | `jaw` | Face parsing region: `jaw` (tight), `neck` (widest), `raw` (default face region) (v15 only) |
| `params.left_cheek_width` | int | `90` | Left cheek width in pixels used by the parsing mask (v15 only) |
| `params.right_cheek_width` | int | `90` | Right cheek width in pixels used by the parsing mask (v15 only) |
| `params.audio_padding_length_left` | int | `2` | Number of audio feature frames padded before each window |
| `params.audio_padding_length_right` | int | `2` | Number of audio feature frames padded after each window |
| `params.generator_batch_size` | int | `8` | Number of samples processed per MuseTalk generator batch |
| `params.use_float16` | bool | `false` | Run the generator in float16 for a memory and latency win |

**Example:**

```yaml
component:
  type: model
  task: lip-sync
  driver: custom
  family: musetalk
  preset: v15
  device: cuda:0
  action:
    video: ${input.video as video}
    audio: ${input.audio as audio}
    params:
      parsing_mode: jaw
      extra_margin: 10
      use_float16: true
```

If audio outlasts the video, source frames are ping-ponged (forward, then reversed, ...) to fill the timeline.

#### Family: `latentsync`

ByteDance/LatentSync diffusion-based lip-sync. Uses InsightFace `buffalo_l` for detection + landmark alignment, a Stable Diffusion VAE, and a 3D UNet trained on LatentSync data. Highest quality of the three families at the cost of longer inference (20-50 DDIM steps). Auto-fetches the preset UNet from `ByteDance/LatentSync-<preset>`; sd-vae-ft-mse and InsightFace weights are auto-downloaded on first pipeline load.

**Presets:**

| Preset | Resolution | Notes |
|--------|-----------|-------|
| `1.5` | 256×256 | Older release; ~6 GB VRAM at fp16 |
| `1.6` | 512×512 | Default; ~12 GB VRAM at fp16 |

**Family-specific Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params.inference_steps` | int | `20` | Number of DDIM denoising steps; upstream recommends 20-50 |
| `params.guidance_scale` | float | `1.5` | Classifier-free guidance scale; upstream recommends 1.0-3.0 |
| `params.enable_deepcache` | bool | `false` | Enable DeepCache for a ~2x speedup at a small quality cost |
| `params.use_float16` | bool | `true` | Run the pipeline in float16 for a memory and latency win |

`seed` defaults to `1247` (upstream's fixed seed) when unset. `num_frames` and resolution are fixed by the preset's config yaml and not exposed at the DSL level.

**Example:**

```yaml
component:
  type: model
  task: lip-sync
  driver: custom
  family: latentsync
  preset: "1.6"
  device: cuda:0
  action:
    video: ${input.video as video}
    audio: ${input.audio as audio}
    params:
      inference_steps: 20
      guidance_scale: 1.5
      use_float16: true
```

LatentSync produces exactly the audio-length duration; the source video is trimmed to match rather than looped.

**Result Shape:**

Every family returns a single mp4 stream (or a list of streams for batched inputs), each with `format: "mp4"` and an `fps` attribute matching the output frame rate.

## Multiple Actions

Define multiple actions for different model operations:

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  device: cuda
  precision: float16
  actions:
    - id: generate-creative
      prompt: ${input.creative_prompt}
      params:
        temperature: 1.2
        top_p: 0.9
        max_output_length: 2048
      output:
        creative_text: ${response.generated_text}
    
    - id: generate-factual
      prompt: ${input.factual_prompt}
      max_output_length: 1024
      params:
        temperature: 0.3
        top_p: 0.8
      output:
        factual_text: ${response.generated_text}
    
    - id: generate-code
      prompt: "Generate Python code:\n${input.code_prompt}"
      max_output_length: 1024
      stop_sequences: [ "```", "\n\n\n" ]
      params:
        temperature: 0.1
      output:
        generated_code: ${response.generated_text}
```

## Device and Performance Configuration

### GPU Configuration

```yaml
component:
  type: model
  task: text-generation
  model: microsoft/DialoGPT-large
  device: cuda:0
  precision: float16
  low_cpu_mem_usage: true
```

### Multi-GPU Setup

```yaml
component:
  type: model
  task: text-generation
  model: microsoft/DialoGPT-xlarge
  device_mode: auto
  precision: bfloat16
```

### CPU Optimization

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
  device: cpu
  precision: float32
  fast_tokenizer: true
```

## Caching and Storage

### Model Caching

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: HuggingFaceTB/SmolLM3-3B
    cache_dir: ./models_cache
    local_files_only: false
```

### Offline Usage

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: HuggingFaceTB/SmolLM3-3B
    local_files_only: true
```

## Advanced Configuration Examples

### Streaming Text Generation

The `streaming` action field is available on tasks that produce time-series output one chunk at a time: `text-generation`, `chat-completion`, `text-to-text`, `image-to-text`, `speech-to-text`, `speaker-diarization`, `voice-activity-detection`, and `shot-boundary-detection`. Other tasks (such as `text-embedding`, `text-classification`, `text-reranking`, `image-embedding`, `video-embedding`, `text-to-speech`) return their result atomically and do not accept a `streaming` field. Streaming also requires `batch_size: 1` with a single input.

**Output vs input streaming.** `streaming: true` controls only the *output* shape: results are emitted as an `AsyncIterator` of chunks instead of a single value. The *input* is still consumed in whatever shape the backend requires:

- **Whisper-family `speech-to-text`** (HuggingFace, faster-whisper): the input audio must be fully available before decoding begins (encoder needs the complete 30-second mel-spectrogram). With `streaming: true`, transcription tokens are emitted as decoding produces them, but the audio itself is not consumed frame-by-frame. Latency for the first token is therefore bounded below by the time to load and process the entire input.
- **`voice-activity-detection` (silero)**: supports true frame-by-frame online streaming when the input is a streamable PCM source (see `is_audio_streamable` — raw PCM formats with a declared sample rate). Segments are emitted as soon as their trailing silence is confirmed. For non-streamable sources (mp3, wav container, etc.) the audio is collated first and segments are then yielded one by one, preserving the `AsyncIterator` interface but not the low-latency behavior.
- **Text tasks**: token-by-token generation is streamed as the decoder produces each token.

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  action:
    prompt: ${input.prompt}
    streaming: true
    params:
      max_output_length: 4096
      temperature: 0.8
      do_sample: true
    output: ${result[]}
```

### Batch Processing

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
  action:
    text: ${input.text_list}  # Array of texts
    params:
      batch_size: 32
    output:
      embeddings: ${response.embeddings}
```

### Custom Stop Sequences

```yaml
component:
  type: model
  task: text-generation
  model: codegen-350M
  action:
    prompt: "def ${input.function_name}(${input.parameters}):\n"
    max_output_length: 512
    stop_sequences: [ "\ndef ", "\nclass ", "\n\n" ]
    params:
      temperature: 0.2
    output:
      generated_function: ${response.generated_text}
```

## Error Handling

Model components handle various error conditions:

- **Model Loading Errors**: Invalid model IDs or network issues
- **GPU Memory Errors**: Insufficient VRAM for model size
- **Input Validation**: Invalid prompts or parameters
- **Generation Errors**: Model inference failures

Use workflow error handling to manage these cases:

```yaml
workflow:
  jobs:
    - id: generate-text
      component: text-model
      input:
        prompt: ${input.prompt}
      on_error:
        - id: fallback-generation
          component: smaller-model
          input:
            prompt: ${input.prompt}
```

## Variable Interpolation

Models support dynamic configuration:

```yaml
component:
  type: model
  task: text-generation
  model: ${env.MODEL_NAME | HuggingFaceTB/SmolLM3-3B}
  action:
    prompt: ${input.prompt}
    params:
      max_output_length: ${input.max_length as integer | 1024}
      temperature: ${input.creativity as float | 0.7}
      device: ${env.COMPUTE_DEVICE | cpu}
```

## Best Practices

1. **Model Selection**: Choose appropriate model sizes for your hardware
2. **Device Management**: Use GPU when available, fall back to CPU
3. **Memory Management**: Enable `low_cpu_mem_usage` for large models
4. **Caching**: Set `cache_dir` to persist downloaded models
5. **Precision**: Use lower precision (float16/bfloat16) to save memory
6. **Batch Processing**: Process multiple inputs together when possible
7. **Stop Sequences**: Use stop sequences to control generation length
8. **Temperature Tuning**: Lower temperature for factual, higher for creative tasks

## Integration with Workflows

Reference model components in workflow jobs:

```yaml
workflow:
  jobs:
    - id: embedding-generation
      component: embedding-model
      input:
        text: ${input.document}
      output:
        document_embedding: ${output.embedding}
        
    - id: similarity-search
      component: vector-store
      input:
        query_embedding: ${embedding-generation.output.document_embedding}
        
    - id: response-generation
      component: chat-model
      input:
        context: ${similarity-search.output.matches}
        question: ${input.question}
```

## Supported Models

### Text Generation Models (causal LM)
- **GPT Models**: GPT-2, GPT-Neo, GPT-J
- **LLaMA Models**: LLaMA, Alpaca, Vicuna
- **Code Models**: CodeGen, InCoder
- **Small Instruction Models**: SmolLM3, Phi

### Text-to-Text Models (seq2seq)
- **T5 Family**: T5, Flan-T5, mT5
- **BART Family**: BART, mBART, BARThez
- **Translation**: MarianMT (Helsinki-NLP), NLLB
- **Summarization**: BART-large-CNN, Pegasus

### Chat Models
- **Conversational**: DialoGPT, BlenderBot
- **Instruction Following**: ChatGLM, Alpaca
- **Code Chat**: CodeLlama-Instruct

### Embedding Models
- **Sentence Transformers**: all-MiniLM, all-mpnet-base
- **Specialized**: E5, BGE, Instructor

### Classification Models
- **Sentiment**: RoBERTa-sentiment, DistilBERT
- **Topic**: BERT-base-classification
- **Intent**: Custom fine-tuned models

### Reranking Models
- **BGE Reranker**: BAAI/bge-reranker-v2-m3, bge-reranker-large, bge-reranker-base
- **Jina Reranker**: jinaai/jina-reranker-v2-base-multilingual
- **Mixedbread**: mixedbread-ai/mxbai-rerank-large-v1, mxbai-rerank-xsmall-v1
- **Cross-Encoder**: cross-encoder/ms-marco-MiniLM-L-6-v2, ms-marco-MiniLM-L-12-v2

### Typed Decision Models
- **Laya** (`family: laya`): convaiinnovations/laya bundle — `english` (ModernBERT-large), `multilingual` (mmBERT-base, 100+ languages), `typed-decisions` (fine-tuned)
- **Kev** (`family: kev`): jaredpalmer/kev-0.8b, kev-4b, kev-9b (LoRA adapter + pointer head on frozen Qwen3.5)
- **Nimble** (`family: nimble`): bespokelabs/Bespoke-Nimble-9B (LoRA adapter merged onto Qwen/Qwen3.5-9B on first startup)

### Image Embedding Models
- **CLIP Family**: openai/clip-vit-base-patch32, clip-vit-large-patch14 (uses `get_image_features`)
- **SigLIP Family**: google/siglip-base-patch16-224
- **Self-Supervised**: facebook/dinov2-base, dinov2-small (pool `last_hidden_state`)

### Multimodal Models
- **Image Captioning**: BLIP, ViT-GPT2
- **Visual QA**: BLIP-VQA, ViLT

### Text-to-Speech Models
- **Qwen3-TTS**: Qwen3-TTS-12Hz-1.7B (CustomVoice, Base, VoiceDesign)

## Common Use Cases

- **Text Generation**: Create articles, stories, code
- **Chatbots**: Build conversational AI systems
- **Content Analysis**: Classify and analyze text
- **Structured Decisions**: Route, triage, or gate text with typed answers (yes/no, one-of-N, ordinal) and calibrated probabilities
- **Search**: Generate embeddings for semantic search
- **Visual Search / Dedup**: Encode images with CLIP/DINOv2 for similarity retrieval and near-duplicate detection
- **Translation**: Translate between languages
- **Summarization**: Create summaries of long documents
- **Code Generation**: Generate and complete code snippets
- **Image Understanding**: Describe and analyze images
- **Text-to-Speech**: Synthesize speech from text with voice generation, cloning, and design
