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
| `task` | string | **required** | Model task type: `text-generation`, `chat-completion`, `text-to-text`, `text-embedding`, `text-classification`, `text-reranking`, `image-to-text`, `image-text-to-text`, `text-to-speech`, `speech-to-text`, `image-generation`, `image-upscale`, `face-detection`, `pose-detection`, `face-embedding`, `music-generation` |
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
    params:
      max_output_length: 2048
      temperature: 0.8
      top_p: 0.9
      top_k: 50
      do_sample: true
      num_return_sequences: 1
    output:
      generated_text: ${response.generated_text}
```

**Text Generation Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_output_length` | integer | `1024` | Maximum tokens to generate |
| `min_output_length` | integer | `1` | Minimum tokens to generate |
| `temperature` | float | `1.0` | Sampling temperature (creativity) |
| `top_p` | float | `0.9` | Nucleus sampling threshold |
| `top_k` | integer | `50` | Top-K sampling limit |
| `num_beams` | integer | `1` | Beam search width |
| `do_sample` | boolean | `true` | Enable sampling vs greedy |
| `stop_sequences` | array | `null` | Stop generation sequences |
| `batch_size` | integer | `1` | Batch processing size |

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
| `max_input_length` | integer | `512` | Maximum tokens per (query, document) pair; longer pairs are truncated. |
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
| `num_beams` | integer | `4` | Beam search width |
| `length_penalty` | float | `1.0` | Length penalty for beam search |
| `early_stopping` | boolean | `true` | Stop when all beams finish |
| `do_sample` | boolean | `false` | Enable sampling (turn on for creative rewriting) |
| `temperature`/`top_k`/`top_p` | — | — | Only used when `do_sample: true` |
| `stop_sequences` | array | `null` | Stop generation sequences |

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

### Face Detection

Detect faces in an image and return bounding boxes (with optional facial landmarks). This task uses `driver: custom` with a `family` field to select the model family.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `face-detection` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `blazeface`) |
| `model` | string | `__default__` | Path or URL of a MediaPipe `.tflite` model. `__default__` auto-downloads the official BlazeFace short-range model to `~/.cache/models/mediapipe/`. |

**Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | image/array | **required** | Input image, list of images, or async stream of images |
| `min_confidence` | float | `0.5` | Minimum detection confidence threshold (0.0 - 1.0) |
| `return_landmarks` | bool | `false` | Include the 6 facial keypoints (eyes, nose, mouth, ears) in the result |
| `batch_size` | int | `1` | Number of images to process per batch |

**Example:**

```yaml
component:
  type: model
  task: face-detection
  driver: custom
  family: blazeface
  action:
    image: ${input.image as image}
    min_confidence: 0.6
    return_landmarks: true
    output:
      faces: ${result.detections}
```

**Result Shape:**

```json
{
  "detections": [
    {
      "box": [x, y, width, height],
      "score": 0.97,
      "landmarks": [{ "x": 123, "y": 45 }, ...]
    }
  ],
  "width": 1280,
  "height": 720
}
```

When the input is a list, the action returns a list of result dicts. When the input is an async stream, the action returns an async iterator that yields per-frame result dicts.

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
| `min_confidence` | float | `0.5` | Minimum pose-detection confidence threshold (0.0 - 1.0) |
| `return_keypoints` | bool | `true` | Include 2D pose keypoints (pixel coordinates) in the result |
| `batch_size` | int | `1` | Number of images to process per batch |

**Family-Specific Fields:**

| Field | `blazepose` | `yolo` | Description |
|-------|:-----------:|:------:|-------------|
| `min_presence_confidence` | ✓ | – | Minimum keypoint-presence confidence (0.0 - 1.0) |
| `min_tracking_confidence` | ✓ | – | Minimum tracking confidence. Reserved for future video running mode. |
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
    min_confidence: 0.6
    return_keypoints_3d: true
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

### Text to Speech

Generate speech audio from text using TTS models. This task uses `driver: custom` with a `family` field to select the model family, and a `method` field to select the generation method.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `text-to-speech` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `qwen`) |
| `model` | string | **required** | Model identifier |
| `method` | string | **required** | Generation method: `generate`, `clone`, `design` |

**Common Action Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | TTS generation method |
| `text` | string/array | **required** | Text to synthesize into speech |
| `language` | string | `null` | Language of the text using [standardized codes](../language-codes.md) |

#### Method: `generate`

Generate speech using a built-in voice with optional style instructions:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
  device: cuda:0
  max_concurrent_count: 1
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice | vivian}
    instructions: ${input.instructions | ""}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `voice` | string | `vivian` | Built-in voice name |
| `instructions` | string | `""` | Emotion/style instructions for the voice |

#### Method: `clone`

Clone a voice from reference audio and generate speech:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-Base
  device: cuda:0
  max_concurrent_count: 1
  action:
    method: clone
    text: ${input.text as text}
    ref_audio: ${input.ref_audio as audio}
    ref_text: ${input.ref_text as text}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ref_audio` | string | **required** | Path or URL to the reference audio for voice cloning |
| `ref_text` | string | **required** | Transcription text of the reference audio |

#### Method: `design`

Design a new voice from a natural language description and generate speech:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
  device: cuda:0
  max_concurrent_count: 1
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `instructions` | string | **required** | Description of the desired voice |

#### Supported Models (Qwen Family)

| Model | Method | Description |
|-------|--------|-------------|
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | `generate` | Built-in voices with style control |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | `clone` | Voice cloning from reference audio |
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | `design` | Voice design from text description |

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
      params:
        temperature: 0.3
        top_p: 0.8
        max_output_length: 1024
      output:
        factual_text: ${response.generated_text}
    
    - id: generate-code
      prompt: "Generate Python code:\n${input.code_prompt}"
      params:
        temperature: 0.1
        stop_sequences: [ "```", "\n\n\n" ]
        max_output_length: 1024
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

The `streaming` action field is only available on tasks that produce time-series output one chunk at a time: `text-generation`, `chat-completion`, `text-to-text`, and `image-to-text`. Other tasks (such as `text-embedding`, `text-classification`, `text-reranking`, `text-to-speech`) return their result atomically and do not accept a `streaming` field. Streaming also requires `batch_size: 1` with a single input.

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
    params:
      max_output_length: 512
      temperature: 0.2
      stop_sequences: [ "\ndef ", "\nclass ", "\n\n" ]
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

### Multimodal Models
- **Image Captioning**: BLIP, ViT-GPT2
- **Visual QA**: BLIP-VQA, ViLT

### Text-to-Speech Models
- **Qwen3-TTS**: Qwen3-TTS-12Hz-1.7B (CustomVoice, Base, VoiceDesign)

## Common Use Cases

- **Text Generation**: Create articles, stories, code
- **Chatbots**: Build conversational AI systems
- **Content Analysis**: Classify and analyze text
- **Search**: Generate embeddings for semantic search
- **Translation**: Translate between languages
- **Summarization**: Create summaries of long documents
- **Code Generation**: Generate and complete code snippets
- **Image Understanding**: Describe and analyze images
- **Text-to-Speech**: Synthesize speech from text with voice generation, cloning, and design
