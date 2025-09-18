# Text Chunk Splitter Example

This example demonstrates how to use model-compose with a text splitter component to break down large text documents into smaller, manageable chunks. This is essential for processing large documents with AI models that have token limits or for creating efficient text embeddings.

## Overview

The Text Chunk Splitter provides intelligent text segmentation capabilities designed for AI and NLP workflows. This configuration showcases:

- Intelligent text chunking with configurable parameters
- Overlap management for context preservation
- Chunk size optimization for AI model compatibility
- Flexible separator-based splitting
- JSON output for easy integration

## Prerequisites

### Environment Setup

```bash
# Install model-compose
pip install -e .
```

### Optional Dependencies
```bash
# For advanced text processing
pip install nltk spacy
pip install tiktoken  # For token-aware splitting
```

## Architecture

### Component Configuration

#### Text Splitter (`text-splitter`)
- **Type**: Text processing component
- **Purpose**: Split large text into smaller chunks
- **Method**: Separator-based chunking with overlap
- **Output**: JSON array of text chunks

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `chunk_size` | 1000 | Maximum characters per chunk |
| `chunk_overlap` | 200 | Characters to overlap between chunks |
| `maximize_chunk` | true | Optimize chunk utilization |

## Workflow

### Text Chunk Splitter

Splits input text into smaller chunks based on separators, with optional overlap and chunk maximization.

```mermaid
graph LR
    A[Large Text Input] --> B[Text Splitter]
    B --> C[Chunk Analysis]
    C --> D[JSON Chunk Array]
```

**Input Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | Yes | - | Text to split into chunks |
| `chunk_size` | integer | No | 1000 | Maximum characters per chunk |
| `chunk_overlap` | integer | No | 200 | Characters to overlap between chunks |
| `maximize_chunk` | boolean | No | true | Optimize chunk size utilization |

**Output:**
- JSON array of text chunks
- Each chunk respects size limits
- Overlaps maintain context between chunks

## Text Splitting Strategies

### Chunk Size Configuration

| Use Case | Chunk Size | Overlap | Maximize | Description |
|----------|------------|---------|----------|-------------|
| **AI Models** | 512-2048 | 50-200 | true | Model token limits |
| **Embeddings** | 200-500 | 50-100 | true | Semantic coherence |
| **Search** | 150-300 | 25-50 | false | Query matching |
| **Summarization** | 1000-3000 | 100-300 | true | Context preservation |

### Separator Strategies

The text splitter uses intelligent separator detection:

1. **Paragraph breaks** (`\n\n`)
2. **Sentence endings** (`. `, `! `, `? `)
3. **Line breaks** (`\n`)
4. **Word boundaries** (` `)
5. **Character boundaries** (fallback)

## How to Run Instructions

### 1. Start the Service

```bash
# Navigate to the example directory
cd examples/split-text

# Start the controller
model-compose up
```

This starts:
- HTTP API server on port 8080 (base path: `/api`)
- Gradio web interface on port 8081

### 2. Access the Web UI

Open http://localhost:8081 in your browser to interact with the text splitting service through a web interface.

### 3. API Usage

#### Basic Text Splitting
```bash
curl -X POST http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This is a long document that needs to be split into smaller chunks for processing by AI models. Each chunk should maintain context while respecting size limits."
  }'
```

#### Custom Chunk Size
```bash
curl -X POST http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Large document text here...",
    "chunk_size": 500,
    "chunk_overlap": 50
  }'
```

#### Optimized for Embeddings
```bash
curl -X POST http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Document for embedding generation...",
    "chunk_size": 300,
    "chunk_overlap": 50,
    "maximize_chunk": false
  }'
```

#### Large Document Processing
```bash
curl -X POST http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Very large document text...",
    "chunk_size": 2000,
    "chunk_overlap": 300,
    "maximize_chunk": true
  }'
```

### Sample Response

```json
{
  "chunks": [
    "This is the first chunk of text that contains the beginning of the document. It maintains natural boundaries while respecting the specified size limits.",
    "boundaries while respecting the specified size limits. This is the second chunk that overlaps with the first to maintain context continuity.",
    "context continuity. This is the final chunk that completes the document processing with proper overlap management."
  ],
  "total_chunks": 3,
  "average_chunk_size": 145,
  "overlap_efficiency": 0.85
}
```

## Advanced Configuration

### Token-Aware Splitting

```yaml
workflows:
  - id: token-aware-splitting
    title: Token-Aware Text Chunking
    jobs:
      - id: count-tokens
        component: token-counter
        input:
          text: ${input.text}
          model: ${input.model | gpt-3.5-turbo}

      - id: split-by-tokens
        component: text-splitter
        input:
          text: ${input.text}
          chunk_size: ${jobs.count-tokens.output.max_tokens * 0.8}
          chunk_overlap: ${input.overlap_tokens | 50}
        depends_on: [count-tokens]
```

### Batch Document Processing

```yaml
workflows:
  - id: batch-text-splitting
    title: Batch Document Processing
    jobs:
      - id: process-documents
        component: text-splitter
        input:
          text: ${input.documents[*].content}
          chunk_size: ${input.chunk_size | 1000}
          chunk_overlap: ${input.overlap | 200}
        output:
          document_chunks: ${output[*].chunks}
          chunk_metadata: ${output[*].metadata}
```

### Content-Type Aware Splitting

```yaml
workflows:
  - id: adaptive-splitting
    title: Content-Type Adaptive Splitting
    jobs:
      - id: analyze-content
        component: content-analyzer
        input:
          text: ${input.text}

      - id: split-technical
        component: text-splitter
        input:
          text: ${input.text}
          chunk_size: 800
          chunk_overlap: 150
        condition: ${jobs.analyze-content.output.type} == "technical"
        depends_on: [analyze-content]

      - id: split-narrative
        component: text-splitter
        input:
          text: ${input.text}
          chunk_size: 1200
          chunk_overlap: 250
        condition: ${jobs.analyze-content.output.type} == "narrative"
        depends_on: [analyze-content]
```

### Quality-Controlled Splitting

```yaml
workflows:
  - id: quality-controlled-splitting
    title: Quality-Controlled Text Splitting
    jobs:
      - id: initial-split
        component: text-splitter
        input:
          text: ${input.text}
          chunk_size: ${input.chunk_size | 1000}
          chunk_overlap: ${input.overlap | 200}

      - id: validate-chunks
        component: chunk-validator
        input:
          chunks: ${jobs.initial-split.output.chunks}
          min_coherence: ${input.min_coherence | 0.7}
        depends_on: [initial-split]

      - id: re-split-if-needed
        component: text-splitter
        input:
          text: ${input.text}
          chunk_size: ${jobs.initial-split.input.chunk_size * 0.8}
          chunk_overlap: ${jobs.initial-split.input.chunk_overlap * 1.2}
        condition: ${jobs.validate-chunks.output.quality_score} < 0.7
        depends_on: [validate-chunks]
```

## Optimization Strategies

### AI Model Integration

#### GPT Models (Token Limits)
```bash
# GPT-3.5-turbo (4,096 tokens)
curl -X POST http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{
    "text": "document text...",
    "chunk_size": 3000,
    "chunk_overlap": 300
  }'

# GPT-4 (8,192 tokens)
curl -X POST http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{
    "text": "document text...",
    "chunk_size": 6000,
    "chunk_overlap": 600
  }'
```

#### Embedding Models
```bash
# OpenAI text-embedding-ada-002 (8,191 tokens)
curl -X POST http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{
    "text": "document text...",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "maximize_chunk": false
  }'
```

### Document Type Optimization

#### Technical Documentation
- **Chunk Size**: 800-1200 characters
- **Overlap**: 100-200 characters
- **Strategy**: Preserve code blocks and technical terms

#### Narrative Text
- **Chunk Size**: 1000-1500 characters
- **Overlap**: 200-300 characters
- **Strategy**: Maintain story flow and character context

#### Academic Papers
- **Chunk Size**: 1200-2000 characters
- **Overlap**: 200-400 characters
- **Strategy**: Preserve citations and arguments

#### Legal Documents
- **Chunk Size**: 800-1000 characters
- **Overlap**: 150-250 characters
- **Strategy**: Maintain legal clause integrity

## Integration Examples

### RAG (Retrieval Augmented Generation) Pipeline

```yaml
workflows:
  - id: rag-document-preparation
    title: RAG Document Preparation
    jobs:
      - id: split-document
        component: text-splitter
        input:
          text: ${input.document}
          chunk_size: 400
          chunk_overlap: 50

      - id: generate-embeddings
        component: embedding-model
        input:
          text: ${jobs.split-document.output.chunks[*]}
        depends_on: [split-document]

      - id: store-in-vector-db
        component: vector-store
        input:
          embeddings: ${jobs.generate-embeddings.output[*]}
          metadata: ${jobs.split-document.output.metadata[*]}
        depends_on: [generate-embeddings]
```

### Document Summarization Pipeline

```yaml
workflows:
  - id: hierarchical-summarization
    title: Hierarchical Document Summarization
    jobs:
      - id: split-document
        component: text-splitter
        input:
          text: ${input.document}
          chunk_size: 2000
          chunk_overlap: 300

      - id: summarize-chunks
        component: gpt-4
        input:
          text: ${jobs.split-document.output.chunks[*]}
          prompt: "Summarize this text chunk in 2-3 sentences:"
        depends_on: [split-document]

      - id: combine-summaries
        component: text-combiner
        input:
          chunks: ${jobs.summarize-chunks.output[*]}
        depends_on: [summarize-chunks]

      - id: final-summary
        component: gpt-4
        input:
          text: ${jobs.combine-summaries.output}
          prompt: "Create a comprehensive summary of this document:"
        depends_on: [combine-summaries]
```

### Translation Pipeline

```yaml
workflows:
  - id: chunked-translation
    title: Large Document Translation
    jobs:
      - id: split-source
        component: text-splitter
        input:
          text: ${input.source_text}
          chunk_size: 1500
          chunk_overlap: 200

      - id: translate-chunks
        component: gpt-4
        input:
          text: ${jobs.split-source.output.chunks[*]}
          prompt: "Translate this text to ${input.target_language}:"
        depends_on: [split-source]

      - id: combine-translation
        component: text-combiner
        input:
          chunks: ${jobs.translate-chunks.output[*]}
          remove_overlap: true
        depends_on: [translate-chunks]
```

### Content Analysis Pipeline

```yaml
workflows:
  - id: content-analysis
    title: Large Document Content Analysis
    jobs:
      - id: split-content
        component: text-splitter
        input:
          text: ${input.document}
          chunk_size: 1000
          chunk_overlap: 150

      - id: analyze-sentiment
        component: sentiment-analyzer
        input:
          text: ${jobs.split-content.output.chunks[*]}
        depends_on: [split-content]

      - id: extract-entities
        component: entity-extractor
        input:
          text: ${jobs.split-content.output.chunks[*]}
        depends_on: [split-content]

      - id: generate-insights
        component: insight-generator
        input:
          sentiments: ${jobs.analyze-sentiment.output[*]}
          entities: ${jobs.extract-entities.output[*]}
          original_chunks: ${jobs.split-content.output.chunks[*]}
        depends_on: [analyze-sentiment, extract-entities]
```

## Performance Optimization

### Memory Efficiency
```bash
# For very large documents, use streaming
curl -X POST http://localhost:8080/api \
  -H "Content-Type: application/json" \
  -d '{
    "text": "extremely large document...",
    "chunk_size": 1000,
    "chunk_overlap": 100,
    "streaming": true
  }'
```

### Processing Speed
```yaml
# Parallel chunk processing
workflows:
  - id: fast-processing
    jobs:
      - id: split-text
        component: text-splitter
        input:
          text: ${input.text}
          chunk_size: 800

      - id: parallel-processing
        component: parallel-processor
        input:
          chunks: ${jobs.split-text.output.chunks}
          batch_size: 10
        depends_on: [split-text]
```

### Quality Metrics

#### Chunk Quality Assessment
- **Coherence Score**: Semantic consistency within chunks
- **Overlap Efficiency**: Context preservation between chunks
- **Size Distribution**: Consistency of chunk sizes
- **Boundary Quality**: Natural language boundaries

## Use Cases

### Document Processing
- **Legal Document Analysis**: Split contracts and agreements
- **Research Paper Processing**: Chunk academic papers for analysis
- **Technical Documentation**: Process API docs and manuals
- **Book Digitization**: Convert books for digital processing

### AI/ML Workflows
- **Training Data Preparation**: Create training datasets
- **Fine-tuning**: Prepare text for model fine-tuning
- **Prompt Engineering**: Split prompts for A/B testing
- **Model Evaluation**: Create test sets from large documents

### Content Management
- **CMS Integration**: Chunk content for better searchability
- **Knowledge Bases**: Organize information into searchable units
- **Content Migration**: Split legacy content for modern systems
- **SEO Optimization**: Create content chunks for search optimization

### Data Science
- **Text Analytics**: Prepare data for NLP analysis
- **Sentiment Analysis**: Process large documents efficiently
- **Topic Modeling**: Create appropriate text segments
- **Information Extraction**: Extract entities from large texts

## Best Practices

### Chunk Size Selection
- **Model Limits**: Stay within token/character limits
- **Content Type**: Adjust for technical vs. narrative text
- **Processing Goals**: Optimize for specific AI tasks
- **Memory Constraints**: Consider system limitations

### Overlap Strategy
- **Context Preservation**: Maintain semantic continuity
- **Processing Efficiency**: Balance overlap with speed
- **Redundancy Management**: Avoid excessive duplication
- **Quality Metrics**: Monitor overlap effectiveness

### Quality Assurance
- **Boundary Validation**: Check for clean breaks
- **Content Integrity**: Ensure no information loss
- **Size Distribution**: Monitor chunk size consistency
- **Performance Monitoring**: Track processing metrics

### Error Handling
```yaml
# Robust splitting with fallbacks
workflows:
  - id: robust-splitting
    jobs:
      - id: primary-split
        component: text-splitter
        input:
          text: ${input.text}
          chunk_size: ${input.chunk_size}

      - id: fallback-split
        component: simple-splitter
        input:
          text: ${input.text}
          chunk_size: ${input.chunk_size * 0.8}
        condition: ${jobs.primary-split.status} == "failed"
        depends_on: [primary-split]
```