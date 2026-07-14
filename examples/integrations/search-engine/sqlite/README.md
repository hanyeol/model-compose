# SQLite Search Engine Example

This example demonstrates how to use model-compose with SQLite FTS5 as a full-text search engine for indexing, searching, and managing documents in workflows.

## Overview

This workflow provides full-text search operations backed by SQLite FTS5:

1. **Index**: Insert documents into the search index
2. **Search**: Run BM25-ranked keyword search over indexed documents
3. **Delete**: Remove documents from the index by id

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python 3.11+ (the bundled `sqlite3` module ships with FTS5 enabled in the official builds)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/search-engine/sqlite
   ```

2. No external service is required. The index is stored as a single SQLite database file under `./data/search.db` and is created on the first `index` action.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflows:**

   **Index documents:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "index-documents", "input": {"documents": [
       {"document_id": "1", "title": "Python tutorial", "content": "Learn Python basics"},
       {"document_id": "2", "title": "JavaScript guide", "content": "Modern JavaScript features"},
       {"document_id": "3", "title": "Rust handbook", "content": "Systems programming in Rust"}
     ]}}'
   ```

   **Search documents:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "search-documents", "input": {"query": "Python", "limit": 5}}'
   ```

   **Delete documents:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "delete-documents", "input": {"document_ids": ["1", "3"]}}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select the desired workflow (index, search, delete)
   - Enter your input parameters
   - Click the "Run Workflow" button

   **Using CLI:**
   ```bash
   # Index documents
   model-compose run index-documents --input '{"documents": [
     {"document_id": "1", "title": "Python tutorial", "content": "Learn Python basics"},
     {"document_id": "2", "title": "JavaScript guide", "content": "Modern JavaScript features"}
   ]}'

   # Search with a field filter
   model-compose run search-documents --input '{"query": "Modern", "search_fields": ["content"], "limit": 5}'

   # Delete documents
   model-compose run delete-documents --input '{"document_ids": ["1"]}'
   ```

## Component Details

### SQLite Search Engine Component (search)
- **Type**: Search-engine component
- **Purpose**: Full-text keyword search over user-supplied documents
- **Driver**: SQLite FTS5
- **Features**:
  - Zero-dependency (uses Python's built-in `sqlite3` with FTS5)
  - Built-in BM25 ranking
  - Multiple indexes co-located in a single database file
  - Upsert semantics when an `id` field is declared
  - Explicit `FileNotFoundError` for `search` / `delete` when the database does not yet exist (no silent empty-file creation)

## Workflow Details

### "Index Documents" Workflow

**Description**: Insert a batch of documents into the FTS5 index. Creates the database file and the index on first use.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `documents` | array of objects | Yes | - | Documents to index. Each object's keys must match the declared field names |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `indexed` | integer | Number of documents inserted in this call |
| `total` | integer | Total number of documents currently in the index |

### "Search Documents" Workflow

**Description**: Run a BM25-ranked keyword search against the index.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | FTS5 query expression |
| `search_fields` | array of strings | No | null | Restrict matching to the listed fields. When omitted, all text fields are searched |
| `limit` | integer | No | 10 | Maximum number of hits to return |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `hits` | array of objects | Matching documents, sorted by descending `score` |
| `count` | integer | Number of hits returned |

Each hit contains the indexed field values plus a `score` field (higher = more relevant).

### "Delete Documents" Workflow

**Description**: Remove documents from the index by their id field value.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `document_ids` | array of strings | Yes | - | Values of the `id`-typed field for the documents to delete |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| `deleted` | integer | Number of documents removed |

## Customization

### Storage Location

```yaml
components:
  - id: search
    type: search-engine
    driver: sqlite
    storage_dir: /var/lib/myapp/search
    database: knowledge.db
```

The full database path is `${storage_dir}/${database}`. Multiple indexes live as separate FTS5 virtual tables inside the same file.

### Field Types

| Type | Behavior |
|------|----------|
| `text` | Tokenized and searchable via full-text MATCH |
| `id` | Unique identifier used for upsert and delete |
| `keyword` | Tag-style value (stored as text in FTS5) |

```yaml
fields:
  - name: document_id
    type: id
  - name: title
    type: text
  - name: tags
    type: keyword
```

### Multiple Indexes in One Component

A single component can serve several indexes by varying the `index` parameter per action. They share the database file but live in independent FTS5 virtual tables:

```yaml
actions:
  - id: index-articles
    method: index
    index: articles
    fields:
      - { name: document_id, type: id }
      - { name: body, type: text }
    documents: ${input.documents}

  - id: index-comments
    method: index
    index: comments
    fields:
      - { name: document_id, type: id }
      - { name: body, type: text }
    documents: ${input.documents}
```
