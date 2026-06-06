# File Store Component

The file store component provides a unified interface for storing, retrieving, and managing files across local filesystems and major cloud object storage services (AWS S3, Google Cloud Storage, Azure Blob Storage). It supports operations like put, get, delete, exists, and list, with streaming I/O for handling large files without memory overhead.

## Basic Configuration

```yaml
component:
  type: file-store
  driver: local
  base_path: ./storage
  action:
    method: put
    path: ${input.filename}
    source: ${input.file}
```

## Configuration Options

### Component Settings

All file-store drivers share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `file-store` |
| `driver` | string | **required** | Backend driver: `local`, `aws-s3`, `gcp-storage`, `azure-blob` |
| `base_path` | string | local: cwd / cloud: bucket root | Base prefix for all action `path` inputs. Not included in the logical `path` users see |
| `actions` | array | `[]` | List of file store actions |

### Common Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Operation method: `put`, `get`, `delete`, `exists`, `list` |

## Supported Drivers

### Local Filesystem

Store files on the local filesystem:

```yaml
component:
  type: file-store
  driver: local
  base_path: ./storage
```

The local driver has no additional fields beyond the common `base_path`.

- **`base_path` default**: current working directory. Explicit configuration is recommended.
- **Auto directory creation**: `put` automatically creates intermediate directories within `base_path` (matching the flat-namespace behavior of cloud drivers).
- **Path traversal protection**: Action `path` values that escape `base_path` via `../` or absolute paths are rejected.

### AWS S3

Store objects in Amazon S3 or S3-compatible storage (MinIO, Cloudflare R2, Wasabi, Backblaze B2, etc.):

```yaml
component:
  type: file-store
  driver: aws-s3
  bucket: my-app-assets
  region: ap-northeast-2
  access_key_id: ${env.AWS_ACCESS_KEY_ID}
  secret_access_key: ${env.AWS_SECRET_ACCESS_KEY}
  base_path: workflows/
```

**AWS S3 Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bucket` | string | **required** | S3 bucket name |
| `region` | string | `null` | AWS region. Uses SDK default if not set |
| `endpoint` | string | `null` | Custom endpoint for S3-compatible storage (MinIO, R2, etc.) |
| `access_key_id` | string | `null` | Auto-loaded from environment/IAM role if not set |
| `secret_access_key` | string | `null` | Auto-loaded from environment/IAM role if not set |
| `session_token` | string | `null` | STS temporary credentials |

**Using S3-compatible storage (MinIO):**

```yaml
component:
  type: file-store
  driver: aws-s3
  bucket: my-bucket
  endpoint: http://minio.local:9000
  access_key_id: ${env.MINIO_ACCESS_KEY}
  secret_access_key: ${env.MINIO_SECRET_KEY}
```

### Google Cloud Storage

Store objects in Google Cloud Storage:

```yaml
component:
  type: file-store
  driver: gcp-storage
  bucket: my-app-assets
  project: my-gcp-project
  credentials_path: ./gcp-service-account.json
```

**GCP Storage Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bucket` | string | **required** | GCS bucket name |
| `project` | string | `null` | GCP project ID. Uses SDK default if not set |
| `credentials_path` | string | `null` | Path to service account JSON key file. Uses Application Default Credentials if not set |

### Azure Blob Storage

Store blobs in Azure Blob Storage:

```yaml
component:
  type: file-store
  driver: azure-blob
  container: my-container
  connection_string: ${env.AZURE_STORAGE_CONNECTION_STRING}
```

**Azure Blob Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `container` | string | **required** | Blob container name |
| `connection_string` | string | `null` | Azure Storage connection string (simplest authentication) |
| `account_name` | string | `null` | Storage account name (when not using `connection_string`) |
| `account_key` | string | `null` | Account key (when not using `connection_string`) |

> **Note**: `connection_string` and `(account_name, account_key)` are mutually exclusive. If neither is provided, `DefaultAzureCredential` (environment-based) is attempted.

## Path Semantics

All action `path` inputs are **logical paths** from the user's perspective. The component-level `base_path` is automatically prepended internally but never appears in user-facing path strings.

| Position | Meaning |
|----------|---------|
| Action input `path` | Logical path. Internally composed as `base_path + path` for the driver call |
| Result `path` | Logical path. Can be passed directly to subsequent `get`/`delete`/`exists` actions |
| Result `url` | External-facing URL. HTTPS for cloud, `file://` for local. Includes `base_path` |

This logical/physical separation:
- Prevents `base_path` from being applied twice in chained actions.
- Lets users change `base_path` without rewriting path references.
- Allows `url` to be used in external systems (logs, downstream components, user-facing outputs).

> **Path values can use `/`**: Paths like `dir1/dir2/file.txt` are valid and natural. On local drivers, this maps to a directory tree; on cloud drivers, slashes are just characters in the flat-namespace key.

## File Store Operations

### Put — Store Data

Write data to the store. On cloud drivers this uploads an object; on local it writes a file.

```yaml
component:
  type: file-store
  driver: aws-s3
  bucket: my-bucket
  action:
    method: put
    path: images/${input.id}.png
    source: ${input.file}
    content_type: image/png
```

**Put Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `put` |
| `path` | string | **required** | Logical path within the store |
| `source` | any | **required** | Data to store (see [Source Handling](#source-handling)) |
| `content_type` | string | inferred from path extension | MIME type |
| `metadata` | dict | `{}` | Object metadata (cloud only; ignored on local) |
| `multipart_threshold` | int \| string | `8MB` | Size threshold for switching to multipart upload (cloud only) |
| `chunk_size` | int \| string | `8MB` | Chunk size for streaming/multipart |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.path` | string | Logical path (same as input — usable in subsequent actions) |
| `result.url` | string | External-facing URL (HTTPS or `file://`). Does not guarantee access permission |
| `result.size` | integer | Bytes written |
| `result.content_type` | string \| null | MIME type if known |

### Get — Retrieve Data

Read data from the store. Three modes are available depending on where the output goes.

```yaml
# Mode 1: Default — bytes in memory (small files only)
component:
  type: file-store
  driver: aws-s3
  bucket: my-bucket
  action:
    method: get
    path: images/${input.id}.png
    output:
      data: ${result.content}
```

```yaml
# Mode 2: Save to local file (large files — recommended)
component:
  type: file-store
  driver: aws-s3
  bucket: my-bucket
  action:
    method: get
    path: ${input.path}
    save_to: /tmp/${input.id}.bin
    output:
      saved_to: ${result.save_to}
```

```yaml
# Mode 3: Stream to next job (lazy consumption)
component:
  type: file-store
  driver: aws-s3
  bucket: my-bucket
  action:
    method: get
    path: ${input.path}
    streaming: true
    output:
      stream: ${result.content}
```

**Get Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `get` |
| `path` | string | **required** | Logical path to retrieve |
| `save_to` | string | `null` | Local path to save into. Parent directory must exist. If an existing directory is given, the file is saved inside it using the basename of `path` |
| `streaming` | bool \| string | `false` | If `true`, returns a `StreamResource` for lazy consumption in subsequent jobs |
| `chunk_size` | int \| string | `8MB` | Streaming/download chunk size |

**Return Value (common fields):**

| Field | Type | Description |
|-------|------|-------------|
| `result.path` | string | Logical path (same as input) |
| `result.url` | string | External-facing URL |
| `result.size` | integer | Bytes downloaded |
| `result.content_type` | string \| null | MIME type if known |
| `result.modified_at` | string \| null | ISO 8601 timestamp of last modification, if available |

**Mode-specific fields:**

| Mode | Additional Field | Description |
|------|------------------|-------------|
| Default (no `save_to`, `streaming: false`) | `result.content` | Downloaded bytes |
| With `save_to` | `result.save_to` | Local path where the file was saved (resolved path when a directory was given) |
| With `streaming: true` | `result.content` | `StreamResource` for chunk-wise consumption |

> **Large files**: Avoid the default in-memory mode. Use `save_to` if you want the file on disk, or `streaming: true` to pipe it into the next job lazily. The default mode loads the entire file into memory and is only appropriate for small files.

> **`save_to` + `streaming: true`**: Setting both is rejected at schema validation time. Choose one — save to disk, or stream to the next job.

### Delete — Remove Data

```yaml
component:
  type: file-store
  driver: aws-s3
  bucket: my-bucket
  action:
    method: delete
    path: temp/${input.id}.bin
```

**Delete Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `delete` |
| `path` | string | **required** | Logical path to delete |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.path` | string | Logical path (same as input) |
| `result.deleted` | boolean | Always `true` if the request succeeded |

> **Idempotent**: `delete` returns `deleted: true` even when the object did not exist (matches S3/GCS/Azure behavior). To check existence before deletion, combine `exists` + `delete` explicitly. Network or permission errors raise exceptions rather than returning `deleted: false`.

### Exists — Check Existence

```yaml
component:
  type: file-store
  driver: aws-s3
  bucket: my-bucket
  action:
    method: exists
    path: ${input.path}
```

**Exists Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `exists` |
| `path` | string | **required** | Logical path to check |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.path` | string | Logical path (same as input) |
| `result.exists` | boolean | Whether the object exists |

### List — Enumerate Objects

```yaml
component:
  type: file-store
  driver: aws-s3
  bucket: my-bucket
  action:
    method: list
    path: images/
    recursive: true
    pattern: "*.png"
    max_result_count: 100
```

**List Action Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Must be `list` |
| `path` | string | `null` | Path prefix filter. On local, lists directory contents; on cloud, matches the key prefix. End with `/` for directory/namespace semantics |
| `recursive` | bool \| string | `false` | If `true`, descend into subdirectories (local) or list across `/` boundaries (cloud). If `false`, only the immediate level under `path` is returned |
| `pattern` | string | `null` | Glob pattern (e.g. `*.jpg`, `**/*.png`) to filter results. Matched against each item's logical `path` relative to `base_path`. Use `**` to span subdirectories regardless of `recursive` semantics |
| `max_result_count` | integer | driver default (S3: 1000, GCS: 1000, Azure: 5000) | Maximum items per response |
| `next_token` | string | `null` | Pass the `next_token` from the previous response to continue pagination. Omit on the first call |

**Return Value:**

| Field | Type | Description |
|-------|------|-------------|
| `result.items` | array | List of object descriptors |
| `result.items[i].path` | string | Logical path — usable directly in subsequent `get`/`delete`/`exists` |
| `result.items[i].url` | string | External-facing URL |
| `result.items[i].size` | integer | Object size in bytes |
| `result.items[i].content_type` | string \| null | MIME type if available |
| `result.items[i].modified_at` | string | ISO 8601 timestamp |
| `result.count` | integer | Items in this response (not total) |
| `result.next_token` | string \| null | Pagination token. `null` if no more pages |

**`recursive` behavior by driver:**

| Driver | `recursive: false` | `recursive: true` |
|--------|--------------------|--------------------|
| `local` | Files directly under `path` only; subdirectories are not descended into | Walks all subdirectories under `path` |
| `aws-s3` / `gcp-storage` / `azure-blob` | Adds a `/` delimiter — only keys without further `/` after the prefix are returned (one "level") | All keys matching the prefix, regardless of `/` boundaries |

> **Glob patterns and pagination**: `pattern` is applied as a post-filter after the driver returns a page. On cloud drivers, a response page may be smaller than `max_result_count` (or even empty) when many items don't match the pattern — `next_token` is still honored, so keep paginating until it becomes `null`.

> **Subdirectories are not listed**: `list` only returns files. Directory entries (local) and common prefixes (cloud) are excluded from `items`. To enumerate the directory structure, use `recursive: true` and derive the structure from each item's `path`.

## Source Handling

The `source` field accepts multiple types and is processed based on the runtime Python type after variable rendering:

| Rendered Type | Processing | Memory |
|---------------|------------|--------|
| `UploadFile` (HTTP upload) | Stream from internal file/buffer in chunks | O(chunk_size) |
| `StreamResource` | Consumed chunk by chunk | O(chunk_size) |
| File-like (`read()` method) | Wrapped as `StreamResource` | O(chunk_size) |
| `bytes` / `bytearray` | Wrapped as `BytesStreamResource`. Split into chunks if larger than `multipart_threshold` | O(data_size) |
| `str` | Encoded as UTF-8 and stored as text. **Not interpreted as a file path** | O(text_size) |

### Common Patterns

```yaml
# 1. Save an HTTP-uploaded file directly (most common case)
- method: put
  path: uploads/${input.filename}
  source: ${input.file}                    # UploadFile is auto-detected

# 2. Upload a local file by explicit path
- method: put
  path: backups/data.bin
  source: ${input.file_path as file;path}  # Cast to file path

# 3. Lazy-pipe a stream from a previous job
- method: put
  path: processed/output.bin
  source: ${jobs.transform.response.stream}  # StreamResource

# 4. Pass raw bytes
- method: put
  path: data/payload.bin
  source: ${jobs.encode.response.data}     # bytes

# 5. Save text
- method: put
  path: logs/message.txt
  source: "Hello, world"                   # str saved as text
```

> **Strings are never interpreted as file paths**: `source: "/etc/passwd"` writes the literal string `/etc/passwd` as text content — it does not read that file. To upload a local file, use `${var as file;path}` casting or pass an `UploadFile`/`StreamResource`.

## Multiple Actions Configuration

Define multiple file store operations under one component:

```yaml
components:
  - id: assets
    type: file-store
    driver: aws-s3
    bucket: my-app-assets
    base_path: workflows/
    actions:
      - id: upload-image
        method: put
        path: images/${input.id}.png
        source: ${input.image_file}
        content_type: image/png

      - id: download-image
        method: get
        path: images/${input.id}.png
        save_to: /tmp/${input.id}.png

      - id: check-image
        method: exists
        path: images/${input.id}.png

      - id: delete-image
        method: delete
        path: images/${input.id}.png

      - id: list-images
        method: list
        path: images/
        max_result_count: 50
```

## Large File Handling

File stores support GB-scale files (model weights, videos, audio datasets) without loading them into memory:

- **Upload**: Pass a file path (via `${var as file;path}`), an `UploadFile`, or a `StreamResource` — the component streams the content in chunks.
- **Cloud multipart**: Files above `multipart_threshold` (default 8MB) are automatically uploaded via multipart APIs (S3 `upload_part`, GCS resumable upload, Azure block blob).
- **Download to disk**: Set `save_to` to write directly to a local file, chunk by chunk.
- **Download as stream**: Set `streaming: true` to return a `StreamResource` for the next job to consume lazily.

**Streaming a large video between jobs:**

```yaml
workflows:
  - id: process-large-video
    jobs:
      - id: fetch
        component: s3-bucket
        action: download-video
        input:
          path: ${input.video_path}
          streaming: true

      - id: transcode
        component: video-converter
        input:
          source: ${jobs.fetch.response.content}
```

> **`StreamResource` is single-use**: It can only be consumed once. If two jobs need the same data, download to a file with `save_to` and share the path.

## Advanced Usage Examples

### Storing AI Model Outputs

Save generated images, audio, or video produced by other components:

```yaml
workflows:
  - id: generate-and-save
    jobs:
      - id: generate
        component: image-generator
        input:
          prompt: ${input.prompt}

      - id: save
        component: s3-bucket
        action: upload-image
        input:
          path: generations/${input.user_id}/${input.request_id}.png
          source: ${jobs.generate.response.image}

components:
  - id: s3-bucket
    type: file-store
    driver: aws-s3
    bucket: my-generations
    base_path: outputs/
    actions:
      - id: upload-image
        method: put
        path: ${input.path}
        source: ${input.source}
        content_type: image/png
```

### Workflow Asset Management

Use list pagination to process many files:

```yaml
components:
  - id: archive
    type: file-store
    driver: gcp-storage
    bucket: my-archive
    actions:
      - id: list-batch
        method: list
        path: batch/${input.date}/
        max_result_count: 100
        next_token: ${input.token}
        output:
          files: ${result.items}
          next: ${result.next_token}
```

### Cross-Driver Migration

Copy files from local to cloud using streaming:

```yaml
workflows:
  - id: migrate-to-s3
    jobs:
      - id: fetch
        component: local-files
        action: read
        input:
          path: ${input.filename}
          streaming: true

      - id: upload
        component: s3-bucket
        action: write
        input:
          path: archive/${input.filename}
          source: ${jobs.fetch.response.content}

components:
  - id: local-files
    type: file-store
    driver: local
    base_path: ./old-storage
    actions:
      - id: read
        method: get
        path: ${input.path}
        streaming: ${input.streaming}

  - id: s3-bucket
    type: file-store
    driver: aws-s3
    bucket: archive-bucket
    actions:
      - id: write
        method: put
        path: ${input.path}
        source: ${input.source}
```

## URL Semantics

The `url` field returned by `put`/`get`/`list` follows driver-specific conventions:

| Driver | `url` Format |
|--------|--------------|
| `local` | `file://<base_path>/<path>` (absolute) |
| `aws-s3` | `https://<bucket>.s3.<region>.amazonaws.com/<base_path><path>` (or `endpoint`-based) |
| `gcp-storage` | `https://storage.googleapis.com/<bucket>/<base_path><path>` |
| `azure-blob` | `https://<account>.blob.core.windows.net/<container>/<base_path><path>` |

> **Access not guaranteed**: The `url` is a standard URL pointer to the object. Whether anonymous access succeeds depends on IAM policies and bucket/object ACLs. The component does not provide presigned URLs — use external tooling if signed URLs are required.

## Driver Scope

File-store drivers only target systems with **native protocol support that does not require OS-level mounting**. Mount-dependent systems (NFS, SMB/CIFS, SSHFS) should be mounted at the OS level and accessed through the `local` driver:

```yaml
- id: nfs-storage
  type: file-store
  driver: local
  base_path: /mnt/nfs-share/workflows   # OS-mounted path
```

S3-compatible storage (MinIO, Cloudflare R2, Wasabi, Backblaze B2, etc.) is supported via the `aws-s3` driver's `endpoint`.

## Error Handling

Common failure modes:

- **Authentication**: Invalid credentials, expired tokens, missing IAM permissions
- **Not found**: `get`/`exists` for missing objects (`exists` returns `false`, `get` raises)
- **Quota/storage limits**: Bucket-level quotas exceeded
- **Network**: Transient connectivity issues — SDKs retry chunks automatically
- **Path validation**: Action `path` containing `..`, absolute paths, or consecutive `/` is rejected

Use workflow error handling for downstream recovery:

```yaml
workflow:
  jobs:
    - id: fetch
      component: assets
      action: download
      input:
        path: ${input.path}
      on_error:
        - id: fallback
          component: backup-store
          action: download
          input:
            path: ${input.path}
```

## Variable Interpolation

All settings support variable interpolation, including credentials, paths, and source data:

```yaml
component:
  type: file-store
  driver: aws-s3
  bucket: ${env.S3_BUCKET}
  region: ${env.AWS_REGION | us-east-1}
  access_key_id: ${env.AWS_ACCESS_KEY_ID}
  secret_access_key: ${env.AWS_SECRET_ACCESS_KEY}
  base_path: ${env.S3_PREFIX | workflows/}
  action:
    method: put
    path: ${input.namespace}/${input.filename}
    source: ${input.file}
    metadata:
      workflow: ${context.workflow_id}
      user: ${input.user_id}
```

## Security Considerations

- **Path traversal (local)**: Action `path` values escaping `base_path` (`../`, absolute paths) are rejected. The local driver enforces this because traversal poses a real filesystem risk.
- **Path normalization (cloud)**: Cloud object keys allow arbitrary strings, but the component still rejects absolute paths, `.`/`..` segments, and consecutive `/` to prevent accidental key collisions. This is normalization, not a security boundary — IAM/bucket policies remain the actual boundary.
- **Credentials**: Store `access_key_id`/`secret_access_key`/`connection_string` etc. in environment variables, not in YAML.
- **`save_to`**: Permission is delegated to the OS. Do not bind untrusted user input directly to `save_to` — the workflow author is responsible for sanitizing.

## Best Practices

1. **Explicit `base_path`**: Always set `base_path` rather than relying on defaults — makes the component's scope self-documenting.
2. **Streaming for large files**: Use `save_to` (to disk) or `streaming: true` (to next job) for files larger than a few MB.
3. **Path conventions**: Use slash-delimited logical paths (`category/subcategory/file.ext`) — they work identically on local and cloud drivers.
4. **Cast source types**: Use `${var as file;path}` for explicit file uploads; let `UploadFile`/`StreamResource`/`bytes` flow naturally otherwise.
5. **Credentials via environment**: Reference credentials with `${env.*}`, never paste them in YAML.
6. **Multipart tuning**: For very large files, increase `multipart_threshold` and `chunk_size` to reduce request overhead — but keep within memory budget.

## Common Use Cases

- **AI output storage**: Save generated images, audio, video from model components
- **Input asset handling**: Receive HTTP-uploaded files and persist them
- **Cross-workflow data sharing**: Pass large artifacts between workflow runs via shared storage
- **Batch processing**: List, fetch, transform, and re-upload files in bulk
- **Backup and archival**: Mirror local data to cloud storage
- **Model weight distribution**: Stream large model weights from object storage at startup
