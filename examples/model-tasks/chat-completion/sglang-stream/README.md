# Chat Completion Streaming with SGLang Example

This example demonstrates **token-level streaming** chat completion using the built-in **SGLang** driver. Tokens are emitted incrementally as they are produced so clients see output as it is generated instead of waiting for the full response.

## Overview

The workflow is identical to `../sglang/` except for two changes that enable streaming:

1. **`streaming: true`** on the action — the driver returns an incremental iterator instead of a final string.
2. **`output: ${output as stream/text}`** on the job — the workflow passes chunks through as a text stream rather than aggregating them.

## Preparation

### Prerequisites

- model-compose installed and available in your `PATH`.
- A CUDA-capable GPU is required for SGLang (Linux + NVIDIA).
- An HTTP client that can consume streaming responses (e.g. `curl -N`).

### Environment

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/chat-completion/sglang-stream
   ```

2. On first run, the component bootstraps `.venv/sglang`, installs SGLang, and downloads the Qwen model.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow (streaming):**

   **Using API (note `curl -N` disables buffering):**
   ```bash
   curl -N -X POST http://localhost:8080/api/workflows/runs \
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
   - Tokens appear in the output area as they stream in.

## Component Details

### Chat Completion Model Component (SGLang, Streaming)
- **Type**: `model` component with `task: chat-completion` and `driver: sglang`
- **Model**: `Qwen/Qwen2.5-0.5B-Instruct`
- **Runtime**: `virtualenv` at `.venv/sglang`
- **Action Flag**: `streaming: true` — generated tokens are emitted incrementally.

### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_prompt` | text | No | System message that sets the assistant's behavior |
| `user_prompt` | text | Yes | User turn the assistant should respond to |

### Output Format

The job output is a text stream — the HTTP response delivers chunks progressively, and `${output as stream/text}` tells model-compose to pass the stream through to the client untouched.

## Customization

### Larger Model

```yaml
component:
  model: Qwen/Qwen2.5-7B-Instruct
  options:
    context_length: 8192
```

### Sampling

```yaml
action:
  params:
    temperature: 0.9
    top_p: 0.95
    do_sample: true
```

## Troubleshooting

- **No incremental output in the terminal**: Add `-N` to `curl` (or disable your client's buffering). Without it, chunks are buffered and look like a single final response.
- **CUDA out of memory**: Lower `mem_fraction_static` or `context_length`, or use a smaller model.
- **Stream stops abruptly**: Check the server logs — streaming aborts if the engine hits `max_output_length` or a stop sequence.

## See Also

- `../sglang/` — non-streaming variant that returns the full response at once
- `../vllm-stream/` — the same streaming workflow on the vLLM driver
