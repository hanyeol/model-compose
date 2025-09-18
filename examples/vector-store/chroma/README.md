# ChromaDB Vector Store Example

This example demonstrates how to use model-compose with ChromaDB as a vector store for semantic search and similarity matching using text embeddings.

## Overview

This workflow provides a complete vector database solution that:

1. **Text Embedding Generation**: Converts text to vector embeddings using sentence transformers
2. **Vector Storage**: Stores embeddings in ChromaDB with metadata
3. **Semantic Search**: Performs similarity-based searches using vector embeddings
4. **CRUD Operations**: Supports insert, update, search, and delete operations

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- ChromaDB server (local or remote)
- Python with PyTorch support

### ChromaDB Installation

```bash
# Install ChromaDB
pip install chromadb

# Or run with Docker
docker run -p 8000:8000 chromadb/chroma
```

### Model Dependencies

```bash
# Install sentence transformers
pip install sentence-transformers torch
```

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/vector-store/chroma
   ```

2. No additional environment configuration required - ChromaDB runs locally by default.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflows:**

   **Insert Text Embedding:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/insert-sentence-embedding/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"text": "This is a sample document about machine learning."}}'
   ```

   **Search Similar Texts:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/search-sentence-embeddings/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"text": "artificial intelligence and neural networks"}}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select the desired workflow (insert, search, update, delete)
   - Enter your input parameters
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   # Insert text embedding
   model-compose run insert-sentence-embedding --input '{"text": "Machine learning is a subset of AI."}'

   # Search for similar texts
   model-compose run search-sentence-embeddings --input '{"text": "deep learning algorithms"}'
   ```

## Component Details

### embedding-model
- **Type**: Model component with text-embedding task
- **Purpose**: Convert text to 384-dimensional vector embeddings
- **Model**: sentence-transformers/all-MiniLM-L6-v2
- **Features**:
  - Fast inference speed
  - Good semantic understanding
  - Compact embedding size

### vector-store
- **Type**: Vector database component
- **Purpose**: Store and search vector embeddings with metadata
- **Driver**: ChromaDB
- **Features**:
  - CRUD operations on vectors
  - Similarity search capabilities
  - Metadata storage and filtering
  - Local and remote deployment

## Workflow Details

### "Insert Sentence Embedding" Workflow

**Description**: Convert text to embeddings and store them in ChromaDB with metadata.

#### Job Flow

```mermaid
graph TD
    %% Jobs (circles)
    J1((generate-embedding<br/>job))
    J2((store-vector<br/>job))

    %% Components (rectangles)
    C1[Text Embedding Model<br/>component]
    C2[ChromaDB Vector Store<br/>component]

    %% Job to component connections (solid: invokes, dotted: returns)
    J1 --> C1
    C1 -.-> |embedding vector| J1
    J2 --> C2
    C2 -.-> |storage confirmation| J2

    %% Job flow
    J1 --> J2

    %% Input/Output
    Input((Input)) --> J1
    J2 --> Output((Output))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | Yes | - | Text to convert and store |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Insertion status confirmation |
| `vector_id` | string | Generated ID for the stored vector |

### "Search Sentence Embeddings" Workflow

**Description**: Perform semantic similarity search using query text to find related stored embeddings.

#### Job Flow

```mermaid
graph TD
    %% Jobs (circles)
    J1((generate-query-embedding<br/>job))
    J2((search-vectors<br/>job))

    %% Components (rectangles)
    C1[Text Embedding Model<br/>component]
    C2[ChromaDB Vector Store<br/>component]

    %% Job to component connections (solid: invokes, dotted: returns)
    J1 --> C1
    C1 -.-> |query embedding| J1
    J2 --> C2
    C2 -.-> |similar documents| J2

    %% Job flow
    J1 --> J2

    %% Input/Output
    Input((Input)) --> J1
    J2 --> Output((Output))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | Yes | - | Query text for similarity search |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `results` | array | Array of similar documents with scores and metadata |
| `total_results` | integer | Number of results returned |

## Available Operations

### Insert Operations
- **insert-sentence-embedding**: Store new text embeddings
- **update-sentence-embedding**: Update existing embeddings by ID

### Search Operations
- **search-sentence-embeddings**: Find similar texts using semantic search

### Management Operations
- **delete-sentence-embedding**: Remove embeddings by ID

## Customization

### Embedding Model Selection

```yaml
components:
  - id: embedding-model
    type: model
    task: text-embedding
    model: sentence-transformers/all-mpnet-base-v2  # Higher accuracy
    # or
    model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2  # Multilingual
```

### ChromaDB Configuration

#### Remote ChromaDB Instance
```yaml
components:
  - id: vector-store
    type: vector-store
    driver: chroma
    host: your-chroma-server.com
    port: 8000
```

#### Custom Collection Settings
```yaml
actions:
  - id: insert
    collection: documents  # Custom collection name
    method: insert
```
