# Vector Processor Component

The vector processor component performs numerical operations on dense vectors, including pairwise similarity and distance, top-k ranking, threshold filtering, L2 normalization, and reductions over vector arrays. It is built on NumPy and is intended for use downstream of embedding models or any component that produces vector-valued outputs.

## Basic Configuration

```yaml
component:
  type: vector-processor
  action:
    method: similarity
    vector: ${input.query_embedding}
    other: ${input.doc_embedding}
    metric: cosine
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `vector-processor` |
| `driver` | string | `native` | Vector processing backend. Currently only `native` (NumPy) is supported. |
| `actions` | array | `[]` | List of vector processing actions |

### Common Action Configuration

All vector processor actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Processing method: `similarity`, `distance`, `dot-product`, `top-k`, `threshold-filter`, `normalize`, `mean`, `sum` |
| `batch_size` | integer / string | `null` | Number of input vectors to process per batch |
| `output` | any | `null` | Output variable mapping |

Every method takes vector-valued inputs that may be:

- A single vector (`VectorValue`) — the action returns a single result.
- A list of vectors — the action returns a list of results in the same order.
- A stream of vectors — the action returns a stream of results.

For array-input methods (`mean`, `sum`, and the `candidates` argument of ranking methods), the same three shapes apply to `VectorArrayValue` (a list of vectors). When both sides of a pairwise or ranking method are provided as batches, elements are paired positionally.

## Vector Processing Methods

### Similarity

Compute pairwise similarity between two vectors.

```yaml
component:
  type: vector-processor
  action:
    method: similarity
    vector: ${input.a}
    other: ${input.b}
    metric: cosine
    output: ${output}
```

**Similarity Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vector` | vector / array / string | **required** | Vector, list of vectors, or stream of vectors |
| `other` | vector / array / string | **required** | Vector, list of vectors, or stream of vectors to compare against `vector` |
| `metric` | string | `cosine` | Similarity metric. Supported: `cosine` |

Returns a float score per pair. Higher scores mean more similar.

### Distance

Compute pairwise distance between two vectors.

```yaml
component:
  type: vector-processor
  action:
    method: distance
    vector: ${input.a}
    other: ${input.b}
    metric: euclidean
    output: ${output}
```

**Distance Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vector` | vector / array / string | **required** | Vector, list of vectors, or stream of vectors |
| `other` | vector / array / string | **required** | Vector, list of vectors, or stream of vectors to compare against `vector` |
| `metric` | string | `euclidean` | Distance metric. Supported: `euclidean` |

Returns a non-negative float per pair. Lower values mean closer.

### Dot Product

Compute the dot product between two vectors.

```yaml
component:
  type: vector-processor
  action:
    method: dot-product
    vector: ${input.a}
    other: ${input.b}
    output: ${output}
```

**Dot Product Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vector` | vector / array / string | **required** | Vector, list of vectors, or stream of vectors |
| `other` | vector / array / string | **required** | Vector, list of vectors, or stream of vectors to pair with `vector` |

Returns a float per pair. No normalization is applied, so magnitudes influence the result.

### Top-K

Rank a flat list of candidate vectors against a query and return the `k` best matches.

```yaml
component:
  type: vector-processor
  action:
    method: top-k
    query: ${input.query_embedding}
    candidates: ${input.doc_embeddings}
    k: 5
    metric: cosine
    output: ${output}
```

**Top-K Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | vector / array / string | **required** | Query vector, or a batch of query vectors |
| `candidates` | vector array / array / string | **required** | Flat list of candidate vectors, or a batch of such lists |
| `k` | integer / string | `1` | Number of top matches to return |
| `metric` | string | `cosine` | Similarity or distance metric. Supported: `cosine`, `euclidean` |

Returns a list of `{ "index": int, "score": float }` objects, ordered best-first. If `metric` is a similarity (`cosine`), higher scores rank first. If `metric` is a distance (`euclidean`), lower scores rank first. When `candidates` is empty, returns an empty list.

### Threshold Filter

Return every candidate whose score against the query passes a threshold.

```yaml
component:
  type: vector-processor
  action:
    method: threshold-filter
    query: ${input.query_embedding}
    candidates: ${input.doc_embeddings}
    threshold: 0.75
    metric: cosine
    output: ${output}
```

**Threshold Filter Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | vector / array / string | **required** | Query vector, or a batch of query vectors |
| `candidates` | vector array / array / string | **required** | Flat list of candidate vectors, or a batch of such lists |
| `threshold` | number / string | **required** | Score threshold for keeping candidates |
| `metric` | string | `cosine` | Similarity or distance metric. Supported: `cosine`, `euclidean` |

Returns a list of `{ "index": int, "score": float }` objects in their original candidate order. When `metric` is a similarity metric, candidates with `score >= threshold` are kept. When `metric` is a distance metric, candidates with `score <= threshold` are kept.

### Normalize

L2-normalize a vector so that its Euclidean norm becomes `1`. A zero vector is returned unchanged.

```yaml
component:
  type: vector-processor
  action:
    method: normalize
    vector: ${input.embedding}
    output: ${output}
```

**Normalize Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vector` | vector / array / string | **required** | Vector, list of vectors, or stream of vectors to L2-normalize |

Returns a vector of the same dimension. This is the standard preprocessing step for cosine-similarity search over dot-product indexes.

### Mean

Compute the mean over a list of vectors.

```yaml
component:
  type: vector-processor
  action:
    method: mean
    vectors: ${input.embeddings}
    axis: 0
    output: ${output}
```

**Mean Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vectors` | vector array / array / string | **required** | Vectors to average, provided as a `VectorArrayValue` or a batch of such arrays |
| `axis` | integer / string | `0` | Axis along which to average. `0` reduces across vectors and returns a single vector of the same dimension; `1` reduces across dimensions and returns a scalar per vector |

### Sum

Compute the sum over a list of vectors.

```yaml
component:
  type: vector-processor
  action:
    method: sum
    vectors: ${input.embeddings}
    axis: 0
    output: ${output}
```

**Sum Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vectors` | vector array / array / string | **required** | Vectors to sum, provided as a `VectorArrayValue` or a batch of such arrays |
| `axis` | integer / string | `0` | Axis along which to sum. `0` reduces across vectors and returns a single vector of the same dimension; `1` reduces across dimensions and returns a scalar per vector |

## Pair Semantics for Ranking Methods

`top-k` and `threshold-filter` treat `query` and `candidates` as parallel inputs: each query is ranked against its own candidate array. When both sides are batched, the i-th query is paired with the i-th candidate array. When one side is a single value and the other is a batch, the scalar side is broadcast across the batch — for example, one query ranked against several independent candidate pools, or several queries ranked against a shared pool. Streaming inputs on either side follow the same pairing rules and produce a stream of ranking results.
