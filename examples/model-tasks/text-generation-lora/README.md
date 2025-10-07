# Text Generation with Multiple LoRA Adapters

This example demonstrates how to use multiple LoRA (Low-Rank Adaptation) adapters with a base language model to enhance text generation capabilities across different domains and tasks.

## Overview

This workflow combines a base Llama 2 7B model with multiple specialized LoRA adapters:

- **Alpaca Adapter** (`tloen/alpaca-lora-7b`): Instruction following capabilities
- **Guanaco Adapter** (`plncmm/guanaco-lora-7b`): Conversational and assistant-like responses

Each adapter can be weighted independently, allowing fine-grained control over the model's behavior.

## Features

- **Multi-Adapter Support**: Load multiple LoRA adapters simultaneously
- **Weight Control**: Adjust the influence of each adapter (0.0 to 2.0+)
- **Device Allocation**: Specify different devices for each adapter
- **Precision Control**: Set individual precision (float16, bfloat16) per adapter

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- CUDA-compatible GPU with sufficient VRAM (recommended: 16GB+)
- Python environment with transformers, torch, and peft (automatically managed)
- HuggingFace token for accessing gated models (e.g., Llama 2)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/text-generation-lora
   ```

2. Set up HuggingFace authentication for gated models:
   ```bash
   export HUGGINGFACE_TOKEN=your_huggingface_token
   ```

   Alternatively, log in via CLI:
   ```bash
   huggingface-cli login
   ```

3. No additional configuration required - models and LoRA adapters are downloaded automatically.

## Configuration

### Base Model
```yaml
model: meta-llama/Llama-2-7b-hf
```

### LoRA Adapters
```yaml
peft_adapters:
  - type: lora
    name: alpaca
    model: tloen/alpaca-lora-7b
    weight: 0.7

  - type: lora
    name: assistant
    model: plncmm/guanaco-lora-7b
    weight: 0.8
```

### Parameters
- `weight`: Scaling factor for adapter influence (default: 1.0)
  - `< 1.0`: Reduce adapter effect
  - `1.0`: Full adapter effect
  - `> 1.0`: Amplify adapter effect
- `precision`: Model precision (e.g., `float16`, `bfloat16`)

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
         "prompt": "Explain quantum computing in simple terms."
       }
     }'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Enter your prompt
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   model-compose run --input '{"prompt": "Explain quantum computing in simple terms."}'
   ```

### Example Prompts

**Instruction Following (Alpaca):**
```
Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
Write a Python function to calculate fibonacci numbers.

### Response:
```

**Conversational (Guanaco):**
```
Human: What are the benefits of using LoRA for fine-tuning?
Assistant:
```

## How It Works

### LoRA Architecture

LoRA decomposes weight updates into low-rank matrices:
```
W = W₀ + ΔW
ΔW = B × A × scaling
```

Where:
- `W₀`: Frozen pretrained weights
- `A`: Low-rank down-projection (rank × input_dim)
- `B`: Low-rank up-projection (output_dim × rank)
- `scaling`: lora_alpha / rank

### Multi-Adapter Blending

When multiple adapters are loaded, they are applied sequentially:
```
output = base_model(input)
for adapter in adapters:
    output += adapter.forward(input) × weight
```

The `weight` parameter controls each adapter's contribution.

## Customization

### Add Your Own LoRA

You can add custom LoRA adapters from HuggingFace Hub or local paths:

```yaml
peft_adapters:
  # HuggingFace Hub
  - type: lora
    name: my_adapter
    model: username/my-lora-adapter
    weight: 1.0

  # Local path
  - type: lora
    name: local_adapter
    model:
      provider: local
      path: ./path/to/lora
    weight: 0.5
```

### Adjust Adapter Weights

Fine-tune the balance between adapters:

```yaml
peft_adapters:
  - type: lora
    name: alpaca
    weight: 0.3  # Less instruction following

  - type: lora
    name: assistant
    weight: 1.2  # More conversational
```

## System Requirements

### Minimum Requirements
- **GPU VRAM**: 16GB+ (required for Llama-2-7b + adapters)
- **RAM**: 16GB system RAM (recommended 32GB+)
- **Disk Space**: 20GB+ for model and adapter storage
- **CUDA**: CUDA 11.8+ compatible GPU (NVIDIA)
- **Internet**: Required for initial model and adapter downloads

### Performance Notes
- First run requires downloading base model (~13GB) and adapters (~100MB each)
- Model loading takes 2-5 minutes depending on hardware
- GPU acceleration is required for practical inference speeds
- Multiple adapters increase memory usage and loading time

## References

- [PEFT Documentation](https://huggingface.co/docs/peft)
- [LoRA Paper](https://arxiv.org/abs/2106.09685)
- [Alpaca Model](https://github.com/tloen/alpaca-lora)
- [Guanaco Dataset](https://huggingface.co/datasets/timdettmers/openassistant-guanaco)
