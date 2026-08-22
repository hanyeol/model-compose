# Video Capture Example

This example demonstrates the `video-capture` component: capturing the local camera and returning the encoded video **directly in the HTTP response** as a fragmented MP4 stream — no file store, no intermediate buffering.

Any device the OS exposes as a camera works: physical webcams, USB capture cards, and virtual cameras (OBS Virtual Camera, Snap Camera, etc.) all appear to ffmpeg as ordinary video devices.

## Overview

A single workflow, `capture-webcam`, opens the default camera, encodes a fragmented MP4 stream, and returns it as the HTTP response. The response is playable as soon as the first fragment lands, so downstream tools that speak MP4 over HTTP can decode without waiting for the capture to finish.

On macOS the encoder defaults to `h264_videotoolbox` (hardware) so 1080p30 stays real-time; on Windows and Linux it defaults to `libx264`.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- `ffmpeg` on the system path (with hardware-encoder support on macOS, which the Homebrew build already has)

### Platform Permissions

The first time you run camera capture:

- **macOS** prompts for Camera permission. Denying yields an empty stream, not an exception.
- **Windows** and **Linux** rely on the current user session's device permissions and do not prompt.

### Finding Your Camera

Platform defaults handle the common case, but if you have multiple cameras or want to target a virtual camera, list the devices first:

```bash
# macOS
ffmpeg -f avfoundation -list_devices true -i ""

# Windows
ffmpeg -f dshow -list_devices true -i dummy

# Linux
v4l2-ctl --list-devices
```

Pass the device via `device` on the action (see [Customization](#customization) below).

### Setup

```bash
cd examples/media-processing/video-capture
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run the workflow:**

   **Using CLI (save the streamed MP4 to disk):**
   ```bash
   # 10-second 720p capture at 30fps → webcam.mp4
   model-compose run capture-webcam \
     --input '{"duration": "10s", "framerate": 30, "width": 1280, "height": 720}' \
     --output webcam.mp4
   ```

   **Using API (curl):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow": "capture-webcam", "input": {"duration": "5s"}}' \
     --output webcam.mp4
   ```

   **Play the result:**
   ```bash
   open webcam.mp4         # macOS
   xdg-open webcam.mp4     # Linux
   start webcam.mp4        # Windows
   ```

   Or open the Web UI at http://localhost:8081 and the encoded video plays inline in the browser.

## Component Details

### Video Capture Component

- **Type**: `video-capture`
- **Purpose**: Live capture of a local camera / capture card / virtual camera
- **Driver**: `ffmpeg` — auto-selects `avfoundation` (macOS) / `dshow` (Windows) / `v4l2` (Linux)
- **Default encoder**: `h264_videotoolbox` on macOS, `libx264` elsewhere

## Workflow Details

### Capture Webcam

**ID**: `capture-webcam`
**Description**: Camera capture that streams fragmented MP4 straight into the HTTP response.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `duration` | string | No | `10s` | Capture length (e.g. `10s`, `30s`, `2m`) |
| `framerate` | number | No | `30` | Video framerate |
| `width` | integer | No | `1280` | Frame width in pixels |
| `height` | integer | No | `720` | Frame height in pixels |

#### Output

The response body is the fragmented MP4 stream itself. When called through `model-compose run --output`, save the bytes to a `.mp4` file and play them with any media player or browser.

## Customization

### Selecting a Specific Camera

Add `device` to the action to target a specific camera by index or name:

```yaml
- id: webcam
  source: camera
  device: 1               # macOS avfoundation index (see `-list_devices` above)
  # device: "OBS Virtual Camera"      # macOS/Windows: match the name exactly
  # device: /dev/video2               # Linux
  framerate: ${input.framerate}
  ...
```

On Windows `device` is required — dshow does not support numeric indices, so you must pass a device name.

### Higher Resolution or Framerate

Increase `width`/`height`/`framerate` on the request:

```bash
model-compose run capture-webcam \
  --input '{"width": 1920, "height": 1080, "framerate": 60, "duration": "5s"}' \
  --output webcam-1080p60.mp4
```

The default encoder on macOS (`h264_videotoolbox`) handles 1080p60 comfortably. On Windows/Linux with `libx264` you may want to bump `encoding.video.bitrate` or override the codec (`h264_nvenc` for NVIDIA, `h264_qsv` for Intel Quick Sync, `h264_vaapi` for Linux VA-API) to keep up with 1080p60 in real time.

### Overriding the Codec or Bitrate

Set `encoding` explicitly on the action:

```yaml
- id: webcam
  source: camera
  ...
  encoding:
    format: mp4
    video:
      codec: h264_nvenc   # or libx264, h264_qsv, h264_vaapi, ...
      bitrate: 8M
```

### Emitting a Different Container

Change `encoding.format` to `ts` for MPEG-TS (lower first-byte latency, decodable even if the capture is interrupted) or `webm` for VP9. Fragmented MP4 flags are added automatically when the format is `mp4` / `mov` / `m4v`, so those pipe cleanly to HTTP without extra tuning.

### Unbounded Capture

Drop `duration` from the input (or set it to null) to stream indefinitely until the client closes the connection. Useful when the consumer decides when to stop; less useful for the "save to a file" demo above because the response only completes when capture stops.
