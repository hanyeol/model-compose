# Chat Completion with vLLM Example

This example demonstrates how to run the `chat-completion` task with the built-in **vLLM** driver, loading a small instruction-tuned model into a dedicated virtual environment and generating a chat response.

## Overview

The workflow performs non-streaming chat completion:

1. **vLLM Engine**: The model is loaded by vLLM inside an isolated `virtualenv` runtime, so vLLM's dependencies do not pollute the main model-compose environment.
2. **Small Instruction Model**: `Qwen/Qwen2.5-0.5B-Instruct` (~1GB) is used so the example is cheap to download and quick to boot — easy to adapt to larger models later.
3. **Standard Chat Format**: Takes a `system` prompt and a `user` prompt and returns the full response as one block.

## Preparation

### Prerequisites

- model-compose installed and available in your `PATH`.
- A CUDA-capable GPU is strongly recommended. vLLM primarily targets Linux + NVIDIA; macOS/CPU-only setups will not run this example.
- Python 3.10+ (used to build the virtual environment).

### Environment

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/chat-completion/vllm
   ```

2. On first run, the component bootstraps `.venv/vllm`, installs vLLM into it, and downloads the Qwen model. No manual setup is required.

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
         "user_prompt": "Explain quantum computing in simple terms."
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
     "user_prompt": "Explain quantum computing in simple terms."
   }'
   ```

## Component Details

### Chat Completion Model Component (vLLM)
- **Type**: `model` component with `task: chat-completion` and `driver: vllm`
- **Model**: `Qwen/Qwen2.5-0.5B-Instruct` (0.5B parameters, instruction-tuned)
- **Runtime**: `virtualenv` at `.venv/vllm` — vLLM is installed only there
- **Engine Options**:
  - `max_model_len: 2048` — context window cap
  - `gpu_memory_utilization: 0.9` — fraction of GPU memory the engine may claim

### Why vLLM
- **Throughput**: PagedAttention and continuous batching give higher tokens/sec than naive HuggingFace generate for concurrent requests.
- **Deterministic Setup**: Isolated virtualenv keeps vLLM's heavy dependency tree out of the main environment.

### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_prompt` | text | No | System message that sets the assistant's behavior |
| `user_prompt` | text | Yes | User turn the assistant should respond to |

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `generated` | text | Complete assistant response as a single string |

## Customization

### Different Model

Swap in another instruction-tuned chat model:
```yaml
component:
  model: Qwen/Qwen2.5-1.5B-Instruct  # or Qwen/Qwen2.5-7B-Instruct, etc.
```

### Larger Context Window

```yaml
component:
  options:
    max_model_len: 8192
```

### Sampling Parameters

```yaml
action:
  params:
    temperature: 0.9
    top_p: 0.95
    do_sample: true
```

## Troubleshooting

- **CUDA errors / out of memory**: Lower `gpu_memory_utilization` (e.g. `0.7`) or `max_model_len`, or use a smaller model.
- **First run is slow**: vLLM installation and model download happen on first boot; subsequent runs reuse the cache.
- **vLLM install failures**: Check that your CUDA toolkit matches vLLM's supported range on the vLLM release notes.

## See Also

- `../huggingface/` — same task on the HuggingFace driver (no vLLM dependency)
- `../llamacpp/` — same task on the llama.cpp driver (CPU/GGUF)
- `../vllm-stream/` — streaming variant of this example
