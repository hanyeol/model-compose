# Text Generation (llama.cpp) Example

This example demonstrates how to run text generation locally using GGUF format models with llama.cpp via model-compose's built-in `llamacpp` driver.

## Overview

This workflow provides local text generation that:

1. **llama.cpp Backend**: Runs GGUF quantized models with minimal memory footprint
2. **CPU-Friendly**: Works well on CPU without requiring a GPU
3. **GGUF Format**: Supports quantized models (Q4, Q5, Q8, etc.) for reduced memory usage
4. **No External APIs**: Completely offline inference without API dependencies

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- `llama-cpp-python` installed (see installation below)
- A GGUF model file placed at `./models/llama-3.2-1b-instruct-q4_k_m.gguf`

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
curl -L -o models/llama-3.2-1b-instruct-q4_k_m.gguf \
  https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf
```

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/text-generation-llamacpp
   ```

2. Place your GGUF model file under `./models/`.

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
         "prompt": "The history of artificial intelligence begins"
       }
     }'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your prompt
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run --input '{"prompt": "The history of artificial intelligence begins"}'
   ```

## Component Details

### Text Generation Model Component
- **Type**: Model component with text-generation task
- **Driver**: `llamacpp`
- **Model**: GGUF quantized model (Q4_K_M by default)
- **Features**:
  - CPU-optimized inference with llama.cpp
  - GPU offloading via `n_gpu_layers` (set `-1` to offload all layers)
  - Configurable context window (`context_length`)
  - Streaming support

## Workflow Details

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompt` | text | Yes | - | Input text to generate from |

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `generated` | text | The generated text continuation |

## Customization

### GPU Offloading

To offload layers to GPU, set `device` and `n_gpu_layers`:

```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: ./models/llama-3.2-1b-instruct-q4_k_m.gguf
    format: gguf
  device: cuda        # or "metal" on macOS
  n_gpu_layers: -1    # -1 = offload all layers
  context_length: 4096
  action:
    text: ${input.prompt as text}
    params:
      max_output_length: 1024
```

### Using a Different Model

```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: ./models/mistral-7b-instruct-v0.2.Q4_K_M.gguf
    format: gguf
  context_length: 8192
  action:
    text: ${input.prompt as text}
```

### Streaming Output

```yaml
component:
  action:
    text: ${input.prompt as text}
    streaming: true
    params:
      max_output_length: 2048
```

## System Requirements

### Minimum Requirements (CPU)
- **RAM**: 2GB+ (depends on model size and quantization)
- **Disk Space**: Model file size (Q4_K_M of 1B ≈ 0.8GB)
- **CPU**: Any modern x86_64 or ARM64 processor

### Recommended (GPU)
- **VRAM**: 2GB+ for 1B models, 6GB+ for 7B models
- **GPU**: NVIDIA (CUDA) or Apple Silicon (Metal)

## GGUF Quantization Guide

| Quantization | Memory | Quality | Recommended For |
|-------------|--------|---------|----------------|
| Q2_K | Lowest | Lowest | Very limited RAM |
| Q4_K_M | Low | Good | General use (default) |
| Q5_K_M | Medium | Better | Better quality |
| Q8_0 | High | Best | Maximum quality |
| F16 | Highest | Lossless | GPU with large VRAM |

## Troubleshooting

1. **`llama_cpp` not found**: Install with `pip install llama-cpp-python`
2. **Out of memory**: Use a smaller quantization (Q4 or Q2) or a smaller model
3. **Slow inference**: Enable GPU offloading with `n_gpu_layers: -1`
4. **Model file not found**: Verify the `path` in the YAML matches your file location
