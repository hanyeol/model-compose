# Workflow Component

The workflow component enables invoking and orchestrating other workflows within your model-compose application. It allows for nested workflow execution, workflow composition, and building complex multi-step processes by combining simpler workflows.

## Basic Configuration

```yaml
component:
  type: workflow
  workflow: process-documents
  input:
    documents: ${input.document_list}
    options: ${input.processing_options}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `workflow` |
| `actions` | array | `[]` | List of workflow actions |

### Action Configuration

Workflow actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `workflow` | string | `__default__` | Name of the workflow to execute |
| `input` | any | `null` | Input data supplied to the workflow |

## Usage Examples

### Simple Workflow Invocation

```yaml
component:
  type: workflow
  workflow: text-processing
  input:
    text: ${input.document_text}
    language: en
  output:
    processed_text: ${response.result}
    metadata: ${response.metadata}
```

### Multiple Workflow Actions

```yaml
component:
  type: workflow
  actions:
    - id: preprocess-data
      workflow: data-preprocessing
      input:
        raw_data: ${input.data}
        cleaning_rules: ${input.rules}
      output:
        cleaned_data: ${response.processed_data}
    
    - id: analyze-data
      workflow: data-analysis
      input:
        data: ${input.analysis_data}
        parameters: ${input.analysis_params}
      output:
        analysis_results: ${response.results}
        
    - id: generate-report
      workflow: report-generation
      input:
        analysis: ${input.analysis_results}
        template: ${input.report_template}
      output:
        report: ${response.generated_report}
```

### Conditional Workflow Execution

```yaml
component:
  type: workflow
  actions:
    - id: basic-processing
      workflow: basic-text-processing
      input:
        text: ${input.text}
      output:
        basic_result: ${response.result}
    
    - id: advanced-processing
      workflow: advanced-nlp-processing
      input:
        text: ${input.text}
        enable_advanced: ${input.advanced_mode | false}
      output:
        advanced_result: ${response.result}
        
    - id: merge-results
      workflow: result-merger
      input:
        basic: ${input.basic_result}
        advanced: ${input.advanced_result}
        merge_strategy: enhanced
      output:
        final_result: ${response.merged_result}
```

## Workflow Composition Patterns

### Sequential Processing Pipeline

Create a pipeline of workflows that process data sequentially:

```yaml
workflows:
  - id: document-processing-pipeline
    jobs:
      - id: extract-text
        component: workflow-runner
        action: extract
        input:
          documents: ${input.documents}
      
      - id: clean-text
        component: workflow-runner  
        action: clean
        input:
          raw_text: ${extract-text.output.extracted_text}
        depends_on: [ extract-text ]
      
      - id: analyze-sentiment
        component: workflow-runner
        action: analyze
        input:
          clean_text: ${clean-text.output.cleaned_text}
        depends_on: [ clean-text ]

components:
  - id: workflow-runner
    type: workflow
    actions:
      - id: extract
        workflow: text-extraction
        input: ${input}
        
      - id: clean
        workflow: text-cleaning
        input: ${input}
        
      - id: analyze
        workflow: sentiment-analysis
        input: ${input}
```

### Parallel Workflow Execution

Execute multiple workflows in parallel and combine results:

```yaml
workflows:
  - id: multi-model-analysis
    jobs:
      - id: model-a-analysis
        component: workflow-runner
        action: run-model-a
        input:
          data: ${input.data}
      
      - id: model-b-analysis  
        component: workflow-runner
        action: run-model-b
        input:
          data: ${input.data}
          
      - id: model-c-analysis
        component: workflow-runner
        action: run-model-c
        input:
          data: ${input.data}
      
      - id: ensemble-results
        component: workflow-runner
        action: ensemble
        input:
          model_a_result: ${model-a-analysis.output}
          model_b_result: ${model-b-analysis.output}
          model_c_result: ${model-c-analysis.output}
        depends_on: [ model-a-analysis, model-b-analysis, model-c-analysis ]

components:
  - id: workflow-runner
    type: workflow
    actions:
      - id: run-model-a
        workflow: model-a-inference
        input: ${input}
        
      - id: run-model-b
        workflow: model-b-inference
        input: ${input}
        
      - id: run-model-c
        workflow: model-c-inference
        input: ${input}
        
      - id: ensemble
        workflow: ensemble-combining
        input: ${input}
```

### Workflow Branching and Routing

Route data to different workflows based on conditions:

```yaml
component:
  type: workflow
  actions:
    - id: classify-document
      workflow: document-classifier
      input:
        document: ${input.document}
      output:
        document_type: ${response.classification}
        confidence: ${response.confidence}
    
    - id: process-legal-doc
      workflow: legal-document-processor
      input:
        document: ${input.document}
        # Only execute if classified as legal document
        condition: ${input.document_type == legal}
      output:
        legal_analysis: ${response.analysis}
    
    - id: process-technical-doc
      workflow: technical-document-processor
      input:
        document: ${input.document}
        condition: ${input.document_type == technical}
      output:
        technical_analysis: ${response.analysis}
        
    - id: process-general-doc
      workflow: general-document-processor
      input:
        document: ${input.document}
        condition: ${input.document_type == general}
      output:
        general_analysis: ${response.analysis}
```

## Error Handling and Fallbacks

Handle workflow failures with fallback workflows:

```yaml
component:
  type: workflow
  actions:
    - id: primary-processing
      workflow: advanced-text-processor
      input:
        text: ${input.text}
        advanced_options: ${input.options}
      output:
        result: ${response.processed_text}
      on_error:
        - id: fallback-processing
          workflow: basic-text-processor
          input:
            text: ${input.text}
          output:
            fallback_result: ${response.processed_text}
```

## Workflow Nesting and Modularity

Build complex systems from modular workflow components:

```yaml
# Main orchestration workflow
workflows:
  - id: content-management-system
    jobs:
      - id: content-ingestion
        component: workflow-orchestrator
        action: ingest-content
        input:
          sources: ${input.content_sources}
      
      - id: content-processing
        component: workflow-orchestrator
        action: process-content
        input:
          raw_content: ${content-ingestion.output.ingested_content}
        depends_on: [ content-ingestion ]
      
      - id: content-indexing
        component: workflow-orchestrator
        action: index-content
        input:
          processed_content: ${content-processing.output.processed_content}
        depends_on: [ content-processing ]

components:
  - id: workflow-orchestrator
    type: workflow
    actions:
      # Content ingestion sub-workflows
      - id: ingest-content
        workflow: content-ingestion-pipeline
        input: ${input}
        
      # Content processing sub-workflows  
      - id: process-content
        workflow: content-processing-pipeline
        input: ${input}
        
      # Content indexing sub-workflows
      - id: index-content
        workflow: content-indexing-pipeline
        input: ${input}

# Sub-workflows defined separately
workflows:
  - id: content-ingestion-pipeline
    jobs:
      - id: fetch-sources
        component: http-client
        # ... fetch content from various sources
      
      - id: validate-content
        component: validator
        # ... validate content format
        
  - id: content-processing-pipeline
    jobs:
      - id: extract-text
        component: text-extractor
        # ... extract text from various formats
      
      - id: clean-text
        component: text-cleaner
        # ... clean and normalize text
        
      - id: generate-embeddings
        component: embedding-model
        # ... generate vector embeddings
        
  - id: content-indexing-pipeline
    jobs:
      - id: store-embeddings
        component: vector-store
        # ... store in vector database
      
      - id: update-search-index
        component: search-indexer
        # ... update search index
```

## Data Flow and Transformations

Transform data between workflows:

```yaml
component:
  type: workflow
  actions:
    - id: extract-features
      workflow: feature-extraction
      input:
        data: ${input.raw_data}
        feature_types: [ textual, numerical, categorical ]
      output:
        features: ${response.extracted_features}
        
    - id: transform-features
      workflow: feature-transformation
      input:
        raw_features: ${input.features}
        transformations:
          - type: normalize
            columns: [ numerical_features ]
          - type: encode  
            columns: [ categorical_features ]
      output:
        transformed_features: ${response.features}
        
    - id: train-model
      workflow: model-training
      input:
        features: ${input.transformed_features}
        labels: ${input.labels}
        model_type: random_forest
      output:
        trained_model: ${response.model}
        metrics: ${response.evaluation_metrics}
```

## Batch and Streaming Processing

Process data in batches or streams using workflows:

```yaml
component:
  type: workflow
  actions:
    - id: batch-processing
      workflow: document-batch-processor
      input:
        documents: ${input.document_batch}
        batch_size: 50
        processing_options:
          extract_entities: true
          generate_summaries: true
      output:
        processed_batch: ${response.results}
        
    - id: streaming-processing
      workflow: real-time-processor
      input:
        data_stream: ${input.stream}
        window_size: 5m
        aggregation_function: mean
      output:
        aggregated_results: ${response.windowed_results}
```

## Integration Patterns

### API Gateway Pattern

Use workflows to orchestrate API calls:

```yaml
component:
  type: workflow
  actions:
    - id: authenticate-user
      workflow: user-authentication
      input:
        credentials: ${input.auth_data}
      output:
        auth_token: ${response.token}
        user_info: ${response.user}
        
    - id: authorize-request
      workflow: request-authorization
      input:
        user_info: ${input.user_info}
        requested_resource: ${input.resource}
      output:
        authorized: ${response.allowed}
        permissions: ${response.permissions}
        
    - id: process-request
      workflow: request-processor
      input:
        request_data: ${input.data}
        user_permissions: ${input.permissions}
      output:
        response_data: ${response.result}
```

### Event-Driven Processing

Chain workflows based on events:

```yaml
component:
  type: workflow
  actions:
    - id: handle-user-signup
      workflow: user-registration-handler
      input:
        user_data: ${input.signup_data}
      output:
        user_id: ${response.created_user_id}
        
    - id: send-welcome-email
      workflow: email-notification-sender
      input:
        user_id: ${input.user_id}
        email_template: welcome
      output:
        email_sent: ${response.success}
        
    - id: setup-user-preferences
      workflow: user-preference-initializer
      input:
        user_id: ${input.user_id}
        default_preferences: ${input.defaults}
      output:
        preferences_created: ${response.success}
```

## Variable Interpolation

Workflow components support dynamic configuration:

```yaml
component:
  type: workflow
  workflow: ${input.selected_workflow | default-workflow}
  input:
    data: ${input.workflow_data}
    options:
      processing_mode: ${env.PROCESSING_MODE | standard}
      max_retries: ${input.retry_count as integer | 3}
      timeout: ${input.timeout_seconds as integer | 300}
```

## Best Practices

1. **Modularity**: Design workflows as reusable, focused components
2. **Error Handling**: Implement proper error handling and fallback workflows
3. **Data Validation**: Validate inputs before passing to sub-workflows
4. **Resource Management**: Monitor resource usage in nested workflows
5. **Logging**: Implement comprehensive logging across workflow chains
6. **Testing**: Test workflows independently and in combination
7. **Documentation**: Document workflow interfaces and dependencies
8. **Performance**: Monitor and optimize workflow execution times

## Integration with Main Workflows

Reference workflow components in main workflow definitions:

```yaml
workflows:
  - id: main-processing-workflow
    jobs:
      - id: preprocess-data
        component: workflow-runner
        action: data-preprocessing
        input:
          raw_data: ${input.data}
          
      - id: run-analysis
        component: workflow-runner
        action: data-analysis
        input:
          preprocessed_data: ${preprocess-data.output.data}
        depends_on: [ preprocess-data ]
        
      - id: generate-insights
        component: workflow-runner
        action: insight-generation
        input:
          analysis_results: ${run-analysis.output.results}
        depends_on: [ run-analysis ]

components:
  - id: workflow-runner
    type: workflow
    actions:
      - id: data-preprocessing
        workflow: data-preprocessing-pipeline
        input: ${input}
        
      - id: data-analysis
        workflow: statistical-analysis
        input: ${input}
        
      - id: insight-generation
        workflow: insight-generator
        input: ${input}
```

## Common Use Cases

- **Microservice Orchestration**: Coordinate calls to multiple microservices
- **Multi-Stage Processing**: Build complex processing pipelines
- **Batch Job Management**: Orchestrate batch processing workflows
- **Event Processing**: Handle complex event-driven scenarios
- **API Composition**: Combine multiple API calls into cohesive workflows
- **Data Pipeline Management**: Orchestrate data processing stages
- **Business Process Automation**: Automate complex business workflows
- **Integration Patterns**: Connect disparate systems and services
