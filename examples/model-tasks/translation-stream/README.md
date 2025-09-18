# Text Translation Stream Model Task Example

This example demonstrates how to use local multilingual models for streaming text translation using model-compose's built-in text-generation task with SMALL100, providing real-time translation with Server-Sent Events (SSE).

## Overview

This workflow provides local streaming text translation that:

1. **Local Streaming Model**: Runs SMALL100 model locally with real-time streaming output
2. **100+ Languages**: Supports streaming translation between over 100 language pairs
3. **Real-time Generation**: Provides incremental translation via Server-Sent Events
4. **Progressive Updates**: Streams translated tokens as they are generated
5. **No External APIs**: Completely offline translation with streaming capabilities

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Sufficient system resources for running SMALL100 (recommended: 8GB+ RAM)
- Python environment with transformers and torch (automatically managed)

### Why Local Streaming Translation

Unlike cloud-based translation APIs, local streaming execution provides:

**Benefits of Local Streaming:**
- **Privacy**: All text processing happens locally, no content sent to external services
- **Real-time Feedback**: Progressive translation generation with immediate visibility
- **Cost**: No per-character or API usage fees after initial setup
- **Offline**: Works without internet connection after model download
- **Latency**: No network latency for translation processing
- **User Experience**: Interactive feel with streaming responses

**Trade-offs:**
- **Hardware Requirements**: Requires adequate RAM for model and streaming processing
- **Setup Time**: Initial model download and loading time
- **Streaming Complexity**: More complex client-side handling for SSE
- **Resource Usage**: Continuous processing during streaming

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/translation-stream
   ```

2. No additional environment configuration required - model and dependencies are managed automatically.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/__default__/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"text": "Hello, how are you today? I hope you are having a wonderful day."}}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your input parameters
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run translation --input '{"text": "Hello, how are you today? I hope you are having a wonderful day."}'
   ```

## Component Details

### Text Translation Streaming Model Component (Default)
- **Type**: Model component with text-generation task (streaming enabled)
- **Purpose**: Local multilingual text translation with real-time streaming
- **Model**: alirezamsh/small100
- **Architecture**: mBART-based sequence-to-sequence transformer
- **Features**:
  - Real-time token-by-token streaming
  - Server-Sent Events (SSE) output format
  - 100+ language support
  - Deterministic translation (sampling disabled)
  - CPU and GPU acceleration support

### Model Information: SMALL100

- **Developer**: Alireza Mohammadshahi
- **Base Architecture**: mBART (Multilingual BART)
- **Parameters**: ~300 million
- **Type**: Multilingual sequence-to-sequence transformer
- **Languages**: 100+ languages including major world languages
- **Streaming**: Token-level generation with immediate output
- **Input Limit**: 1024 tokens (automatically truncated)
- **License**: MIT

## Workflow Details

### "Translate Text" Workflow (Streaming)

**Description**: Translate input text with real-time streaming output using the SMALL100 multilingual model.

#### Job Flow

```mermaid
graph TD
    %% Jobs (circles)
    J1((translate-text<br/>job))

    %% Components (rectangles)
    C1[Streaming Text Translation Model<br/>component]

    %% Job to component connections (solid: invokes, dotted: returns)
    J1 --> C1
    C1 -.-> |streaming translation| J1

    %% Input/Output
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | text | Yes | - | Input text to translate (max 1024 tokens) |

#### Output Format

**Streaming Output (SSE):**
```
data: {"token": "Hola", "is_final": false}

data: {"token": ",", "is_final": false}

data: {"token": " ¿", "is_final": false}

data: {"token": "cómo", "is_final": false}

...

data: {"token": "?", "is_final": true}
```

**Final Output:**
| Field | Type | Description |
|-------|------|-------------|
| `output` | text | Complete translated text (SSE format) |

## Server-Sent Events (SSE) Format

The streaming output uses the SSE protocol for real-time translation updates:

### Event Structure
```
data: {"token": "string", "is_final": boolean}

```

### Token Properties
- **token**: The generated translation token/word
- **is_final**: Boolean indicating if this is the last token

### Connection Headers
```
Content-Type: text/plain
Cache-Control: no-cache
Connection: keep-alive
```

## System Requirements

### Minimum Requirements
- **RAM**: 8GB (recommended 16GB+)
- **Disk Space**: 3GB+ for model storage and cache
- **CPU**: Multi-core processor (4+ cores recommended)
- **Internet**: Required for initial model download only
- **Network**: Local network capability for SSE streaming

### Performance Notes
- First run requires model download (~1.2GB)
- Model loading takes 1-2 minutes depending on hardware
- GPU acceleration improves streaming speed
- Streaming latency depends on generation speed and token complexity

## Language Support

### Real-time Translation Pairs

**Popular Language Pairs:**
- English ↔ Spanish, French, German, Italian, Portuguese
- Spanish ↔ French, German, Portuguese
- Chinese ↔ English, Japanese, Korean
- Arabic ↔ English, French
- Russian ↔ English, German

**Streaming Performance by Language:**
- **Latin Script**: Fastest streaming (English, Spanish, French, etc.)
- **Asian Languages**: Moderate speed (Chinese, Japanese, Korean)
- **Complex Scripts**: Slower but functional (Arabic, Thai, Hindi)

## Customization

### Adjusting Streaming Parameters

Control streaming behavior and translation quality:

```yaml
component:
  type: model
  task: text-generation
  model: alirezamsh/small100
  architecture: seq2seq
  text: ${input.text as text}
  stream: true
  params:
    max_input_length: 1024
    max_length: 1024
    num_beams: 1                # Faster streaming with greedy search
    do_sample: false            # Deterministic output
    streaming_buffer_size: 1    # Stream every token immediately
```

### Custom Language Configuration

```yaml
component:
  type: model
  task: text-generation
  model: alirezamsh/small100
  architecture: seq2seq
  text: |
    Translate from ${input.source_lang | "English"} to ${input.target_lang | "Spanish"}:
    ${input.text as text}
  stream: true
  params:
    max_input_length: 1024
    do_sample: false
```

### Streaming Quality vs Speed Trade-offs

```yaml
# Fast streaming (lower quality)
component:
  stream: true
  params:
    num_beams: 1              # Greedy decoding
    streaming_buffer_size: 1  # Immediate streaming

# Quality streaming (slower)
component:
  stream: true
  params:
    num_beams: 3              # Beam search for quality
    streaming_buffer_size: 3  # Buffer tokens for smoother output
```
