# Media Downloader Component

The media downloader component fetches audio or video from a URL and returns it as a stream, ready to feed into downstream components (normalize, transcribe, index, ...). It wraps the Python API of `yt-dlp`, so any site the [yt-dlp extractor list](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) covers (YouTube, Vimeo, SoundCloud, Bandcamp, and hundreds more) works out of the box.

## Basic Configuration

```yaml
component:
  type: media-downloader
  driver: ytdlp
  action:
    url: ${input.url}
    extract_audio: true
    audio_format: mp3
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `media-downloader` |
| `driver` | string | `ytdlp` | Downloader backend driver. |
| `actions` | array | `[]` | List of download actions. |

### Action Configuration

Common to all drivers:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string \| string[] | **required** | Source URL, or list of URLs, to download from. A list downloads each URL and returns one result per URL. |
| `batch_size` | integer \| string | `1` | Number of URLs downloaded concurrently per batch when `url` is a list or stream. |

Additional fields for the `ytdlp` driver:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `extract_audio` | boolean \| string | `false` | When `true`, runs yt-dlp with the `FFmpegExtractAudio` postprocessor and returns the result as an audio stream. When `false`, returns the raw download as a video stream. |
| `audio_format` | string | `m4a` | Target audio container when `extract_audio` is `true` (e.g., `mp3`, `m4a`, `opus`, `flac`). |
| `video_format` | string | `mp4` | Target video container preferred when merging separate streams (e.g., `mp4`, `webm`). |
| `format_selector` | string | (auto) | yt-dlp format selector expression that overrides the default selection (e.g., `bestaudio[abr<=128]`, `bestvideo[height<=720]+bestaudio`). See [yt-dlp format selection](https://github.com/yt-dlp/yt-dlp#format-selection). |
| `cookies` | dict | `{}` | Cookies sent with the download request as name/value pairs. Required for age-gated / member-only content. |

## Supported Drivers

### yt-dlp

Uses the `yt_dlp.YoutubeDL` Python API directly (no CLI shell-out). Supports every site listed in the yt-dlp extractor list. When `extract_audio: true` is set, yt-dlp invokes `ffmpeg` internally to perform audio extraction.

```yaml
component:
  type: media-downloader
  driver: ytdlp
  action:
    url: ${input.url}
```

**Requires:**
- `yt-dlp` Python package — installed automatically on first run.
- `ffmpeg` binary on `PATH` — required by yt-dlp for audio extraction (`extract_audio: true`) and for merging separate video+audio streams.

## Output Format

Depends on `extract_audio`:

- **`extract_audio: true`** → `AudioStreamResource` with the resulting container as its format hint (e.g. `mp3`, `m4a`).
- **`extract_audio: false`** → `VideoStreamResource` with the resulting container as its format hint (e.g. `mp4`, `webm`).

When `url` is a list, the action returns a list of stream resources in the same order.

The stream is backed by a temporary file that is auto-deleted after the caller finishes reading it, so long downloads don't pin memory.

## Multiple Actions Configuration

Define separate actions for audio-only and video downloads on the same component:

```yaml
component:
  type: media-downloader
  driver: ytdlp
  actions:
    - id: download-audio
      url: ${input.url}
      extract_audio: true
      audio_format: mp3

    - id: download-video
      url: ${input.url}
      video_format: mp4
```

## Integration with Workflows

### Download and Normalize Loudness

Chain the downloader into an audio processor to produce a broadcast-ready file:

```yaml
workflows:
  - id: download-and-normalize
    jobs:
      - id: download
        component: downloader
        input:
          url: ${input.url}
        output: ${output as audio}

      - id: normalize
        component: normalizer
        depends_on: [download]
        input:
          audio: ${jobs.download.output}
          level: -14
        output: ${output as audio}

components:
  - id: downloader
    type: media-downloader
    driver: ytdlp
    action:
      url: ${input.url}
      extract_audio: true
      audio_format: wav

  - id: normalizer
    type: audio-processor
    action:
      method: normalize
      mode: lufs
      audio: ${input.audio}
      level: ${input.level}
```

### Download and Transcribe

```yaml
workflows:
  - id: download-and-transcribe
    jobs:
      - id: download
        component: downloader
        input:
          url: ${input.url}
        output: ${output as audio}

      - id: transcribe
        component: whisper
        depends_on: [download]
        input:
          audio: ${jobs.download.output}
        output:
          transcript: ${output.text}

components:
  - id: downloader
    type: media-downloader
    driver: ytdlp
    action:
      url: ${input.url}
      extract_audio: true
      audio_format: wav
```

### Batch Download from a List

Download several URLs concurrently and pass the resulting streams to a downstream component:

```yaml
workflows:
  - id: batch-download
    job:
      component: downloader
      input:
        urls: ${input.urls}

components:
  - id: downloader
    type: media-downloader
    driver: ytdlp
    action:
      url: ${input.urls}
      batch_size: 4
      extract_audio: true
      audio_format: mp3
```

### Authenticated Download

Pass session cookies from an earlier login job or from workflow input:

```yaml
components:
  - id: downloader
    type: media-downloader
    driver: ytdlp
    action:
      url: ${input.url}
      cookies: ${input.cookies}
      extract_audio: true
      audio_format: m4a
```

## Best Practices

1. **Pick a lossless format for downstream processing.** If the next step re-encodes (normalize, transcribe, splice), use `wav` or `flac` for `audio_format` to avoid double-lossy compression. Reserve `mp3` / `m4a` for terminal delivery.
2. **Use `format_selector` sparingly.** Default selection (`bestaudio/best` when extracting audio; container-preferred merge when not) covers most cases. Reach for `format_selector` only when you need a specific quality cap or codec — for example `bestaudio[abr<=128]` to cap bitrate before download.
3. **Cap concurrency for a single site.** `batch_size` runs URLs concurrently, but hitting one site (e.g., YouTube) with too many parallel requests can trigger rate limiting. Keep `batch_size` at 2–4 for same-site batches.
4. **Cookies are per-request.** The driver writes the `cookies` dict to a temporary Netscape cookie jar for the duration of one download and deletes it after. Nothing is persisted between actions.
5. **`ffmpeg` is required for audio extraction.** yt-dlp shells out to `ffmpeg` for the `FFmpegExtractAudio` postprocessor and for merging separate video+audio streams. Install it via your OS package manager (`brew install ffmpeg`, `apt install ffmpeg`).
