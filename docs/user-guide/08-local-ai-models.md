# Chapter 8: Working with Local AI Models

This chapter covers how to use local AI models with model-compose.

---

## 8.1 Local Model Overview

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

## 8.2 Model Installation and Setup

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

## 8.3 Supported Task Types

model-compose supports the following task types:

| Task | Description | Primary Use Cases |
|------|-------------|-------------------|
| `text-generation` | Text generation | Story writing, code generation |
| `chat-completion` | Conversational completion | Chatbots, assistants |
| `text-classification` | Text classification | Sentiment analysis, topic classification |
| `text-embedding` | Text embedding | Semantic search, RAG |
| `image-to-text` | Image captioning | Image description, VQA |
| `image-generation` | Image generation | Text-to-image conversion |
| `image-upscale` | Image upscaling | Resolution enhancement |
| `text-to-speech` | Text-to-speech synthesis | Voice generation, cloning, design |
| `face-embedding` | Face embedding | Face recognition, comparison |

### 8.3.1 text-generation

Generates text based on prompts.

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  text: ${input.prompt as text}
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

### 8.3.2 chat-completion

Processes conversational messages.

```yaml
component:
  type: model
  task: chat-completion
  model: HuggingFaceTB/SmolLM3-3B
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

### 8.3.3 text-classification

Classifies text into categories.

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased-finetuned-sst-2-english
  text: ${input.text as text}
  output:
    label: ${result.label}
    score: ${result.score}
```

### 8.3.4 text-embedding

Converts text into high-dimensional vectors.

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
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

### 8.3.5 image-to-text

Analyzes images and generates text.

```yaml
component:
  type: model
  task: image-to-text
  model: Salesforce/blip-image-captioning-large
  architecture: blip
  image: ${input.image as image}
  prompt: ${input.prompt as text}
```

**Supported architectures:**
- `blip`: Image captioning
- `git`: Generative Image-to-Text
- `vit-gpt2`: Vision Transformer + GPT-2

### 8.3.6 image-generation

Generates images from text prompts.

```yaml
component:
  type: model
  task: image-generation
  architecture: flux
  model: black-forest-labs/FLUX.1-dev
  prompt: ${input.prompt as text}
  params:
    width: 1024
    height: 1024
    num_inference_steps: 50
```

**Supported architectures:**
- `flux`: FLUX model
- `sdxl`: Stable Diffusion XL
- `hunyuan`: HunyuanDiT

### 8.3.7 image-upscale

Enhances image resolution.

```yaml
component:
  type: model
  task: image-upscale
  architecture: real-esrgan
  model: RealESRGAN_x4plus
  image: ${input.image as image}
  params:
    scale: 4
```

**Supported architectures:**
- `real-esrgan`: Real-ESRGAN
- `esrgan`: ESRGAN
- `swinir`: SwinIR
- `ldsr`: Latent Diffusion Super Resolution

### 8.3.8 text-to-speech

Synthesizes speech audio from text. This task uses `driver: custom` with a `family` field to select the model family, and a `method` field to choose the generation method.

**Available methods:**

| Method | Description | Required Fields |
|--------|-------------|-----------------|
| `generate` | Generate speech using a built-in voice | `voice`, `instructions` (optional) |
| `clone` | Clone a voice from reference audio | `ref_audio`, `ref_text` |
| `design` | Design a new voice from a description | `instructions` |

**Common fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Generation method: `generate`, `clone`, `design` |
| `text` | string/array | **required** | Text to synthesize into speech |
| `language` | string | `null` | Language of the text (auto-detected if not specified) |

#### Generate method

Generate speech using a built-in voice with optional style instructions:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
  device: cuda:0
  method: generate
  text: ${input.text as text}
  voice: ${input.voice | vivian}
  instructions: ${input.instructions | ""}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `voice` | string | `vivian` | Built-in voice name |
| `instructions` | string | `""` | Emotion/style instructions for the voice |

#### Clone method

Clone a voice from reference audio:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-Base
  device: cuda:0
  method: clone
  text: ${input.text as text}
  ref_audio: ${input.ref_audio as audio}
  ref_text: ${input.ref_text as text}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ref_audio` | string | **required** | Path or URL to the reference audio for voice cloning |
| `ref_text` | string | **required** | Transcription text of the reference audio |

#### Design method

Design a new voice from a natural language description:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
  device: cuda:0
  method: design
  text: ${input.text as text}
  instructions: ${input.instructions as text}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `instructions` | string | **required** | Natural language description of the desired voice |

#### Supported models (Qwen family)

| Model | Method | Description |
|-------|--------|-------------|
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | `generate` | Built-in voices with style control |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | `clone` | Voice cloning from reference audio |
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | `design` | Voice design from text description |

### 8.3.9 face-embedding

Extracts feature vectors from face images.

```yaml
component:
  type: model
  task: face-embedding
  model: buffalo_l
  image: ${input.image as image}
```

---

## 8.4 Model Configuration (Device, Precision, Batch Size)

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
  quantization: int8  # 'none', 'int8', 'int4', 'nf4'
```

**Quantization options:**
- `none`: No quantization (default)
- `int8`: 8-bit integer (requires bitsandbytes)
- `int4`: 4-bit integer (requires bitsandbytes)
- `nf4`: 4-bit NormalFloat (for QLoRA)

### Batch Size

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased
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

## 8.5 Using LoRA/PEFT Adapters

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
  text: ${input.prompt as text}
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
  text: ${input.prompt as text}
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

## 8.6 Model Serving Frameworks

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
    streaming: true
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

## 8.7 Performance Optimization Tips

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

**Next Chapter**: [9. Model Training](./09-model-training.md)
