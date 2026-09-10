# Chapter 10: Working with Local AI Models

This chapter covers how to use local AI models with model-compose.

---

## 10.1 Local Model Overview

### What are Local Models?

Local models are AI models that run directly on your system without external APIs. model-compose supports various drivers and model formats, providing a flexible model execution environment.

### Supported Model Drivers

model-compose supports the following model drivers:

| Driver | Description | Primary Use Cases |
|--------|-------------|-------------------|
| `huggingface` | HuggingFace transformers | General-purpose inference, widest model support |
| `unsloth` | Unsloth optimized models | Fast fine-tuning, memory-efficient training |
| `vllm` | vLLM inference engine | High-performance LLM serving, production deployment |
| `llamacpp` | llama.cpp engine | CPU inference, GGUF format, low-resource environments |
| `custom` | Custom implementation | Special models, custom logic |

### Supported Model Formats

Various model formats are supported:

| Format | Description | Compatible Drivers |
|--------|-------------|-------------------|
| `pytorch` | PyTorch default format (.bin, .pt) | huggingface, unsloth |
| `safetensors` | Safe tensor storage format | huggingface, unsloth |
| `onnx` | Optimized cross-platform format | custom |
| `gguf` | llama.cpp quantized format | llamacpp |
| `tensorrt` | NVIDIA TensorRT optimized | custom |

### Pros and Cons of Local Models

**Pros:**
- **Cost savings**: No API call costs
- **Privacy**: Data never leaves your system
- **Offline execution**: No internet connection required
- **Customization**: Apply fine-tuning, LoRA adapters
- **Low latency**: No network delays (depending on local hardware)

**Cons:**
- **Hardware requirements**: GPU memory and compute power needed
- **Model size**: Large model files to download and store
- **Configuration complexity**: Environment setup, dependency management
- **Performance constraints**: Large models require high-end GPUs

### Basic Usage

**Simple model loading (HuggingFace)**
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  # Default driver is huggingface
```

**Specifying driver**
```yaml
component:
  type: model
  task: text-generation
  driver: unsloth  # Use Unsloth driver
  model: unsloth/llama-2-7b-bnb-4bit
```

**Loading local files**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: local
    path: /path/to/model
    format: pytorch
```

**GGUF format**
```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: /models/llama-2-7b-chat.Q4_K_M.gguf
    format: gguf
```

---

## 10.2 Model Installation and Setup

### Specifying Model Sources

model-compose can load models through two providers:

#### 1. HuggingFace Hub (provider: huggingface)

**Simple method (string)**
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  # Automatically loads from HuggingFace Hub
```

**Detailed configuration**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    revision: main                  # Branch or commit hash
    filename: pytorch_model.bin     # Specific file
    cache_dir: /custom/cache        # Cache directory
    local_files_only: false         # Use local cache only
    token: ${env.HUGGINGFACE_TOKEN} # Private model token
```

**HuggingFace configuration fields:**
- `repository`: HuggingFace model repository (required)
- `revision`: Model version or branch (default: `main`)
- `filename`: Specific file within repository (optional)
- `cache_dir`: Model file cache directory (default: `~/.cache/huggingface/`)
- `local_files_only`: Use local cache only (default: `false`)
- `token`: Private model access token (optional)

#### 2. Local Files (provider: local)

**Simple method (path string)**
```yaml
component:
  type: model
  task: text-generation
  model: /path/to/model
  # Automatically recognized as local path
```

**Detailed configuration**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: local
    path: /path/to/model
    format: pytorch  # pytorch, safetensors, onnx, gguf, tensorrt
```

**Local configuration fields:**
- `path`: Model file or directory path (required)
- `format`: Model file format (default: `pytorch`)

**Local path recognition rules:**

Strings starting with these patterns are automatically recognized as local paths:
- Absolute path: `/path/to/model`
- Relative path: `./model`, `../model`
- Home directory: `~/models/model`
- Windows drive: `C:\models\model`

Others are recognized as HuggingFace Hub repositories:
- `meta-llama/Llama-2-7b-hf`
- `gpt2`
- `username/custom-model`

### HuggingFace Model Download

Models are automatically downloaded on first run, and required packages are installed automatically:

```yaml
component:
  type: model
  task: chat-completion
  model: meta-llama/Llama-2-7b-chat-hf
  # Downloaded to ~/.cache/huggingface/ on first run
```

Manual download:
```bash
# Pre-download with HuggingFace CLI
pip install huggingface-hub
huggingface-cli download meta-llama/Llama-2-7b-chat-hf
```

### Accessing Private Models

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    token: ${env.HUGGINGFACE_TOKEN}
```

Environment variable setup:
```bash
export HUGGINGFACE_TOKEN=hf_your_token_here
model-compose up
```

### Using Specific Model Versions

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    revision: v1.0  # Specific tag
    # Or commit hash: revision: a1b2c3d4
```

### Offline Mode

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: gpt2
    local_files_only: true  # Load from local cache only
```

---

## 10.3 Supported Task Types

model-compose supports the following task types:

| Task | Description | Primary Use Cases |
|------|-------------|-------------------|
| `text-generation` | Text generation | Story writing, code generation |
| `chat-completion` | Conversational completion | Chatbots, assistants |
| `text-to-text` | Seq2seq text transforms | Translation, summarization, paraphrasing |
| `text-classification` | Text classification | Sentiment analysis, topic classification |
| `text-embedding` | Text embedding | Semantic search, RAG |
| `text-reranking` | Query-document scoring | Rerank retrieval results in RAG pipelines |
| `image-to-text` | Image captioning | Image description, VQA |
| `image-text-to-text` | Multimodal image + text generation | Visual reasoning, multimodal chat |
| `image-embedding` | Image embedding | Visual search, image dedup, clustering |
| `video-embedding` | Video embedding | Semantic video search, dedup, clustering |
| `image-generation` | Image generation | Text-to-image conversion |
| `image-upscale` | Image upscaling | Resolution enhancement |
| `text-to-speech` | Text-to-speech synthesis | Voice generation, cloning, design |
| `speech-to-text` | Speech recognition | Transcription, subtitles |
| `speaker-diarization` | Who spoke when | Per-speaker turns for meetings, interviews |
| `voice-activity-detection` | Detect speech segments in audio | Pre-ASR silence filtering, subtitle splitting |
| `face-detection` | Face detection | Locate faces in images |
| `pose-detection` | Pose detection | Keypoint estimation |
| `object-detection` | Object detection | Detect objects with class labels and bounding boxes |
| `image-segmentation` | Image segmentation | Generate per-region binary masks (automatic or box-prompted) |
| `text-to-video` | Video generation from text | Prompt-driven short video clips |
| `image-to-video` | Video generation from an image | Animate a still image, optionally guided by a prompt |
| `face-embedding` | Face embedding | Face recognition, comparison |
| `face-tracking` | Face tracking | Track identities across video frames with timecoded segments |
| `pose-tracking` | Pose tracking | Track people (as poses) across video frames with per-track timecoded segments |
| `object-tracking` | Object tracking | Track objects across video frames with per-track timecoded segments |
| `shot-boundary-detection` | Shot boundary detection | Detect hard cuts in a video with per-shot start/end timecodes |
| `music-generation` | Music generation | Audio/music synthesis |
| `music-source-separation` | Music source separation | Split a mix into vocals / drums / bass / other stems |
| `music-transcription` | Music transcription | Convert audio recordings into MIDI + note events |

### 10.3.1 text-generation

Generates text based on prompts.

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  action:
    prompt: ${input.prompt as text}
    params:
      max_output_length: 32768
      temperature: 0.7
      top_p: 0.9
```

**Key parameters:**
- `max_output_length`: Maximum tokens to generate
- `temperature`: Generation randomness (0.0~2.0, lower is more deterministic)
- `top_p`: Nucleus sampling threshold
- `top_k`: Top-K sampling
- `repetition_penalty`: Repetition prevention (1.0~2.0)

### 10.3.2 chat-completion

Processes conversational messages.

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
        content: ${input.user_prompt}
    params:
      max_output_length: 2048
      temperature: 0.7
```

**Message format:**
- `role`: `system`, `user`, `assistant`
- `content`: Message content

**Overriding the chat template:**

Set `chat_template` on the component to override the tokenizer's default Jinja template (applies to `huggingface`, `vllm`, and `llamacpp` drivers):

```yaml
component:
  type: model
  task: chat-completion
  model: HuggingFaceTB/SmolLM3-3B
  chat_template: |
    {%- for message in messages %}
    <|{{ message.role }}|>
    {{ message.content }}</s>
    {%- endfor %}
```

### 10.3.3 text-to-text

Runs seq2seq (encoder-decoder) transforms such as translation, summarization, and paraphrasing.

```yaml
# Translation (Helsinki-NLP)
component:
  type: model
  task: text-to-text
  driver: huggingface
  model: Helsinki-NLP/opus-mt-en-fr
  action:
    text: ${input.text as text}
```

```yaml
# Summarization (BART)
component:
  type: model
  task: text-to-text
  driver: huggingface
  architecture: bart
  model: facebook/bart-large-cnn
  action:
    text: ${input.document as text}
    params:
      max_output_length: 150
```

```yaml
# T5-family (requires task prefix in the input text)
component:
  type: model
  task: text-to-text
  driver: huggingface
  architecture: t5
  model: t5-base
  action:
    text: "summarize: ${input.document}"
```

**Supported architectures:**
- `auto` (default): Automatically inferred from the model
- `bart`: BART-family encoder-decoder models
- `t5`: T5-family models (require task prefixes in the input text)

### 10.3.4 text-classification

Classifies text into categories.

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased-finetuned-sst-2-english
  action:
    text: ${input.text as text}
    output:
      label: ${result.label}
      score: ${result.score}
```

### 10.3.5 text-embedding

Converts text into high-dimensional vectors.

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
  action:
    text: ${input.text as text}
    output:
      embedding: ${result.embedding}
```

Usage example (RAG system):
```yaml
workflow:
  title: Document Search
  jobs:
    - id: embed-query
      component: embedder
      input:
        text: ${input.query}
      output:
        query_vector: ${result.embedding}

    - id: search
      component: vector-store
      action: search
      input:
        vector: ${jobs.embed-query.output.query_vector}
        top_k: 5
```

### 10.3.6 text-reranking

Scores each (query, document) pair with a cross-encoder and returns the documents ordered by relevance. This is the second stage of a typical retrieval pipeline: a vector store fetches a broad candidate set, then a reranker refines the top results.

```yaml
component:
  type: model
  task: text-reranking
  model: BAAI/bge-reranker-v2-m3
  action:
    query: ${input.query}
    documents: ${input.candidates}
    top_k: 5
```

**Key parameters:**
- `query`: Query string. Pass a list to run several independent reranking jobs at once.
- `documents`: Candidate documents. Strings, or objects paired with `document_field: <field>`.
- `top_k`: Keep only the top K results per query.
- `score_threshold`: Drop results below this score.
- `return_documents`: When `false`, results contain only `index` and `score`.

Usage example (RAG rerank stage):
```yaml
workflow:
  title: Reranked Document Search
  jobs:
    - id: embed-query
      component: embedder
      input:
        text: ${input.query}

    - id: retrieve
      component: vector-store
      action: search
      input:
        vector: ${jobs.embed-query.output}
        top_k: 50

    - id: rerank
      component: reranker
      input:
        query: ${input.query}
        candidates: ${jobs.retrieve.output}
        document_field: text
        top_k: 5
```

### 10.3.7 image-to-text

Analyzes images and generates text.

```yaml
component:
  type: model
  task: image-to-text
  model: Salesforce/blip-image-captioning-large
  architecture: blip
  action:
    image: ${input.image as image}
    prompt: ${input.prompt as text}
```

**Supported architectures:**
- `blip`: Image captioning
- `git`: Generative Image-to-Text
- `vit-gpt2`: Vision Transformer + GPT-2

### 10.3.8 image-embedding

Encodes images into fixed-size vectors for visual similarity, dedup, and retrieval.

```yaml
component:
  type: model
  task: image-embedding
  driver: huggingface
  architecture: clip
  model: openai/clip-vit-base-patch32
  action:
    image: ${input.image as image}
    batch_size: 16
    params:
      normalize: true
```

**Supported architectures:**
- `clip`: OpenAI CLIP — image encoder via `get_image_features`
- `siglip`: Google SigLIP — image encoder via `get_image_features`
- `dinov2`: Meta DINOv2 — self-supervised encoder, pooled via `params.pooling`
- `auto`: `AutoModel` fall-through — uses `get_image_features` if the loaded model exposes it, otherwise pools `last_hidden_state`

CLIP and SigLIP have built-in poolers so `params.pooling` is ignored for them. For DINOv2 (and `auto` when the loaded model has no projection head), `params.pooling` chooses among `cls` (default), `mean`, or `max`.

Result: single vector per image (`List[float]`); with a list input, a list of vectors; with an async stream input, an async iterator of vectors.

### 10.3.9 video-embedding

Encodes a sequence of video frames into a single fixed-size vector, suitable for semantic video search, dedup, or clustering. Pair with `video-frame-extractor` to sample frames from a source video first.

```yaml
component:
  id: video-embed
  type: model
  task: video-embedding
  driver: huggingface
  architecture: xclip
  model: microsoft/xclip-base-patch32
  action:
    frames: ${input.frames}
    params:
      normalize: true
    output: ${result}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | image / list | **required** | Frames for one video, a list of frames, a list of per-video frame batches, or a stream of batches |
| `batch_size` | int | `1` | Number of videos processed per batch |
| `params.normalize` | bool | `true` | L2-normalize the output vector |

**Supported architectures:**
- `xclip`: Microsoft X-CLIP (video-text contrastive; e.g., `microsoft/xclip-base-patch32`).
- `videomae`: VideoMAE masked autoencoder (e.g., `MCG-NJU/videomae-base`).
- `auto`: infers from the loaded model config.

Result shape:

```json
[0.021, -0.114, 0.087, ...]
```

Typical pipeline: `video-frame-extractor` → `video-embedding` → `vector-store` for retrieval.

### 10.3.10 image-generation

Generates images from text prompts.

```yaml
component:
  type: model
  task: image-generation
  architecture: flux
  model: black-forest-labs/FLUX.1-dev
  action:
    prompt: ${input.prompt as text}
    width: 1024
    height: 1024
    params:
      num_inference_steps: 50
```

**Supported architectures:**
- `flux`: FLUX model
- `sdxl`: Stable Diffusion XL
- `hunyuan`: HunyuanDiT

### 10.3.11 image-upscale

Enhances image resolution.

```yaml
component:
  type: model
  task: image-upscale
  architecture: real-esrgan
  model: RealESRGAN_x4plus
  action:
    image: ${input.image as image}
    params:
      scale: 4
```

**Supported architectures:**
- `real-esrgan`: Real-ESRGAN
- `esrgan`: ESRGAN
- `swinir`: SwinIR
- `ldsr`: Latent Diffusion Super Resolution

### 10.3.12 text-to-speech

Synthesizes speech audio from text. This task uses `driver: custom` with a `family` field to pick the model family and a `method` field on the action to choose the generation method. Seven families are supported: `qwen`, `kokoro`, `chatterbox`, `luxtts`, `tada`, `cosyvoice`, `fireredtts3`.

**Available methods:**

| Method | Description |
|--------|-------------|
| `generate` | Synthesize with a preset voice, optionally with style controls |
| `clone` | Clone a voice from a reference audio clip |
| `design` | Create a new voice from a natural-language description |
| `edit` | Edit existing audio (content, speed, pitch, volume) |

Not every family implements every method — see the family sections below and the [reference matrix](../reference/compose/components/model.md#text-to-speech).

**Common action fields (all families):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Generation method: `generate`, `clone`, `design`, `edit` |
| `text` | string/array | **required** | Text (or list of texts) to synthesize; ignored by `edit` |
| `language` | string | `null` | Language of the text; used by families that condition on language |
| `batch_size` | int | `1` | Number of input texts processed per batch |

#### Family: `qwen`

Alibaba Qwen3-TTS. All three methods are available; pick the checkpoint that matches the method.

Suggested checkpoints:

| Model | Method | Description |
|-------|--------|-------------|
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | `generate` | Built-in voices with style control |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | `clone` | Voice cloning from reference audio |
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | `design` | Voice design from a description |

`generate` — pick a built-in voice and optionally add style instructions:

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

`clone` — reproduce a target voice from a short reference clip:

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

`design` — describe the voice you want in natural language:

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

Languages: English, Chinese, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian — resolved from the ISO 639-1 prefix of `language` (e.g. `ko`, `zh-CN`).

#### Family: `kokoro`

Kokoro TTS. Lightweight, preset-voice synthesis; `generate` only.

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

Voice IDs follow the Kokoro `<language><gender>_<name>` convention (e.g. `af_heart`, `af_bella`, `am_michael`, `bf_emma`). Languages: American English, British English, Japanese, Mandarin Chinese, Spanish, French, Hindi, Italian, Brazilian Portuguese. Output sample rate: 24 kHz.

#### Family: `chatterbox`

Resemble AI Chatterbox. Preset synthesis and zero-shot cloning with expressive controls (`exaggeration`, `cfg_weight`, `temperature`).

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
    exaggeration: 0.6
    cfg_weight: 0.5
    temperature: 0.8
```

For preset synthesis, switch `method` to `generate` and drop `reference_audio`. Recommended reference length: 5 seconds or more.

#### Family: `luxtts`

LuxTTS. Zero-shot cloning with fine-grained flow-matching controls; `clone` only.

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

Trade quality for speed via `num_steps` (default `4`) and `guidance_scale` (default `3.0`). Output sample rate: 48 kHz. On CPU, thread count is auto-clamped.

#### Family: `tada`

Hume TADA. Zero-shot cloning; `clone` only. If you omit `reference_text`, TADA uses its built-in ASR to transcribe the reference clip — English only.

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

The tokenizer defaults to the ungated `unsloth/Llama-3.2-1B` mirror; override with the component-level `tokenizer` field if needed. Output sample rate: 24 kHz. MPS falls back to CPU because of flow-matching instability on Apple Silicon.

#### Family: `cosyvoice`

FunAudioLLM CosyVoice / CosyVoice2 / CosyVoice3. The AutoModel factory picks the right version by inspecting `cosyvoice{,2,3}.yaml` inside the model directory.

The runtime downloads and installs the upstream `cosyvoice` and `matcha` packages from GitHub on first startup (pinned commits). No `git` CLI is required, but the first run may take a while.

`generate` — use a built-in speaker on `CosyVoice-300M-SFT`, or a pre-registered zero-shot speaker on v2/v3:

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
```

`clone` — with a transcript uses zero-shot, without one uses cross-lingual (any language reference):

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

`design` — instruction-guided voice design (CosyVoice2/3 only):

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

CUDA-only acceleration flags: `load_jit`, `load_trt`, `load_vllm`, `fp16`. All are silently ignored on CPU.

#### Family: `fireredtts3`

FireRedTeam FireRedTTS3. Two presets share the family:

- `preset: base` — cloning only, with language conditioning.
- `preset: instruct` — cloning plus voice design and audio editing.

The runtime downloads and installs the upstream `fireredtts3` package from GitHub on first startup (pinned commit).

`clone` on the `base` preset:

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

`design` on the `instruct` preset — describe the target voice:

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

`edit` on the `instruct` preset — the `text` field is ignored; the instruction alone rewrites the audio:

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

Edit modes: `semantic` for free-form content edits, `acoustic` for template instructions like `adjust the speed to 1.2`. Output sample rate: 24 kHz for both presets. Calling `design`/`edit` on the `base` preset raises a runtime error.

### 10.3.13 speech-to-text

Transcribes audio into text, optionally with per-segment or per-word timestamps. Supports the HuggingFace transformers backend (Whisper family) and several `custom` families (faster-whisper, crisper-whisper, fun-asr, vibevoice).

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

**Common action fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | audio | **required** | Input audio file, list of audios, or async stream |
| `language` | string | `null` | Language code (`en`, `ko`, ...); unset triggers auto-detection where supported |
| `return_timestamps` | bool | `false` | Include per-segment timestamps in the result |
| `timestamp_level` | string | `segment` | `segment` or `word`; word-level requires backend support |
| `time_offset` | time / list | `null` | Offset added to each segment's timestamps; scalars broadcast, lists pair per audio |
| `batch_size` | int | `1` | Number of audios processed per batch |
| `streaming` | bool | `false` | Emit transcribed chunks incrementally |

Family-specific action fields include Whisper-style decoding params (`num_beams`, `temperature`, `no_speech_threshold`, ...) for `faster-whisper` and the HuggingFace `whisper` driver, style/hotword controls (`mode`, `hotwords`, `longform_strategy`, ...) for `crisper-whisper`, and sampling / beam / context knobs (`temperature`, `top_p`, `num_beams`, `context_info`) for `vibevoice`. Fun-ASR configures VAD and punctuation on the component (`voice_activity_detection`, `punctuation`).

Plain-text mode (default) returns a string per input; timestamped mode returns a list of `{ text, start_time, end_time }` segments, with an added `words` array when `timestamp_level: word`.

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

With `streaming: true`, Whisper-family backends stream token-level chunks as decoding proceeds; VibeVoice streaming checkpoints stream per-chunk transcript text. Non-streaming checkpoints (VibeVoice offline, pyannote-based flows) fall back to yielding the collected result as a single chunk to preserve the `AsyncIterator` contract.

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `faster-whisper` | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2 Whisper runtime; beam search, VAD, chunked long-form |
| `crisper-whisper` | [nyralabs/crisperwhisper](https://pypi.org/project/crisperwhisper/) | Word-precise Whisper variant. Picks `ct2` fork when available, else `transformers`. Size shorthands (`large`, `turbo`, `medium`, `small`, and `*_pro`) resolve to `nyralabs/CrisperWhisper2.0_<size>` |
| `fun-asr` | [FunAudioLLM/FunASR](https://github.com/modelscope/FunASR) | Chinese-first multi-language ASR with optional VAD and punctuation stages. Default model: `FunAudioLLM/Fun-ASR-MLT-Nano-2512` |
| `vibevoice` | [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) | Streaming and offline ASR checkpoints. Default: `microsoft/VibeVoice-ASR-Streaming-1.5B`. Language is auto-detected across 10 languages |

The HuggingFace `whisper` driver runs stock Whisper checkpoints via `transformers`; use it when you need the transformers ecosystem (LoRA adapters, quantization) rather than the CT2-backed `faster-whisper` fast path.

### 10.3.14 speaker-diarization

Segments an audio file by speaker and returns per-speaker turns with start/end times and a speaker label. Runs the `pyannote.audio` speaker-diarization pipeline.

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

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | audio | **required** | Input audio file, list of audios, or async stream |
| `speaker_count` | int | `null` | Exact speaker count when known |
| `min_speaker_count` | int | `null` | Lower bound on the number of speakers considered |
| `max_speaker_count` | int | `null` | Upper bound on the number of speakers considered |
| `batch_size` | int | `1` | Number of audios processed per batch |
| `streaming` | bool | `false` | Emit turns as an async iterator (fake stream: pipeline needs the whole audio first) |
| `params.min_segment_duration` | duration | `"0s"` | Discard turns shorter than this |
| `params.merge_gap` | duration | `"0s"` | Merge adjacent same-speaker turns within this gap |

Duration fields accept values like `"250ms"`, `"0.5s"`, or bare numeric seconds.

Result shape (flat list of turns sorted by `start_time`):

```json
[
  { "speaker": "SPEAKER_00", "start_time": 0.48,  "end_time": 3.72,  "confidence": 1.0 },
  { "speaker": "SPEAKER_01", "start_time": 3.90,  "end_time": 7.16,  "confidence": 1.0 },
  { "speaker": "SPEAKER_00", "start_time": 7.44,  "end_time": 12.02, "confidence": 1.0 }
]
```

`confidence` is reported as `1.0` — pyannote does not expose per-turn confidence. Pyannote diarization is not truly streamable: with `streaming: true` the same turns are re-emitted one-by-one to preserve the `AsyncIterator` contract.

The default `pyannote/speaker-diarization-3.1` checkpoint is gated on HuggingFace. Accept the license and pass an access token via `model.token` (or `${env.HUGGINGFACE_TOKEN}`).

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `pyannote` | [pyannote/pyannote-audio](https://github.com/pyannote/pyannote-audio) | Runs any `pyannote.audio` diarization pipeline; requires accepting the HuggingFace license |

### 10.3.15 voice-activity-detection

Detects speech segments in an audio file and returns their start/end timestamps with a confidence score. Silent regions are omitted from the result. Commonly used as a pre-processing step before speech-to-text to skip silence and reduce hallucinations.

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

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sample_rate` | int | `16000` | Target sample rate (16000 or 8000); input is resampled if needed |
| `threshold` | float | `0.5` | Speech probability threshold (0.0 - 1.0); higher = stricter |
| `min_speech_duration` | duration | `250ms` | Discard speech chunks shorter than this |
| `min_silence_duration` | duration | `500ms` | Silence required to split adjacent chunks |
| `speech_padding_time` | duration | `100ms` | Padding added to both sides of each detected chunk |

Duration fields accept values like `"250ms"`, `"0.5s"`, or bare numeric seconds.

Result shape (flat list of speech segments, silent regions omitted):

```json
[
  { "start_time": 0.124, "end_time": 44.58,  "confidence": 0.916 },
  { "start_time": 47.07, "end_time": 150.02, "confidence": 0.937 }
]
```

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `silero` | [snakers4/silero-vad](https://github.com/snakers4/silero-vad) (pip) | Lightweight CNN (~1MB); the model ships inside the pip package |

### 10.3.16 face-embedding

Extracts feature vectors from face images.

```yaml
component:
  type: model
  task: face-embedding
  model: buffalo_l
  action:
    image: ${input.image as image}
```

### 10.3.17 face-tracking

Tracks faces across a sequence of video frames. Per-frame detections are grouped into identity tracks by cosine similarity on the face embedding, and consecutive hits for the same identity are merged into timecoded segments. Uses InsightFace.

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
    return_track_image: true
    params:
      similarity_threshold: 0.4
      min_frame_count: 2
      merge_gap: 1.0
```

Accepts a single frame sequence, a list of sequences, or an async stream of frame batches (runs lazily on streamed input without buffering the whole video). See the [Model Component reference](../reference/compose/components/model.md#face-tracking) for the full option list and result shape.

### 10.3.18 pose-tracking

Tracks people (as poses) across a sequence of video frames. Per-frame pose detections are grouped by the underlying tracker's persistent `track_id`, and consecutive hits are merged into timecoded segments. Uses Ultralytics YOLO-pose.

```yaml
component:
  type: model
  task: pose-tracking
  driver: custom
  family: yolo
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    skeleton_format: openpose
    return_track_image: true
    params:
      min_confidence: 0.5
      min_frame_count: 3
      merge_gap: 0.5
```

Accepts the same input shapes as face-tracking. See the [Model Component reference](../reference/compose/components/model.md#pose-tracking) for the full option list, streaming chunk schema, and result shape.

### 10.3.19 object-tracking

Tracks objects across a sequence of video frames. Per-frame detections are grouped by the tracker's persistent `track_id`, and consecutive hits are merged into timecoded segments with optional interpolation across small gaps. Uses Ultralytics YOLO.

```yaml
component:
  type: model
  task: object-tracking
  driver: custom
  family: yolo
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    labels: [ person, car ]
    return_track_image: true
    params:
      min_confidence: 0.3
      min_frame_count: 3
      merge_gap: 0.5
      tracker: bytetrack
```

Accepts the same input shapes as face-tracking. See the [Model Component reference](../reference/compose/components/model.md#object-tracking) for the full option list, streaming chunk schema, and result shape.

### 10.3.20 object-detection

Detects objects in an image and returns per-object bounding boxes with class labels and confidence scores. Uses Ultralytics YOLO.

```yaml
component:
  type: model
  task: object-detection
  driver: custom
  family: yolo
  action:
    image: ${input.image as image}
    labels: [ person, dog ]      # Optional class filter
    bounding_box_padding: 0.05   # Grow each box by 5% for downstream crops or SAM prompts
    params:
      min_confidence: 0.4
```

Any Ultralytics YOLO detection (or segmentation) `.pt` checkpoint is accepted. See the [Model Component reference](../reference/compose/components/model.md#object-detection) for the full option list and result shape.

### 10.3.21 image-segmentation

Generates per-region binary segmentation masks from an image. Runs in **automatic mode** (masks every distinct region) or **box-prompted mode** (refines masks around user-supplied bounding boxes, e.g. from `object-detection`). Uses Meta's Segment Anything Model (SAM) via Ultralytics.

```yaml
component:
  type: model
  task: image-segmentation
  driver: custom
  family: sam
  action:
    image: ${input.image as image}
    box_prompt: ${input.box_prompt as json}   # Optional; omit for automatic mode
    max_segment_count: 20
    params:
      min_confidence: 0.6
```

Any Ultralytics SAM checkpoint (`sam_b.pt`, `sam2_b.pt`, `mobile_sam.pt`, etc.) is accepted. See the [Model Component reference](../reference/compose/components/model.md#image-segmentation) for the full option list and result shape.

### 10.3.22 text-to-video

Generates a short video clip from a text prompt. Uses `driver: custom` with a `family` field to select the model family and a `preset` field to select the checkpoint variant.

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
    negative_prompt: ${input.negative_prompt | ""}
    params:
      num_frames: 81
      fps: 24
      width: 1280
      height: 720
      inference_steps: 50
      guidance_scale: 5.0
```

**Supported families and presets:**
- `wan`
  - `t2v-a14b` — Wan2.2 T2V 27B (14B active); requires ~80GB+ VRAM.
  - `ti2v-5b` — Wan2.2 hybrid text-and-image-to-video 5B; runs on a single 24GB GPU (RTX 4090).

The result is a single mp4 stream (or a list of mp4 streams for batched prompts). See the [Model Component reference](../reference/compose/components/model.md#text-to-video) for the full option list.

### 10.3.23 image-to-video

Generates a short video clip that animates an input image, optionally guided by a text prompt.

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

**Supported families and presets:**
- `wan`
  - `i2v-a14b` — Wan2.2 I2V 27B (14B active); requires ~80GB+ VRAM.
  - `ti2v-5b` — Wan2.2 hybrid text-and-image-to-video 5B; runs on a single 24GB GPU.

`width`/`height` are optional; when omitted, the input image's dimensions are used. The result shape mirrors `text-to-video` (an mp4 stream per input).

### 10.3.24 shot-boundary-detection

Detects shot boundaries (hard cuts and transitions) in a video and returns per-shot start/end timecodes and frame indices. Uses a deep learning model to identify precise cut points frame-by-frame. Uses `driver: custom` with a `family` field to select the model family.

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

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | video | **required** | Input video file, list of videos, or async stream |
| `start_time` | time | `null` | Time in the source at which detection begins (e.g., `00:01:00`, `60s`) |
| `end_time` | time | `null` | Time in the source at which detection stops |
| `batch_size` | int | `1` | Number of videos processed per batch |
| `streaming` | bool | `false` | Emit each detected shot as it is confirmed (per-input stream) |
| `params.threshold` | float | `0.5` | Confidence threshold above which a frame is treated as a shot boundary (0.0 - 1.0); higher = fewer boundaries |

Result shape (flat list of shots per input):

```json
[
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
```

#### Supported families

| Family | Backend | Notes |
|--------|---------|-------|
| `transnetv2` | [soCzech/TransNetV2](https://github.com/soCzech/TransNetV2) | Deep learning shot detector; GPU-accelerated (TensorFlow). Point `model.path` at the SavedModel folder containing `saved_model.pb` and `variables/` |

Compared with the `video-scene-detector` component (which uses classical CV heuristics via PySceneDetect/FFmpeg to group semantically similar frames), `shot-boundary-detection` runs a neural network trained specifically to localize cut points and is generally more accurate on modern edited content.

### 10.3.25 music-generation

Generates or edits music audio. The action's `method` field selects the operation — generate from scratch (also used for MIDI synthesis), cover an existing track in a new style, rewrite a specific region, extend past the end, add an instrument layer, or generate accompaniment for a vocal-only stem. Uses `driver: custom` with a `family` field to select the model family; ACE-Step also takes a `preset` field for the checkpoint variant.

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

**Supported methods:**

| Method | Purpose | Required fields (beyond common) |
|--------|---------|---------------------------------|
| `generate` | Generate music from scratch | `prompt` (optional `lyrics`, `reference_audio`) |
| `cover` | Cover an existing track in a new style | `source`, `prompt` (optional `lyrics`) |
| `rewrite` | Regenerate a specific `[start_time, end_time]` region | `source`, `start_time`, `end_time`, `prompt` (optional `lyrics`) |
| `extend` | Continue the source past its natural end | `source`, `prompt` (optional `lyrics`) |
| `layer` | Add a new instrument or part on top of the source | `source`, `track_class` (optional `prompt`, `lyrics`) |
| `accompany` | Generate accompaniment for a vocal-only source | `vocal`, `track_classes` (optional `prompt`) |

**Supported families and presets:**
- `ace-step`
  - `acestep-v15-turbo` — fast turbo variant (default `inference_steps: 8`).
  - `acestep-v15-base` — base variant (recommended `inference_steps: 32`).
  - `acestep-v15-sft` — SFT variant (recommended `inference_steps: 50`).
- `midi-ddsp`
  - Synthesizes a monophonic MIDI file with a specific URMP instrument voice (violin, viola, cello, double-bass, flute, oboe, clarinet, saxophone, bassoon, trumpet, horn, trombone, tuba). Uses `method: generate` with `midi` and `instrument` fields. Polyphonic MIDI is rejected.

Neither family accepts HuggingFace Hub identifiers — `model` must be a local checkpoint directory.

MIDI-DDSP pins TensorFlow 2.11 and cannot coexist with the host mindor stack, so the component must run under an isolated runtime (`virtualenv`, `docker`, or `apple-container`); native / embedded / process runtimes are rejected at load time.

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
```

The result is a PCM audio stream per input (or a list of streams for batched inputs). See the [Model Component reference](../reference/compose/components/model.md#music-generation) for the full per-method field list.

### 10.3.26 music-source-separation

Splits a mixed recording into individual instrument stems (vocals, drums, bass, other). Uses `driver: custom` with a `family` field to select the model backend.

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
      stems: [ vocals ]   # omit to return every stem the model produces
      overlap: 0.25
      shifts: 1
```

**Supported families:**

| Family | Scope | Notes |
|--------|-------|-------|
| `demucs` | Four-stem (or six-stem) separation | Meta AI's Hybrid Transformer Demucs. `htdemucs_ft` is a fine-tuned ensemble; `htdemucs_6s` adds `guitar` + `piano` stems |
| `mdx-net` | Vocal isolation | UVR MDX-Net via ONNX Runtime. Instrumental stem is derived by subtracting vocals from the mix |

When one stem is requested, the action returns a single audio stream. When multiple stems are requested (e.g. `stems: [vocals, drums, bass, other]`) — or when `stems` is omitted so every stem the model produces is returned — it returns a `{ "<stem_name>": <stream>, ... }` map. Higher `shifts` and `overlap` trade wall-clock time for cleaner separation.

Chain with `music-transcription` to transcribe each stem into its own MIDI, or with `speech-to-text` on the vocal stem for cleaner lyric transcription. See the [Model Component reference](../reference/compose/components/model.md#music-source-separation) for the full per-family field list.

### 10.3.27 music-transcription

Transcribes recorded audio into a MIDI file and a JSON list of note events (start time, end time, pitch, velocity). Uses `driver: custom` with a `family` field to select the model backend.

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

**Supported families:**

| Family | Scope | Notes |
|--------|-------|-------|
| `basic-pitch` | Polyphonic, instrument-agnostic | Spotify Basic Pitch (ICASSP-2022); runs on CPU via ONNX; checkpoint ships inside the wheel |
| `piano-transcription` | 88-key piano only | ByteDance Piano Transcription; detects sustain-pedal events; auto-downloads ~180 MB checkpoint on first use |

The action returns a dict with two fields per input: `midi` (a MIDI file) and `notes` (a JSON list of `{start_time, end_time, pitch, velocity}` objects with times in seconds and pitch as MIDI note number). Basic Pitch adds a per-note `pitch_bends` array when `return_pitch_bends` is enabled. Piano Transcription bakes pedal events into the MIDI directly.

Chain with `music-source-separation` to transcribe each stem of a mix independently (e.g. transcribe the vocal line and the accompaniment as separate parts). See the [Model Component reference](../reference/compose/components/model.md#music-transcription) for the full per-family field list.

---

## 10.4 Model Configuration (Device, Precision, Batch Size)

### Device Configuration

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  device: cuda         # 'cuda', 'cpu', 'mps' (Apple Silicon)
  device_mode: single  # 'single', 'auto' (multi-GPU)
```

**Device options:**
- `cuda`: NVIDIA GPU
- `cpu`: CPU only
- `mps`: Apple Silicon GPU (M1/M2/M3)

**Device modes:**
- `single`: Single GPU
- `auto`: Automatic distribution across multiple GPUs

Multi-GPU example:
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  device: cuda
  device_mode: auto  # Automatically distribute across GPUs
```

### Precision Configuration

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  precision: float16  # 'auto', 'float32', 'float16', 'bfloat16'
```

**Precision options:**
- `auto`: Automatic selection (float16 for GPU, float32 for CPU)
- `float32`: Highest accuracy, most memory usage
- `float16`: Half memory, faster inference (CUDA)
- `bfloat16`: Alternative to float16, more stable (modern GPUs)

Precision comparison:

| Precision | Memory | Speed | Accuracy | Recommended Use |
|-----------|--------|-------|----------|-----------------|
| float32 | 100% | Baseline | Highest | CPU, high accuracy needed |
| float16 | 50% | 2x faster | Slightly reduced | CUDA GPU |
| bfloat16 | 50% | 2x faster | More stable than float16 | Modern GPUs (A100, H100) |

### Quantization

Quantization to reduce memory and increase speed:

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  quantization: int8  # 'int8', 'int4', 'fp4', 'nf4' (omit for no quantization)
```

**Quantization options:**
- (omit `quantization:`): No quantization (default)
- `int8`: 8-bit integer (requires bitsandbytes)
- `int4`: 4-bit integer (requires bitsandbytes)
- `fp4`: 4-bit floating-point (requires bitsandbytes)
- `nf4`: 4-bit NormalFloat (for QLoRA)

You can also expand `quantization` into a full config:

```yaml
quantization:
  type: nf4
  compute_dtype: bfloat16
  double_quant: true
```

### Batch Size

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased
  action:
    batch_size: 32  # Number of inputs to process at once
```

Batch size selection guide:
- **Small batch (1-8)**: Low latency, real-time inference
- **Medium batch (16-32)**: Balanced throughput/latency
- **Large batch (64+)**: Maximum throughput, batch processing

### Low-Memory Loading

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  low_cpu_mem_usage: true  # Minimize CPU RAM usage
  device: cuda
```

---

## 10.5 Using LoRA/PEFT Adapters

LoRA (Low-Rank Adaptation) is a technique for adapting models to specific tasks by adding small adapter modules without fine-tuning the entire model.

### Applying LoRA Adapters

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  peft_adapters:
    - type: lora
      name: alpaca
      model: tloen/alpaca-lora-7b
      weight: 1.0
  action:
    prompt: ${input.prompt as text}
```

### Multiple LoRA Adapters

Multiple LoRA adapters can be applied simultaneously:

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    token: ${env.HUGGINGFACE_TOKEN}
  peft_adapters:
    - type: lora
      name: alpaca
      model: tloen/alpaca-lora-7b
      weight: 0.7
    - type: lora
      name: assistant
      model: plncmm/guanaco-lora-7b
      weight: 0.8
  action:
    prompt: ${input.prompt as text}
```

### Adapter Weights

Control adapter influence with the `weight` parameter:

```yaml
peft_adapters:
  - type: lora
    name: style-adapter
    model: user/style-lora
    weight: 0.5  # 50% influence
```

- `weight: 0.0`: Disable adapter
- `weight: 0.5`: 50% applied
- `weight: 1.0`: 100% applied (default)

### Local LoRA Adapters

Using adapters from local filesystem:

```yaml
peft_adapters:
  - type: lora
    name: custom-lora
    model:
      provider: local
      path: /path/to/lora/adapter
    weight: 1.0
```

### LoRA Use Cases

**1. Domain Adaptation**
```yaml
# Medical domain specialized model
peft_adapters:
  - type: lora
    name: medical
    model: medalpaca/medalpaca-lora-7b
    weight: 1.0
```

**2. Style Control**
```yaml
# Combining multiple writing styles
peft_adapters:
  - type: lora
    name: formal
    model: user/formal-writing-lora
    weight: 0.6
  - type: lora
    name: technical
    model: user/technical-lora
    weight: 0.4
```

**3. Multilingual Support**
```yaml
# Enhancing Korean language support
peft_adapters:
  - type: lora
    name: korean
    model: beomi/llama-2-ko-7b-lora
    weight: 1.0
```

---

## 10.6 Model Serving Frameworks

For large-scale production environments or high-performance inference, dedicated model serving frameworks can be used.

> **Important:** Model serving frameworks like vLLM and Ollama use local models but are accessed through `http-server` or `http-client` components via HTTP API, not `model` components. This is because a separate server process loads and serves the model.

### vLLM

vLLM is a high-performance inference engine for large language models.

#### vLLM Features

- **PagedAttention**: Memory-efficient attention mechanism
- **Continuous batching**: High throughput
- **Fast inference**: Optimized CUDA kernels
- **OpenAI-compatible API**: Easy integration with existing code

#### vLLM Configuration Example

```yaml
component:
  type: http-server
  manage:
    install:
      - bash
      - -c
      - |
        eval "$(pyenv init -)" &&
        (pyenv activate vllm 2>/dev/null || pyenv virtualenv $(python --version | cut -d' ' -f2) vllm) &&
        pyenv activate vllm &&
        pip install vllm
    start:
      - bash
      - -c
      - |
        eval "$(pyenv init -)" &&
        pyenv activate vllm &&
        python -m vllm.entrypoints.openai.api_server
          --model Qwen/Qwen2-7B-Instruct
          --port 8000
          --served-model-name qwen2-7b-instruct
          --max-model-len 2048
  port: 8000
  action:
    method: POST
    path: /v1/chat/completions
    headers:
      Content-Type: application/json
    body:
      model: qwen2-7b-instruct
      messages:
        - role: user
          content: ${input.prompt as text}
      max_tokens: 512
      temperature: ${input.temperature as number | 0.7}
      stream: true
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

#### vLLM Parameters

**Server parameters:**
- `--model`: Model name or path
- `--port`: Server port
- `--host`: Bind host
- `--served-model-name`: Model name for API
- `--max-model-len`: Maximum sequence length
- `--tensor-parallel-size`: Tensor parallelism (multi-GPU)
- `--dtype`: Data type (auto, float16, bfloat16)

**Inference parameters:**
- `max_tokens`: Maximum tokens to generate
- `temperature`: Generation randomness
- `top_p`: Nucleus sampling
- `streaming`: Enable streaming response

### Ollama

Ollama is a simple tool for running large language models locally.

#### Ollama Features

- **Easy installation**: One-click install
- **Model library**: Pre-optimized models
- **Low barrier to entry**: No complex configuration
- **REST API**: Simple HTTP interface

#### Ollama Automatic Management (http-server component)

When model-compose automatically installs and runs Ollama:

```yaml
component:
  type: http-server
  manage:
    install:
      - bash
      - -c
      - |
        # macOS/Linux
        curl -fsSL https://ollama.ai/install.sh | sh
        # Download model
        ollama pull llama2
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/generate
  headers:
    Content-Type: application/json
  body:
    model: llama2
    prompt: ${input.prompt as text}
    stream: false
  output:
    response: ${response.response}
```

**Streaming example:**

```yaml
component:
  type: http-server
  manage:
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/generate
  body:
    model: llama2
    prompt: ${input.prompt as text}
    stream: true
  stream_format: json
  output: ${response[].response}
```

**Chat API:**

```yaml
component:
  type: http-server
  manage:
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/chat
  body:
    model: llama2
    messages: ${input.messages}
  output:
    message: ${response.message.content}
```

#### Using Existing Ollama Server (http-client)

When an Ollama server is already running:

```yaml
component:
  type: http-client
  endpoint: http://localhost:11434/api/generate
  method: POST
  body:
    model: llama2
    prompt: ${input.prompt as text}
  output:
    response: ${response.response}
```

### TGI (Text Generation Inference)

HuggingFace's production-level inference server.

```yaml
component:
  type: http-client
  endpoint: http://localhost:8080/generate
  method: POST
  headers:
    Content-Type: application/json
  body:
    inputs: ${input.prompt as text}
    parameters:
      max_new_tokens: 512
      temperature: 0.7
      top_p: 0.9
  output:
    generated_text: ${response.generated_text}
```

### Framework Comparison

| Framework | Pros | Cons | Recommended Use |
|-----------|------|------|-----------------|
| **vLLM** | Best performance, high throughput | Complex setup, CUDA only | Production, large-scale services |
| **Ollama** | Easy installation, low barrier | Limited models, limited control | Development, prototyping, personal use |
| **TGI** | HuggingFace integration, stability | Slower than vLLM | When using HuggingFace ecosystem |
| **transformers** | Maximum compatibility, customization | Lower performance | Research, experiments, custom models |

---

## 10.7 Performance Optimization Tips

### 1. Choose Appropriate Precision

```yaml
# With GPU
component:
  type: model
  model: large-model
  precision: float16  # or bfloat16 (modern GPUs)
  device: cuda

# CPU only
component:
  type: model
  model: small-model
  precision: float32  # float32 more stable on CPU
  device: cpu
```

### 2. Use Quantization

```yaml
# When memory is limited
component:
  type: model
  model: meta-llama/Llama-2-13b-hf
  quantization: int8  # ~50% memory reduction
  device: cuda
```

### 3. Appropriate Batch Size

```yaml
# Optimize throughput
component:
  type: model
  task: text-classification
  model: bert-base
  action:
    batch_size: 32  # Adjust to GPU memory
```

### 4. Model Caching

```yaml
# Cache for model reuse
component:
  type: model
  model:
    provider: huggingface
    repository: gpt2
    cache_dir: /data/model-cache  # Use fast SSD
```

### 5. Use Multiple GPUs

```yaml
# Model parallelism
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  device: cuda
  device_mode: auto  # Automatically distribute across GPUs
```

### Common Performance Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Slow first run | Model download, compilation | Pre-download model, warmup |
| OOM (Out of Memory) | Model larger than GPU memory | Quantization, lower precision, smaller batch |
| Low throughput | Small batch size | Increase batch size |
| High latency | Large batch size | Decrease batch size, real-time processing |
| Unstable output | float16 precision issue | Use bfloat16 or float32 |

---

## Next Steps

Try it out:
- Test various models from HuggingFace Hub
- Experiment with quantization and precision settings
- Load and merge LoRA adapters
- Optimize throughput with batch processing

---

**Next Chapter**: [11. Model Training](./11-model-training.md)
