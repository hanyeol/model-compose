# 12. 变量绑定

本章详细介绍 model-compose 的变量绑定语法。变量绑定是使用 `${...}` 语法引用和转换数据的核心功能。

---

## 12.1 基本语法

### 基本结构

变量绑定指定**数据源**(`key.path`),可选地添加**类型转换**(`as type/subtype;format`)、**默认值**(`| default`)和**元数据**(`@(annotation)`)。

**完整语法**:
```
${key.path as type/subtype;format | default @(annotation)}
```

除数据源(`key.path`)外,所有元素都是可选的。

**渐进式示例**:
```yaml
# 最简形式
${input.name}

# 带类型和子类型
${input.avatar as image/png}

# 带格式
${input.photo as image;base64}

# 带默认值
${input.count | 0}

# 带元数据
${input.email @(description "电子邮件地址")}

# 所有元素组合
${input.profile as image/jpeg;url | ${env.DEFAULT_AVATAR} @(description "个人头像")}
```

### 组件说明

| 元素 | 说明 | 示例 |
|---------|-------------|----------|
| **key** | 数据源(`input`、`response`、`result`、`env` 等) | `input`、`response`、`jobs` |
| **path** | 点号表示法的嵌套字段访问,支持数组索引 | `.user.name`、`.data[0].id` |
| **type** | 数据类型(详见下方列表) | `image`、`audio`、`text`、`json` |
| **subtype** | 类型的详细格式(MIME 子类型或文件扩展名) | `jpeg`、`png`、`mp3`、`wav` |
| **format** | 数据格式(源格式或转换时的输出格式) | `base64`、`url`、`sse-json` |
| **default** | 值缺失时的默认值 | `"default"`、`0`、`${env.FALLBACK}` |
| **annotation** | 变量的元数据(UI 提示、描述、验证规则等) | `@(description "用户名")` |

**数据类型(`type`)详细列表**:

| 类别 | 类型 | 说明 |
|----------|------|-------------|
| **基本类型** | `string` | 通用字符串 |
| | `text` | 长文本(文本域) |
| | `integer` | 整数 |
| | `number` | 数字(整数/浮点数) |
| | `boolean` | 真/假 |
| | `list` | 数组 |
| | `json` | JSON 对象 |
| | `object[]` | 对象数组 |
| **编码** | `base64` | Base64 编码数据 |
| | `markdown` | Markdown 文本 |
| **媒体** | `image` | 图像文件 |
| | `audio` | 音频文件 |
| | `video` | 视频文件 |
| | `file` | 通用文件 |
| **UI** | `select` | 下拉选择 |

**数据格式(`format`)详细列表**:

| 类别 | 格式 | 说明 |
|----------|--------|-------------|
| **编码** | `base64` | Base64 编码格式 |
| **源** | `url` | URL 地址格式 |
| | `path` | 文件路径格式 |
| | `stream` | 流式数据 |
| **流式输出** | `sse-text` | Server-Sent Events 文本格式 |
| | `sse-json` | Server-Sent Events JSON 格式 |

---

## 12.2 变量引用

变量引用允许您使用点号表示法和数组索引访问工作流中各种来源的数据。您可以引用输入数据、组件输出、作业结果和环境变量。`${...}` 语法支持嵌套对象路径、数组访问,以及根据使用位置的上下文特定变量。

### 12.2.1 单值引用

```yaml
${input}                    # 整个输入对象
${input.field}              # input 的 field 属性
${input.user.email}         # 嵌套路径
${response.data[0].id}      # 数组索引
```

### 12.2.2 组件响应变量源

**重要**:不同的组件类型使用不同的变量引用响应数据。

| 组件类型 | 变量源 | 流式变量 | 说明 |
|----------------|----------------|-------------------|-------------|
| `http-client` | `${response}` | `${response[]}` | HTTP 响应数据 |
| `http-server` | `${response}` | `${response[]}` | 托管 HTTP 服务器响应 |
| `mcp-client` | `${response}` | - | MCP 响应数据 |
| `mcp-server` | `${response}` | - | 托管 MCP 服务器响应 |
| `model` | `${result}` | `${result[]}` | 模型推理结果 |
| `model-trainer` | `${result}` | - | 训练结果指标 |
| `vector-store` | `${response}` | - | 向量搜索/插入结果 |
| `datasets` | `${result}` | - | 数据集样本 |
| `text-splitter` | `${result}` | - | 分割的文本块 |
| `image-processor` | `${result}` | - | 处理后的图像 |
| `workflow` | `${output}` | - | 子工作流输出 |
| `shell` | `${stdout}`、`${stderr}` | - | 命令执行结果 |

**使用示例**:

```yaml
# HTTP 客户端 - 使用 response
components:
  - id: openai-api
    type: http-client
    endpoint: https://api.openai.com/v1/chat/completions
    output: ${response.choices[0].message.content}

# 本地模型 - 使用 result
components:
  - id: local-model
    type: model
    task: text-generation
    model: gpt2
    output: ${result}

# Vector store - 使用 response
components:
  - id: chroma-db
    type: vector-store
    driver: chroma
    action: search
    output: ${response}

# Shell 命令 - 使用 stdout/stderr
components:
  - id: run-script
    type: shell
    command: echo "Hello"
    output: ${stdout}
```

**关键规则**:
- 基于 HTTP 的组件(`http-client`、`http-server`、`vector-store`、`mcp-client`) → `${response}`
- 本地执行组件(`model`、`datasets`、`text-splitter`、`image-processor`) → `${result}`
- Shell 命令 → `${stdout}` 或 `${stderr}`
- 工作流调用 → `${output}`

### 12.2.3 流式引用(按块)

```yaml
${result[]}                 # 模型流式块
${response[]}               # HTTP 流式块
${result[0]}                # 特定索引块
```

支持流式的组件:
- `http-client`(带 stream_format 设置) → `${response[]}`
- `http-server`(带 stream_format 设置) → `${response[]}`
- `model`(带 streaming: true) → `${result[]}`

### 12.2.4 作业结果引用

```yaml
${jobs.job-id.output}           # 特定作业输出
${jobs.job-id.output.field}     # 作业输出的特定字段
```

### 12.2.5 环境变量

```yaml
${env.OPENAI_API_KEY}       # 环境变量
${env.PORT | 8080}          # 带默认值
```

---

## 12.3 类型转换

类型转换允许您使用 `as` 关键字将变量值转换为特定数据类型。这确保了组件之间的数据兼容性,并为不同用例启用正确的格式化。您可以在基本类型(文本、数字、布尔值)之间转换,从对象数组提取特定字段,以及使用格式规范处理媒体类型。

### 12.3.1 基本类型

| 类型 | 说明 | 示例 |
|------|-------------|---------|
| `text` | 转换为字符串 | `${input.message as text}` |
| `number` | 转换为浮点数 | `${input.price as number}` |
| `integer` | 转换为整数 | `${input.count as integer}` |
| `boolean` | 转换为布尔值 | `${input.enabled as boolean}` |
| `json` | 解析 JSON | `${input.data as json}` |

### 12.3.2 对象数组转换

```yaml
# 从对象数组提取特定字段
${response.users as object[]/id,name}
# 结果: [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

# 嵌套路径支持
${response.data as object[]/user.id,user.email,status}
# 结果: [{"id": 1, "email": "john@example.com", "status": "active"}, ...]
```

### 12.3.3 媒体类型

| 类型 | 子类型 | 格式 | 示例 |
|------|---------|--------|---------|
| `image` | `png`、`jpg`、`webp` | `base64`、`url`、`path` | `${input.photo as image/jpg}` |
| `audio` | `mp3`、`wav`、`ogg` | `base64`、`url`、`path` | `${output as audio/mp3;base64}` |
| `video` | `mp4`、`webm` | `base64`、`url`、`path` | `${result as video/mp4}` |
| `file` | any | `base64`、`url`、`path` | `${input.document as file}` |

### 12.3.4 Base64 编码

```yaml
${output as base64}                      # 将二进制数据编码为 Base64
```

### 12.3.5 Base64 解码

```yaml
${output as audio/mp3;base64}           # 将 Base64 字符串解码为音频
${output as image/png;base64}           # 将 Base64 字符串解码为图像
```

---

## 12.4 变量格式

变量格式说明符控制数据如何序列化并传输到客户端或下游组件。在类型转换后使用分号(`;`)语法,您可以指定流式协议如 SSE 用于实时数据传输,或优化 Web UI 的数据呈现。

### 12.4.1 SSE(Server-Sent Events)流式

```yaml
# 文本流
output: ${output as text;sse-text}

# JSON 流
output: ${output as text;sse-json}
```

### 12.4.2 Web UI 特定

```yaml
# Web UI 自动选择 UI 组件
${input.photo as image}      # 图像上传小部件
${output as audio}           # 音频播放器
${result as text}            # 文本框
```

---

## 12.5 默认值

默认值在变量缺失或为 null 时提供回退数据。使用管道(`|`)运算符,您可以指定字面值或引用环境变量。当使用环境变量作为默认值时,您可以为该环境变量额外指定一层字面默认值。

### 12.5.1 字面默认值

```yaml
${input.temperature | 0.7}             # 数字
${input.model | "gpt-4o"}              # 字符串
${input.enabled | true}                # 布尔值
```

### 12.5.2 环境变量默认值

```yaml
${input.channel | ${env.DEFAULT_CHANNEL}}     # 使用环境变量作为默认值
${input.api_key | ${env.API_KEY}}             # 使用环境变量作为默认值
```

### 12.5.3 嵌套默认值(环境变量 + 字面值)

```yaml
${input.api_key | ${env.API_KEY | "default-key"}}
```

---

## 12.6 注解

用于在 MCP 服务器中提供参数描述。

### 12.6.1 基本注解

```yaml
${input.channel @(description Slack 频道 ID)}
${input.limit as integer | 10 @(description 最大结果数)}
```

### 12.6.2 复杂示例

```yaml
input:
  prompt: ${input.prompt as text @(description 生成的文本提示)}
  temperature: ${input.temperature as number | 0.7 @(description 控制随机性(0-2))}
  max_tokens: ${input.max_tokens as integer | 100 @(description 生成的最大令牌数)}
```

---

## 12.7 UI 类型提示

为 Gradio Web UI 指定输入小部件类型。

### 12.7.1 Select(下拉)

```yaml
${input.voice as select/alloy,echo,fable,onyx,nova,shimmer}
${input.model as select/gpt-4o,gpt-4o-mini,o1-mini}
${input.size as select/256x256,512x512,1024x1024 | 1024x1024}
```

### 12.7.2 Slider(滑块)

```yaml
${input.temperature as slider/0,2,0.1 | 0.7}
# 格式: slider/min,max,step | default
```

### 12.7.3 Textarea(文本域)

```yaml
${input.prompt as text}
# UI 提示不包含在类型中(Web UI 自动检测)
```

---

## 12.8 实用示例

### 12.8.1 OpenAI API 调用

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

### 12.8.2 图像处理流水线

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

### 12.8.3 流式响应

```yaml
workflow:
  output: ${output as text;sse-text}

component:
  type: http-client
  body:
    stream: true
  stream_format: json
  output: ${response[].choices[0].delta.content}
```

### 12.8.4 向量搜索结果格式

```yaml
component:
  type: vector-store
  action: search
  output: ${response as object[]/id,score,metadata.text}
# 结果: [{"id": "1", "score": 0.95, "text": "..."}, ...]
```

### 12.8.5 条件默认值

```yaml
component:
  type: http-client
  headers:
    Authorization: Bearer ${input.api_key | ${env.OPENAI_API_KEY}}
  body:
    model: ${input.model | ${env.DEFAULT_MODEL | "gpt-4o"}}
```

---

## 下一步

尝试这些练习:
- 编写各种类型转换表达式
- 使用环境变量的嵌套默认值
- 使用 UI 类型提示改进 Gradio 界面
- 实验流式输出格式

---

**下一章**: [13. 系统集成](./13-system-integration.md)
