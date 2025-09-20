# Multi-Service Workflows

Multi-service workflows in model-compose enable complex AI pipelines that orchestrate multiple services, models, and data processing steps. This guide covers patterns and best practices for building distributed AI workflows.

## Overview

Multi-service workflows allow you to:
- Chain multiple AI models and services together
- Process data through multiple transformation stages  
- Implement parallel processing patterns
- Build complex AI pipelines with conditional logic
- Integrate external APIs with local models

## Basic Multi-Service Pattern

### Sequential Processing

```yaml
components:
  - id: text-preprocessor
    type: shell
    command: [ python, preprocess.py ]
    
  - id: sentiment-analyzer
    type: model
    model: cardiffnlp/twitter-roberta-base-sentiment-latest
    task: text-classification
    
  - id: response-generator
    type: http-client
    url: https://api.openai.com/v1/chat/completions

workflows:
  - id: sentiment-response
    jobs:
      - id: preprocess
        component: text-preprocessor
        input:
          text: ${input.message}
          
      - id: analyze
        component: sentiment-analyzer
        input:
          text: ${jobs.preprocess.output.stdout}
        depends_on: [ preprocess ]
        
      - id: generate
        component: response-generator
        input:
          model: gpt-3.5-turbo
          messages:
            - role: system
              content: "Respond based on sentiment: ${jobs.analyze.output.label}"
            - role: user
              content: ${jobs.preprocess.output.stdout}
        depends_on: [ analyze ]
```

### Parallel Processing

```yaml
workflows:
  - id: multi-model-analysis
    jobs:
      - id: sentiment
        component: sentiment-analyzer
        input:
          text: ${input.text}
          
      - id: emotion
        component: emotion-detector
        input:
          text: ${input.text}
          
      - id: entities
        component: ner-model
        input:
          text: ${input.text}
          
      - id: summarize
        component: summarization-model
        input:
          sentiment: ${jobs.sentiment.output.label}
          emotion: ${jobs.emotion.output.emotion}
          entities: ${jobs.entities.output.entities}
          original_text: ${input.text}
        depends_on: [ sentiment, emotion, entities ]
```

## Service Patterns

### API Gateway Pattern

```yaml
controller:
  type: http-server
  port: 8080

components:
  - id: auth-service
    type: http-server
    start: [ python, auth_server.py ]
    port: 8001
    
  - id: user-service
    type: http-server
    start: [ python, user_server.py ]
    port: 8002
    
  - id: ai-service
    type: http-server
    start: [ python, ai_server.py ]
    port: 8003

workflows:
  - id: authenticated-ai-request
    jobs:
      - id: authenticate
        component: auth-service
        input:
          token: ${input.auth_token}
          
      - id: get-user-context
        component: user-service
        input:
          user_id: ${jobs.authenticate.output.user_id}
        depends_on: [ authenticate ]
        
      - id: ai-processing
        component: ai-service
        input:
          request: ${input.request}
          context: ${jobs.get-user-context.output.context}
        depends_on: [ get-user-context ]
```

### Microservice Architecture

```yaml
components:
  - id: image-processor
    type: http-server
    start: [ python, image_service.py ]
    port: 8001
    
  - id: text-extractor
    type: http-server
    start: [ python, ocr_service.py ]
    port: 8002
    
  - id: content-analyzer
    type: http-server
    start: [ python, analysis_service.py ]
    port: 8003
    
  - id: report-generator
    type: http-server
    start: [ python, report_service.py ]
    port: 8004

workflows:
  - id: document-processing
    jobs:
      - id: process-image
        component: image-processor
        input:
          image_url: ${input.document_url}
          
      - id: extract-text
        component: text-extractor
        input:
          processed_image: ${jobs.process-image.output.image_data}
        depends_on: [ process-image ]
        
      - id: analyze-content
        component: content-analyzer
        input:
          text: ${jobs.extract-text.output.text}
          metadata: ${jobs.process-image.output.metadata}
        depends_on: [ extract-text ]
        
      - id: generate-report
        component: report-generator
        input:
          analysis: ${jobs.analyze-content.output}
          original_document: ${input.document_url}
        depends_on: [ analyze-content ]
```

## Advanced Patterns

### Fan-Out/Fan-In Pattern

```yaml
workflows:
  - id: distributed-processing
    jobs:
      # Fan-out: Split work across multiple services
      - id: chunk-data
        component: data-splitter
        input:
          data: ${input.large_dataset}
          
      - id: process-chunk-1
        component: processing-service-1
        input:
          chunk: ${jobs.chunk-data.output.chunks[0]}
        depends_on: [ chunk-data ]
        
      - id: process-chunk-2
        component: processing-service-2
        input:
          chunk: ${jobs.chunk-data.output.chunks[1]}
        depends_on: [ chunk-data ]
        
      - id: process-chunk-3
        component: processing-service-3
        input:
          chunk: ${jobs.chunk-data.output.chunks[2]}
        depends_on: [ chunk-data ]
        
      # Fan-in: Combine results
      - id: combine-results
        component: result-aggregator
        input:
          results:
            - ${jobs.process-chunk-1.output}
            - ${jobs.process-chunk-2.output}  
            - ${jobs.process-chunk-3.output}
        depends_on: [ process-chunk-1, process-chunk-2, process-chunk-3 ]
```

### Circuit Breaker Pattern

```yaml
components:
  - id: primary-service
    type: http-client
    url: https://api.primary-service.com
    timeout: 5000
    retry:
      attempts: 3
      delay: 1000
      
  - id: fallback-service
    type: http-client
    url: https://api.fallback-service.com

workflows:
  - id: resilient-processing
    jobs:
      - id: try-primary
        component: primary-service
        input: ${input}

      - id: check-primary-success
        type: if
        conditions:
          - operator: eq
            input: ${jobs.try-primary.status}
            value: success
            if_true: format-primary-result
            if_false: fallback
        depends_on: [ try-primary ]
        
      - id: format-primary-result
        component: result-formatter
        input:
          result: ${jobs.try-primary.output}
          source: primary
          
      - id: fallback
        component: fallback-service
        input: ${input}
        
      - id: format-fallback-result
        component: result-formatter
        input:
          result: ${jobs.fallback.output}
          source: fallback
        depends_on: [ fallback ]
```

## Data Flow Management

### Variable Interpolation

```yaml
workflows:
  - id: complex-data-flow
    variables:
      api_key: ${env.API_KEY}
      base_url: https://api.example.com
      
    jobs:
      - id: fetch-data
        component: data-fetcher
        input:
          url: ${variables.base_url}/data
          auth: ${variables.api_key}
          
      - id: transform
        component: data-transformer
        input:
          raw_data: ${jobs.fetch-data.output.data}
          format: ${input.output_format}
        depends_on: [ fetch-data ]
        
      - id: validate
        component: data-validator
        input:
          data: ${jobs.transform.output.transformed_data}
          schema: ${input.validation_schema}
        depends_on: [ transform ]
```

### Conditional Execution

```yaml
workflows:
  - id: conditional-workflow
    jobs:
      - id: analyze-input
        component: input-analyzer
        input: ${input}
        
      - id: text-processing
        component: text-processor
        input: ${input}
        condition: ${jobs.analyze-input.output.type == 'text'}
        depends_on: [ analyze-input ]
        
      - id: image-processing
        component: image-processor
        input: ${input}
        condition: ${jobs.analyze-input.output.type == 'image'}
        depends_on: [ analyze-input ]
        
      - id: finalize
        component: result-finalizer
        input:
          result: ${jobs.analyze-input.output.type == 'text' ? jobs.text-processing.output : jobs.image-processing.output}
        depends_on: [ text-processing, image-processing ]
```

## Service Discovery and Load Balancing

### Service Registry

```yaml
components:
  - id: service-registry
    type: http-server
    start: [ python, registry.py ]
    port: 8500
    
  - id: load-balancer
    type: http-client
    url: http://localhost:8500/discover
    
workflows:
  - id: load-balanced-request
    jobs:
      - id: discover-service
        component: load-balancer
        input:
          service_name: ai-processor
          
      - id: process-request
        component: dynamic-client
        input:
          url: ${jobs.discover-service.output.endpoint}
          data: ${input}
        depends_on: [ discover-service ]
```

### Health Checking

```yaml
components:
  - id: health-checker
    type: http-client
    method: GET
    path: /health
    
workflows:
  - id: monitored-workflow
    jobs:
      - id: check-service-health
        component: health-checker
        input:
          service_url: ${input.target_service}
          
      - id: execute-if-healthy
        component: main-processor
        input: ${input}
        condition: ${jobs.check-service-health.output.status == 'healthy'}
        depends_on: [ check-service-health ]
        
      - id: fallback-if-unhealthy
        component: fallback-processor
        input: ${input}
        condition: ${jobs.check-service-health.output.status != 'healthy'}
        depends_on: [ check-service-health ]
```

## Error Handling and Resilience

### Retry Logic

```yaml
components:
  - id: unreliable-service
    type: http-client
    url: https://api.unreliable-service.com
    retry:
      attempts: 5
      delay: 2000
      backoff: exponential
      max_delay: 30000
```

### Dead Letter Queue

```yaml
workflows:
  - id: resilient-processing
    jobs:
      - id: primary-processing
        component: main-processor
        input: ${input}
        on_error: continue
        
      - id: dead-letter
        component: error-handler
        input:
          failed_job: primary-processing
          error: ${jobs.primary-processing.error}
          original_input: ${input}
        condition: ${jobs.primary-processing.status == 'failed'}
```

## Monitoring and Observability

### Request Tracing

```yaml
workflows:
  - id: traced-workflow
    metadata:
      trace_id: ${uuid()}
      
    jobs:
      - id: service-a
        component: service-a
        input:
          trace_id: ${metadata.trace_id}
          data: ${input}
          
      - id: service-b
        component: service-b
        input:
          trace_id: ${metadata.trace_id}
          data: ${jobs.service-a.output}
        depends_on: [ service-a ]
```

### Performance Metrics

```yaml
components:
  - id: metrics-collector
    type: http-server
    start: [ python, metrics_server.py ]
    port: 9090
    
workflows:
  - id: monitored-workflow
    jobs:
      - id: start-timer
        component: metrics-collector
        input:
          action: start_timer
          workflow_id: ${workflow.id}
          
      - id: main-processing
        component: main-processor
        input: ${input}
        depends_on: [ start-timer ]
        
      - id: end-timer
        component: metrics-collector
        input:
          action: end_timer
          workflow_id: ${workflow.id}
          duration: ${jobs.main-processing.duration}
        depends_on: [ main-processing ]
```

## Best Practices

### Service Design

1. **Single Responsibility**: Each service should have one clear purpose
2. **Stateless**: Services should be stateless when possible
3. **Health Endpoints**: Implement health check endpoints
4. **Graceful Degradation**: Handle service failures gracefully
5. **Timeout Configuration**: Set appropriate timeouts for all services

### Workflow Design

1. **Clear Dependencies**: Explicitly define job dependencies
2. **Error Handling**: Plan for failure scenarios
3. **Resource Management**: Consider resource usage across services
4. **Testing**: Test individual services and complete workflows
5. **Documentation**: Document service interfaces and data formats

### Performance Optimization

1. **Parallel Execution**: Run independent jobs in parallel
2. **Caching**: Cache results where appropriate
3. **Connection Pooling**: Reuse connections between services
4. **Load Balancing**: Distribute load across service instances
5. **Resource Limits**: Set appropriate resource limits

## Example: Complete Multi-Service Pipeline

```yaml
controller:
  type: http-server
  port: 8080
  webui:
    port: 8081

components:
  - id: content-fetcher
    type: http-client
    
  - id: text-processor
    type: model
    model: sentence-transformers/all-MiniLM-L6-v2
    task: text-embedding
    
  - id: image-analyzer
    type: model
    model: microsoft/DialoGPT-medium
    task: image-to-text
    
  - id: sentiment-analyzer
    type: model
    model: cardiffnlp/twitter-roberta-base-sentiment-latest
    task: text-classification
    
  - id: report-generator
    type: http-client
    url: https://api.openai.com/v1/chat/completions

workflows:
  - id: content-analysis-pipeline
    jobs:
      - id: fetch-content
        component: content-fetcher
        input:
          url: ${input.content_url}
          
      - id: process-text
        component: text-processor
        input:
          text: ${jobs.fetch-content.output.text_content}
        depends_on: [ fetch-content ]
        condition: ${jobs.fetch-content.output.has_text}
        
      - id: analyze-image
        component: image-analyzer
        input:
          image: ${jobs.fetch-content.output.image_content}
        depends_on: [ fetch-content ]
        condition: ${jobs.fetch-content.output.has_image}
        
      - id: sentiment-analysis
        component: sentiment-analyzer
        input:
          text: ${jobs.fetch-content.output.text_content}
        depends_on: [ fetch-content ]
        condition: ${jobs.fetch-content.output.has_text}
        
      - id: generate-report
        component: report-generator
        input:
          model: gpt-4
          messages:
            - role: system
              content: "Generate a comprehensive analysis report"
            - role: user
              content: |
                Content Analysis Results:
                Text Embeddings: ${jobs.process-text.output.embeddings}
                Image Description: ${jobs.analyze-image.output.description}
                Sentiment: ${jobs.sentiment-analysis.output.label}
                Original URL: ${input.content_url}
        depends_on: [ process-text, analyze-image, sentiment-analysis ]
```

This comprehensive guide provides the foundation for building complex, multi-service AI workflows with model-compose. Each pattern can be adapted and combined to meet specific use case requirements.