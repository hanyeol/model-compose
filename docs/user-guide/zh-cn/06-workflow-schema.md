# 第6章：工作流 Schema

本章介绍 model-compose 如何从工作流配置中自动推断生成工作流 Schema，描述每个工作流的输入和输出变量。您将了解如何通过 API 获取 Schema，以及如何利用它进行客户端集成、Web UI 渲染和 MCP 工具映射。

---

## 6.1 什么是工作流 Schema？

**工作流 Schema** 是 model-compose 从工作流配置中自动推断生成的元数据结构。它描述了：

- **输入变量**：调用工作流时需要提供的数据
- **输出变量**：工作流完成后返回的数据

Schema 通过分析工作流作业定义中的变量绑定表达式（`${input.field as type}`）来推导。您无需手动编写 Schema — model-compose 会自动生成。

### Schema 的用途

| 用途 | Schema 使用方式 |
|------|----------------|
| Web UI | 自动生成输入表单（文本框、文件上传、下拉菜单） |
| MCP 服务器 | 将工作流输入映射为工具参数 |
| REST API 客户端 | 为请求/响应验证提供类型信息 |
| 文档 | 自描述的 API 契约 |

---

## 6.2 获取 Schema

### 单个工作流 Schema

```
GET /workflows/{workflow_id}/schema
```

**示例：**
```bash
curl http://localhost:8080/workflows/my-workflow/schema
```

**响应：**
```json
{
  "workflow_id": "my-workflow",
  "title": "My Workflow",
  "description": "A sample workflow",
  "input": [
    {
      "name": "prompt",
      "type": "text"
    },
    {
      "name": "temperature",
      "type": "number",
      "default": 0.7
    }
  ],
  "output": [
    {
      "name": "result",
      "type": "string"
    }
  ],
  "default": true
}
```

### 所有工作流 Schema

```
GET /workflows?include_schema=true
```

返回所有公开工作流的 Schema 对象数组。

### 工作流列表（不含 Schema）

```
GET /workflows
```

返回仅包含 `workflow_id`、`title` 和 `default` 字段的简要列表。

---

## 6.3 输入 Schema

输入 Schema 描述执行工作流时需要提供的变量。

### 变量结构

每个输入变量包含以下字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 变量名称（从 `${input.name}` 推导） |
| `type` | string | 变量的数据类型 |
| `subtype` | string? | 子类型限定符（如音频的 `pcm`） |
| `format` | string? | 传输格式（`base64`、`url`、`path`、`stream`） |
| `default` | any? | 未提供时的默认值 |

### 支持的类型

**基本类型：**

| 类型 | 说明 | 使用场景 |
|------|------|----------|
| `string` | 短文本字符串 | 名称、ID、标签 |
| `text` | 长文本（多行） | 提示词、文档 |
| `integer` | 整数 | 计数、索引 |
| `number` | 浮点数 | 温度、分数 |
| `boolean` | 真/假 | 功能开关 |
| `list` | 值数组 | 标签、关键词 |
| `json` | 任意 JSON 对象 | 复杂结构化数据 |
| `object[]` | 带字段投影的对象数组 | 表格数据 |

**编码类型：**

| 类型 | 说明 |
|------|------|
| `base64` | Base64 编码的二进制数据 |
| `markdown` | Markdown 格式文本 |

**媒体类型：**

| 类型 | 说明 |
|------|------|
| `image` | 图像文件（PNG、JPEG 等） |
| `audio` | 音频文件（WAV、MP3 等） |
| `video` | 视频文件（MP4 等） |
| `file` | 通用文件 |

**流式类型：**

| 类型 | 说明 |
|------|------|
| `sse-text` | Server-Sent Events（文本块） |
| `sse-json` | Server-Sent Events（JSON 块） |

**UI 类型：**

| 类型 | 说明 |
|------|------|
| `select` | 下拉选择（通过 subtype 定义选项） |

### 格式值

`format` 字段指定数据传输方式：

| 格式 | 说明 |
|------|------|
| `base64` | 在请求体中进行 base64 编码 |
| `url` | 通过 URL 引用 |
| `path` | 通过文件路径引用 |
| `stream` | 以流的形式传输 |

### 输入 Schema 推断方式

model-compose 分析作业 `input` 字段中的变量绑定表达式：

```yaml
workflows:
  - id: example
    jobs:
      - id: task
        component: my-component
        input:
          prompt: ${input.prompt as text}
          image: ${input.photo as image;base64}
          count: ${input.count as integer | 5}
```

这将生成以下输入 Schema：

```json
{
  "input": [
    { "name": "prompt", "type": "text" },
    { "name": "photo", "type": "image", "format": "base64" },
    { "name": "count", "type": "integer", "default": 5 }
  ]
}
```

**推断规则：**
- `${input.name}` → 类型默认为 `string`
- `${input.name as type}` → 使用指定类型
- `${input.name as type;format}` → 包含格式
- `${input.name as type | default}` → 包含默认值

---

## 6.4 输出 Schema

输出 Schema 描述工作流完成后返回的数据。它从 **终端作业** — 没有其他作业依赖的作业 — 的 output 中推断。

### 基本输出

```yaml
workflows:
  - id: summarize
    jobs:
      - id: generate
        component: gpt4o
        input:
          prompt: ${input.text as text}
        output:
          summary: ${output as markdown}
```

生成的 Schema：

```json
{
  "output": [
    { "name": "summary", "type": "markdown" }
  ]
}
```

### 多个输出变量

```yaml
output:
  text: ${output.content}
  confidence: ${output.score as number}
```

生成的 Schema：

```json
{
  "output": [
    { "name": "text", "type": "string" },
    { "name": "confidence", "type": "number" }
  ]
}
```

### 分组输出（repeat_count）

当组件作业使用 `repeat_count > 1` 时，输出变量会被包装在一个组中：

```yaml
jobs:
  - id: generate
    component: gpt4o
    repeat_count: 3
    input:
      prompt: ${input.prompt}
    output: ${output as text}
```

生成的 Schema：

```json
{
  "output": [
    {
      "name": null,
      "variables": [
        { "name": null, "type": "text" }
      ],
      "repeat_count": 3
    }
  ]
}
```

这告诉客户端输出将包含变量组的 3 次重复。

---

## 6.5 Schema 的实际应用

### Web UI 表单自动生成

启用 `webui` 后，model-compose 使用输入 Schema 自动生成表单控件：

| 变量类型 | UI 控件 |
|----------|---------|
| `string` | 文本输入框 |
| `text` | 文本区域 |
| `integer` / `number` | 数字输入（带注解时为滑块） |
| `boolean` | 复选框 |
| `image` | 文件上传（图像） |
| `audio` | 文件上传（音频） |
| `file` | 文件上传 |
| `select` | 下拉菜单 |

### MCP 服务器工具映射

当控制器类型为 `mcp-server` 时，工作流输入变量会转换为工具参数：

```yaml
controller:
  type: mcp-server

workflows:
  - id: translate
    jobs:
      - id: task
        component: translator
        input:
          text: ${input.text as text}
          target_lang: ${input.target_lang as select/en,ko,ja,zh}
```

这将注册 MCP 工具 `translate`，参数为：
- `text`（string，必填）
- `target_lang`（enum：en、ko、ja、zh）

### 客户端 SDK 集成

使用 Schema 端点动态构建请求负载：

```python
import requests

# 获取 Schema
schema = requests.get("http://localhost:8080/workflows/my-workflow/schema").json()

# 基于 Schema 构建输入
payload = {}
for var in schema["input"]:
    if var.get("default") is not None:
        payload[var["name"]] = var["default"]
    else:
        payload[var["name"]] = get_user_input(var["name"], var["type"])

# 执行工作流
result = requests.post(
    "http://localhost:8080/workflows/runs",
    json={"workflow_id": "my-workflow", "input": payload}
).json()
```

---

## 6.6 实战示例

### 示例 1：文本聊天工作流

```yaml
components:
  - id: gpt4o
    type: http-client
    action:
      endpoint: https://api.openai.com/v1/chat/completions
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: system
            content: ${input.system_prompt}
          - role: user
            content: ${input.user_prompt}
      output: ${response.choices[0].message.content}

workflows:
  - id: chat
    title: Chat with GPT-4o
    jobs:
      - id: generate
        component: gpt4o
        input:
          system_prompt: ${input.system_prompt as text | You are a helpful assistant.}
          user_prompt: ${input.user_prompt as text}
        output: ${output as markdown}
```

**生成的 Schema：**
```json
{
  "workflow_id": "chat",
  "title": "Chat with GPT-4o",
  "input": [
    { "name": "system_prompt", "type": "text", "default": "You are a helpful assistant." },
    { "name": "user_prompt", "type": "text" }
  ],
  "output": [
    { "name": null, "type": "markdown" }
  ]
}
```

### 示例 2：图像分析工作流

```yaml
workflows:
  - id: analyze-image
    title: Analyze Image
    jobs:
      - id: analyze
        component: vision-model
        input:
          image: ${input.image as image;base64}
          question: ${input.question as text | Describe this image.}
        output:
          description: ${output as markdown}
```

**生成的 Schema：**
```json
{
  "workflow_id": "analyze-image",
  "title": "Analyze Image",
  "input": [
    { "name": "image", "type": "image", "format": "base64" },
    { "name": "question", "type": "text", "default": "Describe this image." }
  ],
  "output": [
    { "name": "description", "type": "markdown" }
  ]
}
```

### 示例 3：流式工作流

```yaml
workflows:
  - id: stream-chat
    title: Streaming Chat
    jobs:
      - id: generate
        component: gpt4o-stream
        input:
          prompt: ${input.prompt as text}
        output: ${output as sse-text}
```

**生成的 Schema：**
```json
{
  "workflow_id": "stream-chat",
  "title": "Streaming Chat",
  "input": [
    { "name": "prompt", "type": "text" }
  ],
  "output": [
    { "name": null, "type": "sse-text" }
  ]
}
```

`sse-text` 输出类型表示客户端应期望通过 Server-Sent Events 接收流式响应。

---

## 6.7 工作流元数据字段

除了输入/输出变量外，Schema 还包含工作流级别的元数据：

| 字段 | 类型 | 说明 |
|------|------|------|
| `workflow_id` | string | 唯一标识符 |
| `title` | string? | 人类可读的标题（在 Web UI 中显示） |
| `description` | string? | 工作流的详细描述 |
| `default` | boolean | 是否为默认工作流 |

### 私有工作流

标记为 `private: true` 的工作流将从 Schema API 中排除：

```yaml
workflows:
  - id: internal-helper
    private: true
    jobs:
      - id: task
        component: helper
```

私有工作流无法通过 `GET /workflows` 或 `GET /workflows/{id}/schema` 访问。

---

## 6.8 最佳实践

1. **始终指定类型** — 使用 `${input.field as type}` 而非 `${input.field}`，以生成准确的 Schema。

2. **提供默认值** — 使用 `${input.field as type | default}` 为可选参数指定默认值，让客户端知道使用什么值。

3. **使用描述性标题** — 在工作流上设置 `title`，使 Web UI 和 MCP 工具显示有意义的名称。

4. **保持 Schema 稳定** — 更改输入变量的名称或类型是对客户端的破坏性变更。建议添加带默认值的新变量。

5. **对内部工作流使用 private** — 将辅助/子工作流标记为 `private: true`，保持公开 Schema 的整洁。

---

> **下一章**：[第7章：控制器配置](./07-controller-configuration.md) — 了解如何配置 HTTP 服务器、MCP 服务器和其他控制器类型。
