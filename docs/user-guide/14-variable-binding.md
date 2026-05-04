# 13. Variable Binding

This chapter provides a detailed explanation of model-compose's variable binding syntax. Variable binding is a core feature that uses the `${...}` syntax to reference and transform data.

---

## 13.1 Syntax Overview

Variable binding specifies a **data source** (`key.path`), and optionally adds **type conversion** (`as type/subtype[attrs];format`), **default value** (`| default`), and **metadata** (`@(annotation)`).

**Full Syntax**:
```
${key.path as type/subtype[attrs];format | default @(annotation)}
```

All elements except the data source (`key.path`) are optional.

**Progressive Examples**:
```yaml
${input.name}                              # Data source only
${input.avatar as image/png}               # With type and subtype
${input.photo as image;base64}             # With format
${input.count | 0}                         # With default value
${input.email @(description "Email")}      # With metadata
${input.profile as image/jpeg;url | ${env.DEFAULT_AVATAR} @(description "Profile Picture")}  # All combined
```

| Element | Description | Examples |
|---------|-------------|----------|
| **key** | Data source | `input`, `response`, `result`, `env`, `jobs` |
| **path** | Nested field access with dot notation and array indexing | `.user.name`, `.data[0].id` |
| **type** | Data type ([13.4](#134-type-conversion)) | `image`, `audio`, `text`, `json` |
| **subtype** | Detailed format of the type | `jpeg`, `png`, `mp3`, `pcm` |
| **attrs** | Additional parameters in brackets | `sample_rate=24000,channels=1` |
| **format** | Encoding state of the data ([13.5](#135-format-and-context-semantics)) | `base64`, `url`, `path`, `sse-json` |
| **default** | Fallback value when value is missing ([13.6](#136-default-values)) | `0`, `"gpt-4o"`, `${env.FALLBACK}` |
| **annotation** | Metadata for MCP/UI ([13.7](#137-metadata-and-ui-hints)) | `@(description "Username")` |

---

## 13.2 Variable Sources

### 13.2.1 Workflow Input

```yaml
${input}                    # Entire input object
${input.field}              # field property of input
${input.user.email}         # Nested path
```

### 13.2.2 Component Response Variables

Different component types use different variable names to reference response data.

| Component Type | Variable Source | Streaming Variable | Description |
|----------------|----------------|-------------------|-------------|
| `http-client` | `${response}` | `${response[]}` | HTTP response data |
| `http-server` | `${response}` | `${response[]}` | Managed HTTP server response |
| `websocket-client` | `${response}` | `${response[]}` | WebSocket received data |
| `websocket-server` | `${response}` | `${response[]}` | Managed WebSocket server data |
| `mcp-client` | `${response}` | - | MCP response data |
| `mcp-server` | `${response}` | - | Managed MCP server response |
| `model` | `${result}` | `${result[]}` | Model inference result |
| `model-trainer` | `${result}` | - | Training result metrics |
| `vector-store` | `${response}` | - | Vector search/insert result |
| `datasets` | `${result}` | - | Dataset samples |
| `text-splitter` | `${result}` | - | Split text chunks |
| `image-processor` | `${result}` | - | Processed image |
| `workflow` | `${output}` | - | Sub-workflow output |
| `shell` | `${stdout}`, `${stderr}` | - | Command execution result |

**Key Rules**:
- HTTP-based components (`http-client`, `http-server`, `vector-store`, `mcp-client`) → `${response}`
- Local execution components (`model`, `datasets`, `text-splitter`, `image-processor`) → `${result}`
- Shell commands → `${stdout}` or `${stderr}`
- Workflow invocation → `${output}`

### 13.2.3 Previous Job Outputs

```yaml
${jobs.job-id.output}           # Specific job output
${jobs.job-id.output.field}     # Specific field of job output
```

### 13.2.4 Environment Variables

```yaml
${env.OPENAI_API_KEY}       # Environment variable
${env.PORT | 8080}          # With default value
```

### 13.2.5 Streaming Chunk References

Append `[]` to the variable name to receive data as a stream of chunks instead of a single value.

```yaml
${response[]}               # HTTP streaming chunks
${result[]}                 # Model streaming chunks
```

Components that support streaming:
- `http-client` / `http-server` → `${response[]}`
- `websocket-client` / `websocket-server` → `${response[]}`
- `model` (with streaming: true) → `${result[]}`

---

## 13.3 Path Access

Variable paths support dot notation for nested objects and bracket notation for array indexing.

```yaml
${response.choices[0].message.content}     # Nested object + array index
${response.data[-1].id}                    # Negative index (last element)
${input.users[0].name}                     # First element's name field
```

---

## 13.4 Type Conversion

Type conversion transforms variable values into specific data types using the `as` keyword.

### 13.4.1 Primitive Types

| Type | Description | Example |
|------|-------------|---------|
| `text` | Convert to string | `${input.message as text}` |
| `number` | Convert to float | `${input.price as number}` |
| `integer` | Convert to integer | `${input.count as integer}` |
| `boolean` | Convert to boolean (`"true"`, `"1"` → true) | `${input.enabled as boolean}` |
| `json` | Parse JSON string to object | `${input.data as json}` |

### 13.4.2 Object Array Projection

Extract specific fields from an array of objects using `subtype` as comma-separated field paths.

```yaml
# Extract specific fields from object array
${response.users as object[]/id,name}
# Result: [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

# Nested path support (last segment becomes the key name)
${response.data as object[]/user.id,user.email,status}
# Result: [{"id": 1, "email": "john@example.com", "status": "active"}, ...]
```

### 13.4.3 Media Types

| Type | Subtype | Format | Example |
|------|---------|--------|---------|
| `image` | `png`, `jpg`, `webp` | `base64`, `url`, `path` | `${input.photo as image/jpg}` |
| `audio` | `mp3`, `wav`, `ogg`, `pcm` | `base64`, `url`, `path` | `${output as audio/mp3;base64}` |
| `video` | `mp4`, `webm` | `base64`, `url`, `path` | `${result as video/mp4}` |
| `file` | any | `base64`, `url`, `path` | `${input.document as file}` |

### 13.4.4 Attributes

Attributes provide additional key-value parameters using bracket syntax: `type/subtype[key=value,...]`. They are passed as a dictionary alongside type and subtype, allowing extra context for type conversion and downstream processing.

```yaml
# PCM audio with encoding parameters
${response[] as audio/pcm[sample_rate=24000,channels=1,bit_depth=16]}
```

### 13.4.5 Base64 Type vs Base64 Format

These are different concepts:

- **`base64` type** (`${value as base64}`) — **Encodes** the value to a base64 string. Always performed regardless of context.
- **`base64` format** (`${value as image;base64}`) — Indicates the value **is already** base64 encoded. In input context, the system decodes it; in output context, it is preserved as metadata.

```yaml
# Encode binary data TO base64 (type)
${output as base64}

# Tell the system this data IS base64-encoded (format) — decoded in input context
${input.photo as image;base64}
```

---

## 13.5 Format and Context Semantics

Format specifiers describe the **encoding state** of the data. The same `as type;format` syntax behaves differently depending on where it is used.

### 13.5.1 Format Values

| Format | Description | Example |
|--------|-------------|---------|
| `base64` | Data is base64 encoded | `${input.photo as image;base64}` |
| `url` | Data is a URL to be fetched | `${input.avatar as image;url}` |
| `path` | Data is a file path | `${output.path as audio;path}` |
| `stream` | Data is a stream | `${output as audio;stream}` |

> **Note:** `sse-text` and `sse-json` are **types**, not formats. Use `${output as sse-text}` or `${output as sse-json}` to convert a value to an SSE stream.

### 13.5.2 Input Context

In component action `input`, format tells the system **how the incoming data is currently encoded**. The system converts it to the form the component expects.

| Type | Format | Input Value | What Happens |
|------|--------|-------------|--------------|
| `image` | `base64` | base64 string | Decoded and saved as a temporary file |
| `image` | `url` | URL string | Downloaded and saved as a temporary file |
| `image` | `path` | file path | Used directly as a file reference |
| `image` | (none) | bytes / stream | Saved as a temporary file |
| `audio` | `base64` | base64 string | Decoded and saved as a temporary file |
| `audio` | `url` | URL string | Downloaded and saved as a temporary file |

```yaml
# "the data is a base64-encoded image" → system decodes it to a file
input:
  image: ${input.photo as image;base64}
```

### 13.5.3 Component/Job Output Context

In component/job action `output`, media file conversion is **not performed**. The value is passed through with only basic type conversion (e.g., `integer`, `json`, `base64` encoding). The format is preserved as metadata for downstream consumers.

| Type | Format | What Happens |
|------|--------|--------------|
| `image` | `base64` | Value passed through as-is (no decoding) |
| `audio` | `path` | File object rendered to its file path |
| `sse-text` | (none) | Wraps value as SSE text stream |
| `sse-json` | (none) | Wraps value as SSE JSON stream |
| `base64` | (any) | Value encoded to base64 string (always performed) |

```yaml
# "tell consumers this is a base64-encoded image"
output: ${result as image;base64}
```

### 13.5.4 Workflow Output Context

Workflow output variables define `type` and `format` in the workflow schema. These are consumed by **controller adapters** to determine how to display and transmit the data:

| Consumer | Format | Behavior |
|----------|--------|----------|
| **Web UI** | `sse-text` | Accumulate text chunks incrementally |
| **Web UI** | `sse-json` | Parse each chunk as JSON, extract field via `subtype` path |
| **Web UI** | `base64` | Decode base64 to display image/audio |
| **Web UI** | `url` | Fetch URL to display image/audio |
| **Web UI** | `path` | Use file path directly |
| **HTTP API** | (any) | Format is not used; transmission is determined by the output data type |

```yaml
# Web UI accumulates text chunks; HTTP API sends as SSE
workflow:
  output: ${output as sse-text}
```

---

## 13.6 Default Values

Default values provide fallback data when a variable is missing or null. Using the pipe (`|`) operator, you can specify literal values or reference environment variables.

### 13.6.1 Literal Default Values

```yaml
${input.temperature | 0.7}             # Number
${input.model | "gpt-4o"}              # String
${input.enabled | true}                # Boolean
```

### 13.6.2 Environment Variable Default Values

```yaml
${input.channel | ${env.DEFAULT_CHANNEL}}     # Use environment variable as default
${input.api_key | ${env.API_KEY}}             # Use environment variable as default
```

### 13.6.3 Nested Default Values (Environment Variable + Literal)

```yaml
${input.api_key | ${env.API_KEY | "default-key"}}
```

---

## 13.7 Metadata and UI Hints

### 13.7.1 Annotations

Used to provide parameter descriptions for MCP servers.

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

### 13.7.2 Select (Dropdown)

```yaml
${input.voice as select/alloy,echo,fable,onyx,nova,shimmer}
${input.model as select/gpt-4o,gpt-4o-mini,o1-mini}
${input.size as select/256x256,512x512,1024x1024 | 1024x1024}
```

### 13.7.3 Slider

```yaml
${input.temperature as slider/0,2,0.1 | 0.7}
# Format: slider/min,max,step | default
```

### 13.7.4 Textarea

```yaml
${input.prompt as text}
# Web UI renders text type as a textarea widget
```

---

## 13.8 Practical Examples

### 13.8.1 OpenAI API Call

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

### 13.8.2 Image Processing Pipeline

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

### 13.8.3 Streaming Response

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

### 13.8.4 Vector Search Result Format

```yaml
component:
  type: vector-store
  action: search
  output: ${response as object[]/id,score,metadata.text}
# Result: [{"id": "1", "score": 0.95, "text": "..."}, ...]
```

### 13.8.5 Conditional Default Values

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

**Next Chapter**: [14. System Integration](./14-system-integration.md)
