# Media Downloader Component

The media downloader component fetches audio or video from a URL and returns it as a stream, ready to feed into downstream components (normalize, transcribe, index, ...). It wraps the Python API of `yt-dlp`, so any site the [yt-dlp extractor list](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) covers (YouTube, Vimeo, SoundCloud, Bandcamp, and hundreds more) works out of the box.

## Basic Configuration

```yaml
component:
  type: media-downloader
  driver: ytdlp
  action:
    url: ${input.url}
    format: mp3
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
| `format` | preset \| string \| object | (best) | Download format. See [Format field](#format-field) below. |
| `cookies` | dict | `{}` | Cookies sent with the download request as name/value pairs. Required for age-gated / member-only content. |

## Format field

`format` is the single entry point for controlling what yt-dlp downloads. It accepts three shapes:

### 1. Preset (string)

A container-name shortcut that expands to a preconfigured selector plus postprocessor. Presets that overlap with yt-dlp's `-t / --preset-alias` (`mp3`, `aac`, `mp4`, `mkv`) mirror those definitions verbatim; the rest follow the same pattern for other common containers. Any string not in this table is treated as a raw yt-dlp expression (see below).

**Audio presets** — return an `AudioStreamResource`:

| Preset | Selector | Notes |
|--------|----------|-------|
| `mp3` | `ba[acodec^=mp3]/ba/b` | mirrors yt-dlp `-t mp3` |
| `aac` | `ba[acodec^=aac]/ba[acodec^=mp4a.40.]/ba/b` | mirrors yt-dlp `-t aac` |
| `m4a` | `ba[ext=m4a]/ba[acodec^=mp4a.40.]/ba/b` | AAC in mp4 container |
| `opus` | `ba[acodec=opus]/ba[ext=webm]/ba/b` | prefers webm/opus source |
| `vorbis` | `ba[acodec=vorbis]/ba/b` | |
| `flac` | `ba/b` + `FFmpegExtractAudio(flac)` | lossless re-encode |
| `alac` | `ba/b` + `FFmpegExtractAudio(alac)` | lossless re-encode |
| `wav` | `ba/b` + `FFmpegExtractAudio(wav)` | uncompressed PCM |

**Video presets** — return a `VideoStreamResource`:

| Preset | Behavior | Notes |
|--------|----------|-------|
| `mp4` | remux to mp4, prefer h264/aac | mirrors yt-dlp `-t mp4` |
| `mkv` | remux to mkv | mirrors yt-dlp `-t mkv` |
| `webm` | remux to webm, prefer vp9/opus | |

```yaml
format: mp3      # audio-only, extracted to mp3
format: opus     # audio-only, opus (webm-preferred)
format: mp4      # merged video remuxed to mp4
format: webm     # merged video remuxed to webm (vp9/opus)
```

### 2. Raw yt-dlp expression (string)

Any string not in the preset table is passed through to yt-dlp's `-f` flag unchanged. Use this for advanced selectors that the structured spec cannot express. See [yt-dlp format selection](https://github.com/yt-dlp/yt-dlp#format-selection) for the full syntax.

```yaml
format: "bestvideo[height<=720]+bestaudio/best"
format: "bestvideo[ext=${input.container}]+bestaudio/best[ext=${input.container}]/best"
```

Raw expressions are always treated as video downloads (the resulting stream is wrapped as `VideoStreamResource`). Use a preset or structured spec if you need audio semantics.

### 3. Structured spec (object)

Declarative fields that compile into a yt-dlp `-f` selector plus any needed postprocessors.

| Field | Type | Applies to | Description |
|-------|------|------------|-------------|
| `media` | `audio` \| `video` | **required** | Whether to download an audio-only stream or a merged video stream. |
| `container` | string | both | Target container/extension (e.g., `mp3`, `m4a`, `opus`, `mp4`, `webm`). For `audio` also sets the `FFmpegExtractAudio` codec; for `video` sets the merge container. |
| `codec` | string | both | Preferred codec prefix (e.g., `avc1` for video, `opus` for audio); routed to yt-dlp's `vcodec^=` / `acodec^=` filter. |
| `max_height` | integer \| string | video | Maximum video height in pixels. |
| `max_fps` | integer \| string | video | Maximum frame rate. |
| `max_bitrate` | integer \| string | both | Maximum bitrate in kbps (`abr<=` for audio, `vbr<=` for video). |
| `max_filesize` | integer \| string | both | Maximum filesize; accepts yt-dlp size expressions (e.g., `50M`, `1G`). |
| `hdr` | boolean | video | Prefer HDR streams when `true`. |
| `prefer_free_formats` | boolean | both | Prefer patent-free formats (webm/opus/vp9) when `true`. |

```yaml
# audio-only, mp3 at ≤128 kbps
format:
  media: audio
  container: mp3
  max_bitrate: 128

# 720p mp4 with avc1 video codec
format:
  media: video
  container: mp4
  codec: avc1
  max_height: 720
```

## Supported Drivers

### yt-dlp

Uses the `yt_dlp.YoutubeDL` Python API directly (no CLI shell-out). Supports every site listed in the yt-dlp extractor list. When `format` selects an audio-only download (preset or `media: audio`), yt-dlp invokes `ffmpeg` internally to perform audio extraction.

```yaml
component:
  type: media-downloader
  driver: ytdlp
  action:
    url: ${input.url}
```

**Requires:**
- `yt-dlp` Python package — installed automatically on first run.
- `ffmpeg` binary on `PATH` — required by yt-dlp for audio extraction and for merging separate video+audio streams.

## Output Format

The output stream type depends on the selected `format`:

- **Audio preset (`mp3`, `m4a`, ...) or `media: audio`** → `AudioStreamResource` with the resulting container as its format hint.
- **Video preset (`mp4`, `mkv`), `media: video`, raw expression, or omitted** → `VideoStreamResource` with the resulting container as its format hint.

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
      format: mp3

    - id: download-video
      url: ${input.url}
      format: mp4
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
      format:
        media: audio
        container: wav

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
      format:
        media: audio
        container: wav
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
      format: mp3
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
      format:
        media: audio
        container: m4a
```

## Best Practices

1. **Pick a lossless format for downstream processing.** If the next step re-encodes (normalize, transcribe, splice), use `wav` or `flac` for the audio container to avoid double-lossy compression. Reserve `mp3` / `m4a` for terminal delivery.
2. **Start with presets, escalate to structured, escape to raw only when needed.** The preset covers the common "give me mp3" case in one word. Move to `format: { media, container, max_height, ... }` when you need caps or filters. Reach for a raw yt-dlp expression only when the structured spec genuinely can't express it.
3. **Cap concurrency for a single site.** `batch_size` runs URLs concurrently, but hitting one site (e.g., YouTube) with too many parallel requests can trigger rate limiting. Keep `batch_size` at 2–4 for same-site batches.
4. **Cookies are per-request.** The driver writes the `cookies` dict to a temporary Netscape cookie jar for the duration of one download and deletes it after. Nothing is persisted between actions.
5. **`ffmpeg` is required for audio extraction.** yt-dlp shells out to `ffmpeg` for the `FFmpegExtractAudio` postprocessor and for merging separate video+audio streams. Install it via your OS package manager (`brew install ffmpeg`, `apt install ffmpeg`).
