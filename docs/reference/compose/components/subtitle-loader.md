# Subtitle Loader Component

The subtitle loader component reads subtitle tracks — either from a URL (YouTube, Vimeo, etc.) via `yt-dlp` or from a local file / uploaded stream / inline text — parses them, and returns segments (start/end/duration/text) that downstream components can align, translate, index, or render. Subtitles come out as structured data, not a file, so the next step never has to know where they came from.

## Basic Configuration

```yaml
component:
  type: subtitle-loader
  driver: ytdlp
  action:
    url: ${input.url}
    languages: [en, ko]
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `subtitle-loader` |
| `driver` | string | `local` | Backend driver. One of `local`, `ytdlp`. |
| `actions` | array | `[]` | List of load actions. |

### Action Configuration

Common to all drivers:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `batch_size` | integer \| string | `1` | Number of sources processed concurrently per batch when the input is a list or stream. |

#### `local` driver

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | string \| string[] | **required** | Subtitle file source, or list of sources. Each entry may be a file path, an upload stream, or raw subtitle text. |
| `format` | string | (auto) | Subtitle format (e.g. `srt`, `vtt`, `ass`). Inferred from the file extension or content when omitted. |
| `encoding` | string | (auto) | Text encoding (e.g. `utf-8-sig`). Auto-detected when omitted. |

#### `ytdlp` driver

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string \| string[] | **required** | Source URL, or list of URLs, whose subtitles are fetched. |
| `languages` | string \| string[] | `null` | Requested subtitle languages as BCP-47 / ISO 639-1 codes. When omitted, the driver requests `en`. Every language actually present on the source is downloaded and returned; entries are emitted in the order given. |
| `format` | string \| string[] | `srt` | Subtitle file format requested from yt-dlp (`srt`, `vtt`, `json3`, ...). |
| `include_auto_generated` | boolean \| string | `true` | Whether to fall back to auto-generated captions when no human subtitle is available for a requested language. |
| `cookies` | dict[] \| string | `[]` | Cookies sent with the request, in the shape returned by browser cookie-export tools. Required for age-gated or member-only content. |
| `extractor_args` | dict[dict] \| string | `{}` | Extractor-specific arguments keyed by extractor name, mirroring yt-dlp's `--extractor-args`. |
| `js_runtimes` | string \| string[] | `deno` | JavaScript runtimes yt-dlp may use to solve player challenges, in priority order. Each entry may carry a path as `RUNTIME:PATH`. |

## Languages field (ytdlp)

`languages` is both a filter and an ordering hint:

- **Filter** — only languages you list are downloaded. Absent tracks are silently skipped.
- **Ordering** — returned entries follow the order you specify, so priority-sensitive consumers can pick the first hit.

For each requested language, yt-dlp emits the human-authored subtitle when present; when it is absent and `include_auto_generated` is `true`, the auto-generated caption is used instead. The `is_auto_generated` flag on each entry tells you which one you got.

If none of the requested languages exist on the source, the action raises — it does not silently return an empty result.

```yaml
# Prefer Korean, fall back to English if Korean isn't there
languages: [ko, en]

# Grab every language you're likely to need — missing ones are just skipped
languages: [en, ko, ja, es]
```

## Output shape

The output shape differs by driver.

### `ytdlp` driver

Each URL produces a **list** of subtitle entries — one per language actually downloaded — in the order requested via `languages`.

```jsonc
[
  {
    "language": "en",
    "is_auto_generated": false,
    "format": "srt",
    "full_text": "Hello, world. ...",
    "segments": [
      { "start_time": 0.0, "end_time": 1.42, "duration": 1.42, "text": "Hello, world." },
      { "start_time": 1.42, "end_time": 3.10, "duration": 1.68, "text": "..." }
    ]
  },
  {
    "language": "ko",
    "is_auto_generated": true,
    "format": "srt",
    "full_text": "안녕, 세계. ...",
    "segments": [ ... ]
  }
]
```

When `url` is a list, the action returns a nested list — one per-URL entry list per input URL: `[[url1_entries], [url2_entries], ...]`.

### `local` driver

Each source (path / stream / raw text) produces a **single** subtitle dict — a local file carries one track, so there is no language dimension to fan out on.

```jsonc
{
  "format": "srt",
  "full_text": "Hello, world. ...",
  "segments": [
    { "start_time": 0.0, "end_time": 1.42, "duration": 1.42, "text": "Hello, world." }
  ]
}
```

When `source` is a list, the action returns a list of these dicts, one per source.

### Segment shape

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | float | Segment start in seconds. |
| `end_time` | float | Segment end in seconds. |
| `duration` | float | `end_time - start_time`, precomputed for convenience. |
| `text` | string | Plain-text content (formatting tags stripped). |

## Examples

### Fetch subtitles from YouTube

```yaml
workflows:
  - id: fetch-subs
    job:
      component: subs
      input:
        url: ${input.url}

components:
  - id: subs
    type: subtitle-loader
    driver: ytdlp
    action:
      url: ${input.url}
      languages: [en, ko]
      format: srt
```

### Load a local subtitle file

```yaml
components:
  - id: subs
    type: subtitle-loader
    driver: local
    action:
      source: ${input.path}
```

### Subtitles → Translation

```yaml
workflows:
  - id: transcript-to-translation
    jobs:
      - id: fetch
        component: subs
        input:
          url: ${input.url}
        output: ${output}

      - id: translate
        component: translator
        depends_on: [fetch]
        input:
          # Pick the first (highest-priority) language actually returned
          text: ${jobs.fetch.output.0.full_text}
        output:
          translated: ${output.text}

components:
  - id: subs
    type: subtitle-loader
    driver: ytdlp
    action:
      url: ${input.url}
      languages: [en]
```

### Batch fetch multiple URLs

```yaml
components:
  - id: subs
    type: subtitle-loader
    driver: ytdlp
    action:
      url: ${input.urls}
      batch_size: 4
      languages: [en]
```

### Authenticated fetch

Pass session cookies for member-only or age-gated content:

```yaml
components:
  - id: subs
    type: subtitle-loader
    driver: ytdlp
    action:
      url: ${input.url}
      cookies: ${input.cookies}
      languages: [en]
```

## Best Practices

1. **List every language you can use.** `languages` is a filter, not a ranking — every match is downloaded. If you want fall-through behavior at the workflow layer, list all acceptable languages and index into the returned array by position.
2. **Check `is_auto_generated` before trusting the text.** Auto-captions from `automatic_captions` are decent for search / indexing but often wrong on proper nouns, jargon, and timing. Downstream steps that show text to a user (rendering, translation-for-publication) should branch on this flag.
3. **Cap concurrency on the same site.** Like the media downloader, hitting one host with too many parallel `yt-dlp` requests invites rate limits. Keep `batch_size` at 2–4 when batching URLs from the same domain.
4. **Prefer `srt` for parsing, `vtt` for cue styling.** The parser handles both, but `srt` is the smallest surface area if you only need timing + text. Reach for `vtt` when you need positional / styling cues (rare for downstream AI use).
