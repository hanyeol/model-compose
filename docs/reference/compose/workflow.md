# Workflow Configuration Reference

Workflows define the execution logic and data flow for your model-compose applications. They orchestrate components, handle data transformation, and manage complex business logic through a sequence of jobs.

## Basic Structure

### Single Workflow

```yaml
workflow:
  id: __default__
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
| `id` | string | `"__default__"` | Unique identifier for the workflow |
| `name` | string | `null` | Name of the workflow |
| `title` | string | `null` | Display title for the workflow |
| `description` | string | `null` | Description of what the workflow does |
| `jobs` | array | `[]` | List of jobs that define execution steps |
| `default` | boolean | `false` | Whether this workflow should be used as default |

## Job Types

Workflows support different job types for various execution patterns:

### Action Job (`action`)

Execute a component action - the most common job type.

```yaml
jobs:
  - id: api-call
    type: action
    component: http-client
    action: post-data
    input:
      data: ${input.payload}
    repeat_count: 1
```

**Configuration:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | `action` | Job type (can be omitted, defaults to action) |
| `component` | string/object | `"__default__"` | Component to execute |
| `action` | string | `"__default__"` | Action to invoke on the component |
| `input` | any | `null` | Input data for the component |
| `repeat_count` | integer/string | `1` | Number of times to repeat execution |

### Delay Job (`delay`)

Add time delays or wait conditions in workflow execution.

```yaml
jobs:
  - id: wait
    type: delay
    mode: time-interval
    interval: 5s
    
  - id: wait-for-condition
    type: delay
    mode: condition
    condition: ${some.variable == "ready"}
    timeout: 30s
```

**Configuration:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `delay` |
| `mode` | string | `time-interval` | Delay mode: `time-interval` or `condition` |
| `interval` | string | `null` | Time to wait (e.g., "5s", "2m") |
| `condition` | string | `null` | Condition to wait for (condition mode) |
| `timeout` | string | `null` | Maximum time to wait for condition |

### Conditional Job (`if`)

Execute jobs based on conditions.

```yaml
jobs:
  - id: conditional-step
    type: if
    condition: ${input.process_mode == "advanced"}
    then:
      - id: advanced-processing
        component: advanced-processor
    else:
      - id: simple-processing
        component: simple-processor
```

**Configuration:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `if` |
| `condition` | string | **required** | Condition expression to evaluate |
| `then` | array | `[]` | Jobs to execute if condition is true |
| `else` | array | `[]` | Jobs to execute if condition is false |

### Switch Job (`switch`)

Route execution based on multiple conditions.

```yaml
jobs:
  - id: router
    type: switch
    value: ${input.operation_type}
    cases:
      create:
        - id: create-job
          component: creator
      update:
        - id: update-job
          component: updater
      delete:
        - id: delete-job
          component: deleter
    default:
      - id: error-job
        component: error-handler
```

**Configuration:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `switch` |
| `value` | string | **required** | Value expression to match against |
| `cases` | object | `{}` | Map of case values to job lists |
| `default` | array | `[]` | Jobs to execute if no case matches |

### Random Router Job (`random-router`)

Randomly distribute execution across multiple job paths.

```yaml
jobs:
  - id: load-balancer
    type: random-router
    routes:
      - weight: 70
        jobs:
          - id: primary-server
            component: server-a
      - weight: 30
        jobs:
          - id: backup-server
            component: server-b
```

**Configuration:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `random-router` |
| `routes` | array | **required** | List of weighted route configurations |
| `routes[].weight` | integer | **required** | Weight for this route (higher = more likely) |
| `routes[].jobs` | array | **required** | Jobs to execute for this route |

### Filter Job (`filter`)

Filter and transform data arrays.

```yaml
jobs:
  - id: filter-data
    type: filter
    items: ${input.records}
    condition: ${item.status == "active"}
    output:
      filtered_items: ${items}
```

**Configuration:**
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `filter` |
| `items` | string | **required** | Expression that returns an array to filter |
| `condition` | string | **required** | Filter condition (use `item` to refer to current item) |

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

Define workflow outputs:

```yaml
workflow:
  jobs:
    - id: process
      component: processor
      
  output:
    result: ${process.output.data}
    status: completed
    metadata:
      execution_time: ${process.execution_time}
```

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
      
    - id: process-image
      type: if
      condition: ${detect-content.output.has_faces == true}
      then:
        - id: face-processing
          component: face-processor
          input: ${input.image}
      else:
        - id: general-processing
          component: general-processor
          input: ${input.image}
          
  output: ${process-image.output}
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
      value: ${classify-request.output.category}
      cases:
        urgent:
          - id: urgent-handler
            component: urgent-processor
            input: ${input}
        normal:
          - id: normal-handler
            component: normal-processor
            input: ${input}
        bulk:
          - id: bulk-handler
            component: bulk-processor
            input: ${input}
      default:
        - id: default-handler
          component: default-processor
          input: ${input}
          
  output: ${route-request.output}
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