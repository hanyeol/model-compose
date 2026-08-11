# Media Inspector Component

The media inspector component queries metadata from a media file (audio, video, or image) without decoding or transcoding the content. It wraps command-line inspection tools (`ffprobe`, `exiftool`) and returns both a normalized field set and, optionally, the tool's raw output.

## Basic Configuration

```yaml
component:
  type: media-inspector
  driver: ffmpeg
  action:
    media: ${input.media as file}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `media-inspector` |
| `driver` | string | `ffmpeg` | Inspection backend driver. One of `ffmpeg`, `exiftool`. |
| `actions` | array | `[]` | List of inspection actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `media` | string \| string[] | **required** | Media source(s) — file path, URL, or interpolated variable (e.g. `${input.media as file}`). A list yields one result per source. |
| `return_raw` | boolean \| string | `true` | Whether to include the driver's raw output under `raw` alongside the normalized fields. |

## Supported Drivers

### FFmpeg

Uses `ffprobe` to read container and stream information. Best suited for audio and video: reports codecs, bitrates, sample rates, resolution, fps, duration, and per-stream tags. Basic image metadata (width, height, pixel format) is also available, but embedded EXIF is not exposed — use the `exiftool` driver for that.

```yaml
component:
  type: media-inspector
  driver: ffmpeg
  action:
    media: ${input.media as file}
```

**Requires:** `ffprobe` binary on `PATH` (bundled with FFmpeg).

### ExifTool

Uses `exiftool` to read embedded metadata. Best suited for images: exposes EXIF, XMP, IPTC, GPS, and camera settings. Also handles many container formats (MP4, MOV, WebP, PDF, ...), though for audio/video stream details the `ffmpeg` driver is more precise.

```yaml
component:
  type: media-inspector
  driver: exiftool
  action:
    media: ${input.media as file}
```

**Requires:** `exiftool` binary on `PATH`.

## Output Format

Behavior depends on `driver`. When `media` is a list, results are returned as a list of the shapes below (one per source).

### FFmpeg driver

```jsonc
{
  "path": "/path/to/input.mp4",
  "format": "mp4",
  "format_long_name": "QuickTime / MOV",
  "duration": 12.5,
  "size": 1048576,
  "bitrate": 671088,
  "start_time": 0.0,
  "tags": { "encoder": "Lavf62.3.100" },
  "video_streams": [
    {
      "index": 0,
      "codec": "h264",
      "codec_long_name": "H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10",
      "profile": "High",
      "width": 1920,
      "height": 1080,
      "pixel_format": "yuv420p",
      "fps": 29.97,
      "bitrate": 500000,
      "duration": 12.5,
      "frames": 375,
      "aspect_ratio": "16:9",
      "rotation": null,
      "tags": { "language": "und", "handler_name": "VideoHandler" }
    }
  ],
  "audio_streams": [
    {
      "index": 1,
      "codec": "aac",
      "codec_long_name": "AAC (Advanced Audio Coding)",
      "profile": "LC",
      "sample_rate": 44100,
      "channels": 2,
      "channel_layout": "stereo",
      "sample_format": "fltp",
      "bitrate": 128000,
      "duration": 12.5,
      "tags": {}
    }
  ],
  "subtitle_streams": [],
  "raw": { /* full ffprobe JSON when return_raw is true */ }
}
```

### ExifTool driver

```jsonc
{
  "path": "/path/to/photo.jpg",
  "format": "jpeg",
  "mime_type": "image/jpeg",
  "size": 3145728,
  "width": 4032,
  "height": 3024,
  "duration": null,
  "created_at": "2024:05:12 14:30:22",
  "modified_at": "2024:05:12 14:30:22",
  "camera": {
    "make": "Apple",
    "model": "iPhone 15 Pro",
    "lens": "iPhone 15 Pro back triple camera 6.86mm f/1.78",
    "software": "17.5",
    "iso": 100,
    "aperture": 1.78,
    "shutter_speed": "1/120",
    "focal_length": 6.86,
    "focal_length_35mm": 24
  },
  "gps": {
    "latitude": 37.5665,
    "longitude": 126.978,
    "altitude": 38.4,
    "timestamp": "2024:05:12 05:30:22Z"
  },
  "metadata": {
    "exif": { "Model": "iPhone 15 Pro", "ISO": 100, /* ... */ },
    "xmp":  { /* XMP-namespaced tags */ },
    "gps":  { "GPSLatitude": 37.5665, /* ... */ },
    "other": { /* everything else */ }
  },
  "raw": { /* raw exiftool -G1 -j output when return_raw is true */ }
}
```

When a source has no GPS data, `gps` is `null`. `duration` is populated for time-based media (video/audio) and `null` for still images.

## Multiple Actions Configuration

Define multiple inspection actions on the same component:

```yaml
component:
  type: media-inspector
  actions:
    - id: inspect
      media: ${input.media as file}

    - id: inspect-lean
      media: ${input.media as file}
      return_raw: false
```

## Integration with Workflows

### Inspect an Uploaded Media File

```yaml
workflows:
  - id: inspect-media
    job:
      component: inspector
      output:
        info: ${output}

components:
  - id: inspector
    type: media-inspector
    action:
      media: ${input.media as file}
      return_raw: false
```

### Route by Container Format

Use the inspector's output to branch downstream jobs on codec or container:

```yaml
workflows:
  - id: transcode-if-needed
    jobs:
      - id: probe
        component: inspector
        input:
          media: ${input.media as file}
        output:
          codec: ${output.video_streams[0].codec}

      - id: transcode
        component: converter
        depends_on: [probe]
        when: ${jobs.probe.output.codec} != "h264"
        input:
          media: ${input.media as file}

components:
  - id: inspector
    type: media-inspector
    action:
      media: ${input.media as file}
      return_raw: false
```

### Read EXIF from a Photo

```yaml
workflows:
  - id: read-exif
    job:
      component: exif-reader
      output:
        camera: ${output.camera}
        gps: ${output.gps}
        taken_at: ${output.created_at}

components:
  - id: exif-reader
    type: media-inspector
    driver: exiftool
    action:
      media: ${input.photo as file}
      return_raw: false
```

## Best Practices

1. **Pick the driver by intent.** Use `ffmpeg` when you need stream-level detail (codecs, sample rates, fps) and `exiftool` when you need embedded metadata (EXIF, XMP, GPS). If both matter, run two inspector components against the same input.
2. **Set `return_raw: false` for production flows.** The `raw` payload can be large and is only useful during discovery/debugging.
3. **Handle missing fields.** Streams don't always populate every field — check for `null` before using derived numbers (e.g. `bitrate`, `fps`, `rotation`).
4. **Streaming inputs are spooled.** Non-file sources (uploads, HTTP streams) are written to a temporary file before probing because both tools need seekable input. Prefer passing a file path when the caller already has one.
