# 12. Variable Binding

This chapter provides a detailed explanation of model-compose's variable binding syntax. Variable binding is a core feature that uses the `${...}` syntax to reference and transform data.

---

## 12.1 Basic Syntax

Variable binding uses the `${...}` syntax to reference and transform data.

**Basic Structure**:
```
${key.path as type/subtype;format | default @(annotation)}
```

---

## 12.2 Key References

### 12.2.1 Single Value Reference

```yaml
${input}                    # Entire input object
${input.field}              # field property of input
${input.user.email}         # Nested path
${response.data[0].id}      # Array index
```

### 12.2.2 Streaming Reference (Per-Chunk)

```yaml
${result[]}                 # Model streaming chunks
${response[]}               # HTTP streaming chunks
${result[0]}                # Specific index chunk
```

### 12.2.3 Job Result Reference

```yaml
${jobs.job-id.output}           # Specific job output
${jobs.job-id.output.field}     # Specific field of job output
```

### 12.2.4 Environment Variables

```yaml
${env.OPENAI_API_KEY}       # Environment variable
${env.PORT | 8080}          # With default value
```

---

## 12.3 Type Conversion

### 12.3.1 Basic Types

| Type | Description | Example |
|------|-------------|---------|
| `text` | Convert to string | `${input.message as text}` |
| `number` | Convert to float | `${input.price as number}` |
| `integer` | Convert to integer | `${input.count as integer}` |
| `boolean` | Convert to boolean | `${input.enabled as boolean}` |
| `json` | Parse JSON | `${input.data as json}` |

### 12.3.2 Object Array Conversion

```yaml
# Extract specific fields from object array
${response.users as object[]/id,name}
# Result: [{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}]

# Nested path support
${response.data as object[]/user.id,user.email,status}
# Result: [{"id": 1, "email": "john@example.com", "status": "active"}, ...]
```

### 12.3.3 Media Types

| Type | Subtype | Format | Example |
|------|---------|--------|---------|
| `image` | `png`, `jpg`, `webp` | `base64`, `url`, `path` | `${input.photo as image/jpg}` |
| `audio` | `mp3`, `wav`, `ogg` | `base64`, `url`, `path` | `${output as audio/mp3;base64}` |
| `video` | `mp4`, `webm` | `base64`, `url`, `path` | `${result as video/mp4}` |
| `file` | any | `base64`, `url`, `path` | `${input.document as file}` |

### 12.3.4 Base64 Encoding

```yaml
${output as base64}                      # Encode binary data to Base64
```

### 12.3.5 Base64 Decoding

```yaml
${output as audio/mp3;base64}           # Decode Base64 string to audio
${output as image/png;base64}           # Decode Base64 string to image
```

---

## 12.4 Output Format

### 12.4.1 SSE (Server-Sent Events) Streaming

```yaml
# Text stream
output: ${output as text;sse-text}

# JSON stream
output: ${output as text;sse-json}
```

### 12.4.2 Gradio UI Specific

```yaml
# Gradio automatically selects UI component
${input.photo as image}      # Image upload widget
${output as audio}           # Audio player
${result as text}            # Textbox
```

---

## 12.5 Default Values

### 12.5.1 Literal Default Values

```yaml
${input.temperature | 0.7}             # Number
${input.model | "gpt-4o"}              # String
${input.enabled | true}                # Boolean
```

### 12.5.2 Environment Variable Default Values

```yaml
${input.channel | ${env.DEFAULT_CHANNEL}}     # Use environment variable as default
${input.api_key | ${env.API_KEY}}             # Use environment variable as default
```

### 12.5.3 Nested Default Values (Environment Variable + Literal)

```yaml
${input.api_key | ${env.API_KEY | "default-key"}}
```

---

## 12.6 Annotations

Used to provide parameter descriptions in MCP servers.

### 12.6.1 Basic Annotation

```yaml
${input.channel @(description Slack channel ID)}
${input.limit as integer | 10 @(description Maximum number of results)}
```

### 12.6.2 Complex Example

```yaml
input:
  prompt: ${input.prompt as text @(description The text prompt for generation)}
  temperature: ${input.temperature as number | 0.7 @(description Controls randomness (0-2))}
  max_tokens: ${input.max_tokens as integer | 100 @(description Maximum tokens to generate)}
```

---

## 12.7 UI Type Hints

Specifies input widget types for Gradio Web UI.

### 12.7.1 Select (Dropdown)

```yaml
${input.voice as select/alloy,echo,fable,onyx,nova,shimmer}
${input.model as select/gpt-4o,gpt-4o-mini,o1-mini}
${input.size as select/256x256,512x512,1024x1024 | 1024x1024}
```

### 12.7.2 Slider

```yaml
${input.temperature as slider/0,2,0.1 | 0.7}
# Format: slider/min,max,step | default
```

### 12.7.3 Textarea

```yaml
${input.prompt as text}
# UI hint not included in type (Gradio auto-detects)
```

---

## 12.8 Practical Examples

### 12.8.1 OpenAI API Call

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

### 12.8.2 Image Processing Pipeline

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

### 12.8.3 Streaming Response

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

### 12.8.4 Vector Search Result Format

```yaml
component:
  type: vector-store
  action: search
  output: ${response as object[]/id,score,metadata.text}
# Result: [{"id": "1", "score": 0.95, "text": "..."}, ...]
```

### 12.8.5 Conditional Default Values

```yaml
component:
  type: http-client
  headers:
    Authorization: Bearer ${input.api_key | ${env.OPENAI_API_KEY}}
  body:
    model: ${input.model | ${env.DEFAULT_MODEL | "gpt-4o"}}
```

---

## Next Steps

Try these exercises:
- Write various type conversion expressions
- Use nested default values with environment variables
- Improve Gradio interface with UI type hints
- Experiment with streaming output formats

---

**Next Chapter**: [13. System Integration](./13-system-integration.md)
