# 14. 变量绑定

本章详细介绍 model-compose 的变量绑定语法。变量绑定是使用 `${...}` 语法引用和转换数据的核心功能。

---

## 14.1 语法概述

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
| **type** | 数据类型 ([14.4](#144-类型转换)) | `image`, `audio`, `text`, `json` |
| **subtype** | 类型的详细格式 | `jpeg`, `png`, `mp3`, `pcm` |
| **attrs** | 方括号内的附加参数 | `sample_rate=24000,channels=1` |
| **format** | 数据的编码状态 ([14.5](#145-格式与上下文语义)) | `base64`, `url`, `path`, `stream/json` |
| **default** | 值缺失时的默认值 ([14.6](#146-默认值)) | `0`, `"gpt-4o"`, `${env.FALLBACK}` |
| **annotation** | MCP/UI 元数据 ([14.7](#147-元数据与-ui-提示)) | `@(description "用户名")` |

---

## 14.2 变量来源

### 14.2.1 工作流输入

```yaml
${input}                    # 整个输入对象
${input.field}              # input 的 field 属性
${input.user.email}         # 嵌套路径
```

### 14.2.2 组件响应变量

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

### 14.2.3 前序作业输出

```yaml
${jobs.job-id.output}           # 特定作业输出
${jobs.job-id.output.field}     # 作业输出的特定字段
```

### 14.2.4 环境变量

```yaml
${env.OPENAI_API_KEY}       # 环境变量
${env.PORT | 8080}          # 带默认值
```

### 14.2.5 流式块引用

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

## 14.3 路径访问

变量路径支持嵌套对象的点号表示法和数组的方括号索引。

```yaml
${response.choices[0].message.content}     # 嵌套对象 + 数组索引
${response.data[-1].id}                    # 负数索引（最后一个元素）
${input.users[0].name}                     # 第一个元素的 name 字段
```

### 14.3.1 数组通配符 (`[*]`)

在路径中使用 `[*]` 可以从数组的每个元素中取出同一字段。结果是一个仅包含该字段的新数组。

```yaml
${response.items[*].id}
# items = [{id: 1, name: "a"}, {id: 2, name: "b"}]
# 结果: [1, 2]

${response.messages[*].tool_calls[*].id}   # 在嵌套数组上串联通配符
```

`[*]` 只做字段选择，不重构元素结构。若要为每个元素构造新对象，请使用[对象数组投影](#1442-对象数组投影)或[映射表达式](#149-映射表达式)。

---

## 14.4 类型转换

使用 `as` 关键字将变量值转换为特定数据类型。

### 14.4.1 基本类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `text` | 转换为字符串 | `${input.message as text}` |
| `number` | 转换为浮点数 | `${input.price as number}` |
| `integer` | 转换为整数 | `${input.count as integer}` |
| `boolean` | 转换为布尔值 (`"true"`, `"1"` → true) | `${input.enabled as boolean}` |
| `json` | 将 JSON 字符串解析为对象 | `${input.data as json}` |

### 14.4.2 对象数组投影

在 `subtype` 中使用逗号分隔的字段路径,从对象数组中提取特定字段。

```yaml
# 从对象数组提取特定字段
${response.users as object[]/id,name}
# 结果: [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

# 嵌套路径支持（最后一段作为键名）
${response.data as object[]/user.id,user.email,status}
# 结果: [{"id": 1, "email": "john@example.com", "status": "active"}, ...]
```

### 14.4.3 媒体类型

| 类型 | 子类型 | 格式 | 示例 |
|------|--------|------|------|
| `image` | `png`, `jpg`, `webp` | `base64`, `url`, `path` | `${input.photo as image/jpg}` |
| `audio` | `mp3`, `wav`, `ogg`, `pcm` | `base64`, `url`, `path` | `${output as audio/mp3;base64}` |
| `video` | `mp4`, `webm` | `base64`, `url`, `path` | `${result as video/mp4}` |
| `file` | 任意 | `base64`, `url`, `path` | `${input.document as file}` |

### 14.4.4 属性

使用方括号语法 `type/subtype[key=value,...]` 提供附加键值参数。属性与类型、子类型一起以字典形式传递，为类型转换和下游处理提供额外上下文。

```yaml
# PCM 音频与编码参数
${response[] as audio/pcm[sample_rate=24000,channels=1,bit_depth=16]}
```

### 14.4.5 Base64 类型 vs Base64 格式

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

## 14.5 格式与上下文语义

格式说明符描述数据的**编码状态**。相同的 `as type;format` 语法在不同使用位置有不同行为。

### 14.5.1 格式值

| 格式 | 说明 | 示例 |
|------|------|------|
| `base64` | 数据是 base64 编码的 | `${input.photo as image;base64}` |
| `url` | 数据是要获取的 URL | `${input.avatar as image;url}` |
| `path` | 数据是文件路径 | `${output.path as audio;path}` |
| `stream` | 数据是流 | `${output as audio;stream}` |

> **注意：** `stream/text` 和 `stream/json` 是**类型**，不是格式。使用 `${output as stream/text}` 或 `${output as stream/json}` 将值转换为 SSE 流。

### 14.5.2 输入上下文

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

### 14.5.3 组件/作业输出上下文

在组件/作业动作 `output` 中，媒体文件转换**不会执行**。值仅应用基本类型转换（如 `integer`、`json`、`base64` 编码）后直接传递。格式作为元数据为下游消费者保留。

| 类型 | 格式 | 处理结果 |
|------|------|----------|
| `image` | `base64` | 值直接传递（不解码） |
| `audio` | `path` | 文件对象渲染为其文件路径 |
| `stream/text` | (无) | 将值包装为 SSE 文本流 |
| `stream/json` | (无) | 将值包装为 SSE JSON 流 |
| `base64` | (任意) | 值编码为 base64 字符串（始终执行） |

```yaml
# "告知消费者此数据是 base64 编码的图像"
output: ${result as image;base64}
```

### 14.5.4 工作流输出上下文

工作流输出变量在工作流 schema 中定义 `type` 和 `format`。**控制器适配器**消费这些信息来决定数据的显示和传输方式：

| 消费者 | 格式 | 行为 |
|--------|------|------|
| **Web UI** | `stream/text` | 逐步累积文本块 |
| **Web UI** | `stream/json` | 将每个块解析为 JSON，通过 `subtype` 路径提取字段 |
| **Web UI** | `base64` | 解码 base64 以显示图像/音频 |
| **Web UI** | `url` | 获取 URL 以显示图像/音频 |
| **Web UI** | `path` | 直接使用文件路径 |
| **HTTP API** | (任意) | 不使用格式；传输方式由输出数据类型决定 |

```yaml
# Web UI 累积文本块；HTTP API 以 SSE 发送
workflow:
  output: ${output as stream/text}
```

---

## 14.6 默认值

默认值在变量缺失或为 null 时提供回退数据。使用管道(`|`)运算符指定字面值或引用环境变量。

### 14.6.1 字面默认值

```yaml
${input.temperature | 0.7}             # 数字
${input.model | "gpt-4o"}              # 字符串
${input.enabled | true}                # 布尔值
```

### 14.6.2 环境变量默认值

```yaml
${input.channel | ${env.DEFAULT_CHANNEL}}     # 使用环境变量作为默认值
${input.api_key | ${env.API_KEY}}             # 使用环境变量作为默认值
```

### 14.6.3 嵌套默认值（环境变量 + 字面值）

```yaml
${input.api_key | ${env.API_KEY | "default-key"}}
```

---

## 14.7 元数据与 UI 提示

### 14.7.1 注解

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

### 14.7.2 Select（下拉）

```yaml
${input.voice as select/alloy,echo,fable,onyx,nova,shimmer}
${input.model as select/gpt-4o,gpt-4o-mini,o1-mini}
${input.size as select/256x256,512x512,1024x1024 | 1024x1024}
```

### 14.7.3 Slider（滑块）

```yaml
${input.temperature as slider/0,2,0.1 | 0.7}
# 格式: slider/min,max,step | default
```

### 14.7.4 Textarea（文本域）

```yaml
${input.prompt as text}
# Web UI 将 text 类型渲染为 textarea 小部件
```

---

## 14.8 展开运算符

展开运算符可以把一个值的内容内联展开到外层的 dict 或 list 中。支持两种形式。

### 14.8.1 Dict 展开 (`"..."`)

在 dict 中，键 `"..."` 会把引用的 dict 的字段合并到外层 dict。显式的同级键会覆盖被展开的字段。

```yaml
body:
  "...": ${input}          # 把 input 的每个字段复制到 body
  model: gpt-4o            # 覆盖 / 追加特定字段
```

被展开的值必须解析为 dict（或 `null`，此时忽略）。

### 14.8.2 List 展开 (`...${x}`)

在 list 中，形如 `...${source}` 的字符串项会被展开，把引用的 list 中的每个元素追加到外层 list。

```yaml
messages:
  - role: system
    content: You are a helpful assistant.
  - ...${input.history}    # 追加所有先前消息
  - role: user
    content: ${input.prompt}
```

被展开的值必须解析为 list（或 `null`，此时忽略）。

---

## 14.9 映射表达式

映射表达式会把源列表的每个元素转换为新的值。使用一个 dict，其 `"*"` 键保存源列表，其余字段构成应用到每个元素的模板。模板内部通过 `${item}` 引用当前元素。

### 14.9.1 基础映射

```yaml
tools:
  "*": ${tools}
  type: function
  function: ${item}
# 结果: [{type: "function", function: <tool0>}, {type: "function", function: <tool1>}, ...]
```

### 14.9.2 与展开结合

结合映射与 dict 展开可保留原始字段，仅覆盖需要修改的部分。

```yaml
messages:
  "*": ${messages}
  "...": ${item}                  # 保留原始字段
  tool_calls:                     # 用嵌套映射重写 tool_calls
    "*": ${item.tool_calls}
    id: ${item.id}
    type: function
    function:
      name: ${item.name}
      arguments: ${item.arguments}
```

### 14.9.3 嵌套映射与 `${item}` 作用域

映射可以嵌套。`${item}` 始终指向**最内层**映射的元素。内层映射结束后，`${item}` 恢复指向外层元素。

```yaml
"*": ${orders}                    # 外层: item = 一个订单
customer: ${item.customer}
lines:
  "*": ${item.lines}              # 内层: item = 该订单的一行
  sku: ${item.sku}
  qty: ${item.qty}
```

### 14.9.4 恒等映射

如果模板为空，则原样返回源列表。用处不大但不会报错。

```yaml
messages:
  "*": ${messages}
# 结果: ${messages} (保持不变)
```

### 14.9.5 映射 vs 对象数组投影

两者都能重构 dict 列表，但适用场景不同：

| 特性 | `as object[]/...` ([14.4.2](#1442-对象数组投影)) | 映射 (`"*"`) |
|------|-------------------------------------------------|--------------|
| 位置 | 位于 `${...}` 表达式内 | YAML dict 布局 |
| 语义 | 从每个元素中选取字段 | 按模板为每个元素构造新值 |
| 常量 / 包装 | ✗ | ✓（可放任意字面量或嵌套结构） |
| 嵌套变换 | ✗ | ✓（映射中的映射） |

简单字段选择使用 `object[]/`；需要添加常量、包装元素或进行嵌套变换时使用映射表达式。

> **`${item}` 是保留的源名称。** 在映射模板内始终指向当前元素；在映射外部则按常规解析（例如 `for-each` 作业注册的 `item` 源）。

---

## 14.10 条件表达式 (`"?"`)

条件表达式计算一个或多个条件，并发出第一个匹配的分支。在字典中使用 `"?"` 键，其值可以是单个条件对象或多个条件对象的列表（列表从上到下求值，首个匹配者胜出）。

### 14.10.1 单条件

```yaml
role:
  "?":
    input: ${item.role}
    value: tool
    if_true: user               # 匹配 → "user"
    if_false: ${item.role}      # 否则 → 沿用原 role
```

**每个条件的字段：**

| 字段 | 必填 | 默认 | 说明 |
|------|:----:|------|------|
| `input` | 是 | — | 待求值的值，通常是 `${...}` 表达式。 |
| `operator` | 否 | `eq` | `eq`、`neq`、`gt`、`gte`、`lt`、`lte`、`in`、`not-in`、`starts-with`、`ends-with`、`match` 之一。 |
| `value` | 通常 | — | 比较右侧的值。对于不需要右侧值的运算符可省略。 |
| `if_true` | 否 | — | 条件匹配时发出的值。 |
| `if_false` | 否 | — | 条件不匹配时发出的值。若省略且条件失败，整个 `"?"` 不贡献任何值（见下文）。 |

### 14.10.2 多条件（首个匹配胜出）

```yaml
content:
  "*": ${item.blocks}
  "?":
    - input: ${item.type}
      value: text
      if_true: { type: text, text: ${item.text} }
    - input: ${item.type}
      value: tool_call
      if_true: { type: tool_use, id: ${item.id}, name: ${item.name}, input: ${item.arguments} }
    - input: ${item.type}
      value: tool_result
      if_true: { type: tool_result, tool_use_id: ${item.id}, content: ${item.content} }
```

每种块类型由首个匹配的分支重写；三种类型都不匹配的块对上层字典不贡献任何内容。

### 14.10.3 值位置 vs 兄弟位置

`"?"` 的行为取决于父字典中是否有其他键。

- **兄弟位置** — `"?"` 与其他键并存。所选分支**必须解析为字典**，其字段会被合并进父字典（如同 `"..."` 展开）。

  ```yaml
  "...": ${item}                # 先合入 item 的所有字段
  "?":                          # 再有选择地覆盖
    input: ${item.role}
    value: tool
    if_true: { role: user }
  ```

- **值位置** — `"?"` 是其字典中唯一的键。所选分支会**替换该字典**成为父字段的值。若要在值位置使用条件，请将其包装在字典中。

  ```yaml
  status:
    "?":
      input: ${jobs.probe.output.ok}
      value: true
      if_true: healthy
      if_false: down
  ```

### 14.10.4 没有匹配的分支时

若无条件匹配且未提供 `if_false`，`"?"` 不发出任何内容：

- **兄弟位置** → 父字典中不添加任何字段。
- **值位置** → 父字段从其字典中被省略（不会发出 `null`）。

这一特性使得 `"?"` 可用于可选装饰，而不会额外添加空字段。

### 14.10.5 注意

- `"?"` **不是映射项过滤器** — 它总是对每个迭代元素有贡献（合并、替换或省略）。要从列表中丢弃条目，请使用 `"*"` 的 `where` 子句进行过滤。
- 用列表提供多条件时，评估在首个匹配处停止。

---

## 14.11 合并运算符 (`"+"`)

`"+"` 键将同类的多个片段合并为单个值。合并方式由元素类型决定：字符串拼接、列表扩展、字典合并（后者胜出）。适合把多个 `"*"` 映射结果、可选片段和字面片段拼在一起，而无需单独的变换步骤。

### 14.11.1 基本形式

```yaml
# 字符串拼接
greeting:
  "+": ["Hello, ", "${input.name}", "!"]

# 列表扩展
tools:
  "+":
    - ${input.builtin_tools}
    - ${input.custom_tools}

# 字典合并（后者胜出）
headers:
  "+":
    - ${env.default_headers}
    - Authorization: Bearer ${env.API_KEY}
```

### 14.11.2 与映射表达式组合

常见用途：对同一源运行多个 `"*"` 映射，然后将它们的投影拼成一个列表。相比链式 `"?"` 分支更加清晰。

```yaml
# 规范 assistant 块 → OpenAI assistant 消息字段。
content:
  "+":
    - "*":
        input: ${item.blocks}
        where: { input: ${item.type}, value: text }
      type: text
      text: ${item.text}
    - "*":
        input: ${item.blocks}
        where: { input: ${item.type}, value: tool_call }
      type: tool_use
      id: ${item.id}
      name: ${item.name}
      input: ${item.arguments}
```

### 14.11.3 规则

- `"+"` 的值必须解析为列表 — 可以是字面 YAML 列表，也可以是解析为列表的 `${...}` 表达式。其他值会抛出 `TypeError`。
- **`None` 元素被跳过。** 这样可以直接放入可选片段（`${maybe_missing}`、`{ "?": {...} }`），无需额外处理。
- **结果为空**（没有元素或全部解析为 `None`）→ 整个 `"+"` 渲染为 `None`。如需占位值，请在外层调用点用 `| default` 追加。
- **类型一致** — 存活的元素必须全部为同种类型（全 `str`、全 `list` 或全 `dict`）；混用会抛出 `TypeError`。这是有意为之：不同类型的合并语义不同，混合会引起歧义。
  - `str` 元素 → 无分隔符拼接（如需分隔符请以字面量插入）。
  - `list` 元素 → 扩展（`[1, 2] + [3] → [1, 2, 3]`）。
  - `dict` 元素 → 后者胜出的合并，与 `"..."` 相同语义。
- `"+"` 是**仅限键**的运算符，且必须是其字典中的唯一键。`{ "+": [...], "other": 1 }` 会被当作普通字典字面量，不触发合并。

---

## 14.12 实用示例

### 14.12.1 OpenAI API 调用

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

### 14.12.2 图像处理流水线

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

### 14.12.3 流式响应

```yaml
workflow:
  output: ${output as stream/text}

component:
  type: http-client
  action:
    body:
      stream: true
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

### 14.12.4 向量搜索结果格式

```yaml
component:
  type: vector-store
  action: search
  output: ${response as object[]/id,score,metadata.text}
# 结果: [{"id": "1", "score": 0.95, "text": "..."}, ...]
```

### 14.12.5 条件默认值

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

**下一章**：[第15章：系统集成](./15-system-integration.md)
