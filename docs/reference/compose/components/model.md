# Model Component

The model component enables loading and running AI/ML models locally using HuggingFace transformers. It supports various tasks including text generation, chat completion, text embedding, classification, translation, summarization, image-to-text processing, and text-to-speech synthesis.

## Basic Configuration

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
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
| `task` | string | **required** | Model task type: `text-generation`, `chat-completion`, `text-embedding`, `text-classification`, `translation`, `summarization`, `image-to-text`, `text-to-speech` |
| `driver` | string | `huggingface` | Model provider (currently only HuggingFace supported) |
| `model` | string/object | **required** | Model identifier or configuration object |
| `cache_dir` | string | `null` | Directory to cache model files |
| `local_files_only` | boolean | `false` | Force loading from local files only |
| `device_mode` | string | `auto` | Device allocation mode: `auto`, `single` |
| `device` | string | `cpu` | Computation device: `cpu`, `cuda`, `cuda:0`, etc. |
| `precision` | string | `null` | Numerical precision: `auto`, `float32`, `float16`, `bfloat16` |
| `low_cpu_mem_usage` | boolean | `false` | Load model with minimal CPU RAM usage |
| `fast_tokenizer` | boolean | `true` | Whether to use fast tokenizer if available |

### Model Source Configuration

You can specify models as a string or detailed configuration:

```yaml
# Simple string format
model: microsoft/DialoGPT-medium

# Detailed configuration
model:
  model_id: microsoft/DialoGPT-medium
  provider: huggingface
  revision: main
  filename: pytorch_model.bin
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model_id` | string | **required** | HuggingFace model identifier |
| `provider` | string | `huggingface` | Model provider |
| `revision` | string | `null` | Model version or branch |
| `filename` | string | `null` | Specific file in model repo |

## Task Types and Examples

### Text Generation

Generate text from prompts using language models:

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
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
  text: ${input.text}
  labels: [ positive, negative, neutral ]
  output:
    predicted_label: ${response.label}
    confidence: ${response.score}
    all_scores: ${response.scores}
```

### Translation

Translate text between languages:

```yaml
component:
  type: model
  task: translation
  model: Helsinki-NLP/opus-mt-en-fr
  text: ${input.text}
  source_language: en
  target_language: fr
  output:
    translated_text: ${response.translation_text}
```

### Summarization

Summarize long text into shorter versions:

```yaml
component:
  type: model
  task: summarization
  model: facebook/bart-large-cnn
  text: ${input.article_text}
  params:
    max_output_length: 150
    min_output_length: 50
  output:
    summary: ${response.summary_text}
```

### Image-to-Text

Generate text descriptions from images:

```yaml
component:
  type: model
  task: image-to-text
  model: Salesforce/blip-image-captioning-base
  image: ${input.image_url}
  output:
    caption: ${response.generated_text}
```

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
| `language` | string | `null` | Language of the text (auto-detected if not specified) |

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
  model: HuggingFaceTB/SmolLM3-3B
  cache_dir: ./models_cache
  local_files_only: false
```

### Offline Usage

```yaml
component:
  type: model
  task: text-generation
  model: ./local_models/my-model
  local_files_only: true
```

## Advanced Configuration Examples

### Streaming Text Generation

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  prompt: ${input.prompt}
  params:
    max_output_length: 4096
    temperature: 0.8
    do_sample: true
    # Enable streaming for real-time generation
    stream: true
  output:
    generated_text: ${response.generated_text}
```

### Batch Processing

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
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

### Text Generation Models
- **GPT Models**: GPT-2, GPT-Neo, GPT-J
- **LLaMA Models**: LLaMA, Alpaca, Vicuna
- **Code Models**: CodeGen, CodeT5, InCoder
- **Instruction Models**: Flan-T5, UL2

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
