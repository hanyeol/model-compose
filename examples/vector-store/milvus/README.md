# Milvus Vector Store Example

This example demonstrates how to use model-compose with Milvus as a vector database for large-scale semantic search and similarity matching. It provides a complete pipeline for embedding text, storing vectors, and performing efficient similarity searches using the `sentence-transformers/all-MiniLM-L6-v2` embedding model.

## Overview

Milvus is an open-source vector database built for scalable similarity search and AI applications. This configuration showcases:

- High-performance text embedding generation
- Scalable vector storage and retrieval with Milvus
- CRUD operations on vector embeddings with integer IDs
- Fast semantic similarity search capabilities
- Production-ready vector database features

## Prerequisites

### Milvus Installation

#### Option 1: Docker Compose (Recommended)
```bash
# Download Milvus docker-compose.yml
wget https://github.com/milvus-io/milvus/releases/download/v2.3.0/milvus-standalone-docker-compose.yml -O docker-compose.yml

# Start Milvus
docker-compose up -d

# Verify installation
docker-compose ps
```

#### Option 2: Milvus Standalone
```bash
# Install Milvus CLI
pip install pymilvus

# Or use Milvus cloud service
# Sign up at https://cloud.zilliz.com/
```

### Model Dependencies
```bash
# Install sentence transformers
pip install sentence-transformers torch pymilvus
```

### Environment Setup
```bash
# Install model-compose
pip install -e .
```

## Architecture

The system consists of two main components optimized for production use:

### Components

#### 1. Embedding Model (`embedding-model`)
- **Type**: Local model
- **Task**: Text embedding
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Purpose**: Converts text into high-quality vector embeddings

#### 2. Vector Store (`vector-store`)
- **Type**: Vector database
- **Driver**: Milvus
- **Host**: localhost
- **Port**: 19530
- **Protocol**: HTTP
- **Database**: test
- **Collection**: test
- **Purpose**: High-performance vector storage and similarity search

### Connection Configuration

| Parameter | Value | Description |
|-----------|-------|-------------|
| `host` | localhost | Milvus server hostname |
| `port` | 19530 | Milvus gRPC port |
| `protocol` | http | Connection protocol |
| `database` | test | Target database name |

### Available Actions

| Action | Method | ID Type | Description |
|--------|---------|---------|-------------|
| `insert` | INSERT | Auto-generated | Add new vector with metadata |
| `update` | UPDATE | Integer | Modify existing vector by ID |
| `search` | SEARCH | N/A | Find similar vectors |
| `delete` | DELETE | Integer | Remove vector by ID |

## Workflows

### 1. Insert Sentence Embedding

Converts text to embeddings and stores them in Milvus with auto-generated IDs.

```mermaid
graph LR
    A[Input Text] --> B[Embedding Model]
    B --> C[Milvus Insert]
    C --> D[Storage Confirmation + ID]
```

**Input Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | Yes | Text to convert and store |

**Output:**
- JSON confirmation with generated vector ID and status

**Usage Example:**
```bash
curl -X POST http://localhost:8080/api/insert-sentence-embedding \
  -H "Content-Type: application/json" \
  -d '{"text": "This is a comprehensive guide to machine learning algorithms."}'
```

**Sample Response:**
```json
{
  "status": "success",
  "vector_id": 450234567890,
  "message": "Vector inserted successfully"
}
```

### 2. Update Sentence Embedding

Updates an existing vector embedding with new text using integer ID.

```mermaid
graph LR
    A[Input Text + Integer ID] --> B[Embedding Model]
    B --> C[Milvus Update]
    C --> D[Update Confirmation]
```

**Input Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | Yes | New text content |
| `vector_id` | integer | Yes | Integer ID of vector to update |

**Output:**
- JSON confirmation with update status

**Usage Example:**
```bash
curl -X POST http://localhost:8080/api/update-sentence-embedding \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Updated comprehensive guide to deep learning and neural networks.",
    "vector_id": 450234567890
  }'
```

### 3. Search Sentence Embeddings

Performs high-speed semantic similarity search using query text.

```mermaid
graph LR
    A[Query Text] --> B[Embedding Model]
    B --> C[Milvus Search]
    C --> D[Ranked Results]
```

**Input Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | Yes | Query text for similarity search |

**Output:**
- Array of objects with `id`, `score`, and `metadata.text`
- Results ranked by similarity score (higher = more similar)
- Optimized for sub-millisecond search times

**Usage Example:**
```bash
curl -X POST http://localhost:8080/api/search-sentence-embeddings \
  -H "Content-Type: application/json" \
  -d '{"text": "artificial intelligence and deep learning techniques"}'
```

**Sample Response:**
```json
[
  {
    "id": 450234567890,
    "score": 0.92,
    "metadata": {
      "text": "Deep learning and neural networks are fundamental AI techniques."
    }
  },
  {
    "id": 450234567891,
    "score": 0.87,
    "metadata": {
      "text": "Machine learning algorithms form the basis of artificial intelligence."
    }
  }
]
```

### 4. Delete Sentence Embedding

Removes a vector embedding by its integer ID.

```mermaid
graph LR
    A[Integer Vector ID] --> B[Milvus Delete]
    B --> C[Deletion Confirmation]
```

**Input Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `vector_id` | integer | Yes | Integer ID of vector to delete |

**Output:**
- JSON confirmation with deletion status

**Usage Example:**
```bash
curl -X POST http://localhost:8080/api/delete-sentence-embedding \
  -H "Content-Type: application/json" \
  -d '{"vector_id": 450234567890}'
```

## How to Run Instructions

### 1. Start Milvus

```bash
# Using Docker Compose
docker-compose up -d

# Verify Milvus is running
curl http://localhost:19530/health
```

### 2. Start the Service

```bash
# Navigate to the example directory
cd examples/vector-store/milvus

# Start the controller
model-compose up
```

This starts:
- HTTP API server on port 8080
- Gradio web interface on port 8081
- Connection to Milvus on port 19530

### 3. Access the Web UI

Open http://localhost:8081 in your browser to interact with the workflows through a web interface.

### 4. API Endpoints

Base URL: `http://localhost:8080/api`

- `POST /insert-sentence-embedding` - Store new text embeddings
- `POST /update-sentence-embedding` - Update existing embeddings
- `POST /search-sentence-embeddings` - Search for similar texts
- `POST /delete-sentence-embedding` - Remove embeddings

## System Requirements

### Hardware
- **RAM**: 4GB+ for Milvus + embedding model
- **Storage**: 2GB+ for Milvus data and model files
- **CPU**: Multi-core recommended for concurrent operations
- **GPU**: Optional, but recommended for large-scale deployments

### Software
- Python 3.8+
- PyTorch (CPU or GPU)
- Docker & Docker Compose
- Milvus 2.3.0+

## Customization Options

### Milvus Configuration

#### Remote Milvus Instance
```yaml
components:
  - id: vector-store
    type: vector-store
    driver: milvus
    host: your-milvus-server.com
    port: 19530
    protocol: https
    database: production
    # Add authentication
    username: ${env.MILVUS_USERNAME}
    password: ${env.MILVUS_PASSWORD}
```

#### Milvus Cloud (Zilliz)
```yaml
components:
  - id: vector-store
    type: vector-store
    driver: milvus
    host: your-cluster.aws-us-west-2.vectordb.zillizcloud.com
    port: 19530
    protocol: https
    database: default
    token: ${env.ZILLIZ_API_KEY}
```

### Embedding Model Options

#### Higher Accuracy Model
```yaml
components:
  - id: embedding-model
    type: model
    task: text-embedding
    model: sentence-transformers/all-mpnet-base-v2  # 768 dimensions, higher accuracy
```

#### Multilingual Model
```yaml
components:
  - id: embedding-model
    type: model
    task: text-embedding
    model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

### Collection Settings

#### Multiple Collections
```yaml
actions:
  - id: insert-documents
    collection: documents
    method: insert
  - id: insert-products
    collection: products
    method: insert
```

#### Custom Index Parameters
```yaml
actions:
  - id: search
    collection: test
    method: search
    query: ${input.vector}
    search_params:
      metric_type: "IP"  # Inner Product
      params: {"nprobe": 16}
    output_fields: [text, category, timestamp]
```

## Performance Optimization

### Milvus Performance Tuning

#### Index Configuration
- **HNSW**: Best for accuracy and query performance
- **IVF_FLAT**: Balanced performance and memory usage
- **IVF_PQ**: Memory efficient for large datasets

#### Search Parameters
```yaml
search_params:
  metric_type: "L2"      # Euclidean distance
  params:
    nprobe: 16           # Number of clusters to search
    max_empty_result_buckets: 2
```

### Scaling Considerations

#### Horizontal Scaling
- Use Milvus cluster mode for large deployments
- Implement read replicas for query-heavy workloads
- Consider data partitioning strategies

#### Memory Management
- Monitor collection size and memory usage
- Implement data lifecycle policies
- Use data compression for cold storage

## Production Deployment

### Monitoring and Observability
```yaml
# Add monitoring endpoints
components:
  - id: milvus-metrics
    type: http-client
    endpoint: http://localhost:9091/metrics
```

### Backup and Recovery
```bash
# Backup Milvus data
docker exec milvus-standalone /bin/bash -c "cd /var/lib/milvus && tar -czf backup.tar.gz db_data"

# Restore from backup
docker exec milvus-standalone /bin/bash -c "cd /var/lib/milvus && tar -xzf backup.tar.gz"
```

### High Availability
- Deploy Milvus in cluster mode
- Use load balancers for API endpoints
- Implement health checks and failover

## Use Cases

### Large-Scale Document Search
Handle millions of documents with sub-millisecond search times for enterprise knowledge bases.

### Real-time Recommendation Systems
Power recommendation engines with fast similarity searches across product catalogs.

### Image and Multimodal Search
Extend to image embeddings for visual similarity search applications.

### Anomaly Detection
Use embeddings to detect outliers and anomalies in data streams.

### Content Moderation
Classify and filter content using embedding-based similarity to known patterns.

## Troubleshooting

### Milvus Connection Issues
```bash
# Check Milvus status
docker-compose ps
docker logs milvus-standalone

# Test connection
python -c "from pymilvus import connections; connections.connect('default', host='localhost', port='19530')"
```

### Performance Issues
- Monitor Milvus metrics via Prometheus endpoint (port 9091)
- Check index build status and query performance
- Optimize search parameters based on use case

### Memory Issues
- Adjust Milvus memory limits in docker-compose.yml
- Monitor collection sizes and implement data retention policies
- Use appropriate index types for your data size

### Data Consistency
- Ensure proper transaction handling for updates
- Implement retry logic for failed operations
- Monitor data integrity with checksums

## API Rate Limits

This example uses local models and Milvus, so external API rate limits don't apply. Performance is limited by:
- Milvus cluster capacity and configuration
- Local hardware resources (CPU, memory, storage)
- Network latency for remote Milvus instances
- Embedding model inference speed

For production deployments, consider:
- Connection pooling for high-concurrency scenarios
- Request queuing and rate limiting at the application level
- Load balancing across multiple Milvus instances