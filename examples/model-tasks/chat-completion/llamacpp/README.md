# Chat Completion (llama.cpp) Example

This example demonstrates how to run chat completion locally using GGUF format models with llama.cpp via model-compose's built-in `llamacpp` driver.

## Overview

This workflow provides local chat completion that:

1. **llama.cpp Backend**: Runs GGUF quantized models with minimal memory footprint
2. **OpenAI-Compatible Chat Format**: Supports system/user/assistant message roles
3. **Tool Use (Function Calling)**: Supports tool definitions for function calling workflows
4. **No External APIs**: Completely offline chat inference without API dependencies

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- `llama-cpp-python` installed (see installation below)
- A GGUF instruct model placed at `./.models/llama-3.2-1b-instruct-q4_k_m.gguf`

### Install llama-cpp-python

```bash
# CPU only
pip install llama-cpp-python

# macOS with Metal (Apple Silicon / AMD GPU)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# CUDA (NVIDIA GPU)
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
```

### Download a GGUF Model

```bash
mkdir -p models

# Download Llama-3.2-1B-Instruct Q4_K_M from HuggingFace
curl -L -o .models/llama-3.2-1b-instruct-q4_k_m.gguf \
  https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf
```

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/chat-completion-llamacpp
   ```

2. Place your GGUF instruct model file under `./.models/`.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "system_prompt": "You are a helpful AI assistant.",
         "user_prompt": "Explain what a GGUF file is in simple terms."
       }
     }'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your system prompt and user prompt
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "system_prompt": "You are a helpful AI assistant.",
     "user_prompt": "Explain what a GGUF file is in simple terms."
   }'
   ```

## Component Details

### Chat Completion Model Component
- **Type**: Model component with chat-completion task
- **Driver**: `llamacpp`
- **Model**: GGUF quantized instruct model (Q4_K_M by default)
- **Features**:
  - CPU-optimized inference with llama.cpp
  - System and user message role support
  - Tool use (function calling) support
  - GPU offloading via `n_gpu_layers`
  - Streaming support

## Workflow Details

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `system_prompt` | text | No | - | System message defining the assistant's role |
| `user_prompt` | text | Yes | - | User message the assistant should respond to |

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `generated` | text | The assistant's response |

## Customization

### GPU Offloading

```yaml
component:
  type: model
  task: chat-completion
  driver: llamacpp
  model:
    provider: local
    path: ./.models/llama-3.2-1b-instruct-q4_k_m.gguf
    format: gguf
  device: cuda        # or "metal" on macOS
  n_gpu_layers: -1    # -1 = offload all layers
  context_length: 4096
  action:
    messages:
      - role: system
        content: ${input.system_prompt}
      - role: user
        content: ${input.user_prompt}
```

### Streaming Output

```yaml
component:
  action:
    messages:
      - role: system
        content: ${input.system_prompt}
      - role: user
        content: ${input.user_prompt}
    streaming: true
```

### Tool Use (Function Calling)

```yaml
component:
  action:
    messages:
      - role: user
        content: ${input.user_prompt}
    tools:
      - name: get_weather
        description: Get the current weather for a location
        parameters:
          type: object
          properties:
            location:
              type: string
              description: City name
          required:
            - location
```

## System Requirements

### Minimum Requirements (CPU)
- **RAM**: 2GB+ (depends on model size and quantization)
- **Disk Space**: Model file size (Q4_K_M of 1B ≈ 0.8GB)
- **CPU**: Any modern x86_64 or ARM64 processor

### Recommended (GPU)
- **VRAM**: 2GB+ for 1B models, 6GB+ for 7B models
- **GPU**: NVIDIA (CUDA) or Apple Silicon (Metal)

## Troubleshooting

1. **`llama_cpp` not found**: Install with `pip install llama-cpp-python`
2. **Poor response quality**: Use an instruct/chat-tuned GGUF model, not a base model
3. **Out of memory**: Use a smaller quantization (Q4 or Q2) or a smaller model
4. **Slow inference**: Enable GPU offloading with `n_gpu_layers: -1`
