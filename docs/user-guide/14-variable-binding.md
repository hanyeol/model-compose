# 14. Variable Binding

This chapter provides a detailed explanation of model-compose's variable binding syntax. Variable binding is a core feature that uses the `${...}` syntax to reference and transform data.

---

## 14.1 Syntax Overview

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
| **type** | Data type ([14.4](#144-type-conversion)) | `image`, `audio`, `text`, `json` |
| **subtype** | Detailed format of the type | `jpeg`, `png`, `mp3`, `pcm` |
| **attrs** | Additional parameters in brackets | `sample_rate=24000,channels=1` |
| **format** | Encoding state of the data ([14.5](#145-format-and-context-semantics)) | `base64`, `url`, `path`, `stream/json` |
| **default** | Fallback value when value is missing ([14.6](#146-default-values)) | `0`, `"gpt-4o"`, `${env.FALLBACK}` |
| **annotation** | Metadata for MCP/UI ([14.7](#147-metadata-and-ui-hints)) | `@(description "Username")` |

---

## 14.2 Variable Sources

### 14.2.1 Workflow Input

```yaml
${input}                    # Entire input object
${input.field}              # field property of input
${input.user.email}         # Nested path
```

### 14.2.2 Component Response Variables

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

### 14.2.3 Previous Job Outputs

```yaml
${jobs.job-id.output}           # Specific job output
${jobs.job-id.output.field}     # Specific field of job output
```

### 14.2.4 Environment Variables

```yaml
${env.OPENAI_API_KEY}       # Environment variable
${env.PORT | 8080}          # With default value
```

### 14.2.5 Streaming Chunk References

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

## 14.3 Path Access

Variable paths support dot notation for nested objects and bracket notation for array indexing.

```yaml
${response.choices[0].message.content}     # Nested object + array index
${response.data[-1].id}                    # Negative index (last element)
${input.users[0].name}                     # First element's name field
```

### 14.3.1 Array Wildcard (`[*]`)

Use `[*]` in a path to pick a field from every element of an array. The result is a new array containing only that field.

```yaml
${response.items[*].id}
# Given items = [{id: 1, name: "a"}, {id: 2, name: "b"}]
# Result: [1, 2]

${response.messages[*].tool_calls[*].id}   # Chained wildcards over nested arrays
```

`[*]` only picks fields — it does not restructure elements. To build new objects per element, use [object array projection](#1442-object-array-projection) or [map expressions](#149-map-expressions).

---

## 14.4 Type Conversion

Type conversion transforms variable values into specific data types using the `as` keyword.

### 14.4.1 Primitive Types

| Type | Description | Example |
|------|-------------|---------|
| `text` | Convert to string | `${input.message as text}` |
| `number` | Convert to float | `${input.price as number}` |
| `integer` | Convert to integer | `${input.count as integer}` |
| `boolean` | Convert to boolean (`"true"`, `"1"` → true) | `${input.enabled as boolean}` |
| `json` | Parse JSON string to object | `${input.data as json}` |

### 14.4.2 Object Array Projection

Extract specific fields from an array of objects using `subtype` as comma-separated field paths.

```yaml
# Extract specific fields from object array
${response.users as object[]/id,name}
# Result: [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

# Nested path support (last segment becomes the key name)
${response.data as object[]/user.id,user.email,status}
# Result: [{"id": 1, "email": "john@example.com", "status": "active"}, ...]
```

### 14.4.3 Media Types

| Type | Subtype | Format | Example |
|------|---------|--------|---------|
| `image` | `png`, `jpg`, `webp` | `base64`, `url`, `path` | `${input.photo as image/jpg}` |
| `audio` | `mp3`, `wav`, `ogg`, `pcm` | `base64`, `url`, `path` | `${output as audio/mp3;base64}` |
| `video` | `mp4`, `webm` | `base64`, `url`, `path` | `${result as video/mp4}` |
| `file` | any | `base64`, `url`, `path` | `${input.document as file}` |

### 14.4.4 Attributes

Attributes provide additional key-value parameters using bracket syntax: `type/subtype[key=value,...]`. They are passed as a dictionary alongside type and subtype, allowing extra context for type conversion and downstream processing.

```yaml
# PCM audio with encoding parameters
${response[] as audio/pcm[sample_rate=24000,channels=1,bit_depth=16]}
```

### 14.4.5 Base64 Type vs Base64 Format

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

## 14.5 Format and Context Semantics

Format specifiers describe the **encoding state** of the data. The same `as type;format` syntax behaves differently depending on where it is used.

### 14.5.1 Format Values

| Format | Description | Example |
|--------|-------------|---------|
| `base64` | Data is base64 encoded | `${input.photo as image;base64}` |
| `url` | Data is a URL to be fetched | `${input.avatar as image;url}` |
| `path` | Data is a file path | `${output.path as audio;path}` |
| `stream` | Data is a stream | `${output as audio;stream}` |

> **Note:** `stream/text` and `stream/json` are **types**, not formats. Use `${output as stream/text}` or `${output as stream/json}` to convert a value to an SSE stream.

### 14.5.2 Input Context

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

### 14.5.3 Component/Job Output Context

In component/job action `output`, media file conversion is **not performed**. The value is passed through with only basic type conversion (e.g., `integer`, `json`, `base64` encoding). The format is preserved as metadata for downstream consumers.

| Type | Format | What Happens |
|------|--------|--------------|
| `image` | `base64` | Value passed through as-is (no decoding) |
| `audio` | `path` | File object rendered to its file path |
| `stream/text` | (none) | Wraps value as SSE text stream |
| `stream/json` | (none) | Wraps value as SSE JSON stream |
| `base64` | (any) | Value encoded to base64 string (always performed) |

```yaml
# "tell consumers this is a base64-encoded image"
output: ${result as image;base64}
```

### 14.5.4 Workflow Output Context

Workflow output variables define `type` and `format` in the workflow schema. These are consumed by **controller adapters** to determine how to display and transmit the data:

| Consumer | Format | Behavior |
|----------|--------|----------|
| **Web UI** | `stream/text` | Accumulate text chunks incrementally |
| **Web UI** | `stream/json` | Parse each chunk as JSON, extract field via `subtype` path |
| **Web UI** | `base64` | Decode base64 to display image/audio |
| **Web UI** | `url` | Fetch URL to display image/audio |
| **Web UI** | `path` | Use file path directly |
| **HTTP API** | (any) | Format is not used; transmission is determined by the output data type |

```yaml
# Web UI accumulates text chunks; HTTP API sends as SSE
workflow:
  output: ${output as stream/text}
```

---

## 14.6 Default Values

Default values provide fallback data when a variable is missing or null. Using the pipe (`|`) operator, you can specify literal values or reference environment variables.

### 14.6.1 Literal Default Values

```yaml
${input.temperature | 0.7}             # Number
${input.model | "gpt-4o"}              # String
${input.enabled | true}                # Boolean
```

### 14.6.2 Environment Variable Default Values

```yaml
${input.channel | ${env.DEFAULT_CHANNEL}}     # Use environment variable as default
${input.api_key | ${env.API_KEY}}             # Use environment variable as default
```

### 14.6.3 Nested Default Values (Environment Variable + Literal)

```yaml
${input.api_key | ${env.API_KEY | "default-key"}}
```

---

## 14.7 Metadata and UI Hints

### 14.7.1 Annotations

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

### 14.7.2 Select (Dropdown)

```yaml
${input.voice as select/alloy,echo,fable,onyx,nova,shimmer}
${input.model as select/gpt-4o,gpt-4o-mini,o1-mini}
${input.size as select/256x256,512x512,1024x1024 | 1024x1024}
```

### 14.7.3 Slider

```yaml
${input.temperature as slider/0,2,0.1 | 0.7}
# Format: slider/min,max,step | default
```

### 14.7.4 Textarea

```yaml
${input.prompt as text}
# Web UI renders text type as a textarea widget
```

---

## 14.8 Spread Operators

Spread operators inline the contents of one value into a surrounding dict or list. Two forms are supported.

### 14.8.1 Dict Spread (`"..."`)

Inside a dict, the key `"..."` merges the fields of the referenced dict into the surrounding one. Explicit sibling keys override the spread fields.

```yaml
body:
  "...": ${input}          # Copy every field of input into body
  model: gpt-4o            # Override / add a specific field
```

The spread value must resolve to a dict (or `null`, which is ignored).

### 14.8.2 List Spread (`...${x}`)

Inside a list, a string item of the form `...${source}` is expanded so that every element of the referenced list is appended to the surrounding list.

```yaml
messages:
  - role: system
    content: You are a helpful assistant.
  - ...${input.history}    # Append every previous message
  - role: user
    content: ${input.prompt}
```

The spread value must resolve to a list (or `null`, which is ignored).

---

## 14.9 Map Expressions

A map expression transforms every element of a source list into a new value. Use a dict whose `"*"` key holds the source list; the remaining fields form the template applied to each element. Within the template, the current element is referenced as `${item}`.

### 14.9.1 Basic Map

```yaml
tools:
  "*": ${tools}
  type: function
  function: ${item}
# Result: [{type: "function", function: <tool0>}, {type: "function", function: <tool1>}, ...]
```

### 14.9.2 Map with Spread

Combine a map with a dict spread to preserve original fields and override only what changes.

```yaml
messages:
  "*": ${messages}
  "...": ${item}                  # Keep original fields
  tool_calls:                     # Override tool_calls with a nested map
    "*": ${item.tool_calls}
    id: ${item.id}
    type: function
    function:
      name: ${item.name}
      arguments: ${item.arguments}
```

### 14.9.3 Nested Maps and `${item}` Scope

Maps may be nested. `${item}` always refers to the element of the **innermost** enclosing map. When the inner map ends, `${item}` reverts to the outer element.

```yaml
"*": ${orders}                    # outer: item = an order
customer: ${item.customer}
lines:
  "*": ${item.lines}              # inner: item = a line of that order
  sku: ${item.sku}
  qty: ${item.qty}
```

### 14.9.4 Identity Map

If the template is empty, the source list is returned as-is. This is rarely useful but not an error.

```yaml
messages:
  "*": ${messages}
# Result: ${messages} (unchanged)
```

### 14.9.5 Map vs Object Array Projection

Both restructure a list of dicts, but they solve different problems:

| Feature | `as object[]/...` ([14.4.2](#1442-object-array-projection)) | Map (`"*"`) |
|---------|------------------------------------------------------------|-------------|
| Location | Inside a `${...}` expression | YAML dict layout |
| Semantics | Pick fields from each element | Build a new element per template |
| Constants / wrappers | ✗ | ✓ (any literal or nested structure) |
| Nested transformation | ✗ | ✓ (maps within maps) |

Use `object[]/` for simple field picking. Use map expressions when you need to add constants, wrap elements, or perform nested transformations.

> **`${item}` is a reserved source name.** Inside a map template it always refers to the current element; outside a map it resolves normally (e.g., the `item` source registered by a `for-each` job).

---

## 14.10 Practical Examples

### 14.10.1 OpenAI API Call

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

### 14.10.2 Image Processing Pipeline

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

### 14.10.3 Streaming Response

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

### 14.10.4 Vector Search Result Format

```yaml
component:
  type: vector-store
  action: search
  output: ${response as object[]/id,score,metadata.text}
# Result: [{"id": "1", "score": 0.95, "text": "..."}, ...]
```

### 14.10.5 Conditional Default Values

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

**Next Chapter**: [15. System Integration](./15-system-integration.md)
