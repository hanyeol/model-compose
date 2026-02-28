# 11. Streaming Mode

This chapter explains how to use model-compose's streaming capabilities to generate and process real-time responses.

---

## 11.1 Streaming Overview

### 11.1.1 What is Streaming?

Streaming mode delivers partial results as they are generated, rather than waiting for the complete response from a model or API.

**Benefits:**
- Immediate feedback to users
- Reduced time-to-first-token (TTFT) for long responses
- Build real-time streaming applications
- Better user experience (typing effect)

**Use Cases:**
- Chatbot conversations (ChatGPT-style)
- Real-time text generation
- Long document summarization
- Translation services
- Code generation

### 11.1.2 Supported Components

Components that support streaming:

| Component Type | Streaming Support | Configuration |
|---------------|------------------|---------------|
| `model` (text-generation) | ✅ | `streaming: true` |
| `model` (chat-completion) | ✅ | `streaming: true` |
| `http-client` | ✅ | `stream_format: json/text` |
| `http-server` | ✅ | `stream_format: json/text` |

### 11.1.3 Streaming Protocol

model-compose uses the **SSE (Server-Sent Events)** protocol.

**SSE Format:**
```
data: chunk1

data: chunk2

data: chunk3

```

Each chunk is sent with a `data:` prefix and separated by blank lines.

---

## 11.2 Component-Specific Streaming Configuration

### 11.2.1 Model Components

#### Basic Configuration

```yaml
component:
  type: model
  task: text-generation
  model: facebook/bart-large-cnn
  streaming: true                  # Enable streaming
  action:
    text: ${input.text as text}
    params:
      max_output_length: 150
```

**Important Constraints:**
- `batch_size` must be `1`
- Only single input supported (no batch processing)
- Recommended `num_beams: 1` during streaming

#### Text Generation Streaming

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  streaming: true
  action:
    text: ${input.prompt as text}
    params:
      max_output_length: 200
      do_sample: false               # Deterministic generation (faster)
      num_beams: 1                   # Disable beam search
```

**Output References:**
- Streaming: `${result[]}` (per chunk)
- Non-streaming: `${result}` (after full completion)

#### Chat Completion Streaming

```yaml
component:
  type: model
  task: chat-completion
  model: microsoft/DialoGPT-medium
  streaming: true
  action:
    messages:
      - role: user
        content: ${input.message as text}
    params:
      max_output_length: 100
```

**Features:**
- Chat template automatically applied
- Same streaming mechanism as text generation
- Per-chunk processing with `${result[]}`

### 11.2.2 HTTP Components

#### HTTP Client Streaming

**OpenAI API Streaming:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  action:
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.prompt as text}
      stream: true                   # API parameter
    stream_format: json              # Parse chunks as JSON
    output: ${response[].choices[0].delta.content}
```

**stream_format Options:**

- `json`: Parse each chunk as JSON
  ```yaml
  stream_format: json
  output: ${response[].choices[0].delta.content}
  ```

- `text`: Decode each chunk as UTF-8 text
  ```yaml
  stream_format: text
  output: ${response[]}
  ```

- Not specified: Pass raw bytes

**Output References:**
- Streaming: `${response[]}` (per chunk)
- Non-streaming: `${response}` (after full completion)

#### HTTP Server (Managed Service) Streaming

**vLLM Server Streaming:**

```yaml
component:
  type: http-server
  start:
    - vllm
    - serve
    - Qwen/Qwen2-7B-Instruct
    - --port
    - "8000"
  port: 8000
  healthcheck:
    path: /health
  action:
    method: POST
    path: /v1/chat/completions
    body:
      model: qwen2-7b-instruct
      messages:
        - role: user
          content: ${input.prompt as text}
      stream: true
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

---

## 11.3 Using Streaming in Workflows

### 11.3.1 Basic Streaming Workflow

```yaml
controller:
  type: http-server
  port: 8080

workflow:
  title: Streaming Chat
  output: ${output as text;sse-text}    # Output as SSE text format

component:
  type: http-client
  base_url: https://api.openai.com/v1
  action:
    path: /chat/completions
    method: POST
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}
    body:
      model: gpt-4o
      messages:
        - role: user
          content: ${input.prompt as text}
      stream: true
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

**Workflow Output Formats:**

- `as text;sse-text`: SSE text stream
  ```yaml
  output: ${output as text;sse-text}
  ```

- `as text;sse-json`: SSE JSON stream
  ```yaml
  output: ${output as text;sse-json}
  ```

### 11.3.2 Multi-Step Workflow Streaming

```yaml
workflows:
  - id: translate-and-summarize
    title: Translate and Summarize
    output: ${output as text;sse-text}
    jobs:
      - id: translate
        component: translator
        input:
          text: ${input.text}
          target_lang: en
        # Translation without streaming (waits for full completion)

      - id: summarize
        component: summarizer
        input:
          text: ${jobs.translate.output}
        # Summary with streaming output
        depends_on: [translate]

components:
  - id: translator
    type: model
    task: translation
    model: Helsinki-NLP/opus-mt-ko-en
    streaming: false
    action:
      text: ${input.text as text}

  - id: summarizer
    type: model
    task: text-generation
    model: facebook/bart-large-cnn
    streaming: true                    # Only last job streams
    action:
      text: ${input.text as text}
      params:
        max_output_length: 150
```

**Important:**
- Only the **last job** in a workflow can stream
- Intermediate jobs must wait for completion
- Only final output streams with `${result[]}`

### 11.3.3 Conditional Streaming

```yaml
workflow:
  title: Conditional Streaming
  output: ${output as text;sse-text}

component:
  type: model
  task: text-generation
  model: gpt2
  streaming: ${input.stream | false}   # Streaming determined by input
  action:
    text: ${input.prompt as text}
    params:
      max_output_length: 100
```

**API Call Examples:**

```bash
# Enable streaming
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"prompt": "Hello", "stream": true},
    "output_only": true,
    "wait_for_completion": true
  }'

# Disable streaming
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"prompt": "Hello", "stream": false},
    "wait_for_completion": true
  }'
```

---

## 11.4 Processing Streaming Responses

### 11.4.1 API Endpoints

**Streaming Request Requirements:**

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"prompt": "Write a story"},
    "output_only": true,              # Required: return output only
    "wait_for_completion": true       # Required: wait until completion
  }'
```

**Response Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
```

**Response Body (SSE):**
```
data: Once

data:  upon

data:  a

data:  time

```

### 11.4.2 Client Implementation (JavaScript)

**Using EventSource API:**

```javascript
const eventSource = new EventSource(
  'http://localhost:8080/api/workflows/runs',
  {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      input: { prompt: 'Hello' },
      output_only: true,
      wait_for_completion: true
    })
  }
);

eventSource.onmessage = (event) => {
  const chunk = event.data;
  console.log('Received:', chunk);
  // Update UI
  document.getElementById('output').textContent += chunk;
};

eventSource.onerror = (error) => {
  console.error('Error:', error);
  eventSource.close();
};
```

**Using Fetch API:**

```javascript
const response = await fetch('http://localhost:8080/api/workflows/runs', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    input: { prompt: 'Hello' },
    output_only: true,
    wait_for_completion: true
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const content = line.substring(6);
      console.log('Chunk:', content);
      // Update UI
      document.getElementById('output').textContent += content;
    }
  }
}
```

### 11.4.3 Client Implementation (Python)

**Using requests library:**

```python
import requests
import json

url = 'http://localhost:8080/api/workflows/runs'
payload = {
    'input': {'prompt': 'Hello'},
    'output_only': True,
    'wait_for_completion': True
}

response = requests.post(url, json=payload, stream=True)

for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('data: '):
            chunk = line[6:]
            print(chunk, end='', flush=True)
```

**Using aiohttp library (async):**

```python
import aiohttp
import asyncio

async def stream_workflow():
    url = 'http://localhost:8080/api/workflows/runs'
    payload = {
        'input': {'prompt': 'Hello'},
        'output_only': True,
        'wait_for_completion': True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    chunk = line[6:]
                    print(chunk, end='', flush=True)

asyncio.run(stream_workflow())
```

### 11.4.4 Web UI Integration

**Gradio Auto-Streaming:**

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Streaming Chat
  output: ${output as text;sse-text}

component:
  type: model
  task: chat-completion
  model: gpt2
  streaming: true
  action:
    messages:
      - role: user
        content: ${input.prompt as text}
```

Gradio Web UI automatically:
- Detects `sse-text` format
- Displays real-time text accumulation
- Shows typing animation effect

---

## 11.5 Performance and Optimization

### 11.5.1 Model Streaming Optimization

**Settings for Fast Token Generation:**

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  streaming: true
  action:
    text: ${input.prompt as text}
    params:
      # Performance optimization
      do_sample: false               # Deterministic generation (no beam search)
      num_beams: 1                   # Single beam
      max_output_length: 100         # Appropriate length limit

      # Quality vs Speed balance
      # top_p: 0.9                   # Use with sampling
      # temperature: 0.8             # Use with sampling
```

**Impact by Setting:**

| Parameter | Value | Effect |
|-----------|-------|--------|
| `do_sample` | `false` | Fastest, deterministic |
| `do_sample` | `true` | Slower, diverse outputs |
| `num_beams` | `1` | Fast |
| `num_beams` | `>1` | Slower, better quality |
| `max_output_length` | Small | Quick completion |
| `max_output_length` | Large | Longer wait time |

### 11.5.2 HTTP Streaming Optimization

**Chunk Size Adjustment:**

Default chunk size is 65536 bytes. Can be adjusted with aiohttp settings:

```python
# Custom HTTP client settings (code level)
import aiohttp

async with aiohttp.ClientSession() as session:
    async with session.get(url, chunk_size=8192) as response:
        async for chunk in response.content.iter_chunked(8192):
            # Process
```

**Timeout Settings:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  timeout: 60                      # 60 second timeout
  action:
    path: /chat/completions
    body:
      stream: true
    stream_format: json
```

### 11.5.3 Memory Management

**Memory Usage During Streaming:**

- Model streaming: Thread-based, uses queues (minimal memory)
- HTTP streaming: Chunk-based processing (no full response buffering)
- Workflow: Per-chunk rendering (no accumulation)

**Recommendations:**
- GPU memory: Determined by model size
- CPU memory: Only chunk size needed during streaming
- Long responses are memory efficient

### 11.5.4 Network Optimization

**Minimize Latency:**

1. **Server Location**: Close to users
2. **Use HTTP/2**: Keep-alive connections
3. **CDN**: Cache static assets
4. **Compression**: gzip compression (SSE is automatic)

**Bandwidth Optimization:**

- Extract only necessary fields
  ```yaml
  output: ${response[].choices[0].delta.content}
  # Only content, not full response
  ```

- Minimize JSON format
  ```yaml
  stream_format: text              # Lighter than JSON
  ```

### 11.5.5 Error Handling

**Retry Logic:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  max_retries: 3                   # Max 3 retries
  retry_delay: 1                   # 1 second wait
  action:
    path: /chat/completions
    body:
      stream: true
```

**Timeout Handling:**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  timeout: 30                      # 30 second timeout
  action:
    path: /chat/completions
    body:
      stream: true
```

**Stream Interruption Handling:**

On client side:
```javascript
const controller = new AbortController();

// Auto-abort after 5 seconds
setTimeout(() => controller.abort(), 5000);

fetch(url, {
  signal: controller.signal,
  // ...
});
```

---

## 11.6 Real-World Examples

### 11.6.1 Real-time Translation Streaming

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: Real-time Translation
  output: ${output as text;sse-text}

component:
  type: model
  task: translation
  model: Helsinki-NLP/opus-mt-ko-en
  streaming: true
  action:
    text: ${input.text as text}
    params:
      max_output_length: 512
```

### 11.6.2 OpenAI + Claude Combination

```yaml
workflows:
  - id: multi-model-chat
    title: Multi-Model Chat
    output: ${output as text;sse-text}
    jobs:
      - id: openai-response
        component: openai-client
        input:
          prompt: ${input.prompt}
        condition: ${input.model == 'openai'}

      - id: claude-response
        component: claude-client
        input:
          prompt: ${input.prompt}
        condition: ${input.model == 'claude'}

components:
  - id: openai-client
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt as text}
        stream: true
      stream_format: json
      output: ${response[].choices[0].delta.content}

  - id: claude-client
    type: http-client
    base_url: https://api.anthropic.com/v1
    action:
      path: /messages
      headers:
        x-api-key: ${env.ANTHROPIC_API_KEY}
        anthropic-version: "2023-06-01"
      body:
        model: claude-3-5-sonnet-20241022
        messages:
          - role: user
            content: ${input.prompt as text}
        stream: true
      stream_format: json
      output: ${response[].delta.text}
```

### 11.6.3 Local Model Streaming Server

```yaml
controller:
  type: http-server
  port: 8080

workflow:
  title: Local Model Streaming
  output: ${output as text;sse-text}

component:
  type: http-server
  start:
    - vllm
    - serve
    - meta-llama/Llama-2-7b-chat-hf
    - --port
    - "8000"
    - --gpu-memory-utilization
    - "0.9"
  port: 8000
  healthcheck:
    path: /health
    interval: 5s
  action:
    method: POST
    path: /v1/chat/completions
    body:
      model: llama-2-7b-chat
      messages:
        - role: user
          content: ${input.prompt as text}
      stream: true
      max_tokens: 256
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

---

## 11.7 Streaming Best Practices

### Streaming Usage Recommendations

**When Should You Use Streaming?**

✅ **Recommended:**
- Long responses (100+ tokens)
- Real-time user experience needed
- Chatbot and conversation systems
- Progressive result display

❌ **Not Recommended:**
- Short responses (< 50 tokens)
- Batch processing
- Background tasks
- Complete response needed (analysis, storage, etc.)

### Performance Optimization Checklist

- [ ] Set `num_beams: 1` (model streaming)
- [ ] Set `do_sample: false` (fast generation)
- [ ] Set appropriate `max_output_length`
- [ ] Configure timeout
- [ ] Implement error handling
- [ ] Client-side abort logic
- [ ] Use GPU (when available)

### Security Considerations

- Manage API keys via environment variables
- Use HTTPS (production)
- Set rate limiting
- Input validation
- Output filtering (harmful content)

---

## Next Steps

Practice:
- Test local model streaming
- Integrate external API streaming
- Check real-time responses in Web UI
- Experiment with various output formats

---

**Next Chapter**: [12. Variable Binding](./12-variable-binding.md)
