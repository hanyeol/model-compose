# Vector Store Component

The vector store component enables storing, searching, and managing vector embeddings using various backend databases. It supports operations like inserting, updating, searching, and deleting vectors with metadata, making it ideal for semantic search, recommendation systems, and RAG (Retrieval-Augmented Generation) applications.

## Basic Configuration

```yaml
component:
  type: vector-store
  driver: chroma
  collection: documents
  method: insert
  vector: ${input.embedding}
  metadata: 
    text: ${input.text}
    source: ${input.source}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `vector-store` |
| `driver` | string | **required** | Backend driver: `chroma`, `milvus`, `qdrant`, `faiss` |
| `actions` | array | `[]` | List of vector store actions |

### Common Action Configuration

All vector store actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Operation method: `insert`, `update`, `search`, `delete` |
| `id_field` | string | `id` | Field name used to identify vectors |
| `vector_field` | string | `vector` | Field name where vector embeddings are stored |
| `batch_size` | integer | `0` | Number of items to process in a single batch |

## Supported Drivers

### Chroma

ChromaDB for local and server-based vector storage:

```yaml
component:
  type: vector-store
  driver: chroma
  mode: local
  storage_dir: ./chroma_data
  # Or server mode:
  # mode: server
  # host: localhost
  # port: 8000
  # protocol: http
```

**Chroma Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | `local` | Mode: `local` or `server` |
| `storage_dir` | string | `./chroma` | Local storage directory |
| `host` | string | `localhost` | Server hostname (server mode) |
| `port` | integer | `8000` | Server port (server mode) |
| `protocol` | string | `http` | Connection protocol: `http`, `https` |
| `tenant` | string | `null` | Target tenant name |
| `database` | string | `null` | Target database name |
| `timeout` | float | `30.0` | Operation timeout in seconds |

### Milvus

Milvus for high-performance vector similarity search:

```yaml
component:
  type: vector-store
  driver: milvus
  host: localhost
  port: 19530
  database: default
  collection: embeddings
```

### Qdrant

Qdrant for vector similarity search and storage:

```yaml
component:
  type: vector-store
  driver: qdrant
  host: localhost
  port: 6333
  collection: vectors
```

### FAISS

Facebook AI Similarity Search for local vector operations:

```yaml
component:
  type: vector-store
  driver: faiss
  index_path: ./faiss_index
  dimension: 384
```

## Vector Store Operations

### Insert Vectors

Add new vectors to the store:

```yaml
component:
  type: vector-store
  driver: chroma
  collection: documents
  method: insert
  vector: ${input.embedding}
  vector_id: ${input.document_id}
  metadata:
    text: ${input.text}
    category: ${input.category}
    timestamp: ${now}
  output:
    inserted_id: ${response.id}
    success: ${response.success}
```

### Update Vectors

Modify existing vectors and metadata:

```yaml
component:
  type: vector-store
  driver: chroma
  collection: documents
  method: update
  vector_id: ${input.document_id}
  vector: ${input.new_embedding}
  metadata:
    text: ${input.updated_text}
    last_modified: ${now}
  insert_if_not_exist: true
  output:
    updated: ${response.success}
```

### Search Vectors

Find similar vectors using similarity search:

```yaml
component:
  type: vector-store
  driver: chroma
  collection: documents
  method: search
  query: ${input.query_embedding}
  top_k: 10
  metric_type: COSINE
  filter:
    category: science
    timestamp: 
      gte: 2024-01-01
  output_fields: [text, category, score]
  output:
    matches: ${response.results}
    scores: ${response.scores}
```

### Delete Vectors

Remove vectors from the store:

```yaml
component:
  type: vector-store
  driver: chroma
  collection: documents
  method: delete
  vector_id: ${input.document_id}
  # Or delete by filter:
  filter:
    category: outdated
    timestamp:
      lt: 2023-01-01
  output:
    deleted_count: ${response.deleted}
```

## Multiple Actions Configuration

Define multiple vector store operations:

```yaml
component:
  type: vector-store
  driver: chroma
  storage_dir: ./vector_db
  actions:
    - id: add-document
      collection: documents
      method: insert
      vector: ${input.embedding}
      vector_id: ${input.doc_id}
      metadata:
        title: ${input.title}
        content: ${input.content}
        category: ${input.category}
      output:
        document_id: ${response.id}
    
    - id: search-similar
      collection: documents
      method: search
      query: ${input.query_vector}
      top_k: 5
      filter:
        category: ${input.search_category}
      output_fields: [title, content, score]
      output:
        similar_docs: ${response.results}
    
    - id: update-document
      collection: documents
      method: update
      vector_id: ${input.doc_id}
      vector: ${input.new_embedding}
      metadata:
        content: ${input.updated_content}
        last_updated: ${now}
    
    - id: remove-document
      collection: documents
      method: delete
      vector_id: ${input.doc_id}
```

## Filtering and Querying

### Filter Conditions

Vector stores support various filter conditions:

```yaml
filter:
  # Exact match
  category: technology
  
  # Range queries
  score:
    gte: 0.8
    lt: 1.0
  
  # Array membership
  tags:
    in: [AI, "machine learning"]
  
  # Negation
  status:
    neq: deleted
  
  # Multiple conditions (AND)
  category: science
  published:
    gte: 2024-01-01
```

### Supported Filter Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `eq` | Equal to | `category: tech` |
| `neq` | Not equal to | `status: { neq: deleted }` |
| `gt` | Greater than | `score: { gt: 0.5 }` |
| `gte` | Greater than or equal | `timestamp: { gte: 2024-01-01 }` |
| `lt` | Less than | `price: { lt: 100 }` |
| `lte` | Less than or equal | `rating: { lte: 4.5 }` |
| `in` | In array | `category: { in: [tech, science] }` |
| `not-in` | Not in array | `status: { not-in: [draft, deleted] }` |

## Distance Metrics

Choose appropriate distance metrics for your use case:

```yaml
method: search
query: ${input.query_vector}
metric_type: COSINE
```

### Available Metrics

- **COSINE**: Cosine similarity (good for text embeddings)
- **L2**: Euclidean distance (default for many applications)  
- **IP**: Inner product (for normalized vectors)
- **HAMMING**: Hamming distance (for binary vectors)

## Batch Operations

Process multiple vectors efficiently:

```yaml
component:
  type: vector-store
  driver: chroma
  collection: bulk_documents
  method: insert
  vector: ${input.embedding_batch}  # Array of vectors
  vector_id: ${input.id_batch}      # Array of IDs
  metadata: ${input.metadata_batch} # Array of metadata
  batch_size: 100
  output:
    inserted_count: ${response.count}
    batch_results: ${response.results}
```

## Integration with Text Embeddings

Combine with model components for end-to-end workflows:

```yaml
workflows:
  - id: document-indexing
    jobs:
      - id: generate-embedding
        component: embedding-model
        input:
          text: ${input.document_text}
        output:
          embedding: ${output.embedding}
      
      - id: store-embedding
        component: vector-store
        action: add-document
        input:
          embedding: ${generate-embedding.output.embedding}
          doc_id: ${input.document_id}
          title: ${input.title}
          content: ${input.document_text}
        depends_on: [ generate-embedding ]

  - id: semantic-search
    jobs:
      - id: query-embedding
        component: embedding-model
        input:
          text: ${input.search_query}
        output:
          query_vector: ${output.embedding}
      
      - id: find-similar
        component: vector-store
        action: search-similar
        input:
          query_vector: ${query-embedding.output.query_vector}
          search_category: ${input.category}
        output:
          search_results: ${output.similar_docs}
        depends_on: [ query-embedding ]

components:
  - id: embedding-model
    type: model
    task: text-embedding
    model: sentence-transformers/all-MiniLM-L6-v2
    text: ${input.text}
    
  - id: vector-store
    type: vector-store
    driver: chroma
    storage_dir: ./embeddings_db
    actions:
      - id: add-document
        collection: documents
        method: insert
        vector: ${input.embedding}
        vector_id: ${input.doc_id}
        metadata:
          title: ${input.title}
          content: ${input.content}
          category: ${input.category}
      
      - id: search-similar
        collection: documents
        method: search
        query: ${input.query_vector}
        top_k: 10
        filter:
          category: ${input.search_category}
        output_fields: [ title, content ]
```

## Advanced Usage Examples

### RAG System Implementation

```yaml
workflows:
  - id: rag-query
    jobs:
      - id: embed-question
        component: embedding-model
        input:
          text: ${input.question}
      
      - id: retrieve-context
        component: vector-store
        action: search-knowledge
        input:
          query_vector: ${embed-question.output.embedding}
        depends_on: [ embed-question ]
      
      - id: generate-answer
        component: chat-model
        input:
          messages:
            - role: system
              content: Answer based on the provided context.
            - role: user
              content: |
                Context: ${retrieve-context.output.context}
                Question: ${input.question}
        depends_on: [ retrieve-context ]

components:
  - id: vector-store
    type: vector-store
    driver: chroma
    actions:
      - id: search-knowledge
        collection: knowledge_base
        method: search
        query: ${input.query_vector}
        top_k: 5
        output_fields: [ text, source ]
        output:
          context: ${response.results | join('\n\n')}
```

### Recommendation System

```yaml
component:
  type: vector-store
  driver: chroma
  actions:
    - id: find-similar-items
      collection: product_embeddings
      method: search
      query: ${input.user_preference_vector}
      top_k: 20
      filter:
        category: ${input.preferred_category}
        in_stock: true
        price:
          lte: ${input.max_price}
      output_fields: [ name, description, price, rating ]
      output:
        recommendations: ${response.results}
```

### Duplicate Detection

```yaml
component:
  type: vector-store
  driver: chroma
  actions:
    - id: find-duplicates
      collection: documents
      method: search
      query: ${input.document_embedding}
      top_k: 5
      metric_type: COSINE
      filter:
        # Exclude the document itself
        id: 
          neq: ${input.document_id}
      output:
        potential_duplicates: ${response.results | filter(score > 0.95)}
```

## Performance Optimization

### Indexing Strategy

```yaml
component:
  type: vector-store
  driver: milvus
  collection: large_corpus
  method: search
  # Use appropriate index for your data size
  metric_type: L2
  batch_size: 1000  # Process in batches for large operations
```

### Memory Management

```yaml
component:
  type: vector-store
  driver: faiss
  index_path: ./large_index
  # Configure for memory efficiency
  batch_size: 500
```

## Error Handling

Vector store operations can fail for various reasons:

- **Connection Issues**: Database server unreachable
- **Collection Errors**: Collection doesn't exist or access denied
- **Data Validation**: Invalid vector dimensions or metadata
- **Storage Limits**: Insufficient disk space or quota exceeded

Use workflow error handling to manage failures:

```yaml
workflow:
  jobs:
    - id: store-vectors
      component: vector-store
      action: insert-embeddings
      input:
        vectors: ${input.embeddings}
      on_error:
        - id: retry-storage
          component: backup-vector-store
          input:
            vectors: ${input.embeddings}
```

## Variable Interpolation

Vector store supports dynamic configuration:

```yaml
component:
  type: vector-store
  driver: ${env.VECTOR_DB_DRIVER | chroma}
  collection: ${input.collection_name}
  method: ${input.operation}
  vector: ${input.embedding}
  metadata:
    timestamp: ${now}
    user_id: ${input.user_id}
    source: ${env.DATA_SOURCE}
```

## Best Practices

1. **Vector Dimensions**: Ensure consistent vector dimensions across operations
2. **Batch Processing**: Use batching for large-scale operations
3. **Indexing**: Create appropriate indexes for your query patterns
4. **Metadata**: Store relevant metadata for filtering and retrieval
5. **Collection Management**: Organize vectors into logical collections
6. **Distance Metrics**: Choose metrics appropriate for your embedding type
7. **Filtering**: Use filters to improve search precision and performance
8. **Backup**: Regularly backup vector data for production systems

## Integration with Workflows

Reference vector store in workflow jobs:

```yaml
workflow:
  jobs:
    - id: process-documents
      component: text-processor
      input:
        documents: ${input.documents}
        
    - id: generate-embeddings
      component: embedding-model
      input:
        texts: ${process-documents.output.processed_texts}
      depends_on: [ process-documents ]
        
    - id: store-vectors
      component: vector-store
      action: bulk-insert
      input:
        embeddings: ${generate-embeddings.output.embeddings}
        metadata: ${process-documents.output.metadata}
      depends_on: [ generate-embeddings ]
```

## Common Use Cases

- **Semantic Search**: Find similar documents, products, or content
- **Recommendation Systems**: Suggest similar items or content
- **RAG Applications**: Retrieve relevant context for question answering
- **Duplicate Detection**: Identify similar or duplicate content
- **Clustering**: Group similar items based on vector similarity
- **Content Discovery**: Enable content exploration through similarity
- **Personalization**: Create personalized experiences using user vectors
- **Knowledge Management**: Build searchable knowledge bases
