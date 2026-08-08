# Media Inspector Example

This example demonstrates the `media-inspector` component, which reads metadata from a media file (audio, video, or image) without decoding the content. It wraps `ffprobe` (bundled with FFmpeg) and `exiftool` and returns both a normalized field set and the tool's raw output.

## Overview

This example exposes three workflows:

1. **Inspect Media (ffprobe)**: Returns the full metadata payload for an audio or video file.
2. **Summarize AV**: Returns a compact summary — container format, duration, size, and the primary video/audio streams.
3. **Inspect Image (exiftool)**: Returns EXIF/XMP/GPS metadata for an image.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- [FFmpeg](https://ffmpeg.org/) (`ffprobe` binary) on your PATH — required for the `ffmpeg` driver
- [ExifTool](https://exiftool.org/) on your PATH — required for the `exiftool` driver

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/media-inspector
```

Verify the tools are installed:
```bash
ffprobe -version
exiftool -ver
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   The service will start:
   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run workflows:**

   **Using CLI:**
   ```bash
   # Full metadata payload for an audio/video file
   model-compose run inspect --input '{
     "media": "/path/to/input.mp4"
   }'

   # Compact summary — format/duration/size + primary streams
   model-compose run summary --input '{
     "media": "/path/to/input.mp4"
   }'

   # EXIF/XMP/GPS for an image
   model-compose run inspect-image --input '{
     "image": "/path/to/photo.jpg"
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=summary" \
     -F "media=@/path/to/input.mp4"
   ```

## Component Details

### Media Inspector Component

- **Type**: `media-inspector`
- **Drivers**: `ffmpeg` (uses `ffprobe`), `exiftool`
- **Purpose**: Read container/stream/EXIF metadata from a media file without decoding.

#### Key Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `media` | media source | Yes | - | File path, URL, or interpolated variable |
| `return_raw` | boolean | No | `true` | Include the driver's raw output under `raw` |

## Workflow Details

### 1. Inspect Media (ffprobe)

**Description**: Full ffprobe payload — container format, per-stream codec/bitrate/duration/resolution/fps, and raw JSON.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `media` | file | Yes | Source audio/video file |

#### Output (selected fields)

| Field | Type | Description |
|-------|------|-------------|
| `format` | string | Container format (e.g. `mp4`, `mkv`, `wav`) |
| `duration` | float | Duration in seconds |
| `bitrate` | integer | Overall bitrate in bits/s |
| `video_streams` | list | One entry per video stream (codec, width, height, fps, ...) |
| `audio_streams` | list | One entry per audio stream (codec, sample_rate, channels, ...) |
| `raw` | object | Raw ffprobe JSON |

### 2. Summarize AV

**Description**: Trims the ffprobe payload down to a short summary — useful for logging, quick UI display, or routing decisions.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `media` | file | Yes | Source audio/video file |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `format` | string | Container format |
| `duration` | float | Duration in seconds |
| `size` | integer | File size in bytes |
| `video` | object \| null | Primary video stream, or `null` if none |
| `audio` | object \| null | Primary audio stream, or `null` if none |

### 3. Inspect Image (exiftool)

**Description**: EXIF/XMP/GPS metadata for an image file. Also returns camera settings (ISO, aperture, focal length) and GPS coordinates when present.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image` | file | Yes | Source image file (JPEG, PNG, HEIC, etc.) |

#### Output (selected fields)

| Field | Type | Description |
|-------|------|-------------|
| `width`, `height` | integer | Image dimensions |
| `camera` | object | Make/model/lens + exposure settings |
| `gps` | object \| null | Latitude/longitude/altitude, or `null` if not embedded |
| `metadata.exif` | object | EXIF tag block |
| `metadata.xmp` | object | XMP tag block |

## Tips

- **Pick the driver by intent**: use `ffmpeg` for stream-level detail (codecs, sample rates, fps) and `exiftool` for embedded metadata (EXIF, XMP, GPS). Both drivers can be used in the same compose file against the same or different components.
- **Set `return_raw: false`** for production workflows — the raw payload is verbose and only useful when discovering fields.
- **Streaming inputs are spooled**: non-file sources (uploads, HTTP streams) are written to a temp file before probing because both tools need seekable input.

## Troubleshooting

### Common Issues

1. **`ffprobe` / `exiftool` not found**: Install the missing tool and ensure it is on your `PATH`.
2. **`raw` payload too large**: Set `return_raw: false` on the action, or map only specific fields via `output:` in the workflow.
3. **`fps: null` on some inputs**: ffprobe reports `0/0` for unknown frame rates; the driver normalizes this to `null` so callers can distinguish "no fps info" from "zero fps".
