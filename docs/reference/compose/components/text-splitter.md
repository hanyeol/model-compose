# Text Splitter Component

The text splitter component enables splitting large text documents into smaller, manageable chunks. This is essential for processing long documents with language models that have token limits, creating embeddings for vector databases, or preparing text for batch processing operations.

## Basic Configuration

```yaml
component:
  type: text-splitter
  text: ${input.document}
  chunk_size: 1000
  chunk_overlap: 200
  separators: [ "\n\n", "\n", " ", "" ]
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `text-splitter` |
| `actions` | array | `[]` | List of text splitting actions |

### Action Configuration

Text splitter actions support the following options:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `text` | string | **required** | Input text to be split into chunks |
| `chunk_size` | integer | `1000` | Maximum number of characters per chunk |
| `chunk_overlap` | integer | `200` | Number of overlapping characters between chunks |
| `separators` | array | `null` | Custom separators for splitting (defaults to standard text separators) |
| `stream` | boolean | `false` | Whether to stream chunks one by one instead of returning full list |

## Usage Examples

### Basic Text Splitting

```yaml
component:
  type: text-splitter
  text: ${input.document_text}
  chunk_size: 1000
  chunk_overlap: 200
  output:
    chunks: ${response.chunks}
    chunk_count: ${response.chunks | length}
```

### Custom Separator Splitting

```yaml
component:
  type: text-splitter
  text: ${input.article}
  chunk_size: 500
  chunk_overlap: 50
  separators: [ "\n\n", "\n", ". ", " ", "" ]
  output:
    text_chunks: ${response.chunks}
    total_chunks: ${response.chunks | length}
```

### Multiple Splitting Strategies

```yaml
component:
  type: text-splitter
  actions:
    - id: paragraph-splitting
      text: ${input.document}
      chunk_size: 2000
      chunk_overlap: 100
      separators: [ "\n\n", "\n" ]
      output:
        paragraph_chunks: ${response.chunks}
    
    - id: sentence-splitting
      text: ${input.document}
      chunk_size: 500
      chunk_overlap: 50
      separators: [ ". ", "! ", "? ", "\n" ]
      output:
        sentence_chunks: ${response.chunks}
        
    - id: word-splitting
      text: ${input.document}
      chunk_size: 200
      chunk_overlap: 20
      separators: [ " ", "\n", "\t" ]
      output:
        word_chunks: ${response.chunks}
```

### Streaming Text Chunks

```yaml
component:
  type: text-splitter
  text: ${input.large_document}
  chunk_size: 1500
  chunk_overlap: 150
  stream: true
  output:
    # Streaming output provides chunks one by one
    streaming_chunks: ${response.stream}
```

## Separator Strategies

### Hierarchical Separators

Use hierarchical separators to maintain document structure:

```yaml
component:
  type: text-splitter
  text: ${input.structured_document}
  separators: [
    "\n\n\n",    # Major sections
    "\n\n",      # Paragraphs
    "\n",        # Lines
    ". ",        # Sentences
    " ",         # Words
    ""           # Characters (last resort)
  ]
  chunk_size: 1000
  chunk_overlap: 100
```

### Document-Type Specific Separators

#### Markdown Documents

```yaml
component:
  type: text-splitter
  text: ${input.markdown_content}
  separators: [
    "\n## ",     # Sections
    "\n### ",    # Subsections
    "\n\n",      # Paragraphs
    "\n",        # Lines
    " ",         # Words
    ""
  ]
  chunk_size: 800
  chunk_overlap: 80
```

#### Code Documents

```yaml
component:
  type: text-splitter
  text: ${input.source_code}
  separators: [
    "\nclass ",      # Class definitions
    "\ndef ",        # Function definitions
    "\n\n",          # Empty lines
    "\n",            # Line breaks
    " ",             # Spaces
    ""
  ]
  chunk_size: 1200
  chunk_overlap: 100
```

#### Academic Papers

```yaml
component:
  type: text-splitter
  text: ${input.research_paper}
  separators: [
    "\n# ",          # Main sections
    "\n## ",         # Subsections
    "\n\n",          # Paragraphs
    ". ",            # Sentences
    " ",             # Words
    ""
  ]
  chunk_size: 1500
  chunk_overlap: 150
```

## Chunk Overlap Strategies

### Minimal Overlap for Independent Processing

```yaml
component:
  type: text-splitter
  text: ${input.text}
  chunk_size: 1000
  chunk_overlap: 0      # No overlap - for independent chunk processing
```

### Moderate Overlap for Context Preservation

```yaml
component:
  type: text-splitter
  text: ${input.text}
  chunk_size: 1000
  chunk_overlap: 200    # 20% overlap - maintains context between chunks
```

### High Overlap for Semantic Continuity

```yaml
component:
  type: text-splitter
  text: ${input.text}
  chunk_size: 1000
  chunk_overlap: 400    # 40% overlap - ensures semantic continuity
```

## Integration with Vector Databases

Create embeddings for vector storage:

```yaml
workflows:
  - id: document-indexing
    jobs:
      - id: split-document
        component: text-splitter
        input:
          document: ${input.document_content}
        output:
          text_chunks: ${output.chunks}
          
      - id: generate-embeddings
        component: embedding-model
        input:
          texts: ${split-document.output.text_chunks}
        output:
          embeddings: ${output.embeddings}
        depends_on: [ split-document ]
          
      - id: store-vectors
        component: vector-store
        action: batch-insert
        input:
          vectors: ${generate-embeddings.output.embeddings}
          metadata: ${input.metadata}
          chunks: ${split-document.output.text_chunks}
        depends_on: [ generate-embeddings ]

components:
  - id: text-splitter
    type: text-splitter
    text: ${input.document}
    chunk_size: 1000
    chunk_overlap: 200
    separators: [ "\n\n", "\n", ". ", " ", "" ]
    
  - id: embedding-model
    type: model
    task: text-embedding
    model: sentence-transformers/all-MiniLM-L6-v2
    text: ${input.texts}
    
  - id: vector-store
    type: vector-store
    driver: chroma
    collection: documents
    actions:
      - id: batch-insert
        method: insert
        vector: ${input.vectors}
        metadata: 
          text: ${input.chunks}
          document_id: ${input.metadata.document_id}
```

## RAG System Integration

Prepare documents for Retrieval-Augmented Generation:

```yaml
workflows:
  - id: prepare-knowledge-base
    jobs:
      - id: split-documents
        component: document-splitter
        input:
          documents: ${input.document_collection}
        output:
          all_chunks: ${output.processed_chunks}
          
      - id: filter-chunks
        component: chunk-filter
        input:
          chunks: ${split-documents.output.all_chunks}
          min_length: 100
          max_length: 2000
        output:
          filtered_chunks: ${output.valid_chunks}
        depends_on: [ split-documents ]
          
      - id: create-embeddings
        component: embedding-model
        input:
          texts: ${filter-chunks.output.filtered_chunks}
        depends_on: [ filter-chunks ]
        
      - id: index-knowledge
        component: vector-store
        input:
          embeddings: ${create-embeddings.output.embeddings}
          text_chunks: ${filter-chunks.output.filtered_chunks}
        depends_on: [ create-embeddings ]

components:
  - id: document-splitter
    type: text-splitter
    actions:
      - id: split-by-document
        text: ${input.document_text}
        chunk_size: 1200
        chunk_overlap: 120
        separators: [ "\n\n", "\n", ". ", " " ]
        output:
          processed_chunks: ${response.chunks}
```

## Batch Processing

Process multiple documents efficiently:

```yaml
workflows:
  - id: batch-document-processing
    jobs:
      - id: split-all-documents
        component: batch-splitter
        input:
          document_batch: ${input.documents}
        output:
          chunked_documents: ${output.batch_results}
          
      - id: process-chunks
        component: text-processor
        input:
          chunk_batches: ${split-all-documents.output.chunked_documents}
        depends_on: [ split-all-documents ]

components:
  - id: batch-splitter
    type: text-splitter
    actions:
      - id: process-batch
        text: ${input.document_batch}  # Array of documents
        chunk_size: 1000
        chunk_overlap: 150
        separators: [ "\n\n", "\n", ". ", " ", "" ]
        output:
          batch_results: ${response.chunks}
```

## Advanced Configuration Examples

### Adaptive Chunk Sizing

Adjust chunk size based on content type:

```yaml
component:
  type: text-splitter
  actions:
    - id: technical-content
      text: ${input.technical_doc}
      chunk_size: 1500  # Larger chunks for technical content
      chunk_overlap: 150
      separators: [ "\n## ", "\n\n", "\n", " " ]
      
    - id: narrative-content
      text: ${input.story}
      chunk_size: 800   # Smaller chunks for narrative content
      chunk_overlap: 100
      separators: [ "\n\n", ". ", " " ]
      
    - id: code-content
      text: ${input.source_code}
      chunk_size: 2000  # Large chunks to preserve code structure
      chunk_overlap: 200
      separators: [ "\nclass ", "\ndef ", "\n\n", "\n" ]
```

### Quality-Based Filtering

Filter chunks based on quality criteria:

```yaml
workflows:
  - id: quality-chunking
    jobs:
      - id: initial-split
        component: text-splitter
        input:
          text: ${input.document}
          
      - id: filter-quality
        component: chunk-quality-filter
        input:
          chunks: ${initial-split.output.chunks}
          min_words: 20
          max_words: 500
          filter_short_sentences: true
        depends_on: [ initial-split ]
        
components:
  - id: text-splitter
    type: text-splitter
    text: ${input.text}
    chunk_size: 1000
    chunk_overlap: 100
    output:
      chunks: ${response.chunks}
      # Additional quality metrics
      avg_chunk_length: ${response.chunks | map(length) | avg}
      chunk_lengths: ${response.chunks | map(length)}
```

### Streaming for Large Documents

Handle very large documents with streaming:

```yaml
component:
  type: text-splitter
  text: ${input.large_document}  # Multi-GB document
  chunk_size: 2000
  chunk_overlap: 200
  stream: true
  output:
    # Process chunks as they become available
    chunk_stream: ${response.stream}
```

## Overlap Visualization

Understanding how overlap works:

```yaml
# Example with chunk_size=100, chunk_overlap=20
# Document: "This is a very long document that needs to be split into smaller chunks for processing..."
#
# Chunk 1: "This is a very long document that needs to be split into smaller chunks for proces" (100 chars)
# Chunk 2: "chunks for processing with some additional text that continues the document..." (starts 80 chars into previous chunk)
# Chunk 3: "continues the document with more content..." (starts 80 chars into chunk 2)
```

## Variable Interpolation

Text splitter supports dynamic configuration:

```yaml
component:
  type: text-splitter
  text: ${input.document_text}
  chunk_size: ${input.max_chunk_size as integer | 1000}
  chunk_overlap: ${input.overlap_ratio as integer | 200}
  separators: ${input.custom_separators | ['\n\n', '\n', ' ', '']}
  streaming: ${input.enable_streaming as boolean | false}
```

## Best Practices

1. **Choose Appropriate Chunk Size**: Balance between context preservation and processing efficiency
2. **Use Hierarchical Separators**: Start with larger text units and fall back to smaller ones
3. **Consider Content Type**: Adjust separators and chunk sizes based on document structure
4. **Maintain Context**: Use appropriate overlap to preserve meaning across chunks
5. **Test with Your Data**: Experiment with different settings on representative documents
6. **Monitor Performance**: Track chunk quality and processing efficiency
7. **Handle Edge Cases**: Account for very short or very long documents
8. **Preserve Structure**: Use separators that respect document formatting

## Integration with Workflows

Reference text splitter in workflow jobs:

```yaml
workflow:
  jobs:
    - id: split-text
      component: text-splitter
      input:
        document: ${input.long_document}
        chunk_size: 1200
        
    - id: process-chunks
      component: text-processor
      input:
        chunks: ${split-text.output.chunks}
      depends_on: [ split-text ]
      
    - id: combine-results
      component: result-combiner
      input:
        processed_chunks: ${process-chunks.output.results}
      depends_on: [ process-chunks ]
```

## Common Use Cases

- **Document Embeddings**: Split documents for vector database storage
- **RAG Systems**: Prepare knowledge base chunks for retrieval
- **LLM Processing**: Break large documents into model-compatible sizes
- **Batch Analysis**: Process large documents in manageable chunks
- **Content Indexing**: Create searchable text segments
- **Multi-modal Processing**: Prepare text for cross-modal analysis
- **Document Summarization**: Create summaries from document sections
- **Information Extraction**: Extract entities and relationships from text chunks
