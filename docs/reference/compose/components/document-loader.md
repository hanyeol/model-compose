# Document Loader Component

The document loader component parses documents — PDFs, DOCX, HTML, images, and more — into a stream of chunk records suitable for embedding, retrieval indexing, or LLM prompting. Two drivers are available: `docling` (rich, model-driven parsing with heading and table structure recovery) and `pypdf` (lightweight page-by-page text extraction, no models loaded).

## Basic Configuration

```yaml
component:
  type: document-loader
  driver: docling
  backend: pypdfium2
  tokenizer: sentence-transformers/all-MiniLM-L6-v2
  action:
    source: ${input.source as file/path}
    chunker: hybrid
    max_token_count: 384
    streaming: true
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `document-loader`. |
| `driver` | string | `docling` | Backend driver. One of `docling`, `pypdf`. |
| `actions` | array | `[]` | List of load actions. |

#### `docling` driver — component-level

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `backend` | string | (docling default) | PDF backend override. Set to `pypdfium2` for fast text-layer extraction; the default backend keeps docling-parse's full pipeline. `pypdfium2` skips OCR entirely. |
| `tokenizer` | string | `null` | HuggingFace tokenizer id used by chunkers that respect a token budget (`hybrid`, `line`). Loaded once when the component starts and reused across every action. |
| `enable_ocr` | boolean | `false` | Whether to run OCR on scanned or image-based pages. |
| `ocr_engine` | string | (docling default) | One of `easyocr`, `tesseract`, `rapidocr`, `ocrmac`. Only meaningful when `enable_ocr` is `true`. |
| `recognize_table` | boolean | `true` | Whether to run table structure recognition. Turning it off cuts a large share of parse time on table-heavy documents. |
| `table_mode` | string | (docling default) | `fast` or `accurate`. Only meaningful when `recognize_table` is `true`. |
| `accelerator` | string | (docling default) | Accelerator device for model inference. One of `auto`, `cpu`, `cuda`, `mps`. |

#### `pypdf` driver — component-level

No component-level settings beyond the shared fields.

### Action Configuration

Common to all drivers:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string \| string[] | **required** | Document source, or list of sources — a file path, upload stream, URL, or raw bytes. Use the DSL type hint (`${input.source as file/path}`, `${input.source as file/url}`) so the driver receives the right stream resource. |
| `batch_size` | integer \| string | `1` | Number of sources processed concurrently per batch when the input is a list or stream. |
| `streaming` | boolean \| string | `false` | When `true`, chunks are emitted incrementally through a stream iterator; when `false`, the full chunk list is returned as one response. |

#### `docling` driver — action-level

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `chunker` | string | `hybrid` | Chunking strategy. One of `hybrid`, `hierarchical`, `line`, `page`. Omit or set to `null` to emit the whole document as a single markdown chunk. |
| `max_token_count` | integer \| string | `null` | Maximum tokens per chunk for token-aware chunkers (`hybrid`, `line`). |
| `merge_peers` | boolean \| string | `true` | (hybrid) Merge adjacent under-sized chunks that share the same headings/captions. |
| `repeat_table_header` | boolean \| string | `true` | (hybrid) Repeat table header rows across chunks that split a table. |
| `omit_header_on_overflow` | boolean \| string | `false` | (hybrid) Drop the heading prefix when a chunk overflows the token budget. |
| `always_emit_headings` | boolean \| string | `false` | (hierarchical) Emit headings as standalone chunks in addition to prefixing them onto following content. |
| `code_chunking_strategy` | string | `null` | (hierarchical) Strategy for splitting fenced code blocks. Only `"standard"` is supported. |
| `max_line_count` | integer \| string | `null` | (line) Maximum lines per chunk. Combined with `max_token_count`, whichever limit fires first wins. |
| `return_enriched_text` | boolean \| string | `false` | When `true`, each chunk carries an `enriched_text` field with heading/caption prefixes prepended (docling's `contextualize()` output). |

#### `pypdf` driver — action-level

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `password` | string | `null` | Password used to decrypt the PDF when it is encrypted. |
| `extraction_mode` | string | `plain` | Text extraction mode. `plain` returns reading-order text; `layout` preserves positional whitespace. |
| `page_range` | string | `null` | Page range spec like `"1-5,7"` (one-based). Omit to emit every page. |

## Output shape

Every chunk record shares this shape:

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Chunk text. |
| `index` | integer | Zero-based position in the emit order. |
| `meta` | object | Driver-specific metadata (see below). |
| `enriched_text` | string | Only present when `return_enriched_text` is `true` on the docling driver. Chunk text with heading and caption prefixes prepended. |

Docling `meta` fields (exported from `DocMeta`):

| Field | Type | Description |
|-------|------|-------------|
| `headings` | string[] | Heading hierarchy leading to the chunk. |
| `doc_items` | array | Provenance items for the source elements (page numbers, bounding boxes, item kinds). |
| `origin` | object | Original document reference (name, mimetype, hash). |

pypdf `meta` fields:

| Field | Type | Description |
|-------|------|-------------|
| `number` | integer | One-based page number. |
| `rotation` | integer | Page rotation in degrees. |

### Non-streaming envelope

When `streaming` is `false`, each source produces a wrapper dict instead of a raw chunk sequence:

```jsonc
// docling driver
{
  "chunks": [
    { "text": "...", "index": 0, "meta": { "headings": [...], "doc_items": [...] } },
    ...
  ]
}

// pypdf driver
{
  "pages": [
    { "text": "...", "index": 0, "meta": { "number": 1, "rotation": 0 } },
    ...
  ]
}
```

When `source` is a list, the action returns a list of these wrapper dicts, one per source.

## Chunker strategies (docling)

| Strategy | Token-aware | Best for |
|----------|-------------|----------|
| `hybrid` (default) | yes | Retrieval / embedding pipelines that need heading-scoped, uniformly sized chunks. |
| `hierarchical` | no | Reading-order preservation. Chunks follow heading boundaries with no size cap. |
| `line` | yes | Structured content where line boundaries matter (tables, code, logs). |
| `page` | no | Per-page provenance. One chunk per source page. |
| (omitted) | n/a | Whole document as a single markdown chunk. Useful for downstream consumers that want the full text. |

## Examples

### Parse a PDF into token-sized chunks

```yaml
components:
  - id: loader
    type: document-loader
    driver: docling
    backend: pypdfium2
    tokenizer: sentence-transformers/all-MiniLM-L6-v2
    action:
      source: ${input.source as file/path}
      chunker: hybrid
      max_token_count: 384
      streaming: true
```

### Stream page text with pypdf

```yaml
components:
  - id: loader
    type: document-loader
    driver: pypdf
    action:
      source: ${input.source as file/path}
      page_range: "1-5"
      streaming: true
```

### Attach heading-enriched text for embedding

```yaml
components:
  - id: loader
    type: document-loader
    driver: docling
    tokenizer: BAAI/bge-small-en
    action:
      source: ${input.source as file/path}
      chunker: hybrid
      max_token_count: 512
      return_enriched_text: true
      streaming: true
```

### Enable OCR for scanned pages

```yaml
components:
  - id: loader
    type: document-loader
    driver: docling
    enable_ocr: true
    ocr_engine: easyocr
    action:
      source: ${input.source as file/path}
      chunker: hybrid
```

`backend: pypdfium2` cannot run OCR; leave the backend unset (docling-parse default) when scanning image-based pages.

### Whole document as a single chunk

```yaml
components:
  - id: loader
    type: document-loader
    driver: docling
    action:
      source: ${input.source as file/path}
      streaming: true
      # `chunker` omitted → entire document as one markdown chunk
```

## Performance notes

Docling's parsing stage is not lazy: the full document must be parsed before the first chunk is emitted. Time-to-first-chunk therefore equals the parsing time, not the chunker's per-chunk cost.

To shorten that gap:
- Prefer `backend: pypdfium2` on text-layer PDFs.
- Keep `enable_ocr: false` unless the document is scanned.
- Turn off `recognize_table` when tables aren't important — TableFormer dominates parse time on table-heavy pages.
- Set `accelerator: cuda` or `mps` when a GPU is available.

For truly lazy, page-by-page streaming, use the `pypdf` driver instead; it opens the file and emits pages as it reads them.

## Best Practices

1. **Match the tokenizer to the downstream model.** The docling driver's `tokenizer` field decides how `max_token_count` is counted. If your embedding or LLM step uses a different tokenizer, chunks may under- or over-shoot the real token limit.
2. **Use `file/path` and `file/url` hints on inputs.** The DSL type hint (`${input.source as file/path}` / `${input.source as file/url}`) tells the renderer whether the source is a filesystem path, a URL, or a stream. Without it, ambiguous strings are treated as raw text.
3. **Enable `streaming: true` for large documents.** Otherwise the whole chunk list is materialized in memory before the response begins.
4. **Reach for `pypdf` when you don't need docling's structural recovery.** It has no model warm-up and streams page text as it reads.
5. **Combine `pypdfium2` + `enable_ocr: false` for the fastest text-only path with docling.** The driver logs a warning if the two are mixed; the OCR request is silently ignored by the backend.
