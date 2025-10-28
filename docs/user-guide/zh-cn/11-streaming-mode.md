# 11. 流式模式

本章介绍如何使用model-compose的流式功能来生成和处理实时响应。

---

## 11.1 流式概述

### 11.1.1 什么是流式？

流式模式在生成时传递部分结果，而不是等待模型或API的完整响应。

**优势：**
- 向用户提供即时反馈
- 减少长响应的首个令牌时间（TTFT）
- 构建实时流式应用程序
- 更好的用户体验（打字效果）

**使用场景：**
- 聊天机器人对话（ChatGPT风格）
- 实时文本生成
- 长文档摘要
- 翻译服务
- 代码生成

### 11.1.2 支持的组件

支持流式的组件：

| 组件类型 | 流式支持 | 配置 |
|---------------|------------------|---------------|
| `model`（text-generation） | ✅ | `streaming: true` |
| `model`（chat-completion） | ✅ | `streaming: true` |
| `http-client` | ✅ | `stream_format: json/text` |
| `http-server` | ✅ | `stream_format: json/text` |

### 11.1.3 流式协议

model-compose使用**SSE（Server-Sent Events）**协议。

**SSE格式：**
```
data: chunk1

data: chunk2

data: chunk3

```

每个块以`data:`前缀发送，并由空行分隔。

---

## 11.2 特定组件的流式配置

### 11.2.1 模型组件

#### 基本配置

```yaml
component:
  type: model
  task: text-generation
  model: facebook/bart-large-cnn
  text: ${input.text as text}
  streaming: true                  # 启用流式
  params:
    max_output_length: 150
```

**重要约束：**
- `batch_size`必须为`1`
- 仅支持单个输入（不支持批处理）
- 流式时推荐`num_beams: 1`

#### 文本生成流式

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  text: ${input.prompt as text}
  streaming: true
  params:
    max_output_length: 200
    do_sample: false               # 确定性生成（更快）
    num_beams: 1                   # 禁用束搜索
```

**输出引用：**
- 流式：`${result[]}`（每个块）
- 非流式：`${result}`（完整完成后）

#### 聊天补全流式

```yaml
component:
  type: model
  task: chat-completion
  model: microsoft/DialoGPT-medium
  messages:
    - role: user
      content: ${input.message as text}
  streaming: true
  params:
    max_output_length: 100
```

**功能：**
- 自动应用聊天模板
- 与文本生成相同的流式机制
- 使用`${result[]}`进行每块处理

### 11.2.2 HTTP组件

#### HTTP客户端流式

**OpenAI API流式：**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  path: /chat/completions
  method: POST
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  body:
    model: gpt-4o
    messages:
      - role: user
        content: ${input.prompt as text}
    stream: true                   # API参数
  stream_format: json              # 将块解析为JSON
  output: ${response[].choices[0].delta.content}
```

**stream_format选项：**

- `json`: 将每个块解析为JSON
  ```yaml
  stream_format: json
  output: ${response[].choices[0].delta.content}
  ```

- `text`: 将每个块解码为UTF-8文本
  ```yaml
  stream_format: text
  output: ${response[]}
  ```

- 未指定：传递原始字节

**输出引用：**
- 流式：`${response[]}`（每个块）
- 非流式：`${response}`（完整完成后）

#### HTTP服务器（托管服务）流式

**vLLM服务器流式：**

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

## 11.3 在工作流中使用流式

### 11.3.1 基本流式工作流

```yaml
controller:
  type: http-server
  port: 8080

workflow:
  title: Streaming Chat
  output: ${output as text;sse-text}    # 输出为SSE文本格式

component:
  type: http-client
  base_url: https://api.openai.com/v1
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

**工作流输出格式：**

- `as text;sse-text`: SSE文本流
  ```yaml
  output: ${output as text;sse-text}
  ```

- `as text;sse-json`: SSE JSON流
  ```yaml
  output: ${output as text;sse-json}
  ```

### 11.3.2 多步骤工作流流式

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
        # 无流式的翻译（等待完整完成）

      - id: summarize
        component: summarizer
        input:
          text: ${jobs.translate.output}
        # 带流式输出的摘要
        depends_on: [translate]

components:
  - id: translator
    type: model
    task: translation
    model: Helsinki-NLP/opus-mt-ko-en
    text: ${input.text as text}
    streaming: false

  - id: summarizer
    type: model
    task: text-generation
    model: facebook/bart-large-cnn
    text: ${input.text as text}
    streaming: true                    # 仅最后一个作业流式
    params:
      max_output_length: 150
```

**重要提示：**
- 工作流中只有**最后一个作业**可以流式
- 中间作业必须等待完成
- 只有最终输出使用`${result[]}`流式

### 11.3.3 条件流式

```yaml
workflow:
  title: Conditional Streaming
  output: ${output as text;sse-text}

component:
  type: model
  task: text-generation
  model: gpt2
  text: ${input.prompt as text}
  streaming: ${input.stream | false}   # 流式由输入决定
  params:
    max_output_length: 100
```

**API调用示例：**

```bash
# 启用流式
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"prompt": "Hello", "stream": true},
    "output_only": true,
    "wait_for_completion": true
  }'

# 禁用流式
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"prompt": "Hello", "stream": false},
    "wait_for_completion": true
  }'
```

---

## 11.4 处理流式响应

### 11.4.1 API端点

**流式请求要求：**

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {"prompt": "Write a story"},
    "output_only": true,              # 必需：仅返回输出
    "wait_for_completion": true       # 必需：等待完成
  }'
```

**响应头：**
```
Content-Type: text/event-stream
Cache-Control: no-cache
```

**响应体（SSE）：**
```
data: Once

data:  upon

data:  a

data:  time

```

### 11.4.2 客户端实现（JavaScript）

**使用EventSource API：**

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
  // 更新UI
  document.getElementById('output').textContent += chunk;
};

eventSource.onerror = (error) => {
  console.error('Error:', error);
  eventSource.close();
};
```

**使用Fetch API：**

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
      // 更新UI
      document.getElementById('output').textContent += content;
    }
  }
}
```

### 11.4.3 客户端实现（Python）

**使用requests库：**

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

**使用aiohttp库（异步）：**

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

### 11.4.4 Web UI集成

**Gradio自动流式：**

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
  messages:
    - role: user
      content: ${input.prompt as text}
  streaming: true
```

Gradio Web UI自动：
- 检测`sse-text`格式
- 显示实时文本累积
- 显示打字动画效果

---

## 11.5 性能和优化

### 11.5.1 模型流式优化

**快速令牌生成的设置：**

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  text: ${input.prompt as text}
  streaming: true
  params:
    # 性能优化
    do_sample: false               # 确定性生成（无束搜索）
    num_beams: 1                   # 单束
    max_output_length: 100         # 适当的长度限制

    # 质量与速度平衡
    # top_p: 0.9                   # 与采样一起使用
    # temperature: 0.8             # 与采样一起使用
```

**按设置的影响：**

| 参数 | 值 | 效果 |
|-----------|-------|--------|
| `do_sample` | `false` | 最快，确定性 |
| `do_sample` | `true` | 较慢，多样化输出 |
| `num_beams` | `1` | 快速 |
| `num_beams` | `>1` | 较慢，更好的质量 |
| `max_output_length` | 小 | 快速完成 |
| `max_output_length` | 大 | 更长的等待时间 |

### 11.5.2 HTTP流式优化

**块大小调整：**

默认块大小为65536字节。可以使用aiohttp设置调整：

```python
# 自定义HTTP客户端设置（代码级别）
import aiohttp

async with aiohttp.ClientSession() as session:
    async with session.get(url, chunk_size=8192) as response:
        async for chunk in response.content.iter_chunked(8192):
            # 处理
```

**超时设置：**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  timeout: 60                      # 60秒超时
  path: /chat/completions
  body:
    stream: true
  stream_format: json
```

### 11.5.3 内存管理

**流式期间的内存使用：**

- 模型流式：基于线程，使用队列（最小内存）
- HTTP流式：基于块的处理（无完整响应缓冲）
- 工作流：每块渲染（无累积）

**建议：**
- GPU内存：由模型大小决定
- CPU内存：流式期间仅需要块大小
- 长响应具有内存效率

### 11.5.4 网络优化

**最小化延迟：**

1. **服务器位置**：靠近用户
2. **使用HTTP/2**：保持连接
3. **CDN**：缓存静态资源
4. **压缩**：gzip压缩（SSE自动）

**带宽优化：**

- 仅提取必要字段
  ```yaml
  output: ${response[].choices[0].delta.content}
  # 仅内容，而非完整响应
  ```

- 最小化JSON格式
  ```yaml
  stream_format: text              # 比JSON更轻量
  ```

### 11.5.5 错误处理

**重试逻辑：**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  max_retries: 3                   # 最多3次重试
  retry_delay: 1                   # 1秒等待
  path: /chat/completions
  body:
    stream: true
```

**超时处理：**

```yaml
component:
  type: http-client
  base_url: https://api.openai.com/v1
  timeout: 30                      # 30秒超时
  path: /chat/completions
  body:
    stream: true
```

**流中断处理：**

在客户端：
```javascript
const controller = new AbortController();

// 5秒后自动中止
setTimeout(() => controller.abort(), 5000);

fetch(url, {
  signal: controller.signal,
  // ...
});
```

---

## 11.6 实际示例

### 11.6.1 实时翻译流式

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
  text: ${input.text as text}
  streaming: true
  params:
    max_output_length: 512
```

### 11.6.2 OpenAI + Claude组合

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

### 11.6.3 本地模型流式服务器

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

## 11.7 流式最佳实践

### 流式使用建议

**何时应该使用流式？**

✅ **推荐：**
- 长响应（100+令牌）
- 需要实时用户体验
- 聊天机器人和对话系统
- 渐进式结果显示

❌ **不推荐：**
- 短响应（< 50令牌）
- 批处理
- 后台任务
- 需要完整响应（分析、存储等）

### 性能优化清单

- [ ] 设置`num_beams: 1`（模型流式）
- [ ] 设置`do_sample: false`（快速生成）
- [ ] 设置适当的`max_output_length`
- [ ] 配置超时
- [ ] 实现错误处理
- [ ] 客户端中止逻辑
- [ ] 使用GPU（可用时）

### 安全考虑

- 通过环境变量管理API密钥
- 使用HTTPS（生产环境）
- 设置速率限制
- 输入验证
- 输出过滤（有害内容）

---

## 下一步

实践：
- 测试本地模型流式
- 集成外部API流式
- 在Web UI中检查实时响应
- 尝试各种输出格式

---

**下一章**：[12. 变量绑定](./12-variable-binding.md)
