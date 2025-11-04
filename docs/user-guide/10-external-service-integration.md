# Chapter 10: External Service Integration

This chapter covers integrating external AI services with model-compose.

---

## 10.1 OpenAI API

OpenAI API provides various AI services including chat completions, image generation, and audio processing.

### 10.1.1 Chat Completions

Use GPT-4o, GPT-4, and GPT-3.5 models for text generation tasks.

#### Basic Configuration

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /chat/completions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
    Content-Type: application/json
  body:
    model: gpt-4o
    messages:
      - role: user
        content: ${input.prompt as text}
    temperature: ${input.temperature as number | 0.7}
  output:
    message: ${response.choices[0].message.content}
```

#### Available Models

| Model | Description | Use Case |
|-------|-------------|----------|
| `gpt-4o` | Multimodal model, fastest GPT-4 | General tasks, image analysis |
| `gpt-4-turbo` | High-performance GPT-4 | Complex reasoning |
| `gpt-4` | Standard GPT-4 model | Deep analysis |
| `gpt-3.5-turbo` | Fast and cost-effective | Simple tasks |

#### Key Parameters

```yaml
body:
  model: gpt-4o
  messages:
    - role: system
      content: "You are a helpful assistant."
    - role: user
      content: ${input.prompt as text}
  temperature: 0.7           # 0.0-2.0, creativity control
  max_tokens: 1000           # Maximum response length
  top_p: 1.0                 # Nucleus sampling
  frequency_penalty: 0.0     # Reduce repetition
  presence_penalty: 0.0      # Topic diversity
```

#### Environment Variables

```bash
export OPENAI_API_KEY=sk-...
```

### 10.1.2 Image Generation (DALL-E)

DALL-E 3 and DALL-E 2 for AI image generation.

#### Basic Configuration

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /images/generations
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
    Content-Type: application/json
  body:
    model: dall-e-3
    prompt: ${input.prompt as text}
    size: ${input.size | "1024x1024"}
    quality: ${input.quality | "standard"}
    n: 1
  output:
    image_url: ${response.data[0].url}
```

#### Available Options

**Models:**
- `dall-e-3`: High-quality, detailed images
- `dall-e-2`: Fast generation

**Sizes (DALL-E 3):**
- `1024x1024`
- `1792x1024`
- `1024x1792`

**Quality:**
- `standard`: Standard quality
- `hd`: High detail

### 10.1.3 Audio (TTS, Transcriptions)

#### Text-to-Speech

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /audio/speech
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
    Content-Type: application/json
  body:
    model: tts-1
    voice: ${input.voice | "alloy"}
    input: ${input.text as text}
  output: ${response as base64}
```

**Available Voices:**
- `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

#### Speech-to-Text

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /audio/transcriptions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  body:
    model: whisper-1
    file: ${input.audio as base64}
    language: ${input.language | "en"}
  output:
    text: ${response.text}
```

---

## 10.2 Anthropic Claude API

Claude API provides state-of-the-art language models.

### Basic Configuration

```yaml
component:
  type: http-client
  base_url: https://api.anthropic.com/v1
  path: /messages
  method: POST
  headers:
    x-api-key: ${env.ANTHROPIC_API_KEY}
    anthropic-version: "2023-06-01"
    Content-Type: application/json
  body:
    model: claude-3-5-sonnet-20241022
    messages:
      - role: user
        content: ${input.prompt as text}
    max_tokens: ${input.max_tokens as number | 1024}
  output:
    message: ${response.content[0].text}
```

### Available Models

| Model | Description | Use Case |
|-------|-------------|----------|
| `claude-3-5-sonnet-20241022` | Latest Claude 3.5 Sonnet | General tasks |
| `claude-3-5-haiku-20241022` | Fast, cost-effective | Simple tasks |
| `claude-3-opus-20240229` | Highest capability | Complex reasoning |
| `claude-3-sonnet-20240229` | Balanced performance | General use |

### Key Parameters

```yaml
body:
  model: claude-3-5-sonnet-20241022
  messages:
    - role: user
      content: ${input.prompt as text}
  max_tokens: 1024           # Maximum response length (required)
  temperature: 1.0           # 0.0-1.0, creativity control
  top_p: 1.0                 # Nucleus sampling
  top_k: 0                   # Top-k sampling
  system: "You are a helpful assistant."  # System prompt
```

### Environment Variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## 10.3 Google Gemini API

Google Gemini provides multimodal AI capabilities.

### Basic Configuration

```yaml
component:
  type: http-client
  base_url: https://generativelanguage.googleapis.com/v1beta
  path: /models/gemini-pro:generateContent
  method: POST
  params:
    key: ${env.GOOGLE_API_KEY}
  body:
    contents:
      - parts:
          - text: ${input.prompt as text}
  output:
    message: ${response.candidates[0].content.parts[0].text}
```

### Available Models

| Model | Description | Use Case |
|-------|-------------|----------|
| `gemini-pro` | Text generation | General tasks |
| `gemini-pro-vision` | Multimodal model | Image + text |
| `gemini-1.5-pro` | Latest model | Advanced tasks |
| `gemini-1.5-flash` | Fast inference | Simple tasks |

### Multimodal Configuration

```yaml
component:
  type: http-client
  base_url: https://generativelanguage.googleapis.com/v1beta
  path: /models/gemini-pro-vision:generateContent
  method: POST
  params:
    key: ${env.GOOGLE_API_KEY}
  body:
    contents:
      - parts:
          - text: ${input.prompt as text}
          - inline_data:
              mime_type: image/jpeg
              data: ${input.image as base64}
  output:
    message: ${response.candidates[0].content.parts[0].text}
```

### Environment Variables

```bash
export GOOGLE_API_KEY=AIza...
```

---

## 10.4 ElevenLabs (TTS)

ElevenLabs provides high-quality text-to-speech services.

### Basic Configuration

```yaml
component:
  type: http-client
  base_url: https://api.elevenlabs.io/v1
  path: /text-to-speech/${input.voice_id}
  method: POST
  headers:
    xi-api-key: ${env.ELEVENLABS_API_KEY}
    Content-Type: application/json
  body:
    text: ${input.text as text}
    model_id: eleven_multilingual_v2
    voice_settings:
      stability: ${input.stability | 0.5}
      similarity_boost: ${input.similarity_boost | 0.75}
  output: ${response as base64}
```

### Available Models

| Model | Description | Languages |
|-------|-------------|-----------|
| `eleven_multilingual_v2` | Multilingual model | 29 languages |
| `eleven_monolingual_v1` | English-optimized | English only |
| `eleven_turbo_v2` | Fast generation | English + multilingual |

### Voice Selection

Use the List Voices API to get available voices:

```yaml
component:
  type: http-client
  base_url: https://api.elevenlabs.io/v1
  path: /voices
  method: GET
  headers:
    xi-api-key: ${env.ELEVENLABS_API_KEY}
  output: ${response.voices}
```

### Environment Variables

```bash
export ELEVENLABS_API_KEY=sk_...
```

---

## 10.5 Stability AI (Image Generation)

Stability AI provides Stable Diffusion models for image generation.

### Basic Configuration

```yaml
component:
  type: http-client
  base_url: https://api.stability.ai/v2beta
  path: /stable-image/generate/sd3
  method: POST
  headers:
    Authorization: Bearer ${env.STABILITY_API_KEY}
    Content-Type: application/json
  body:
    prompt: ${input.prompt as text}
    model: sd3-large
    aspect_ratio: ${input.aspect_ratio | "1:1"}
    output_format: ${input.output_format | "png"}
  output:
    image: ${response.image as base64}
```

### Available Models

| Model | Description | Use Case |
|-------|-------------|----------|
| `sd3-large` | Stable Diffusion 3 Large | Highest quality |
| `sd3-medium` | Stable Diffusion 3 Medium | Balanced |
| `sdxl-1.0` | Stable Diffusion XL | High resolution |

### Key Parameters

```yaml
body:
  prompt: ${input.prompt as text}
  negative_prompt: ${input.negative_prompt | ""}
  model: sd3-large
  aspect_ratio: "1:1"        # 1:1, 16:9, 21:9, 2:3, 3:2, 4:5, 5:4, 9:16, 9:21
  seed: 0                     # Reproducibility
  output_format: png          # png, jpeg, webp
```

### Environment Variables

```bash
export STABILITY_API_KEY=sk-...
```

---

## 10.6 Replicate

Replicate provides access to various open-source AI models.

### Basic Configuration

```yaml
component:
  type: http-client
  base_url: https://api.replicate.com/v1
  path: /predictions
  method: POST
  headers:
    Authorization: Bearer ${env.REPLICATE_API_TOKEN}
    Content-Type: application/json
  body:
    version: ${input.model_version}
    input: ${input.params}
  output:
    prediction_id: ${response.id}
```

### Example: FLUX Image Generation

```yaml
component:
  type: http-client
  base_url: https://api.replicate.com/v1
  path: /predictions
  method: POST
  headers:
    Authorization: Bearer ${env.REPLICATE_API_TOKEN}
    Content-Type: application/json
  body:
    version: "black-forest-labs/flux-schnell"
    input:
      prompt: ${input.prompt as text}
      num_outputs: 1
      aspect_ratio: "1:1"
  output:
    prediction_id: ${response.id}
    status: ${response.status}
```

### Example: Llama 3 Text Generation

```yaml
component:
  type: http-client
  base_url: https://api.replicate.com/v1
  path: /predictions
  method: POST
  headers:
    Authorization: Bearer ${env.REPLICATE_API_TOKEN}
    Content-Type: application/json
  body:
    version: "meta/meta-llama-3-70b-instruct"
    input:
      prompt: ${input.prompt as text}
      max_tokens: 512
      temperature: 0.7
  output:
    prediction_id: ${response.id}
```

### Polling for Results

```yaml
component:
  type: http-client
  base_url: https://api.replicate.com/v1
  path: /predictions/${input.prediction_id}
  method: GET
  headers:
    Authorization: Bearer ${env.REPLICATE_API_TOKEN}
  output:
    status: ${response.status}
    result: ${response.output}
```

### Environment Variables

```bash
export REPLICATE_API_TOKEN=r8_...
```

---

## 10.7 Custom HTTP API

Integrate any REST API using the `http-client` component.

### Basic Pattern

```yaml
component:
  type: http-client
  base_url: https://api.example.com
  path: /v1/endpoint
  method: POST
  headers:
    Authorization: Bearer ${env.API_KEY}
    Content-Type: application/json
  body: ${input}
  output: ${response}
```

### Authentication Methods

#### Bearer Token

```yaml
headers:
  Authorization: Bearer ${env.API_KEY}
```

#### API Key Header

```yaml
headers:
  X-API-Key: ${env.API_KEY}
```

#### Basic Authentication

```yaml
headers:
  Authorization: Basic ${env.BASIC_AUTH_TOKEN}
```

### Query Parameters

```yaml
component:
  type: http-client
  base_url: https://api.example.com
  path: /search
  method: GET
  params:
    q: ${input.query}
    limit: 10
    offset: ${input.offset | 0}
  output: ${response}
```

### Multi-Action Component

```yaml
component:
  type: http-client
  base_url: https://api.example.com
  headers:
    Authorization: Bearer ${env.API_KEY}
  actions:
    - id: create
      path: /resources
      method: POST
      body: ${input}
      output: ${response}

    - id: get
      path: /resources/${input.id}
      method: GET
      output: ${response}

    - id: update
      path: /resources/${input.id}
      method: PUT
      body: ${input}
      output: ${response}

    - id: delete
      path: /resources/${input.id}
      method: DELETE
      output: ${response}
```

Usage:

```yaml
workflow:
  jobs:
    - id: create
      component: api
      action: create
      input:
        name: "Example"

    - id: get
      component: api
      action: get
      input:
        id: ${jobs.create.output.id}
```

---

## 10.8 External Service Integration Best Practices

### 1. API Key Management

**Use environment variables:**

```yaml
headers:
  Authorization: Bearer ${env.API_KEY}
```

```bash
export API_KEY=your-secret-key
```

**Never hardcode API keys:**

```yaml
# Bad - Don't do this
headers:
  Authorization: Bearer sk-hardcoded-key
```

### 2. Error Handling

Add error handling in workflows:

```yaml
workflow:
  jobs:
    - id: api-call
      component: external-api
      on_error:
        action: retry
        max_retry_count: 3
        backoff: exponential
```

### 3. Cost Optimization

**Use appropriate models:**

```yaml
# Use cheaper models for simple tasks
body:
  model: gpt-3.5-turbo  # Instead of gpt-4o for simple tasks
```

**Limit response length:**

```yaml
body:
  max_tokens: 256  # Set reasonable limits
```

**Cache responses:**

```yaml
component:
  type: http-client
  cache:
    enabled: true
    ttl: 3600  # Cache for 1 hour
```

### 4. Rate Limiting

External APIs typically have rate limits on requests. Exceeding these limits can result in rejected requests or additional costs.

**Component-level limits:**

```yaml
component:
  type: http-client
  endpoint: https://api.example.com/v1/process
  rate_limit:
    requests_per_minute: 60    # Maximum 60 requests per minute
    requests_per_day: 10000    # Maximum 10,000 requests per day
  headers:
    Authorization: Bearer ${env.API_KEY}
  body: ${input}
```

**Add delays in workflows:**

```yaml
workflow:
  jobs:
    - id: api-call-1
      component: external-api
      input: ${input}

    - id: delay
      component: shell
      command: ["sleep", "1"]  # Wait 1 second

    - id: api-call-2
      component: external-api
      input: ${input}
```

Common rate limits:
- OpenAI: 3,500 requests/min (Tier 1), 10,000 requests/min (Tier 2)
- Anthropic: 50 requests/min (Free), 1,000 requests/min (Pro)
- Google Gemini: 60 requests/min (Free)

### 5. Logging and Monitoring

When using external APIs, it's important to track usage and request/response information for cost management and troubleshooting.

**Track usage:**

Extract token usage from API responses to monitor costs:

```yaml
workflow:
  jobs:
    - id: call-gpt
      component: openai-chat
      input: ${input}
      output:
        message: ${output.choices[0].message.content}
        prompt_tokens: ${output.usage.prompt_tokens}
        completion_tokens: ${output.usage.completion_tokens}
        total_tokens: ${output.usage.total_tokens}
```

You can log or store this token information in a database to analyze usage patterns.

**Log requests/responses:**

Record API request IDs and metadata for debugging and tracking:

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /chat/completions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  body: ${input}
  output:
    response: ${response}
    request_id: ${response.id}       # Request ID for tracking
    model: ${response.model}         # Model used
    created: ${response.created}     # Timestamp
```

This information is useful for:
- Providing request_id when reporting issues to API providers
- Analyzing response times and monitoring performance
- Verifying the actual model used (can change due to fallbacks)

---

## Next Steps

Try experimenting with:
- Combining multiple AI services in workflows
- Building multi-modal applications
- Creating custom API integrations
- Optimizing for cost and performance

---

**Next Chapter**: [11. Streaming Mode](./11-streaming-mode.md)
