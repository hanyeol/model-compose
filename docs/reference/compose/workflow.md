# Workflow Configuration Reference

Workflows define the execution logic and data flow for your model-compose applications. They orchestrate components, handle data transformation, and manage complex business logic through a sequence of jobs.

## Basic Structure

### Single Workflow

```yaml
workflow:
  id: main
  title: My Workflow
  description: Description of what this workflow does
  jobs:
    - id: step1
      component: my-component
      input: ${input}
    - id: step2
      component: another-component
      input: ${step1.output}
  output: ${step2.output}
```

### Multiple Workflows

```yaml
workflows:
  - id: workflow-1
    title: First Workflow
    default: true
    jobs:
      - id: job1
        component: component-a
        
  - id: workflow-2
    title: Second Workflow
    jobs:
      - id: job1
        component: component-b
```

## Workflow Configuration

### Core Properties

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | `"__workflow__"` | Unique identifier for the workflow |
| `name` | string | `null` | Name of the workflow |
| `title` | string | `null` | Display title for the workflow |
| `description` | string | `null` | Description of what the workflow does |
| `jobs` | array | `[]` | List of jobs that define execution steps (use `job:` for a single job) |
| `output` | any | `null` | Mapping expression for the workflow's final output. If omitted, outputs of terminal jobs are merged and returned. |
| `default` | boolean | `false` | Whether this workflow should be used as default |
| `private` | boolean | `false` | Whether this workflow is private and should not be exposed externally |

## Common Job Fields

Every job type supports a shared set of fields for identification, dependencies, interrupts, hooks, retries, and error handling. Individual job-type sections below list only their type-specific fields.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | `"__job__"` | Unique job identifier |
| `name` | string | `null` | Human-readable label used as a group label in the web UI |
| `depends_on` | array | `[]` | List of job IDs that must complete before this job runs |
| `max_run_count` | integer | `5` | Maximum executions within a single workflow run (including re-runs from routing) |
| `interrupt` | object | `null` | Human-in-the-Loop interrupt points; see [Job Interrupts](#job-interrupts) |
| `hook` | object | `null` | Inline Python hooks; see [Job Hooks](#job-hooks) |
| `retry` | integer/object | `null` | Retry policy applied to this job on failure; see [Job Retry](#job-retry) |
| `on_error` | string/object | `null` | Fallback behavior after retries are exhausted; see [Job On-Error](#job-on-error) |
| `output` | any | `null` | Output mapping expression for this job (except router-only jobs like `if`, `switch`, `random-router`) |

### Job Interrupts

Pause execution before and/or after a job runs so a human can inspect, approve, or override the state. Interrupts work on every job type.

```yaml
jobs:
  - id: send-invoice
    component: mailer
    interrupt:
      before:
        message: "Confirm before sending"
        condition:
          input: ${input.amount}
          operator: gt
          value: 1000
      after: true
```

Each interrupt point accepts `{ condition?, message?, metadata? }`. Setting a point to `true` interrupts unconditionally. Conditions use `{ operator, input, value }` with the operators defined by `ConditionOperator` (`eq`, `ne`, `gt`, `lt`, etc.).

When an interrupt fires, the workflow transitions to `interrupted` state and exposes an `InterruptState` on the task:

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | string | ID of the job that interrupted |
| `run_id` | string \| null | Per-run identifier — non-null only for `component` jobs with `repeat_count > 1`, where each parallel run interrupts independently |
| `phase` | `"before"` \| `"after"` | Whether the interrupt fired before or after the job body |
| `message` | string \| null | Human-readable message from the interrupt config |
| `metadata` | object \| null | Structured metadata from the interrupt config |

To resume, callers pass `task_id`, `job_id`, `run_id`, and an optional `answer` back to the controller. If the answer is not `null`, it replaces the job's input (before phase) or output (after phase).

### Job Hooks

Run inline Python code before and/or after a job runs. Unlike interrupts, hooks execute automatically without external intervention.

```yaml
jobs:
  - id: transform
    component: my-component
    hook:
      before:
        script: |
          async def hook(input, **kwargs):
              input["timestamp"] = int(kwargs["run_id"] or 0)
              return input
      after:
        - script: |
            async def hook(input, output, **kwargs):
                output["source_job"] = kwargs["job_id"]
                return output
        - script: |
            async def hook(input, output, **kwargs):
                # observation-only hook: return the value unchanged
                print(f"[{kwargs['phase']}] output = {output}")
                return output
```

Each phase accepts a single hook object or a list of hooks. Hooks run in declaration order and pipe their results together.

**Hook function signatures:**

- **Before phase:** `async def hook(input, **kwargs)` → returned value replaces the input
- **After phase:** `async def hook(input, output, **kwargs)` → returned value replaces the output

**`kwargs` fields (from `HookPoint`):**

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | string | The workflow task ID |
| `job_id` | string | The job's ID |
| `run_id` | string \| null | Per-run identifier — non-null only for `component` jobs with `repeat_count > 1` |
| `phase` | `"before"` \| `"after"` | The phase this hook is bound to |

Hooks may be sync or async. The return value is always used verbatim: to leave data unchanged, explicitly `return input` (before) or `return output` (after). For routing jobs (`if`, `switch`, `random-router`), after-hook `output` is `None` and the return value is discarded — after hooks on those jobs are observation-only.

**Execution order per job:** interrupt → hook. When a job declares an `output` mapping expression, it is rendered *before* the after-hook, so hooks see the shaped output.

### Job Retry

Retry a job when it raises an exception. The retry loop lives inside the job itself — retries do **not** count against `max_run_count`, which only tracks re-runs driven by routing.

```yaml
jobs:
  - id: fetch
    component: http-api
    retry: 3               # shorthand — 3 total attempts, no delay
```

Or the full form:

```yaml
jobs:
  - id: fetch
    component: http-api
    retry:
      max_attempt_count: 5
      delay: 1s
      backoff: exponential
      max_delay: 30s
```

Any exception raised by the job body is retried up to `max_attempt_count` times.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_attempt_count` | integer | `1` | Total attempts including the first, before falling through to `on_error`. Must be ≥ 1 |
| `delay` | string/number | `0` | Base delay between attempts (duration string like `1s`, `500ms`, or seconds) |
| `backoff` | `"fixed"` \| `"exponential"` | `"fixed"` | How the delay grows across attempts |
| `max_delay` | string/number | `null` | Cap for the delay after backoff is applied |

**Backoff calculation:**

- `fixed`: `delay = base`
- `exponential`: `delay = base * 2^(attempt - 1)`

When retries are exhausted, control falls through to [Job On-Error](#job-on-error) if configured; otherwise the exception propagates and fails the workflow.

### Job On-Error

Apply a fallback strategy after retries are exhausted. Without `on_error`, an unhandled exception fails the workflow.

```yaml
jobs:
  - id: fetch
    component: http-api
    on_error: ignore       # shorthand — swallow the error, return null
```

Or the full form:

```yaml
jobs:
  - id: fetch
    component: http-api
    retry: 3
    on_error:
      output:
        status: failed
        reason: ${error.message}
      to: cleanup_job
```

The `on_error: ignore` string form is a shorthand for `on_error: {}` — swallow the error and return `null`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `output` | any | `null` | Fallback output rendered on failure. Can reference `${error.*}` variables |
| `to` | string | `null` | Job ID to route to on failure (like a routing job's target) |

**Resolution order** when `on_error` fires:

1. If `to` is set → return a routing target to that job (any `output` is ignored).
2. Else if `output` is set → render `output` and return it as the job's result.
3. Else → return `null`.

**Error variables** available inside `output` templates via variable binding:

| Path | Description |
|------|-------------|
| `${error.message}` | The exception's message (`str(e)`) |

**Interaction with `retry`:** `on_error` only fires after all retry attempts have failed. If any retry attempt succeeds, `on_error` is not invoked and the successful output is used.

## Job Types

Workflows support different job types for various execution patterns:

### Component Job (`component`)

Execute a component action - the most common job type.

```yaml
jobs:
  - id: api-call
    type: component
    component: http-client
    action: post-data
    input:
      data: ${input.payload}
    repeat_count: 1
```

**Type-specific configuration** (see [Common Job Fields](#common-job-fields) for shared fields):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | `component` | Job type (can be omitted, defaults to component) |
| `component` | string/object | `"__default__"` | Component to execute |
| `action` | string | `"__default__"` | Action to invoke on the component |
| `input` | any | `null` | Input data for the component |
| `repeat_count` | integer/string | `1` | Number of times to repeat execution (must be >= 1). Each repeat gets its own `run_id`, so interrupts and hooks are isolated per run. |

### Delay Job (`delay`)

Wait for a fixed duration or until a specific point in time.

```yaml
jobs:
  - id: wait
    type: delay
    mode: time-interval
    duration: 5s

  - id: wait-until
    type: delay
    mode: specific-time
    time: "2026-01-01T09:00:00"
    timezone: Asia/Seoul
```

**Type-specific configuration** (see [Common Job Fields](#common-job-fields) for shared fields):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `delay` |
| `mode` | string | `time-interval` | Delay mode: `time-interval` or `specific-time` |

**`time-interval` mode:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `duration` | string/number | **required** | Time to wait before continuing (e.g., `"5s"`, `"2m"`, or seconds as a number) |

**`specific-time` mode:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `time` | string/datetime | **required** | Absolute date and time to wait until |
| `timezone` | string | `null` | Timezone identifier used to interpret `time` (e.g., `Asia/Seoul`) |

### Conditional Job (`if`)

Route to one of several jobs based on evaluated conditions.

```yaml
jobs:
  - id: conditional-step
    type: if
    input: ${input.process_mode}
    conditions:
      - operator: eq
        value: advanced
        if_true: advanced-processing
      - operator: eq
        value: simple
        if_true: simple-processing
    otherwise: default-processing

  - id: advanced-processing
    component: advanced-processor
  - id: simple-processing
    component: simple-processor
  - id: default-processing
    component: default-processor
```

For a single condition you can inline the fields instead of using a list:

```yaml
- id: check
  type: if
  input: ${jobs.previous.output.status}
  operator: eq
  value: ok
  if_true: ok-job
  if_false: fail-job
```

**Type-specific configuration** (see [Common Job Fields](#common-job-fields) for shared fields):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `if` |
| `input` | any | `null` | Input evaluated against each condition |
| `conditions` | array | `[]` | List of `{ operator, value, if_true, if_false }` entries |
| `otherwise` | string | `null` | Job ID to run when no condition matches or no branch is taken |

### Switch Job (`switch`)

Route to one of many jobs based on the value of an input.

```yaml
jobs:
  - id: router
    type: switch
    input: ${input.operation_type}
    cases:
      - value: create
        then: create-job
      - value: update
        then: update-job
      - value: delete
        then: delete-job
    otherwise: error-job

  - id: create-job
    component: creator
  - id: update-job
    component: updater
  - id: delete-job
    component: deleter
  - id: error-job
    component: error-handler
```

**Type-specific configuration** (see [Common Job Fields](#common-job-fields) for shared fields):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `switch` |
| `input` | any | `null` | Value matched against each case |
| `cases` | array | `[]` | List of `{ value, then }` entries |
| `otherwise` | string | `null` | Job ID routed to when no case matches |

### Random Router Job (`random-router`)

Randomly route to one of several jobs.

```yaml
jobs:
  - id: load-balancer
    type: random-router
    mode: weighted
    routings:
      - to: primary-server
        weight: 0.7
      - to: backup-server
        weight: 0.3

  - id: primary-server
    component: server-a
  - id: backup-server
    component: server-b
```

**Type-specific configuration** (see [Common Job Fields](#common-job-fields) for shared fields):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `random-router` |
| `mode` | string | `uniform` | Routing mode: `uniform` or `weighted` |
| `routings` | array | `[]` | List of `{ to, weight? }` entries (weights are only used in `weighted` mode) |

### Filter Job (`filter`)

Placeholder job used to shape a workflow's output without executing a component; the job's `output` mapping expression forms its result.

```yaml
jobs:
  - id: filter-data
    type: filter
    output:
      active: ${jobs.load.output.records}
```

**Type-specific configuration** (see [Common Job Fields](#common-job-fields) for shared fields):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `filter` |
| `output` | any | `null` | Output mapping expression |

### For-Each Job (`for-each`)

Run a component once per item in an input collection.

```yaml
jobs:
  - id: process-each
    type: for-each
    input: ${input.items}
    batch_size: 4
    streaming: false
    do:
      component: item-processor
      action: transform
      input:
        item: ${item}
      output: ${result}
```

**Type-specific configuration** (see [Common Job Fields](#common-job-fields) for shared fields):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `for-each` |
| `input` | any | **required** | Source of items to iterate over (list, async stream, or any iterable) |
| `batch_size` | integer | `null` (=1) | Number of items processed concurrently per batch |
| `streaming` | boolean | `false` | If true, yield results as they complete instead of accumulating a list |
| `do.component` | string/object | `"__default__"` | Component to invoke for each item |
| `do.action` | string | `"__default__"` | Action to invoke |
| `do.input` | any | `null` | Input for each iteration; `${item}` refers to the current element |
| `do.output` | any | `null` | Output mapping applied to each iteration's result |

## Job Dependencies and Execution Order

### Sequential Execution

Jobs execute in the order they are defined by default:

```yaml
jobs:
  - id: step1
    component: first-component
    
  - id: step2
    component: second-component
    input: ${step1.output}  # Uses output from step1
    
  - id: step3
    component: third-component
    input: ${step2.output}  # Uses output from step2
```

### Explicit Dependencies

Use `depends_on` to specify explicit dependencies:

```yaml
jobs:
  - id: parallel-job-1
    component: component-a
    
  - id: parallel-job-2 
    component: component-b
    
  - id: final-job
    component: component-c
    depends_on: ["parallel-job-1", "parallel-job-2"]
    input:
      result1: ${parallel-job-1.output}
      result2: ${parallel-job-2.output}
```

## Variable Interpolation and Data Flow

### Input Variables

Access workflow input data:

```yaml
input: ${input.user_prompt}
```

### Job Outputs

Reference outputs from previous jobs:

```yaml
input: ${previous-job.output}
# or access specific fields
input: ${api-call.output.data.results[0].name}
```

### Jobs Context

Access all job outputs:

```yaml
input:
  step1_result: ${jobs.step1.output}
  step2_result: ${jobs.step2.output}
```

### Type Conversion

Convert data types:

```yaml
input:
  count: ${input.number as integer}
  temperature: ${input.temp as number | 0.7}
  enabled: ${input.flag as boolean}
  data: ${response as json}
```

### Default Values

Provide fallback values:

```yaml
input:
  model: ${input.model | "gpt-4o"}
  max_tokens: ${input.max_tokens | 1000}
```

## Output Configuration

A workflow can declare its final `output` as a mapping expression that is evaluated after all jobs complete. Any structure is supported — a single value, a dictionary, or a nested object — and variable bindings (`${jobs.<id>.output...}`, `${input...}`, etc.) are rendered just like job inputs.

```yaml
workflow:
  jobs:
    - id: process
      component: processor

  output:
    result: ${jobs.process.output.data}
    status: completed
    metadata:
      execution_time: ${jobs.process.execution_time}
```

If `output` is omitted, the workflow's result is derived from the outputs of its **terminal jobs** (jobs that no other job depends on). When multiple terminal jobs each produce a dictionary, their outputs are merged; otherwise the last terminal job's output is used as-is. Defining `output` explicitly overrides this default merging behavior and lets you reshape the response.

## Workflow Examples

### Simple Linear Workflow

```yaml
workflow:
  title: Text Processing Pipeline
  description: Process text input through multiple stages
  jobs:
    - id: clean-text
      component: text-cleaner
      input: ${input.text}
      
    - id: analyze-sentiment 
      component: sentiment-analyzer
      input: ${clean-text.output}
      
    - id: generate-summary
      component: summarizer
      input: ${clean-text.output}
      
  output:
    cleaned_text: ${clean-text.output}
    sentiment: ${analyze-sentiment.output}
    summary: ${generate-summary.output}
```

### Conditional Workflow

```yaml
workflow:
  title: Smart Image Processing
  jobs:
    - id: detect-content
      component: image-analyzer
      input: ${input.image}

    - id: route
      type: if
      input: ${jobs.detect-content.output.has_faces}
      operator: eq
      value: true
      if_true: face-processing
      if_false: general-processing

    - id: face-processing
      component: face-processor
      input: ${input.image}

    - id: general-processing
      component: general-processor
      input: ${input.image}

  output:
    face: ${jobs.face-processing.output}
    general: ${jobs.general-processing.output}
```

### Parallel Processing Workflow

```yaml
workflow:
  title: Multi-Model Analysis
  jobs:
    - id: model-a-analysis
      component: model-a
      input: ${input}
      
    - id: model-b-analysis
      component: model-b  
      input: ${input}
      
    - id: model-c-analysis
      component: model-c
      input: ${input}
      
    - id: aggregate-results
      component: aggregator
      depends_on: ["model-a-analysis", "model-b-analysis", "model-c-analysis"]
      input:
        results:
          - ${model-a-analysis.output}
          - ${model-b-analysis.output}  
          - ${model-c-analysis.output}
          
  output: ${aggregate-results.output}
```

### Complex Routing Workflow

```yaml
workflow:
  title: Request Router
  jobs:
    - id: classify-request
      component: classifier
      input: ${input}
      
    - id: route-request
      type: switch
      input: ${jobs.classify-request.output.category}
      cases:
        - value: urgent
          then: urgent-handler
        - value: normal
          then: normal-handler
        - value: bulk
          then: bulk-handler
      otherwise: default-handler

    - id: urgent-handler
      component: urgent-processor
      input: ${input}
    - id: normal-handler
      component: normal-processor
      input: ${input}
    - id: bulk-handler
      component: bulk-processor
      input: ${input}
    - id: default-handler
      component: default-processor
      input: ${input}

  output:
    urgent: ${jobs.urgent-handler.output}
    normal: ${jobs.normal-handler.output}
    bulk: ${jobs.bulk-handler.output}
    default: ${jobs.default-handler.output}
```

## Workflow Variable Types

When defining input/output schemas, workflows support rich variable types:

### Basic Types

```yaml
variables:
  - name: user_input
    type: text
    required: true
  - name: count  
    type: integer
    default: 10
  - name: enabled
    type: boolean
    default: false
```

### Media Types

```yaml
variables:
  - name: profile_image
    type: image
    format: base64
  - name: audio_file
    type: audio
    format: url
  - name: document
    type: file
    format: path
```

### Selection Types

```yaml
variables:
  - name: model_choice
    type: select
    options: ["gpt-4o", "gpt-3.5-turbo", "claude-3"]
    default: gpt-4o
```

## Best Practices

1. **Job Naming**: Use descriptive job IDs that indicate their purpose
2. **Error Handling**: Include error handling jobs for critical workflows
3. **Dependencies**: Use explicit `depends_on` for complex dependency graphs
4. **Data Flow**: Keep data transformations simple and readable
5. **Testing**: Test workflows with different input scenarios
6. **Documentation**: Use `title` and `description` fields for clarity
7. **Modularity**: Break complex workflows into smaller, reusable components
8. **Performance**: Consider parallel execution where possible

## Integration with Components

Workflows orchestrate components through the job system:

```yaml
components:
  - id: api-client
    type: http-client
    base_url: https://api.example.com
    
  - id: data-processor
    type: shell
    command: python process.py

workflow:
  jobs:
    - id: fetch-data
      component: api-client
      action: get-data
      
    - id: process-data
      component: data-processor
      input: ${fetch-data.output}
```

## Common Patterns

- **ETL Pipelines**: Extract, Transform, Load data processing
- **API Orchestration**: Coordinating multiple API calls
- **Content Processing**: Multi-stage content analysis and generation
- **Conditional Logic**: Dynamic execution based on input or intermediate results
- **Error Recovery**: Fallback and retry mechanisms
- **Load Balancing**: Distributing work across multiple components