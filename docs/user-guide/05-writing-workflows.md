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

### Example: Text Generation

```yaml
components:
  - id: gpt4o
    type: http-client
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

### Simplified Form

Single-job workflows can be written more concisely:

```yaml
workflows:
  - id: generate-text
    component: gpt4o
    input:
      prompt: ${input.prompt}
    output:
      result: ${output.text}
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

The default job type that executes a component.

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

### If Job

Branch to different jobs based on a condition.

#### Basic Structure

```yaml
jobs:
  - id: condition-check
    type: if
    operator: eq          # Comparison operator
    input: ${input.value}
    value: "expected"
    if_true: job-when-true
    if_false: job-when-false
```

#### Supported Operators

- `eq`: Equal
- `neq`: Not equal
- `gt`: Greater than
- `gte`: Greater than or equal
- `lt`: Less than
- `lte`: Less than or equal
- `in`: Contains
- `not-in`: Does not contain
- `starts-with`: Starts with
- `ends-with`: Ends with
- `match`: Regex match

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

Route to one of many paths based on a value.

#### Basic Structure

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

Wait for a specified duration or until a specific time.

#### Time Interval Wait (time-interval)

```yaml
jobs:
  - id: wait
    type: delay
    mode: time-interval
    duration: 5000  # milliseconds
```

#### Wait Until Specific Time (specific-time)

```yaml
jobs:
  - id: wait-until
    type: delay
    mode: specific-time
    time: "2024-12-25T09:00:00"
    timezone: "Asia/Seoul"  # Optional
```

### Filter Job

Extract parts of data and restructure into a new shape.

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

Randomly select one of multiple jobs. Use `weight` to adjust the probability of each route.

#### Equal Distribution (50:50)

```yaml
jobs:
  - id: ab-test
    type: random-router
    routes:
      - id: variant-a
        weight: 50
      - id: variant-b
        weight: 50
```

#### Unequal Distribution (70:20:10)

```yaml
jobs:
  - id: traffic-split
    type: random-router
    routes:
      - id: primary-model
        weight: 70
      - id: experimental-model
        weight: 20
      - id: fallback-model
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
        depends_on: [ check-safety ]

      - id: reject
        component: rejection-handler
        input:
          text: ${input.text}
        depends_on: [ check-safety ]
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
    endpoint: https://api.example.com/process-image
    body:
      image: ${input.data}
    output: ${response}

  - id: video-processor
    type: http-client
    endpoint: https://api.example.com/process-video
    body:
      video: ${input.data}
    output: ${response}

  - id: audio-processor
    type: http-client
    endpoint: https://api.example.com/process-audio
    body:
      audio: ${input.data}
    output: ${response}

  - id: default-processor
    type: http-client
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

Model components enable streaming by setting `streaming: true` at the action level:

```yaml
components:
  - id: local-llm
    type: model
    task: text-generation
    model:
      provider: huggingface
      repository: meta-llama/Llama-2-7b-hf
      token: ${env.HUGGINGFACE_TOKEN}
    text: ${input.prompt}
    streaming: true  # Enable streaming
```

#### HTTP Components

`http-client` and `http-server` components automatically switch to streaming mode when the API returns a stream response:

```yaml
components:
  - id: gpt4o-stream
    type: http-client
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
          max_attempts: 3
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
          max_attempts: 2
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
          max_attempts: 3
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
