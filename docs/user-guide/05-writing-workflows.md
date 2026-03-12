# Chapter 5: Writing Workflows

This chapter covers how to write workflows in model-compose. From single-job workflows to complex multi-step pipelines, you'll learn about data passing between jobs, conditional execution, streaming mode, and error handling.

## 5.1 What is a Workflow?

A **Workflow** is an execution unit that combines one or more jobs to form a complete execution pipeline. When writing a workflow, you need to define three core elements:

### 1. Job Definitions
Each job specifies the component to execute and the input to pass to that component.

```yaml
jobs:
  - id: my-task
    component: my-component
    input:
      field: ${input.value}
```

### 2. Job Dependencies
Use the `depends_on` field to explicitly define the execution order between jobs. This allows you to create sequential execution, parallel execution, or complex execution graphs.

```yaml
jobs:
  - id: task1
    component: component1

  - id: task2
    component: component2
    depends_on: [task1]  # Executes after task1 completes
```

### 3. Input/Output Definitions
- **input**: Maps workflow input or previous job outputs to the current job's input
- **output**: Uses the job's result as workflow output or as input for subsequent jobs

Each job's output is stored in `${jobs.job_id.output}` and can be referenced as input by subsequent jobs.

```yaml
jobs:
  - id: task1
    component: component1
    input:
      data: ${input.user_data}     # Use workflow input
    output:
      result: ${output.processed}
    # Output is stored in jobs.task1.output

  - id: task2
    component: component2
    input:
      data: ${jobs.task1.output.result}  # Use task1's output as input
    depends_on: [task1]
```

By combining these three elements, you can build workflows ranging from simple single jobs to complex multi-step pipelines.

---

## 5.2 Single-Job Workflows

The simplest form of a workflow contains just one job.

### Basic Structure

```yaml
workflows:
  - id: simple-workflow
    jobs:
      - id: task
        component: my-component
        input:
          field: ${input.value}
```

### Simplified Form

When there's only one job, you can omit `jobs` and the job `id`. If the `id` is omitted, it defaults to `__job__`.

```yaml
workflows:
  - id: simple-workflow
    component: my-component
    input:
      field: ${input.value}
```

### Example: Text Generation

```yaml
components:
  - id: gpt4o
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
            content: ${input.prompt}
      output:
        text: ${response.choices[0].message.content}

workflows:
  - id: generate-text
    jobs:
      - id: generate
        component: gpt4o
        input:
          prompt: ${input.prompt}
        output:
          result: ${output.text}
```

Execution:
```bash
model-compose run generate-text --input '{"prompt": "Hello, AI!"}'
```

---

## 5.3 Multi-Step Workflows

Workflows that execute multiple jobs sequentially.

### Job Dependencies (depends_on)

Use the `depends_on` field to explicitly define the execution order between jobs. This field specifies a list of job IDs that must complete before the current job starts.

**Basic format:**
```yaml
depends_on: [job-id-1, job-id-2]
```

**Key features:**
- Can specify dependencies on multiple jobs as an array
- Executes after all dependent jobs complete
- Jobs without dependencies can run in parallel
- Circular dependencies are not allowed

### Sequential Execution

```yaml
workflows:
  - id: multi-step
    jobs:
      - id: step1
        component: component1
        input: ${input}
        output:
          data1: ${output}

      - id: step2
        component: component2
        input:
          data: ${jobs.step1.output.data1}
        output:
          data2: ${output}
        depends_on: [step1]  # Executes after step1 completes

      - id: step3
        component: component3
        input:
          data: ${jobs.step2.output.data2}
        depends_on: [step2]  # Executes after step2 completes
```

### Parallel Execution

Jobs without dependencies run concurrently:

```yaml
workflows:
  - id: parallel-workflow
    jobs:
      - id: task-a
        component: component-a
        input: ${input}
        output:
          result-a: ${output}

      - id: task-b
        component: component-b
        input: ${input}
        output:
          result-b: ${output}
      # task-a and task-b run in parallel

      - id: combine
        component: combiner
        input:
          data-a: ${jobs.task-a.output.result-a}
          data-b: ${jobs.task-b.output.result-b}
        depends_on: [task-a, task-b]  # Executes after both tasks complete
```

### Complex Dependency Graph

```yaml
workflows:
  - id: complex-workflow
    jobs:
      - id: fetch-data
        component: data-fetcher
        output:
          raw: ${output}

      - id: process-1
        component: processor-1
        input: ${jobs.fetch-data.output.raw}
        depends_on: [fetch-data]
        output:
          processed-1: ${output}

      - id: process-2
        component: processor-2
        input: ${jobs.fetch-data.output.raw}
        depends_on: [fetch-data]
        output:
          processed-2: ${output}

      - id: merge
        component: merger
        input:
          data-1: ${jobs.process-1.output.processed-1}
          data-2: ${jobs.process-2.output.processed-2}
        depends_on: [process-1, process-2]
        output:
          merged: ${output}
```

Structure diagram:
```mermaid
graph TB
    fetch["Job: fetch-data"]
    proc1["Job: process-1"]
    proc2["Job: process-2"]
    merge["Job: merge"]

    fetch --> proc1
    fetch --> proc2
    proc1 --> merge
    proc2 --> merge
```

### Example: Text Generation and Speech Synthesis

```yaml
components:
  - id: text-generator
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
            content: ${input.prompt}
      output:
        text: ${response.choices[0].message.content}

  - id: text-to-speech
    type: http-client
    action:
      endpoint: https://api.elevenlabs.io/v1/text-to-speech/${input.voice_id}
      headers:
        xi-api-key: ${env.ELEVENLABS_API_KEY}
        Content-Type: application/json
      body:
        text: ${input.text}
        model_id: eleven_multilingual_v2
      output: ${response as base64}

workflows:
  - id: text-to-voice
    jobs:
      - id: generate
        component: text-generator
        input:
          prompt: ${input.prompt}
        output:
          text: ${output.text}

      - id: synthesize
        component: text-to-speech
        input:
          text: ${jobs.generate.output.text}
          voice_id: ${input.voice_id}
        output:
          audio: ${output}
        depends_on: [ generate ]
```

Structure diagram:
```mermaid
graph LR
    job1["Job: generate"]
    job2["Job: synthesize"]

    job1 -->|text| job2

    job1 -.-> comp1[[Component:<br/>text-generator]]
    job2 -.-> comp2[[Component:<br/>text-to-speech]]
```

---

## 5.4 Data Passing Between Jobs

How to pass data between jobs in a workflow.

### Variable Binding Syntax

```yaml
${input.field}              # Workflow input
${output.field}             # Current job output
${jobs.job-id.output.field} # Specific job output
${env.VAR_NAME}             # Environment variable
```

### Example: Complex Data Passing

```yaml
workflows:
  - id: data-pipeline
    jobs:
      - id: fetch
        component: data-fetcher
        input:
          url: ${input.source_url}
        output:
          raw_data: ${output.data}
          metadata: ${output.meta}

      - id: transform
        component: data-transformer
        input:
          data: ${jobs.fetch.output.raw_data}
          options:
            format: json
            encoding: utf-8
        output:
          transformed: ${output.result}
        depends_on: [ fetch ]

      - id: save
        component: data-saver
        input:
          data: ${jobs.transform.output.transformed}
          metadata: ${jobs.fetch.output.metadata}
          destination: ${input.target_path}
        depends_on: [ transform, fetch ]
```

Structure diagram:
```mermaid
graph LR
    fetch["Job: fetch"]
    transform["Job: transform"]
    save["Job: save"]

    fetch -->|raw_data| transform
    fetch -->|metadata| save
    transform -->|transformed| save

    fetch -.-> comp1[[Component:<br/>data-fetcher]]
    transform -.-> comp2[[Component:<br/>data-transformer]]
    save -.-> comp3[[Component:<br/>data-saver]]
```

### Type Conversion

You can apply type conversions during data passing:

```yaml
workflows:
  - id: image-workflow
    jobs:
      - id: generate
        component: image-generator
        output:
          image_base64: ${output as base64}

      - id: process
        component: image-processor
        input:
          image: ${jobs.generate.output.image_base64 as image/png;base64}
```

---

## 5.5 Job Types

model-compose provides various job types to support different task patterns.

### Available Job Types

| Type | Purpose | Description |
|------|---------|-------------|
| `action` | Component execution | Invoke a component to perform a task (default type) |
| `if` | Conditional branching | Route to different jobs based on a condition |
| `switch` | Multi-way branching | Route to one of many paths based on a value |
| `delay` | Wait | Wait for a specified duration |
| `filter` | Data restructuring | Extract and restructure data into a new shape |
| `random-router` | Random routing | Randomly select one job |

> **Note**: If `type` is not specified, it defaults to `action`.

### Action Job

The default job type that executes a component. If `type` is omitted, the job is treated as an action job.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `component` | `string` or object | `"__default__"` | The component to run. Either a string ID referencing a defined component, or an inline component config object. |
| `action` | `string` | `"__default__"` | The action to invoke on the component. For components with multiple actions, specify which one to call. |
| `input` | any | `null` | Input data supplied to the component. Supports variable binding (`${input.field}`, `${jobs.*.output}`). |
| `output` | any | `null` | Output mapping. Extracts and reshapes the component's output for use by subsequent jobs. |
| `repeat_count` | `int` or `string` | `1` | Number of times to repeat the component execution. Must be at least 1. Supports variable binding. |
| `interrupt` | object | `null` | Human-in-the-loop interrupt configuration. See [Interrupt](#interrupt-human-in-the-loop) below. |
| `depends_on` | `string[]` | `[]` | List of job IDs that must complete before this job runs. |

#### Basic Structure

```yaml
jobs:
  - id: my-task
    type: action  # Optional (default)
    component: my-component
    action: my-action  # For multi-action components
    input: ${input}
    output:
      result: ${output}
```

#### Inline Component

Instead of referencing a predefined component by ID, you can define the component inline:

```yaml
jobs:
  - id: my-task
    component:
      type: http-client
      action:
        endpoint: https://api.example.com/run
        body:
          data: ${input.data}
        output: ${response.result}
```

#### Repeat Execution

Run a component multiple times with the same input. Results are collected into an array:

```yaml
jobs:
  - id: generate-variants
    component: text-generator
    input:
      prompt: ${input.prompt}
    repeat_count: 3
```

The `repeat_count` also supports variable binding:

```yaml
repeat_count: ${input.count}
```

#### Interrupt (Human-in-the-Loop)

Action jobs support an `interrupt` field that pauses workflow execution at defined points and waits for external input before continuing. This enables human-in-the-loop patterns such as approval gates, data review, or interactive editing.

**Basic structure:**

```yaml
jobs:
  - id: my-task
    component: my-component
    input: ${input}
    interrupt:
      before: true   # Pause before component executes
      after: true    # Pause after component executes
```

**Interrupt phases:**

| Phase | Timing | Resume data effect |
|-------|--------|-------------------|
| `before` | Before the component runs | Replaces the job's input |
| `after` | After the component runs | Replaces the job's output |

**Configuration options:**

Each phase accepts either `true` (always interrupt) or a detailed configuration:

```yaml
interrupt:
  before:
    message: "Review the input before processing"
    metadata:
      preview: ${input.data}
  after:
    condition:
      operator: gt
      input: ${output.confidence}
      value: 0.5
    message: "Low confidence result. Please review."
```

- **`message`**: A message displayed to the user or client when the interrupt fires.
- **`metadata`**: Structured data passed to the client (e.g., preview data, options).
- **`condition`**: An optional condition that must evaluate to true for the interrupt to fire. Uses the same operators as [If Job](#if-job) (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `not-in`, `match`). If omitted, the interrupt always fires.

**Task states:**

When a workflow hits an interrupt, the task transitions through these states:

```
PENDING → PROCESSING → INTERRUPTED → PROCESSING → ... → COMPLETED / FAILED
```

The task remains in the `INTERRUPTED` state until it is resumed via the CLI, HTTP API, or MCP tool.

**Resuming via HTTP API:**

```bash
curl -X POST http://localhost:8080/api/tasks/{task_id}/resume \
  -H "Content-Type: application/json" \
  -d '{"job_id": "my-task", "data": {"revised": "value"}}'
```

**Resuming via CLI:**

When using `model-compose run`, the CLI automatically prompts for input at interrupt points. Use `--auto-resume` to skip prompts. See [Chapter 3: CLI Usage](./03-cli-usage.md#interrupt-handling) for details.

**Example: Shell command with human approval:**

```yaml
workflow:
  jobs:
    - id: run-command
      component: shell-executor
      input:
        command: ls -la
      interrupt:
        before:
          message: "About to execute: ls -la"
          metadata:
            command: ls -la
        after:
          message: "Command finished. Review the output above."
      output:
        result: ${output as text}

component:
  id: shell-executor
  type: shell
  action:
    command: ["sh", "-c", "${input.command}"]
    output: ${result.stdout}
```

Structure diagram:
```mermaid
graph LR
    start(["Start"]) --> before{"Interrupt<br/>(before)"}
    before -->|resumed| exec["Execute<br/>component"]
    exec --> after{"Interrupt<br/>(after)"}
    after -->|resumed| done(["Done"])
```

### If Job

Branch to different jobs based on a condition. Conditions are evaluated in order; the first match determines the routing target.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `conditions` | `IfCondition[]` | `[]` | List of conditions to evaluate in order. |
| `otherwise` | `string` | `null` | Job ID to route to if no conditions matched. |
| `depends_on` | `string[]` | `[]` | Jobs that must complete before this job runs. |

**IfCondition fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `operator` | `string` | `"eq"` | Comparison operator (see below). |
| `input` | any | `null` | Value to evaluate. Supports variable binding. |
| `value` | any | `null` | Value to compare against. Supports variable binding. |
| `if_true` | `string` | `null` | Job ID to route to when the condition is true. |
| `if_false` | `string` | `null` | Job ID to route to when the condition is false. |

#### Supported Operators

| Operator | Description |
|----------|-------------|
| `eq` | Equal |
| `neq` | Not equal |
| `gt` | Greater than |
| `gte` | Greater than or equal |
| `lt` | Less than |
| `lte` | Less than or equal |
| `in` | Contained in value |
| `not-in` | Not contained in value |
| `starts-with` | Starts with |
| `ends-with` | Ends with |
| `match` | Regex match |

#### Single Condition (Shorthand)

When there is only one condition, you can write the condition fields directly on the job without wrapping in `conditions`:

```yaml
jobs:
  - id: condition-check
    type: if
    operator: eq
    input: ${input.value}
    value: "expected"
    if_true: job-when-true
    if_false: job-when-false
```

#### Multiple Conditions

```yaml
jobs:
  - id: multi-condition
    type: if
    conditions:
      - operator: gt
        input: ${input.score}
        value: 80
        if_true: excellent-handler
      - operator: gt
        input: ${input.score}
        value: 60
        if_true: good-handler
    otherwise: need-improvement-handler
```

### Switch Job

Route to one of many paths based on exact value matching. Like a switch-case statement.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `input` | any | `null` | Value to match against cases. Supports variable binding. |
| `cases` | `SwitchCase[]` | `[]` | List of cases to evaluate. |
| `otherwise` | `string` | `null` | Job ID to route to if no cases match. |
| `depends_on` | `string[]` | `[]` | Jobs that must complete before this job runs. |

**SwitchCase fields:**

| Field | Type | Description |
|-------|------|-------------|
| `value` | `string` | Value to match against the input. |
| `then` | `string` | Job ID to route to if the value matches. |

#### Single Case (Shorthand)

```yaml
jobs:
  - id: check-type
    type: switch
    input: ${input.type}
    value: "image"
    then: process-image
    otherwise: process-other
```

#### Multiple Cases

```yaml
jobs:
  - id: route-by-type
    type: switch
    input: ${input.type}
    cases:
      - value: "image"
        then: process-image
      - value: "video"
        then: process-video
      - value: "audio"
        then: process-audio
    otherwise: process-unknown
```

### Delay Job

Wait for a specified duration or until a specific time. Has two modes selected by the `mode` field.

#### Fields (time-interval)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `"time-interval"` | - | Wait for a duration. |
| `duration` | `number` or `string` | - | Time to wait in milliseconds. Supports variable binding. |
| `output` | any | `null` | Optional output mapping. |
| `depends_on` | `string[]` | `[]` | Jobs that must complete before this job runs. |

```yaml
jobs:
  - id: wait
    type: delay
    mode: time-interval
    duration: 5000  # 5 seconds
```

#### Fields (specific-time)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `"specific-time"` | - | Wait until a specific date/time. |
| `time` | `datetime` or `string` | - | Target date and time (ISO 8601 format). Supports variable binding. |
| `timezone` | `string` | `null` | Timezone identifier (e.g., `"Asia/Seoul"`, `"UTC"`). |
| `output` | any | `null` | Optional output mapping. |
| `depends_on` | `string[]` | `[]` | Jobs that must complete before this job runs. |

```yaml
jobs:
  - id: wait-until
    type: delay
    mode: specific-time
    time: "2024-12-25T09:00:00"
    timezone: "Asia/Seoul"
```

### Filter Job

Extract parts of data and restructure into a new shape. Does not execute any component — it only transforms data using variable bindings.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `output` | any | `null` | Output mapping that defines the new data shape. Uses variable binding to extract values from workflow input or previous job outputs. |
| `depends_on` | `string[]` | `[]` | Jobs that must complete before this job runs. |

```yaml
jobs:
  - id: reshape-data
    type: filter
    output:
      user_id: ${input.user.id}
      user_name: ${input.user.profile.name}
      score: ${input.metrics.score}
```

### Random Router Job

Randomly select one of multiple jobs. Supports uniform (equal probability) and weighted (custom probability) modes.

#### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | `"uniform"` or `"weighted"` | `"uniform"` | Routing mode. `uniform` gives equal probability; `weighted` uses the `weight` field of each route. |
| `routings` | `Routing[]` | `[]` | List of possible routing destinations. |
| `depends_on` | `string[]` | `[]` | Jobs that must complete before this job runs. |

**Routing fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `target` | `string` | - | Destination job ID. |
| `weight` | `number` | `null` | Relative weight for weighted mode. Ignored in uniform mode. |

#### Uniform Distribution

```yaml
jobs:
  - id: ab-test
    type: random-router
    mode: uniform
    routings:
      - target: variant-a
      - target: variant-b
```

#### Weighted Distribution (70:20:10)

```yaml
jobs:
  - id: traffic-split
    type: random-router
    mode: weighted
    routings:
      - target: primary-model
        weight: 70
      - target: experimental-model
        weight: 20
      - target: fallback-model
        weight: 10
```

> **Note**: Weight values don't need to sum to 100. They work as relative ratios.

---

## 5.6 Conditional Execution

Using If and Switch jobs to control execution flow based on conditions.

### Example 1: Content Filtering with If Job

```yaml
components:
  - id: content-moderator
    type: http-client
    action:
      endpoint: https://api.openai.com/v1/moderations
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
        Content-Type: application/json
      body:
        input: ${input.text}
      output:
        flagged: ${response.results[0].flagged}

  - id: text-processor
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
            content: ${input.text}
      output:
        result: ${response.choices[0].message.content}

  - id: rejection-handler
    type: http-client
    action:
      endpoint: https://api.example.com/log-rejection
      method: POST
      body:
        text: ${input.text}
        reason: "content_flagged"
      output: ${response}

workflows:
  - id: safe-processing
    jobs:
      - id: moderate
        component: content-moderator
        input:
          text: ${input.text}
        output:
          flagged: ${output.flagged}

      - id: check-safety
        type: if
        operator: eq
        input: ${jobs.moderate.output.flagged}
        value: false
        if_true: process
        if_false: reject
        depends_on: [ moderate ]

      - id: process
        component: text-processor
        input:
          text: ${input.text}
        output:
          result: ${output.result}

      - id: reject
        component: rejection-handler
        input:
          text: ${input.text}
```

Structure diagram:
```mermaid
graph TB
    moderate["Job: moderate<br/>(action)"]
    check["Job: check-safety<br/>(if)"]
    process["Job: process<br/>(action)"]
    reject["Job: reject<br/>(action)"]

    moderate --> check
    check -->|flagged=false| process
    check -->|flagged=true| reject

    moderate -.-> comp1[[Component:<br/>content-moderator]]
    process -.-> comp2[[Component:<br/>text-processor]]
    reject -.-> comp3[[Component:<br/>rejection-handler]]
```

### Example 2: Media Type Processing with Switch Job

```yaml
components:
  - id: image-processor
    type: http-client
    action:
      endpoint: https://api.example.com/process-image
      body:
        image: ${input.data}
      output: ${response}

  - id: video-processor
    type: http-client
    action:
      endpoint: https://api.example.com/process-video
      body:
        video: ${input.data}
      output: ${response}

  - id: audio-processor
    type: http-client
    action:
      endpoint: https://api.example.com/process-audio
      body:
        audio: ${input.data}
      output: ${response}

  - id: default-processor
    type: http-client
    action:
      endpoint: https://api.example.com/process-unknown
      body:
        data: ${input.data}
      output: ${response}

workflows:
  - id: media-processing
    jobs:
      - id: route-by-type
        type: switch
        input: ${input.media_type}
        cases:
          - value: "image"
            then: process-image
          - value: "video"
            then: process-video
          - value: "audio"
            then: process-audio
        otherwise: process-unknown

      - id: process-image
        component: image-processor
        input:
          data: ${input.data}
        depends_on: [ route-by-type ]

      - id: process-video
        component: video-processor
        input:
          data: ${input.data}
        depends_on: [ route-by-type ]

      - id: process-audio
        component: audio-processor
        input:
          data: ${input.data}
        depends_on: [ route-by-type ]

      - id: process-unknown
        component: default-processor
        input:
          data: ${input.data}
        depends_on: [ route-by-type ]
```

Structure diagram:
```mermaid
graph TB
    route["Job: route-by-type<br/>(switch)"]
    img["Job: process-image"]
    vid["Job: process-video"]
    aud["Job: process-audio"]
    unk["Job: process-unknown"]

    route -->|"image"| img
    route -->|"video"| vid
    route -->|"audio"| aud
    route -->|"otherwise"| unk

    img -.-> comp1[[Component:<br/>image-processor]]
    vid -.-> comp2[[Component:<br/>video-processor]]
    aud -.-> comp3[[Component:<br/>audio-processor]]
    unk -.-> comp4[[Component:<br/>default-processor]]
```

---

## 5.7 Streaming Mode

When components support streaming, you can stream data in real-time.

> **For more details, see [Chapter 11: Streaming Mode](./11-streaming-mode.md).**

### Streaming Configuration in Components

#### Model Components

Model components enable streaming by setting `streaming: true` at the component level:

```yaml
components:
  - id: local-llm
    type: model
    task: text-generation
    model:
      provider: huggingface
      repository: meta-llama/Llama-2-7b-hf
      token: ${env.HUGGINGFACE_TOKEN}
    streaming: true  # Enable streaming
    action:
      text: ${input.prompt}
```

#### HTTP Components

`http-client` and `http-server` components automatically switch to streaming mode when the API returns a stream response:

```yaml
components:
  - id: gpt4o-stream
    type: http-client
    action:
      endpoint: https://api.openai.com/v1/chat/completions
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
        Content-Type: application/json
      body:
        model: gpt-4o
        messages: ${input.messages}
        stream: true  # Request streaming from API
      output: ${response}
```

> **Note**: `http-client` and `http-server` automatically detect stream responses from APIs, so no explicit `streaming` setting is needed.

### Using Streaming in Workflows

```yaml
workflows:
  - id: chat
    jobs:
      - id: respond
        component: gpt4o-stream
        input:
          messages: ${input.messages}
    output: ${output}
```

> **Note**: If a component's output is a stream, the job's output is also a stream. If the last job's output is a stream, the workflow output is also returned as a stream.

### Requesting Streaming via HTTP API

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "chat",
    "input": {
      "messages": [
        {"role": "user", "content": "Tell me a story"}
      ]
    }
  }'
```

> **Note**: Streaming responses are delivered in Server-Sent Events (SSE) format.

---

## 5.8 Error Handling

Handle errors that may occur during workflow execution.

### Retry Configuration

```yaml
workflows:
  - id: resilient-workflow
    jobs:
      - id: api-call
        component: external-api
        retry:
          max_retry_count: 3
          delay: 1000  # milliseconds
          backoff: exponential
        input: ${input}
```

### Fallback Handling

```yaml
workflows:
  - id: fallback-workflow
    jobs:
      - id: primary
        component: primary-service
        input: ${input}
        on_error: continue

      - id: fallback
        component: fallback-service
        condition: ${jobs.primary.error}
        input: ${input}
```

### Example: Multi-Model Fallback

```yaml
components:
  - id: gpt4o
    type: http-client
    action:
      endpoint: https://api.openai.com/v1/chat/completions
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
        Content-Type: application/json
      body:
        model: gpt-4o
        messages: ${input.messages}
      output:
        text: ${response.choices[0].message.content}

  - id: claude
    type: http-client
    action:
      endpoint: https://api.anthropic.com/v1/messages
      headers:
        x-api-key: ${env.ANTHROPIC_API_KEY}
        anthropic-version: "2023-06-01"
        Content-Type: application/json
      body:
        model: claude-3-5-sonnet-20241022
        messages: ${input.messages}
        max_tokens: 1024
      output:
        text: ${response.content[0].text}

workflows:
  - id: robust-chat
    jobs:
      - id: try-gpt4o
        component: gpt4o
        retry:
          max_retry_count: 2
          delay: 500
        input:
          messages: ${input.messages}
        output:
          result: ${output.text}
        on_error: continue

      - id: fallback-claude
        component: claude
        condition: ${jobs.try-gpt4o.error}
        input:
          messages: ${input.messages}
        output:
          result: ${output.text}
        depends_on: [ try-gpt4o ]
```

Structure diagram:
```mermaid
graph TB
    try["Job: try-gpt4o<br/>(retry: 2)"]
    fallback["Job: fallback-claude"]

    try -->|success| output[Output]
    try -->|error| fallback
    fallback --> output

    try -.-> comp1[[Component:<br/>gpt4o]]
    fallback -.-> comp2[[Component:<br/>claude]]
```

### Accessing Error Information

```yaml
workflows:
  - id: error-logging
    jobs:
      - id: risky-operation
        component: risky-api
        input: ${input}
        on_error: continue

      - id: log-error
        component: error-logger
        condition: ${jobs.risky-operation.error}
        input:
          error_message: ${jobs.risky-operation.error.message}
          error_code: ${jobs.risky-operation.error.code}
          timestamp: ${jobs.risky-operation.error.timestamp}
        depends_on: [ risky-operation ]
```

---

## 5.9 Workflow Best Practices

### 1. Clear Job Names

```yaml
# Good
workflows:
  - id: user-onboarding
    jobs:
      - id: validate-email
        component: email-validator
      - id: create-account
        component: account-creator
      - id: send-welcome-email
        component: email-sender

# Bad
workflows:
  - id: workflow1
    jobs:
      - id: step1
        component: comp1
      - id: step2
        component: comp2
```

### 2. Job Decomposition

Break complex logic into smaller jobs:

```yaml
# Good - Clear step separation
workflows:
  - id: content-pipeline
    jobs:
      - id: fetch-content
        component: content-fetcher
      - id: validate-content
        component: content-validator
      - id: transform-content
        component: content-transformer
      - id: publish-content
        component: content-publisher

# Bad - One monolithic job
workflows:
  - id: content-pipeline
    jobs:
      - id: process-everything
        component: monolithic-processor
```

### 3. Reusable Workflows

```yaml
components:
  - id: preprocessing-workflow
    type: workflow
    workflow: preprocessing

workflows:
  - id: preprocessing
    jobs:
      - id: clean
        component: data-cleaner
      - id: normalize
        component: data-normalizer

  - id: analysis
    jobs:
      - id: preprocess
        component: preprocessing-workflow
        input: ${input.raw_data}
      - id: analyze
        component: analyzer
        input: ${jobs.preprocess.output}
        depends_on: [ preprocess ]
```

### 4. Document Inputs and Outputs

```yaml
workflows:
  - id: image-generation
    # Input: { prompt: string, style: string, size: string }
    # Output: { image_url: string, width: number, height: number }
    jobs:
      - id: generate
        component: image-generator
        input:
          prompt: ${input.prompt}
          style: ${input.style}
          size: ${input.size}
```

### 5. Consider Error Handling

Always add retry or fallback logic for critical jobs:

```yaml
workflows:
  - id: critical-workflow
    jobs:
      - id: important-task
        component: critical-service
        retry:
          max_retry_count: 3
          delay: 1000
        on_error: continue

      - id: fallback-task
        component: backup-service
        condition: ${jobs.important-task.error}
        depends_on: [ important-task ]
```

---

## Next Steps

Try it out:
- Start with simple single-job workflows
- Gradually expand to complex multi-step workflows
- Add error handling and retry logic
- Build reusable workflow components

---

**Next Chapter**: [6. Controller Configuration](./06-controller-configuration.md)
