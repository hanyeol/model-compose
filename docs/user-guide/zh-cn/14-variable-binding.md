# 13. 变量绑定

本章详细介绍 model-compose 的变量绑定语法。变量绑定是使用 `${...}` 语法引用和转换数据的核心功能。

---

## 13.1 语法概述

变量绑定指定**数据源**(`key.path`),可选地添加**类型转换**(`as type/subtype[attrs];format`)、**默认值**(`| default`)和**元数据**(`@(annotation)`)。

**完整语法**:
```
${key.path as type/subtype[attrs];format | default @(annotation)}
```

除数据源(`key.path`)外,所有元素都是可选的。

**渐进式示例**:
```yaml
${input.name}                              # 仅数据源
${input.avatar as image/png}               # 带类型和子类型
${input.photo as image;base64}             # 带格式
${input.count | 0}                         # 带默认值
${input.email @(description "邮箱")}        # 带元数据
${input.profile as image/jpeg;url | ${env.DEFAULT_AVATAR} @(description "个人头像")}  # 所有元素组合
```

| 元素 | 说明 | 示例 |
|------|------|------|
| **key** | 数据源 | `input`, `response`, `result`, `env`, `jobs` |
| **path** | 点号表示法的嵌套字段访问,支持数组索引 | `.user.name`, `.data[0].id` |
| **type** | 数据类型 ([13.4](#134-类型转换)) | `image`, `audio`, `text`, `json` |
| **subtype** | 类型的详细格式 | `jpeg`, `png`, `mp3`, `pcm` |
| **attrs** | 方括号内的附加参数 | `sample_rate=24000,channels=1` |
| **format** | 数据的编码状态 ([13.5](#135-格式与上下文语义)) | `base64`, `url`, `path`, `sse-json` |
| **default** | 值缺失时的默认值 ([13.6](#136-默认值)) | `0`, `"gpt-4o"`, `${env.FALLBACK}` |
| **annotation** | MCP/UI 元数据 ([13.7](#137-元数据与-ui-提示)) | `@(description "用户名")` |

---

## 13.2 变量来源

### 13.2.1 工作流输入

```yaml
${input}                    # 整个输入对象
${input.field}              # input 的 field 属性
${input.user.email}         # 嵌套路径
```

### 13.2.2 组件响应变量

不同的组件类型使用不同的变量名引用响应数据。

| 组件类型 | 变量源 | 流式变量 | 说明 |
|---------|--------|---------|------|
| `http-client` | `${response}` | `${response[]}` | HTTP 响应数据 |
| `http-server` | `${response}` | `${response[]}` | 托管 HTTP 服务器响应 |
| `websocket-client` | `${response}` | `${response[]}` | WebSocket 接收数据 |
| `websocket-server` | `${response}` | `${response[]}` | 托管 WebSocket 服务器数据 |
| `mcp-client` | `${response}` | - | MCP 响应数据 |
| `mcp-server` | `${response}` | - | 托管 MCP 服务器响应 |
| `model` | `${result}` | `${result[]}` | 模型推理结果 |
| `model-trainer` | `${result}` | - | 训练结果指标 |
| `vector-store` | `${response}` | - | 向量搜索/插入结果 |
| `datasets` | `${result}` | - | 数据集样本 |
| `text-splitter` | `${result}` | - | 分割的文本块 |
| `image-processor` | `${result}` | - | 处理后的图像 |
| `workflow` | `${output}` | - | 子工作流输出 |
| `shell` | `${stdout}`, `${stderr}` | - | 命令执行结果 |

**关键规则**:
- 基于 HTTP 的组件 (`http-client`, `http-server`, `vector-store`, `mcp-client`) → `${response}`
- 本地执行组件 (`model`, `datasets`, `text-splitter`, `image-processor`) → `${result}`
- Shell 命令 → `${stdout}` 或 `${stderr}`
- 工作流调用 → `${output}`

### 13.2.3 前序作业输出

```yaml
${jobs.job-id.output}           # 特定作业输出
${jobs.job-id.output.field}     # 作业输出的特定字段
```

### 13.2.4 环境变量

```yaml
${env.OPENAI_API_KEY}       # 环境变量
${env.PORT | 8080}          # 带默认值
```

### 13.2.5 流式块引用

在变量名后附加 `[]`,以块流而非单一值的方式接收数据。

```yaml
${response[]}               # HTTP 流式块
${result[]}                 # 模型流式块
```

支持流式的组件:
- `http-client` / `http-server` → `${response[]}`
- `websocket-client` / `websocket-server` → `${response[]}`
- `model` (设置 streaming: true) → `${result[]}`

---

## 13.3 路径访问

变量路径支持嵌套对象的点号表示法和数组的方括号索引。

```yaml
${response.choices[0].message.content}     # 嵌套对象 + 数组索引
${response.data[-1].id}                    # 负数索引（最后一个元素）
${input.users[0].name}                     # 第一个元素的 name 字段
```

---

## 13.4 类型转换

使用 `as` 关键字将变量值转换为特定数据类型。

### 13.4.1 基本类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `text` | 转换为字符串 | `${input.message as text}` |
| `number` | 转换为浮点数 | `${input.price as number}` |
| `integer` | 转换为整数 | `${input.count as integer}` |
| `boolean` | 转换为布尔值 (`"true"`, `"1"` → true) | `${input.enabled as boolean}` |
| `json` | 将 JSON 字符串解析为对象 | `${input.data as json}` |

### 13.4.2 对象数组投影

在 `subtype` 中使用逗号分隔的字段路径,从对象数组中提取特定字段。

```yaml
# 从对象数组提取特定字段
${response.users as object[]/id,name}
# 结果: [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

# 嵌套路径支持（最后一段作为键名）
${response.data as object[]/user.id,user.email,status}
# 结果: [{"id": 1, "email": "john@example.com", "status": "active"}, ...]
```

### 13.4.3 媒体类型

| 类型 | 子类型 | 格式 | 示例 |
|------|--------|------|------|
| `image` | `png`, `jpg`, `webp` | `base64`, `url`, `path` | `${input.photo as image/jpg}` |
| `audio` | `mp3`, `wav`, `ogg`, `pcm` | `base64`, `url`, `path` | `${output as audio/mp3;base64}` |
| `video` | `mp4`, `webm` | `base64`, `url`, `path` | `${result as video/mp4}` |
| `file` | 任意 | `base64`, `url`, `path` | `${input.document as file}` |

### 13.4.4 属性

使用方括号语法 `type/subtype[key=value,...]` 提供附加键值参数。属性与类型、子类型一起以字典形式传递，为类型转换和下游处理提供额外上下文。

```yaml
# PCM 音频与编码参数
${response[] as audio/pcm[sample_rate=24000,channels=1,bit_depth=16]}
```

### 13.4.5 Base64 类型 vs Base64 格式

两者是不同的概念：

- **`base64` 类型** (`${value as base64}`) — 将值**编码**为 base64 字符串。无论上下文如何始终执行。
- **`base64` 格式** (`${value as image;base64}`) — 表示值**已经**是 base64 编码的。在输入上下文中系统会解码；在输出上下文中作为元数据保留。

```yaml
# 将二进制数据编码为 base64（类型）
${output as base64}

# 告知系统此数据已是 base64 编码（格式）— 在输入上下文中解码
${input.photo as image;base64}
```

---

## 13.5 格式与上下文语义

格式说明符描述数据的**编码状态**。相同的 `as type;format` 语法在不同使用位置有不同行为。

### 13.5.1 格式值

| 格式 | 说明 | 示例 |
|------|------|------|
| `base64` | 数据是 base64 编码的 | `${input.photo as image;base64}` |
| `url` | 数据是要获取的 URL | `${input.avatar as image;url}` |
| `path` | 数据是文件路径 | `${output.path as audio;path}` |
| `stream` | 数据是流 | `${output as audio;stream}` |

> **注意：** `sse-text` 和 `sse-json` 是**类型**，不是格式。使用 `${output as sse-text}` 或 `${output as sse-json}` 将值转换为 SSE 流。

### 13.5.2 输入上下文

在组件动作 `input` 中，格式告知系统**传入数据当前的编码方式**，系统将其转换为组件期望的形式。

| 类型 | 格式 | 输入值 | 处理结果 |
|------|------|--------|----------|
| `image` | `base64` | base64 字符串 | 解码并保存为临时文件 |
| `image` | `url` | URL 字符串 | 下载并保存为临时文件 |
| `image` | `path` | 文件路径 | 直接用作文件引用 |
| `image` | (无) | bytes / stream | 保存为临时文件 |
| `audio` | `base64` | base64 字符串 | 解码并保存为临时文件 |
| `audio` | `url` | URL 字符串 | 下载并保存为临时文件 |

```yaml
# "此数据是 base64 编码的图像" → 系统将其解码为文件
input:
  image: ${input.photo as image;base64}
```

### 13.5.3 组件/作业输出上下文

在组件/作业动作 `output` 中，媒体文件转换**不会执行**。值仅应用基本类型转换（如 `integer`、`json`、`base64` 编码）后直接传递。格式作为元数据为下游消费者保留。

| 类型 | 格式 | 处理结果 |
|------|------|----------|
| `image` | `base64` | 值直接传递（不解码） |
| `audio` | `path` | 文件对象渲染为其文件路径 |
| `sse-text` | (无) | 将值包装为 SSE 文本流 |
| `sse-json` | (无) | 将值包装为 SSE JSON 流 |
| `base64` | (任意) | 值编码为 base64 字符串（始终执行） |

```yaml
# "告知消费者此数据是 base64 编码的图像"
output: ${result as image;base64}
```

### 13.5.4 工作流输出上下文

工作流输出变量在工作流 schema 中定义 `type` 和 `format`。**控制器适配器**消费这些信息来决定数据的显示和传输方式：

| 消费者 | 格式 | 行为 |
|--------|------|------|
| **Web UI** | `sse-text` | 逐步累积文本块 |
| **Web UI** | `sse-json` | 将每个块解析为 JSON，通过 `subtype` 路径提取字段 |
| **Web UI** | `base64` | 解码 base64 以显示图像/音频 |
| **Web UI** | `url` | 获取 URL 以显示图像/音频 |
| **Web UI** | `path` | 直接使用文件路径 |
| **HTTP API** | (任意) | 不使用格式；传输方式由输出数据类型决定 |

```yaml
# Web UI 累积文本块；HTTP API 以 SSE 发送
workflow:
  output: ${output as sse-text}
```

---

## 13.6 默认值

默认值在变量缺失或为 null 时提供回退数据。使用管道(`|`)运算符指定字面值或引用环境变量。

### 13.6.1 字面默认值

```yaml
${input.temperature | 0.7}             # 数字
${input.model | "gpt-4o"}              # 字符串
${input.enabled | true}                # 布尔值
```

### 13.6.2 环境变量默认值

```yaml
${input.channel | ${env.DEFAULT_CHANNEL}}     # 使用环境变量作为默认值
${input.api_key | ${env.API_KEY}}             # 使用环境变量作为默认值
```

### 13.6.3 嵌套默认值（环境变量 + 字面值）

```yaml
${input.api_key | ${env.API_KEY | "default-key"}}
```

---

## 13.7 元数据与 UI 提示

### 13.7.1 注解

用于在 MCP 服务器中提供参数描述。

```yaml
${input.channel @(description Slack channel ID)}
${input.limit as integer | 10 @(description Maximum number of results)}
```

```yaml
input:
  prompt: ${input.prompt as text @(description The text prompt for generation)}
  temperature: ${input.temperature as number | 0.7 @(description Controls randomness (0-2))}
  max_tokens: ${input.max_tokens as integer | 100 @(description Maximum tokens to generate)}
```

### 13.7.2 Select（下拉）

```yaml
${input.voice as select/alloy,echo,fable,onyx,nova,shimmer}
${input.model as select/gpt-4o,gpt-4o-mini,o1-mini}
${input.size as select/256x256,512x512,1024x1024 | 1024x1024}
```

### 13.7.3 Slider（滑块）

```yaml
${input.temperature as slider/0,2,0.1 | 0.7}
# 格式: slider/min,max,step | default
```

### 13.7.4 Textarea（文本域）

```yaml
${input.prompt as text}
# Web UI 将 text 类型渲染为 textarea 小部件
```

---

## 13.8 实用示例

### 13.8.1 OpenAI API 调用

```yaml
body:
  model: ${input.model as select/gpt-4o,gpt-4o-mini,o1-mini | gpt-4o}
  messages:
    - role: user
      content: ${input.prompt as text}
  temperature: ${input.temperature as slider/0,2,0.1 | 0.7}
  max_tokens: ${input.max_tokens as integer | 1000}
output:
  message: ${response.choices[0].message.content}
```

### 13.8.2 图像处理流水线

```yaml
jobs:
  - id: analyze
    component: vision-model
    input:
      image: ${input.image as image/jpg}
    output: ${output}

  - id: enhance
    component: image-editor
    input:
      image: ${input.image as image/jpg}
      prompt: ${jobs.analyze.output.description}
    output: ${output as image/png;base64}
```

### 13.8.3 流式响应

```yaml
workflow:
  output: ${output as sse-text}

component:
  type: http-client
  action:
    body:
      stream: true
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

### 13.8.4 向量搜索结果格式

```yaml
component:
  type: vector-store
  action: search
  output: ${response as object[]/id,score,metadata.text}
# 结果: [{"id": "1", "score": 0.95, "text": "..."}, ...]
```

### 13.8.5 条件默认值

```yaml
component:
  type: http-client
  action:
    headers:
      Authorization: Bearer ${input.api_key | ${env.OPENAI_API_KEY}}
    body:
      model: ${input.model | ${env.DEFAULT_MODEL | "gpt-4o"}}
```

---

**下一章**: [14. 系统集成](./14-system-integration.md)
