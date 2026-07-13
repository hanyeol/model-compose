# Chapter 6: Workflow Schema

This chapter explains how model-compose automatically generates workflow schemas that describe the input and output variables of each workflow. You'll learn how to retrieve schemas via the API and how to leverage them for client integration, Web UI rendering, and MCP tool mapping.

---

## 6.1 What is a Workflow Schema?

A **Workflow Schema** is a metadata structure that model-compose automatically infers from your workflow configuration. It describes:

- **Input Variables**: What data the workflow expects when invoked
- **Output Variables**: What data the workflow produces upon completion

The schema is derived by analyzing the variable binding expressions (`${input.field as type}`) in your workflow's job definitions. You don't need to write the schema manually — model-compose generates it for you.

### Why Schemas Matter

| Use Case | How Schema is Used |
|----------|-------------------|
| Web UI | Automatically generates input forms (text fields, file uploads, dropdowns) |
| MCP Server | Maps workflow inputs to tool parameters |
| REST API Clients | Provides type information for request/response validation |
| Documentation | Self-describing API contracts |

---

## 6.2 Retrieving the Schema

### Single Workflow Schema

```
GET /workflows/{workflow_id}/schema
```

**Example:**
```bash
curl http://localhost:8080/workflows/my-workflow/schema
```

**Response:**
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

### All Workflow Schemas

```
GET /workflows?include_schema=true
```

Returns an array of schema objects for all public workflows.

### Workflow List (Without Schema)

```
GET /workflows
```

Returns a simplified list with only `workflow_id`, `title`, and `default` fields.

---

## 6.3 Input Schema

The input schema describes the variables that must be provided when executing a workflow.

### Variable Structure

Each input variable has the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Variable name (derived from `${input.name}`) |
| `type` | string | Data type of the variable |
| `subtype` | string? | Subtype qualifier (e.g., `pcm` for audio) |
| `format` | string? | Transfer format (`base64`, `url`, `path`, `stream`) |
| `default` | any? | Default value if not provided |

### Supported Types

**Primitive Types:**

| Type | Description | Example Use |
|------|-------------|-------------|
| `string` | Short text string | Names, IDs, labels |
| `text` | Long text (multi-line) | Prompts, documents |
| `integer` | Whole number | Counts, indices |
| `number` | Floating-point number | Temperature, scores |
| `boolean` | True/false | Feature flags |
| `list` | Array of values | Tags, keywords |
| `object` | Structured object | Nested records |
| `json` | Arbitrary JSON object | Complex structured data |

Any primitive can be marked as a list by appending `[]` to the type (e.g. `string[]`, `object[]`). Internally this sets the variable's `is_list` flag.

**Encoded Types:**

| Type | Description |
|------|-------------|
| `base64` | Base64-encoded binary data |
| `markdown` | Markdown-formatted text |

**Media Types:**

| Type | Description |
|------|-------------|
| `image` | Image file (PNG, JPEG, etc.) |
| `audio` | Audio file (WAV, MP3, etc.) |
| `video` | Video file (MP4, etc.) |
| `file` | Generic file |

**Streaming Types:**

| Type | Description |
|------|-------------|
| `stream/text` | Server-Sent Events (text chunks) |
| `stream/json` | Server-Sent Events (JSON chunks) |

**UI Types:**

| Type | Description |
|------|-------------|
| `select` | Dropdown selection (options defined via subtype) |

### Format Values

The `format` field specifies how data is transferred:

| Format | Description |
|--------|-------------|
| `base64` | Data is base64-encoded in the request body |
| `data-uri` | Data is embedded as a data URI (e.g. `data:image/png;base64,...`) |
| `url` | Data is referenced by URL |
| `path` | Data is referenced by file path |

### How Input Schema is Inferred

model-compose analyzes variable binding expressions in job `input` fields:

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

This produces the following input schema:

```json
{
  "input": [
    { "name": "prompt", "type": "text" },
    { "name": "photo", "type": "image", "format": "base64" },
    { "name": "count", "type": "integer", "default": 5 }
  ]
}
```

**Inference rules:**
- `${input.name}` → type defaults to `string`
- `${input.name as type}` → uses the specified type
- `${input.name as type;format}` → includes format
- `${input.name as type | default}` → includes default value

---

## 6.4 Output Schema

The output schema describes the data returned when the workflow completes.

- If the workflow declares an explicit `output` mapping, the schema is derived **directly from that mapping**.
- Otherwise, it is inferred from the **terminal jobs** — jobs that no other job depends on.

### Workflow-Level Output

When you define `output` on the workflow itself, the schema reflects exactly the variables in that mapping:

```yaml
workflows:
  - id: summarize
    jobs:
      - id: generate
        component: gpt4o
        input:
          prompt: ${input.text as text}

    output:
      summary: ${jobs.generate.output.text as markdown}
      tokens: ${jobs.generate.output.usage.total_tokens as integer}
```

Produces:

```json
{
  "output": [
    { "name": "summary", "type": "markdown" },
    { "name": "tokens", "type": "integer" }
  ]
}
```

### Basic Output

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

Produces:

```json
{
  "output": [
    { "name": "summary", "type": "markdown" }
  ]
}
```

### Multiple Output Variables

```yaml
output:
  text: ${output.content}
  confidence: ${output.score as number}
```

Produces:

```json
{
  "output": [
    { "name": "text", "type": "string" },
    { "name": "confidence", "type": "number" }
  ]
}
```

### Grouped Output (repeat_count)

When a component job uses `repeat_count > 1`, the output variables are wrapped in a group:

```yaml
jobs:
  - id: generate
    component: gpt4o
    repeat_count: 3
    input:
      prompt: ${input.prompt}
    output: ${output as text}
```

Produces:

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

This tells the client that the output will contain 3 iterations of the variable group.

---

## 6.5 Schema in Practice

### Web UI Form Generation

When `webui` is enabled, model-compose uses the input schema to automatically generate form controls:

| Variable Type | UI Control |
|--------------|------------|
| `string` | Text input |
| `text` | Textarea |
| `integer` / `number` | Number input (with slider if annotated) |
| `boolean` | Checkbox |
| `image` | File upload (image) |
| `audio` | File upload (audio) |
| `file` | File upload |
| `select` | Dropdown |

### MCP Server Tool Mapping

When the controller type is `mcp-server`, workflow input variables become tool parameters:

```yaml
controller:
  adapter:
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

This registers an MCP tool `translate` with parameters:
- `text` (string, required)
- `target_lang` (enum: en, ko, ja, zh)

### Client SDK Integration

Use the schema endpoint to dynamically build request payloads:

```python
import requests

# Get schema
schema = requests.get("http://localhost:8080/workflows/my-workflow/schema").json()

# Build input from schema
payload = {}
for var in schema["input"]:
    if var.get("default") is not None:
        payload[var["name"]] = var["default"]
    else:
        payload[var["name"]] = get_user_input(var["name"], var["type"])

# Execute workflow
result = requests.post(
    "http://localhost:8080/workflows/runs",
    json={"workflow_id": "my-workflow", "input": payload}
).json()
```

---

## 6.6 Practical Examples

### Example 1: Text Chat Workflow

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

**Generated Schema:**
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

### Example 2: Image Analysis Workflow

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

**Generated Schema:**
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

### Example 3: Streaming Workflow

```yaml
workflows:
  - id: stream-chat
    title: Streaming Chat
    jobs:
      - id: generate
        component: gpt4o-stream
        input:
          prompt: ${input.prompt as text}
        output: ${output as stream/text}
```

**Generated Schema:**
```json
{
  "workflow_id": "stream-chat",
  "title": "Streaming Chat",
  "input": [
    { "name": "prompt", "type": "text" }
  ],
  "output": [
    { "name": null, "type": "stream/text" }
  ]
}
```

The `stream/text` output type indicates the client should expect a streaming response via Server-Sent Events.

---

## 6.7 Workflow Metadata Fields

Beyond input/output variables, the schema includes workflow-level metadata:

| Field | Type | Description |
|-------|------|-------------|
| `workflow_id` | string | Unique identifier |
| `title` | string? | Human-readable title (displayed in Web UI) |
| `description` | string? | Detailed description of the workflow |
| `default` | boolean | Whether this is the default workflow |

### Private Workflows

Workflows marked with `private: true` are excluded from the schema API:

```yaml
workflows:
  - id: internal-helper
    private: true
    jobs:
      - id: task
        component: helper
```

Private workflows cannot be accessed via `GET /workflows` or `GET /workflows/{id}/schema`.

---

## 6.8 Best Practices

1. **Always specify types** — Use `${input.field as type}` instead of bare `${input.field}` to generate accurate schemas.

2. **Provide defaults** — Use `${input.field as type | default}` for optional parameters so clients know what values to use.

3. **Use descriptive titles** — Set `title` on workflows so the Web UI and MCP tools have meaningful names.

4. **Keep schemas stable** — Changing input variable names or types is a breaking change for clients. Add new variables with defaults instead.

5. **Use private for internal workflows** — Mark helper/sub-workflows as `private: true` to keep the public schema clean.

---

> **Next Chapter**: [Chapter 7: Controller Configuration](./07-controller-configuration.md) — Learn how to configure HTTP servers, MCP servers, and other controller types.
