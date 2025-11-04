# 第10章：外部服务集成

本章介绍如何将外部AI服务与model-compose集成。

---

## 10.1 OpenAI API

OpenAI API提供各种AI服务，包括聊天补全、图像生成和音频处理。

### 10.1.1 聊天补全

使用GPT-4o、GPT-4和GPT-3.5模型进行文本生成任务。

#### 基本配置

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

#### 可用模型

| 模型 | 描述 | 使用场景 |
|-------|-------------|----------|
| `gpt-4o` | 多模态模型，最快的GPT-4 | 通用任务、图像分析 |
| `gpt-4-turbo` | 高性能GPT-4 | 复杂推理 |
| `gpt-4` | 标准GPT-4模型 | 深度分析 |
| `gpt-3.5-turbo` | 快速且经济实惠 | 简单任务 |

#### 关键参数

```yaml
body:
  model: gpt-4o
  messages:
    - role: system
      content: "You are a helpful assistant."
    - role: user
      content: ${input.prompt as text}
  temperature: 0.7           # 0.0-2.0，创造性控制
  max_tokens: 1000           # 最大响应长度
  top_p: 1.0                 # 核采样
  frequency_penalty: 0.0     # 减少重复
  presence_penalty: 0.0      # 主题多样性
```

#### 环境变量

```bash
export OPENAI_API_KEY=sk-...
```

### 10.1.2 图像生成（DALL-E）

DALL-E 3和DALL-E 2用于AI图像生成。

#### 基本配置

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

#### 可用选项

**模型：**
- `dall-e-3`: 高质量、详细的图像
- `dall-e-2`: 快速生成

**尺寸（DALL-E 3）：**
- `1024x1024`
- `1792x1024`
- `1024x1792`

**质量：**
- `standard`: 标准质量
- `hd`: 高细节

### 10.1.3 音频（TTS、转录）

#### 文本转语音

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

**可用声音：**
- `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

#### 语音转文本

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

Claude API提供最先进的语言模型。

### 基本配置

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

### 可用模型

| 模型 | 描述 | 使用场景 |
|-------|-------------|----------|
| `claude-3-5-sonnet-20241022` | 最新的Claude 3.5 Sonnet | 通用任务 |
| `claude-3-5-haiku-20241022` | 快速、经济实惠 | 简单任务 |
| `claude-3-opus-20240229` | 最高能力 | 复杂推理 |
| `claude-3-sonnet-20240229` | 平衡性能 | 通用使用 |

### 关键参数

```yaml
body:
  model: claude-3-5-sonnet-20241022
  messages:
    - role: user
      content: ${input.prompt as text}
  max_tokens: 1024           # 最大响应长度（必需）
  temperature: 1.0           # 0.0-1.0，创造性控制
  top_p: 1.0                 # 核采样
  top_k: 0                   # Top-k采样
  system: "You are a helpful assistant."  # 系统提示
```

### 环境变量

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## 10.3 Google Gemini API

Google Gemini提供多模态AI能力。

### 基本配置

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

### 可用模型

| 模型 | 描述 | 使用场景 |
|-------|-------------|----------|
| `gemini-pro` | 文本生成 | 通用任务 |
| `gemini-pro-vision` | 多模态模型 | 图像+文本 |
| `gemini-1.5-pro` | 最新模型 | 高级任务 |
| `gemini-1.5-flash` | 快速推理 | 简单任务 |

### 多模态配置

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

### 环境变量

```bash
export GOOGLE_API_KEY=AIza...
```

---

## 10.4 ElevenLabs（TTS）

ElevenLabs提供高质量的文本转语音服务。

### 基本配置

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

### 可用模型

| 模型 | 描述 | 语言 |
|-------|-------------|-----------|
| `eleven_multilingual_v2` | 多语言模型 | 29种语言 |
| `eleven_monolingual_v1` | 英语优化 | 仅英语 |
| `eleven_turbo_v2` | 快速生成 | 英语+多语言 |

### 声音选择

使用List Voices API获取可用声音：

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

### 环境变量

```bash
export ELEVENLABS_API_KEY=sk_...
```

---

## 10.5 Stability AI（图像生成）

Stability AI为图像生成提供Stable Diffusion模型。

### 基本配置

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

### 可用模型

| 模型 | 描述 | 使用场景 |
|-------|-------------|----------|
| `sd3-large` | Stable Diffusion 3 Large | 最高质量 |
| `sd3-medium` | Stable Diffusion 3 Medium | 平衡 |
| `sdxl-1.0` | Stable Diffusion XL | 高分辨率 |

### 关键参数

```yaml
body:
  prompt: ${input.prompt as text}
  negative_prompt: ${input.negative_prompt | ""}
  model: sd3-large
  aspect_ratio: "1:1"        # 1:1, 16:9, 21:9, 2:3, 3:2, 4:5, 5:4, 9:16, 9:21
  seed: 0                     # 可重现性
  output_format: png          # png, jpeg, webp
```

### 环境变量

```bash
export STABILITY_API_KEY=sk-...
```

---

## 10.6 Replicate

Replicate提供对各种开源AI模型的访问。

### 基本配置

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

### 示例：FLUX图像生成

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

### 示例：Llama 3文本生成

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

### 轮询结果

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

### 环境变量

```bash
export REPLICATE_API_TOKEN=r8_...
```

---

## 10.7 自定义HTTP API

使用`http-client`组件集成任何REST API。

### 基本模式

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

### 认证方法

#### Bearer令牌

```yaml
headers:
  Authorization: Bearer ${env.API_KEY}
```

#### API密钥头

```yaml
headers:
  X-API-Key: ${env.API_KEY}
```

#### 基本认证

```yaml
headers:
  Authorization: Basic ${env.BASIC_AUTH_TOKEN}
```

### 查询参数

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

### 多操作组件

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

使用方法：

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

## 10.8 外部服务集成最佳实践

### 1. API密钥管理

**使用环境变量：**

```yaml
headers:
  Authorization: Bearer ${env.API_KEY}
```

```bash
export API_KEY=your-secret-key
```

**永远不要硬编码API密钥：**

```yaml
# 错误 - 不要这样做
headers:
  Authorization: Bearer sk-hardcoded-key
```

### 2. 错误处理

在工作流中添加错误处理：

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

### 3. 成本优化

**使用合适的模型：**

```yaml
# 简单任务使用更便宜的模型
body:
  model: gpt-3.5-turbo  # 对于简单任务，不用gpt-4o
```

**限制响应长度：**

```yaml
body:
  max_tokens: 256  # 设置合理的限制
```

**缓存响应：**

```yaml
component:
  type: http-client
  cache:
    enabled: true
    ttl: 3600  # 缓存1小时
```

### 4. 速率限制

外部API通常对请求有速率限制。超过这些限制可能导致请求被拒绝或产生额外费用。

**组件级别限制：**

```yaml
component:
  type: http-client
  endpoint: https://api.example.com/v1/process
  rate_limit:
    requests_per_minute: 60    # 每分钟最多60个请求
    requests_per_day: 10000    # 每天最多10,000个请求
  headers:
    Authorization: Bearer ${env.API_KEY}
  body: ${input}
```

**在工作流中添加延迟：**

```yaml
workflow:
  jobs:
    - id: api-call-1
      component: external-api
      input: ${input}

    - id: delay
      component: shell
      command: ["sleep", "1"]  # 等待1秒

    - id: api-call-2
      component: external-api
      input: ${input}
```

常见速率限制：
- OpenAI: 3,500请求/分钟（Tier 1），10,000请求/分钟（Tier 2）
- Anthropic: 50请求/分钟（免费），1,000请求/分钟（专业版）
- Google Gemini: 60请求/分钟（免费）

### 5. 日志和监控

使用外部API时，跟踪使用情况和请求/响应信息对于成本管理和故障排除非常重要。

**跟踪使用情况：**

从API响应中提取令牌使用情况以监控成本：

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

您可以将此令牌信息记录或存储在数据库中以分析使用模式。

**记录请求/响应：**

记录API请求ID和元数据以进行调试和跟踪：

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
    request_id: ${response.id}       # 用于跟踪的请求ID
    model: ${response.model}         # 使用的模型
    created: ${response.created}     # 时间戳
```

此信息用于：
- 向API提供商报告问题时提供request_id
- 分析响应时间和监控性能
- 验证实际使用的模型（可能因回退而变化）

---

## 下一步

尝试实验：
- 在工作流中组合多个AI服务
- 构建多模态应用程序
- 创建自定义API集成
- 优化成本和性能

---

**下一章**：[11. 流式模式](./11-streaming-mode.md)
