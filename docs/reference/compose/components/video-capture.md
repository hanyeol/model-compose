# Video Capture Component

The video capture component records from a local camera device — a physical webcam, a USB capture card, or a virtual camera such as OBS Virtual Camera — and emits the encoded video as a continuous byte stream. Unlike media components that read from a file, this one is a **live source**: with no `duration` set, it streams indefinitely until the consumer stops reading.

Typical uses include feeding a webcam into a face-detection or gesture-tracking model, capturing a broadcast camera through a capture card for downstream re-encoding, and previewing an OBS scene without going through OBS's built-in server.

## Basic Configuration

```yaml
component:
  id: cam
  type: video-capture
  driver: ffmpeg
  action:
    source: camera
    framerate: 30
    resolution:
      width: 1280
      height: 720
    duration: 30s
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-capture` |
| `driver` | string | `ffmpeg` | Capture backend; currently only `ffmpeg` |
| `actions` | array | `[]` | List of capture actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | `capture` | Only `capture` is defined today |
| `source` | string | `camera` | Video input kind; currently only `camera` |
| `device` | integer \| string | platform default | Device index (avfoundation) or name (dshow) or path (v4l2). Required on Windows |
| `resolution` | object | `null` | Requested frame resolution; when unset the device's default is used |
| `framerate` | number | `30` | Video framerate (frames per second) |
| `pixel_format` | string | `null` | Requested input pixel format (e.g. `uyvy422`, `yuyv422`, `mjpeg`) |
| `encoding` | object | `null` | Video encoding settings (see below) |
| `duration` | string \| number | `null` | Total capture duration (e.g. `30s`, `2m`). `null` = capture until stopped |
| `output` | string | `null` | Output template applied to the captured result |

### Resolution Object

| Field | Type | Description |
|-------|------|-------------|
| `width` | integer | Frame width in pixels |
| `height` | integer | Frame height in pixels |

### Encoding Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string | `ts` | Container format for the emitted stream |
| `video.codec` | string | `libx264` | Video codec passed to ffmpeg `-c:v` |
| `video.bitrate` | string | `null` | Video bitrate (e.g. `6M`, `2000k`) |

The default video container is MPEG-TS (`ts`) because each packet is self-contained, so encoded chunks are available with sub-second latency. `mp4` also works (fragmented-mp4 flags are added automatically) but has higher first-byte latency over a pipe.

## Supported Drivers

### FFmpeg

The FFmpeg driver picks the right capture backend per platform:

| Platform | Backend | Device format |
|----------|---------|---------------|
| macOS | `avfoundation` | Numeric index (`"0"`) or device name |
| Windows | `dshow` | Device name (`"USB Video Device"`); index not supported |
| Linux | `v4l2` | Node path (`/dev/video0`, `/dev/video1`, …) |

Virtual cameras (OBS Virtual Camera, Snap Camera, etc.) are exposed by the OS as ordinary video devices, so they work with the same `source: camera` path — just point `device` at the virtual device's name or index.

**Requires:** `ffmpeg` binary on the system path.

**Permissions:**
- macOS asks for Camera permission the first time an avfoundation video input runs. Denying the prompt yields empty streams, not an exception.
- Windows and Linux camera access relies on the current user's session and does not prompt.

## Output Format

Each capture returns a dict with the encoded video stream and a monotonic timestamp anchor:

```python
{
  "video": <VideoStreamResource>,
  "capture_pts": 1427085.607881958
}
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `video` | VideoStreamResource | Encoded video chunks |
| `capture_pts` | float | `time.monotonic()` value recorded when the capture started, useful for aligning the video track with an absolute broadcast timeline |

Reading the resource drives the capture forward; closing it or breaking out of the loop stops the underlying ffmpeg process.

## Multiple Actions Configuration

```yaml
component:
  id: cam
  type: video-capture
  driver: ffmpeg
  actions:
    - id: preview
      source: camera
      framerate: 15
      resolution:
        width: 640
        height: 360
      duration: 10s

    - id: broadcast
      source: camera
      framerate: 30
      resolution:
        width: 1920
        height: 1080
      encoding:
        format: ts
        video:
          codec: libx264
          bitrate: 6M

    - id: capture-card
      source: camera
      device: "Elgato Cam Link 4K"
      framerate: 60
      pixel_format: uyvy422
```

## Integration with Workflows

### Webcam → Face Detection

```yaml
workflows:
  - id: face-track
    jobs:
      - id: capture
        component: cam
        action: preview

      - id: detect
        component: face-detector
        input:
          video: ${jobs.capture.output.video}
        depends_on: [capture]

components:
  - id: cam
    type: video-capture
    action:
      source: camera
      framerate: 15
      resolution:
        width: 640
        height: 360

  - id: face-detector
    type: model
    task: face-detection
    model: insightface/buffalo_l
```

### Capture Card → RTMP Broadcast

```yaml
components:
  - id: broadcast-cam
    type: video-capture
    action:
      source: camera
      device: "Elgato Cam Link 4K"
      framerate: 60
      resolution:
        width: 1920
        height: 1080
      encoding:
        format: ts
        video:
          codec: libx264
          bitrate: 8M
```

## Platform Notes

### macOS

- The `device` field is the avfoundation video device index. Run `ffmpeg -f avfoundation -list_devices true -i ""` to see indices and names — cameras come first, then displays.
- Built-in cameras usually appear at `device: 0`.
- Some devices only expose certain resolutions or pixel formats; if capture fails, omit `resolution` and `pixel_format` and let ffmpeg negotiate.

### Windows

- `device` is a dshow device name, not an index. Enumerate installed cameras with `ffmpeg -f dshow -list_devices true -i dummy` and copy the name exactly (case-sensitive).
- OBS Virtual Camera appears as `"OBS Virtual Camera"` once you start it in OBS.

### Linux

- `device` is a v4l2 node path (default `/dev/video0`). Multi-camera systems expose additional nodes as `/dev/video1`, `/dev/video2`, etc.
- Query supported resolutions and pixel formats with `v4l2-ctl --device=/dev/video0 --list-formats-ext`.

## Best Practices

1. **Match `resolution` and `framerate` to what the downstream consumer needs.** A face detector rarely benefits from 1080p60 — 480p15 cuts CPU load dramatically without hurting accuracy.
2. **Prefer `ts` for pipeline consumers, `mp4` for file writes.** The default `ts` container yields chunks with sub-second latency; `mp4` is easier for downstream tools that expect a seekable file.
3. **Pin the `device` explicitly in production.** Platform defaults change when USB devices are plugged in; naming the exact device (or v4l2 path) removes that fragility.
4. **Anchor timelines with `capture_pts`.** When you run video capture in parallel with `audio-capture` or `screen-capture`, the shared `capture_pts` is what lets you re-align tracks without decoding timestamps back out of the encoded stream.
5. **Set `duration` in short-lived tests, leave it `null` in production sources.** An unbounded stream stops the moment the consumer closes the resource, so long-running captures don't need an explicit timeout.
