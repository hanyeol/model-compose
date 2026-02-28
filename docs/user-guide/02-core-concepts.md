# Chapter 2: Core Concepts

This chapter provides an in-depth look at model-compose's core concepts and the structure of the `model-compose.yml` configuration file.

---

## 2.1 model-compose.yml Structure

`model-compose.yml` is the central configuration file for model-compose. This file declaratively defines all aspects of your AI workflows.

### Basic Structure

```yaml
controller:
  # Defines how workflows are hosted and executed
  type: http-server
  port: 8080

components:
  # Defines executable modules
  - id: my-component
    type: http-client

workflows:
  # Defines workflow pipelines
  - id: my-workflow
    jobs:
      - component: my-component

listeners:
  # Defines event listeners (optional)

gateways:
  # Defines HTTP tunneling services (optional)
```

### Main Sections

1. **controller** (required): Workflow execution environment configuration
2. **components** (optional): Executable module definitions
3. **workflows** (optional): Workflow pipeline definitions
4. **listeners** (optional): Event listener definitions
5. **gateways** (optional): Tunneling service definitions

### Configuration File Priority

You can use multiple configuration files, with later files overriding earlier ones:

```bash
model-compose -f base.yml -f override.yml up
```

---

## 2.2 Controller

The **controller** is the runtime environment that hosts and executes workflows.

### Controller Types

#### HTTP Server

Exposes workflows as REST API endpoints.

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio  # or static
    port: 8081
```

**Main Settings:**
- `port`: HTTP server port (default: 8080)
- `base_path`: Base path for API endpoints (default: /api)
- `webui`: Optional Web UI configuration
  - `driver`: `gradio` or `static`
  - `port`: Web UI port

**API Endpoints:**
- `POST /api/workflows/runs` - Execute workflow

#### MCP Server

Exposes workflows through Model Context Protocol.

```yaml
controller:
  type: mcp-server
  port: 8080
  base_path: /mcp
```

**Main Settings:**
- `port`: MCP server port (default: 8080)
- `base_path`: Base path for MCP endpoints

**Transport Method:**
> **Note**: Currently only SSE (Server-Sent Events) transport is supported.
>
> SSE is an HTTP-based protocol that provides unidirectional real-time data streaming from server to client. This means:
> - MCP clients must connect to the server via HTTP connections
> - stdio transport (standard input/output) is not yet supported
> - When using with MCP clients like Claude Desktop, the `@modelcontextprotocol/server-stdio` adapter is required
>
> **Practical Example**:
> ```json
> // Claude Desktop configuration (claude_desktop_config.json)
> {
>   "mcpServers": {
>     "my-workflow": {
>       "command": "npx",
>       "args": ["-y", "@modelcontextprotocol/server-stdio", "http://localhost:8080/mcp"]
>     }
>   }
> }
> ```

### Runtime Configuration

```yaml
controller:
  type: http-server
  port: 8080
  runtime:
    type: native  # or docker
  max_concurrent_count: 10  # Concurrent execution limit
```

**Runtime Types:**
- `native`: Execute directly in current environment
- `docker`: Execute in Docker container

---

## 2.3 Components

**Components** are reusable building blocks that define one or more actions. Each component groups actions for a specific service or functionality.

### Single Action Component

The simplest form, where a component defines only one action using `action:` (singular):

```yaml
components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
        Content-Type: application/json
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
      output:
        response: ${response.choices[0].message.content}
```

### Multiple Actions Component

You can define multiple actions in a single component:

```yaml
components:
  - id: slack-api
    type: http-client
    base_url: https://slack.com/api
    headers:
      Authorization: Bearer ${env.SLACK_TOKEN}
    actions:
      - id: send-message
        path: /chat.postMessage
        method: POST
        body:
          channel: ${input.channel}
          text: ${input.text}
        output: ${response}

      - id: list-channels
        path: /conversations.list
        method: GET
        output: ${response.channels}
```

In workflows, use `component.action` format to execute a specific action:

```yaml
workflow:
  jobs:
    - id: send
      component: slack-api
      action: send-message
      input:
        channel: "#general"
        text: "Hello!"
```

### Main Component Types

#### 1. HTTP Client

Calls external APIs.

```yaml
- id: api-call
  type: http-client
  action:
    endpoint: https://api.example.com/v1/endpoint
    method: POST
    headers:
      Authorization: Bearer ${env.API_KEY}
    body:
      data: ${input.data}
    output:
      result: ${response.result}
```

#### 2. Model

Runs local AI models.

```yaml
- id: local-llm
  type: model
  source: huggingface
  model_id: meta-llama/Llama-3.2-3B-Instruct
  task: chat-completion
  device: cuda
  input:
    messages: ${input.messages}
  output:
    response: ${output.content}
```

#### 3. Shell

Executes shell commands.

```yaml
- id: run-script
  type: shell
  command: python process.py
  args:
    - ${input.file_path}
  output:
    result: ${stdout}
```

#### 4. Workflow

Calls another workflow as a component.

```yaml
- id: sub-workflow
  type: workflow
  workflow_id: preprocessing
  input: ${input}
  output: ${output}
```

### Input/Output Mapping

Components receive input and generate output:

```yaml
- id: translator
  type: http-client
  action:
    endpoint: https://api.translate.com/v1/translate
    body:
      text: ${input.text}      # From input
      target: ${input.language} # From input
    output:
      translated: ${response.translation}  # Extract to output
```

---

## 2.4 Workflows

**Workflows** are named sequences of jobs that define complete AI pipelines.

### Basic Workflow

```yaml
workflows:
  - id: generate-text
    title: Text Generation
    description: Generate text using GPT-4o
    default: true
    jobs:
      - id: generate
        component: chatgpt
        input:
          prompt: ${input.prompt}
        output:
          result: ${output.response}
```

### Workflow Properties

- `id` (required): Unique workflow identifier
- `title`: Human-readable title
- `description`: Workflow description
- `default`: Set as default workflow (true/false)
- `jobs`: List of jobs to execute

### Simplified Workflow

For single workflows, use `workflow` (singular object) instead of `workflows` (plural array):

```yaml
# Explicit form (workflows)
workflows:
  - id: chat
    title: Chat with GPT
    jobs:
      - component: chatgpt

# Simplified form (workflow)
workflow:
  title: Chat with GPT
  component: chatgpt  # Single component workflow
```

---

## 2.5 Jobs

**Jobs** are individual steps within a workflow.

### Job Definition

```yaml
jobs:
  - id: step1
    component: chatgpt
    input:
      prompt: ${input.query}
    output:
      answer: ${output.response}
```

### Job Properties

- `id`: Unique job identifier (used to reference by other jobs)
- `component`: Component ID to execute
- `input`: Input mapping to pass to component
- `output`: Map component output to workflow output
- `depends_on`: Define dependencies (jobs that must complete before this one)

### Data Passing Between Jobs

```yaml
jobs:
  - id: generate-quote
    component: quote-generator
    input:
      topic: ${input.topic}
    output:
      quote: ${output.text}

  - id: convert-to-speech
    component: text-to-speech
    input:
      text: ${jobs.generate-quote.output.quote}  # Use previous job's output
    output:
      audio: ${output as audio/mp3;base64}
    depends_on: [ generate-quote ]  # Explicit dependency
```

### Job Execution Order

By default, jobs execute sequentially:

```yaml
jobs:
  - id: step1      # Executes 1st
    component: comp1

  - id: step2      # Executes 2nd (after step1)
    component: comp2
    depends_on: [ step1 ]

  - id: step3      # Executes 3rd (after step2)
    component: comp3
    depends_on: [ step2 ]
```

Parallel execution is possible (when no dependencies):

```yaml
jobs:
  - id: parallel1
    component: comp1

  - id: parallel2  # Can run in parallel with parallel1
    component: comp2

  - id: final      # Runs after both parallel1 and parallel2 complete
    component: comp3
    depends_on: [ parallel1, parallel2 ]
```

---

## 2.6 Data Flow and Variable Binding

**Variable binding** uses the `${...}` syntax to connect data between workflow steps. You can reference environment variables, user input, component outputs, and previous job results, with support for type conversion, default values, and format specification. This enables you to build complex data pipelines declaratively without writing code.

### Variable Sources

#### 1. Environment Variables

```yaml
${env.VARIABLE_NAME}
```

Example:
```yaml
headers:
  Authorization: Bearer ${env.OPENAI_API_KEY}
```

#### 2. Workflow Input

```yaml
${input.field}
```

Example:
```yaml
body:
  prompt: ${input.user_question}
  temperature: ${input.temperature | 0.7}  # Default 0.7
```

#### 3. Component Response

**Important**: Response variables differ by component type.

```yaml
${response.field}   # HTTP-based components (http-client, http-server, vector-store, etc.)
${result.field}     # Local execution components (model, datasets, text-splitter, etc.)
${stdout}           # Shell commands (shell)
${output}           # Workflow invocation (workflow)
```

Examples:
```yaml
# HTTP client
output:
  message: ${response.choices[0].message.content}
  tokens: ${response.usage.total_tokens}

# Local model
output:
  generated_text: ${result}

# Shell command
output:
  command_output: ${stdout}
```

> 💡 **Detailed Variable Reference**: See [12.2.2 Component Response Variable Sources](./12-variable-binding.md#1222-component-response-variable-sources) for a complete list of variable sources for all component types.

#### 4. Previous Job Output

```yaml
${jobs.job-id.output.field}
```

Example:
```yaml
input:
  text: ${jobs.generate-text.output.content}
  language: ${jobs.detect-language.output.lang}
```

### Variable Transformations

#### Type Casting

```yaml
${input.value as number}     # Convert to number
${input.value as text}       # Convert to text
${input.value as boolean}    # Convert to boolean
```

#### Base64 Encoding

```yaml
${output as base64}                      # Encode to Base64
```

#### Base64 Decoding

```yaml
${output as audio/mp3;base64}           # Decode Base64 to audio
${output as image/png;base64}           # Decode Base64 to image
```

#### Default Values

```yaml
${input.temperature | 0.7}               # Use 0.7 if input.temperature is missing
${env.PORT | 8080}                       # Use 8080 if PORT env var is missing
${input.model | gpt-4o}                  # Specify default model
```

### Complete Data Flow Example

```yaml
controller:
  type: http-server
  port: 8080

components:
  - id: generate-quote
    type: http-client
    action:
      endpoint: https://api.openai.com/v1/chat/completions
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
        Content-Type: application/json
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.topic}
      output:
        quote: ${response.choices[0].message.content}

  - id: text-to-speech
    type: http-client
    action:
      endpoint: https://api.elevenlabs.io/v1/text-to-speech/${input.voice_id}?output_format=mp3_44100_128
      headers:
        xi-api-key: ${env.ELEVENLABS_API_KEY}
        Content-Type: application/json
      body:
        text: ${input.text}
        model_id: eleven_multilingual_v2
      output: ${response as base64}

workflow:
  title: Quote to Voice
  jobs:
    - id: create-quote
      component: generate-quote
      input:
        topic: ${input.topic}
      output:
        text: ${output.quote}

    - id: create-voice
      component: text-to-speech
      input:
        text: ${jobs.create-quote.output.text}
        voice_id: ${input.voice_id | JBFqnCBsd6RMkjVDRZzb}
      output:
        quote: ${jobs.create-quote.output.text}
        audio: ${output}
      depends_on: [create-quote]
```

**Data Flow:**
1. User provides `topic` and `voice_id` input
2. `create-quote` job:
   - Pass `${input.topic}` to GPT-4o
   - Extract quote to `${output.quote}`
3. `create-voice` job:
   - Get quote from previous job via `${jobs.create-quote.output.text}`
   - Get voice ID from `${input.voice_id}` (or use default)
   - Pass to TTS API to generate MP3 audio
   - Encode audio to Base64 and return

---

## 2.7 Components vs Jobs

In model-compose, **Components** and **Jobs** serve different purposes. Understanding this distinction is key to designing effective workflows.

### Component

A **component** is a **reusable functional definition**.

- **Definition**: Declared in the `components` section
- **Role**: Defines how to access a specific service or functionality (e.g., API calls, model execution)
- **Reusability**: Can be reused across multiple workflows and jobs
- **Execution**: Components themselves don't execute; they are executed through jobs
- **Distributed Deployment**: Components can be deployed to remote servers to build distributed environments

```yaml
components:
  - id: gpt4o
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
```

### Job

A **job** is an **actual execution instance of a component within a workflow**.

- **Definition**: Declared in the `workflow.jobs` section
- **Role**: Executes a component, passes input data, and collects output
- **Execution Order**: Defines execution sequence with other jobs via `depends_on`
- **Data Flow**: Passes results from previous jobs as input to subsequent jobs

```yaml
workflow:
  jobs:
    - id: generate-text
      component: gpt4o
      input:
        prompt: "Write a haiku"
      output: ${output}

    - id: analyze-sentiment
      component: gpt4o
      input:
        prompt: "Analyze sentiment: ${jobs.generate-text.output}"
      depends_on: [generate-text]
```

### Key Differences Summary

| Aspect | Component | Job |
|--------|-----------|-----|
| **Definition Location** | `components` section | `workflow.jobs` section |
| **Role** | Functional definition (template) | Execution instance |
| **Reusability** | Reusable across workflows | Bound to specific workflow |
| **Execution** | Cannot execute directly | Executes when workflow runs |
| **Data** | Defines input/output schema | Handles actual data passing |
| **Dependencies** | None | Uses `depends_on` for job ordering |

### Practical Example

```yaml
# Component definition: How to call OpenAI API
components:
  - id: openai-chat
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
      output:
        text: ${response.choices[0].message.content}

# Workflow: Reuse the same component in multiple jobs
workflows:
  - id: content-pipeline
    jobs:
      # Job 1: Generate title
      - id: generate-title
        component: openai-chat
        input:
          prompt: "Create a catchy title for a blog about AI"
        output: ${output}

      # Job 2: Generate body (uses title)
      - id: generate-body
        component: openai-chat
        input:
          prompt: "Write a blog post with this title: ${jobs.generate-title.output.text}"
        depends_on: [generate-title]
        output: ${output}

      # Job 3: Generate summary (uses body)
      - id: generate-summary
        component: openai-chat
        input:
          prompt: "Summarize this text: ${jobs.generate-body.output.text}"
        depends_on: [generate-body]
        output: ${output}
```

In this example:
- **Component** `openai-chat`: Defines OpenAI API calling method once
- **Jobs** (`generate-title`, `generate-body`, `generate-summary`): Execute the same component three times with different prompts and data

---

## Next Steps

Try it out:
- Build workflows with multiple jobs
- Experiment with various variable binding patterns
- Explore component reusability patterns

---

**Next Chapter**: [3. CLI Usage](./03-cli-usage.md)
