# Text Embedding (llama.cpp) Example

This example demonstrates how to generate text embeddings locally using GGUF format embedding models with llama.cpp via model-compose's built-in `llamacpp` driver.

## Overview

This workflow provides local text embedding that:

1. **llama.cpp Backend**: Runs GGUF quantized embedding models efficiently
2. **CPU-Friendly**: Works well on CPU without requiring a GPU
3. **L2 Normalization**: Optionally normalizes embeddings for cosine similarity
4. **No External APIs**: Completely offline embedding without API dependencies

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- `llama-cpp-python` installed (see installation below)
- A GGUF embedding model placed at `./models/nomic-embed-text-v1.5.Q4_K_M.gguf`

### Install llama-cpp-python

```bash
# CPU only
pip install llama-cpp-python

# macOS with Metal (Apple Silicon / AMD GPU)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# CUDA (NVIDIA GPU)
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
```

### Download a GGUF Embedding Model

```bash
mkdir -p models

# Download nomic-embed-text-v1.5 Q4_K_M from HuggingFace
curl -L -o models/nomic-embed-text-v1.5.Q4_K_M.gguf \
  https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q4_K_M.gguf
```

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/text-embedding-llamacpp
   ```

2. Place your GGUF embedding model file under `./models/`.

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
         "text": "The quick brown fox jumps over the lazy dog."
       }
     }'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your text
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run --input '{"text": "The quick brown fox jumps over the lazy dog."}'
   ```

## Component Details

### Text Embedding Model Component
- **Type**: Model component with text-embedding task
- **Driver**: `llamacpp`
- **Model**: GGUF quantized embedding model (nomic-embed-text-v1.5 Q4_K_M by default)
- **Features**:
  - CPU-optimized inference with llama.cpp
  - Automatic `embedding=True` mode activation
  - L2 normalization for cosine similarity use cases
  - Batch processing support
  - GPU offloading via `n_gpu_layers`

## Workflow Details

### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | text | Yes | - | Input text to embed |

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `embedding` | JSON array | Floating-point embedding vector |

## Customization

### GPU Offloading

```yaml
component:
  type: model
  task: text-embedding
  driver: llamacpp
  model:
    provider: local
    path: ./models/nomic-embed-text-v1.5.Q4_K_M.gguf
    format: gguf
  device: cuda        # or "metal" on macOS
  n_gpu_layers: -1    # -1 = offload all layers
  context_length: 2048
  action:
    text: ${input.text}
    params:
      normalize: true
```

### Batch Embedding

```yaml
component:
  action:
    text: ${input.texts}   # Pass a list of strings
    batch_size: 16
    params:
      normalize: true
```

### Without Normalization

```yaml
component:
  action:
    text: ${input.text}
    params:
      normalize: false    # Return raw embeddings
```

## System Requirements

### Minimum Requirements (CPU)
- **RAM**: 1GB+ (depends on model size and quantization)
- **Disk Space**: Model file size (nomic-embed Q4_K_M ≈ 80MB)
- **CPU**: Any modern x86_64 or ARM64 processor

### Recommended (GPU)
- **VRAM**: 1GB+ for most embedding models
- **GPU**: NVIDIA (CUDA) or Apple Silicon (Metal)

## Recommended GGUF Embedding Models

| Model | Dimensions | Size (Q4) | Use Case |
|-------|-----------|-----------|---------|
| `nomic-ai/nomic-embed-text-v1.5-GGUF` | 768 | ~80MB | General purpose |
| `CompendiumLabs/bge-large-en-v1.5-gguf` | 1024 | ~300MB | High quality English |
| `CompendiumLabs/bge-m3-gguf` | 1024 | ~600MB | Multilingual |

## Troubleshooting

1. **`llama_cpp` not found**: Install with `pip install llama-cpp-python`
2. **Wrong model type**: Use a dedicated embedding model, not a generative model
3. **Out of memory**: Use a smaller quantization or smaller embedding model
4. **Slow embedding**: Enable GPU offloading with `n_gpu_layers: -1`
5. **All-zero embeddings**: Ensure the model supports embedding mode (use dedicated embedding GGUFs)
