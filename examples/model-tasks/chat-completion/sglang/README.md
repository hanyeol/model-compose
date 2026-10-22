# Chat Completion with SGLang Example

This example demonstrates how to run the `chat-completion` task with the built-in **SGLang** driver, loading a small instruction-tuned model into a dedicated virtual environment and generating a chat response.

## Overview

The workflow performs non-streaming chat completion:

1. **SGLang Engine**: The model is loaded by SGLang inside an isolated `virtualenv` runtime so SGLang's dependencies stay separate from the main environment.
2. **Small Instruction Model**: `Qwen/Qwen2.5-0.5B-Instruct` (~1GB) keeps the smoke test cheap.
3. **Standard Chat Format**: Takes a `system` prompt and a `user` prompt and returns the full response as one block.

## Preparation

### Prerequisites

- model-compose installed and available in your `PATH`.
- A CUDA-capable GPU is required for SGLang (Linux + NVIDIA); macOS/CPU-only setups will not run this example.
- Python 3.10+ (used to build the virtual environment).

### Environment

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/chat-completion/sglang
   ```

2. On first run, the component bootstraps `.venv/sglang`, installs SGLang, and downloads the Qwen model.

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

### Chat Completion Model Component (SGLang)
- **Type**: `model` component with `task: chat-completion` and `driver: sglang`
- **Model**: `Qwen/Qwen2.5-0.5B-Instruct`
- **Runtime**: `virtualenv` at `.venv/sglang`
- **Engine Options**:
  - `context_length: 2048` — context window cap
  - `mem_fraction_static: 0.85` — fraction of GPU memory reserved for the model and KV cache

### Why SGLang
- **Structured Generation**: SGLang excels at structured outputs, constrained decoding, and multi-turn programs.
- **RadixAttention**: Prefix caching across requests can be a win for workloads with shared system prompts.

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

```yaml
component:
  model: Qwen/Qwen2.5-1.5B-Instruct  # or Qwen/Qwen2.5-7B-Instruct, etc.
```

### Larger Context Window

```yaml
component:
  options:
    context_length: 8192
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

- **CUDA errors / out of memory**: Lower `mem_fraction_static` (e.g. `0.7`) or `context_length`, or use a smaller model.
- **First run is slow**: SGLang installation and model download happen on first boot; subsequent runs reuse the cache.
- **SGLang install failures**: Check the SGLang release notes for the matching CUDA + PyTorch version pair.

## See Also

- `../huggingface/` — same task on the HuggingFace driver (no SGLang dependency)
- `../vllm/` — same task on the vLLM driver
- `../sglang-stream/` — streaming variant of this example
