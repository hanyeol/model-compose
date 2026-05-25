# Search Engine Component

The search-engine component provides full-text search over arbitrary document collections. It supports document indexing, BM25-ranked keyword search, and deletion through a declarative configuration. Multiple named indexes can be hosted on a single backend.

## Basic Configuration

```yaml
component:
  type: search-engine
  driver: sqlite
  storage_dir: ./data
  database: search.db
  actions:
    - id: index
      method: index
      index: docs
      fields:
        - name: document_id
          type: id
        - name: title
          type: text
        - name: content
          type: text
      documents: ${input.documents}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `search-engine` |
| `driver` | string | **required** | Search engine backend driver: `sqlite` |
| `storage_dir` | string | `./sqlite-search` | Directory where the backing database file is stored (sqlite driver) |
| `database` | string | `search.db` | Database file name. Multiple indexes are stored as virtual tables in the same database (sqlite driver) |

### SQLite Driver

The `sqlite` driver uses SQLite FTS5 for BM25-ranked full-text search. The index is stored as a virtual table in a single SQLite file and is created automatically on the first `index` action.

```yaml
component:
  type: search-engine
  driver: sqlite
  storage_dir: ./data
  database: search.db
```

## Methods

### Index

Insert documents into a search index. Fields are declared on the first call and reused for subsequent appends.

```yaml
component:
  type: search-engine
  driver: sqlite
  action:
    method: index
    index: docs
    fields:
      - name: document_id
        type: id
      - name: title
        type: text
      - name: content
        type: text
    documents: ${input.documents}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `index` |
| `index` | string | **required** | Target index name |
| `fields` | array | `null` | Index schema field definitions. Optional when appending to an existing index |
| `documents` | array | **required** | List of documents (objects) to index |

**Field Types:**

| Type | Description |
|------|-------------|
| `text` | Tokenized for full-text search |
| `id` | Exact-match identifier (used by `delete`) |
| `keyword` | Tag-like value matched as a single token |

**Example documents:**

```json
[
  {"document_id": "1", "title": "Python tutorial", "content": "Learn Python basics"},
  {"document_id": "2", "title": "JavaScript guide", "content": "Modern JavaScript features"}
]
```

### Search

Run a BM25-ranked keyword search over an index.

```yaml
component:
  type: search-engine
  driver: sqlite
  action:
    method: search
    index: docs
    query: ${input.query}
    search_fields: ${input.search_fields}
    limit: 10
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `search` |
| `index` | string | **required** | Target index name |
| `query` | string | **required** | Search query string |
| `search_fields` | array | `null` | Fields to search in. When omitted, all `text` fields are searched |
| `limit` | integer | `10` | Maximum number of search results to return |

### Delete

Remove documents from an index by their id-field values.

```yaml
component:
  type: search-engine
  driver: sqlite
  action:
    method: delete
    index: docs
    document_ids: ${input.document_ids}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `delete` |
| `index` | string | **required** | Target index name |
| `document_ids` | array | **required** | List of document ID values to delete |

## Multiple Actions

Combine index, search, and delete in a single component:

```yaml
component:
  type: search-engine
  driver: sqlite
  storage_dir: ./data
  database: search.db
  actions:
    - id: index
      method: index
      index: docs
      fields:
        - name: document_id
          type: id
        - name: title
          type: text
        - name: content
          type: text
      documents: ${input.documents}

    - id: search
      method: search
      index: docs
      query: ${input.query}
      search_fields: ${input.search_fields}
      limit: ${input.limit}

    - id: delete
      method: delete
      index: docs
      document_ids: ${input.document_ids}
```

## Usage Examples

### Document Search Workflow

```yaml
components:
  - id: search
    type: search-engine
    driver: sqlite
    storage_dir: ./data
    database: search.db
    actions:
      - id: index
        method: index
        index: docs
        fields:
          - name: document_id
            type: id
          - name: title
            type: text
          - name: content
            type: text
        documents: ${input.documents}

      - id: search
        method: search
        index: docs
        query: ${input.query}
        limit: ${input.limit | 10}

workflows:
  - id: index-documents
    job:
      component: search
      action: index
      input: ${input}

  - id: search-documents
    job:
      component: search
      action: search
      input: ${input}
```

### Multiple Indexes in One Backend

A single component can host multiple indexes by varying the `index` name in each action:

```yaml
component:
  type: search-engine
  driver: sqlite
  storage_dir: ./data
  database: search.db
  actions:
    - id: index-articles
      method: index
      index: articles
      fields:
        - name: article_id
          type: id
        - name: body
          type: text
      documents: ${input.articles}

    - id: index-products
      method: index
      index: products
      fields:
        - name: sku
          type: id
        - name: name
          type: text
        - name: category
          type: keyword
      documents: ${input.products}
```

## Variable Interpolation

```yaml
component:
  type: search-engine
  driver: sqlite
  storage_dir: ${env.SEARCH_DATA_DIR | ./data}
  action:
    method: search
    index: docs
    query: ${input.query}
    limit: ${input.limit as integer | 10}
```

## Best Practices

1. **Declare fields once**: Provide `fields` on the first `index` call; subsequent appends to the same index can omit it
2. **Choose the right field type**: Use `id` for identifiers used in deletion, `keyword` for tag-like values, `text` for searchable content
3. **Scope queries**: Pass `search_fields` to limit search to specific text fields when documents have many fields
4. **Persistent storage**: Place `storage_dir` outside ephemeral runtime directories so the index survives restarts
5. **Single backend, many indexes**: Reuse one component for related indexes rather than spinning up multiple search-engine components

## Common Use Cases

- **Document retrieval**: Keyword search over manuals, knowledge bases, and articles
- **Hybrid search**: Combine with `vector-store` for keyword + semantic retrieval
- **Audit and discovery**: Search across logs, transcripts, and chat history
- **RAG keyword stage**: Pre-filter candidates by keyword match before vector ranking
