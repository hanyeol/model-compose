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
| `task` | string | **required** | Model task type: `text-generation`, `chat-completion`, `text-to-text`, `text-embedding`, `text-classification`, `text-reranking`, `image-to-text`, `image-text-to-text`, `image-embedding`, `text-to-speech`, `speech-to-text`, `voice-activity-detection`, `image-generation`, `image-upscale`, `text-to-video`, `image-to-video`, `face-detection`, `face-tracking`, `pose-detection`, `face-embedding`, `music-generation` |
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
| `return_embedding` | bool | `false` | Include the track's L2-normalized identity centroid embedding in the result. |
| `return_track_image` | bool | `false` | Include one representative face crop per segment (highest-scoring frame in the segment, cropped at the detected bounding box in the frame's native resolution). |
| `bounding_box_padding` | float | `0.0` | Padding ratio applied when cropping the returned face image. Grows the box by this fraction of its width/height on each side (e.g. `0.2` = +20% on each side). Only affects `segment.image`; embeddings and clustering still use the un-padded box. |
| `batch_size` | int | `1` | Number of frame batches per iteration. |
| `params.similarity_threshold` | float | `0.4` | Cosine similarity above which two faces are grouped into the same track. |
| `params.min_face_size` | int | `0` | Minimum face bounding box size in pixels. `0` disables the filter. |
| `params.min_frame_count` | int | `1` | Discard tracks that appear in fewer than this many frames. |
| `params.max_face_count_per_frame` | int | `0` | Maximum number of faces to keep per frame. `0` disables the limit. |
| `params.merge_gap` | float | `0.0` | Merge adjacent segments separated by less than this many seconds. |

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
  "frame_count": 40
}
```

- `tracks[i].score` is the highest detection confidence across all frames in the track. Useful for ranking or filtering tracks.
- `tracks[i].segments[j].score` is the detection confidence of the representative frame for that segment (the highest-scoring frame within the segment; the same frame `image` is cropped from when `return_track_image` is enabled).
- `tracks[i].embedding` is present only when `return_embedding` is enabled — a 512-d L2-normalized centroid (for antelopev2) suitable for cosine matching against an identity DB or for merging tracks that turn out to be the same person.
- `tracks[i].segments[j].image` is present only when `return_track_image` is enabled — the highest-scoring frame in that segment, cropped at the detected bounding box in the frame's native resolution.
- `tracks[i].gender` (`"male"` / `"female"`) and `tracks[i].age` (integer) are present only when `return_gender_age` is enabled — taken from the track's highest-scoring frame. Absent if the model pack doesn't ship gender/age submodels.
- `frame_count` at the top level is the total number of sampled frames analyzed.

When `frames` is a list of sequences, the action returns a list of result dicts (one per sequence). When it is an async stream of frame batches, the action returns an async iterator that yields one result dict per batch.

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
| `preset` | string | `wan2.2-ti2v-5b` | Checkpoint preset (`wan2.2-t2v-a14b`, `wan2.2-ti2v-5b`) |
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
  preset: wan2.2-t2v-a14b
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
| `wan` | `wan2.2-t2v-a14b` | Wan2.2 T2V, 27B parameters (14B active). Requires ~80GB+ VRAM on a single GPU. |
| `wan` | `wan2.2-ti2v-5b` | Wan2.2 hybrid text-and-image-to-video, 5B parameters. Runs on a single 24GB GPU (e.g. RTX 4090). |

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
| `preset` | string | `wan2.2-i2v-a14b` | Checkpoint preset (`wan2.2-i2v-a14b`, `wan2.2-ti2v-5b`) |
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
  preset: wan2.2-i2v-a14b
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
| `wan` | `wan2.2-i2v-a14b` | Wan2.2 I2V, 27B parameters (14B active). Requires ~80GB+ VRAM on a single GPU. |
| `wan` | `wan2.2-ti2v-5b` | Wan2.2 hybrid text-and-image-to-video, 5B parameters. Runs on a single 24GB GPU. |

**Result Shape:**

Returns a single mp4 stream (or a list of streams for batched inputs), each with `format: "mp4"` and an `fps` attribute matching the requested frame rate.

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
[
  { "start_time": 0.124, "end_time": 44.58,  "confidence": 0.916 },
  { "start_time": 47.07, "end_time": 150.02, "confidence": 0.937 },
  { "start_time": 151.10, "end_time": 175.24, "confidence": 0.949 }
]
```

When the input is a list, the action returns a list of per-audio segment lists. When `streaming: true`, per-input results are async iterators that yield one segment dict at a time as speech regions are confirmed.

#### Supported Families

| Family | Backend | Notes |
|--------|---------|-------|
| `silero` | [snakers4/silero-vad](https://github.com/snakers4/silero-vad) (pip) | Lightweight CNN (~1MB), 16 kHz and 8 kHz supported, frame size 32 ms @ 16 kHz |

### Music Generation

Generate or edit music audio. The action selects an operation via the `method` field — from scratch generation, cover of an existing track, in-place region rewrite, continuation past the end, adding a new instrument layer, or generating accompaniment for a vocal-only stem. This task uses `driver: custom` with a `family` field to select the model family and a `preset` field to select the checkpoint variant.

**Component Settings:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task` | string | **required** | Must be `music-generation` |
| `driver` | string | `custom` | Model driver |
| `family` | string | **required** | Model family (currently `ace-step`) |
| `preset` | string | `acestep-v15-turbo` | Checkpoint preset (`acestep-v15-turbo`, `acestep-v15-base`, `acestep-v15-sft`) |
| `model` | string | **required** | Local checkpoint directory. ACE-Step does not accept HuggingFace Hub identifiers |

**Common Action Fields:**

Every method shares these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Operation: `generate`, `cover`, `rewrite`, `extend`, `layer`, `accompany` |
| `seed` | int | `null` | Random seed for reproducible generation |
| `batch_size` | int | `1` | Number of inputs processed per batch |
| `params.duration` | int | `30` | Duration of the generated music in seconds |
| `params.bpm` | int | `120` | Target tempo in beats per minute |
| `params.key_scale` | string | `null` | Musical key of the generated music (e.g., `C`, `D`, `Em`) |
| `params.time_signature` | string | `4/4` | Musical time signature (e.g., `4/4`, `3/4`) |
| `params.inference_steps` | int | `8` | Number of diffusion inference steps (turbo: `8`, base: `32`, sft: `50`) |
| `params.guidance_scale` | float | `5.0` | Classifier-free guidance scale applied during sampling |

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

**Result Shape:**

Returns a single PCM audio stream (or a list of streams for batched inputs). Each stream carries `sample_rate`, `channels`, and `bit_depth` attributes.

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

The `streaming` action field is available on tasks that produce time-series output one chunk at a time: `text-generation`, `chat-completion`, `text-to-text`, `image-to-text`, `speech-to-text`, and `voice-activity-detection`. Other tasks (such as `text-embedding`, `text-classification`, `text-reranking`, `image-embedding`, `text-to-speech`) return their result atomically and do not accept a `streaming` field. Streaming also requires `batch_size: 1` with a single input.

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
- **Search**: Generate embeddings for semantic search
- **Visual Search / Dedup**: Encode images with CLIP/DINOv2 for similarity retrieval and near-duplicate detection
- **Translation**: Translate between languages
- **Summarization**: Create summaries of long documents
- **Code Generation**: Generate and complete code snippets
- **Image Understanding**: Describe and analyze images
- **Text-to-Speech**: Synthesize speech from text with voice generation, cloning, and design
