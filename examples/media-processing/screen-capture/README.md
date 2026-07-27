# Screen Capture Example

This example demonstrates the `screen-capture` component: capturing the local display, a screen region, or the microphone as continuous encoded streams and writing them to disk via `file-store`.

## Overview

Three workflows show the three MVP capture modes:

1. **Capture Desktop Clip** — full-display capture at a chosen framerate, saved as an MPEG-TS clip
2. **Capture Screen Region** — rectangular crop of the display, using native region flags on Windows/Linux and a post-decode crop filter on macOS
3. **Capture Microphone Audio** — audio-only capture from the default microphone, saved as AAC (does not require Screen Recording permission)

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- `ffmpeg` on the system path
- macOS system audio capture (not exercised in this example) also requires the [`audiotee`](https://github.com/makeusabrew/audiotee) CLI; microphone-only capture here does not.

### Platform Permissions

The first time you run a video capture:

- **macOS** asks for Screen Recording permission. Denying the prompt yields an empty stream, not an exception.
- **Linux Wayland** captures require PipeWire portal approval per session.

Microphone capture uses a separate OS permission (Microphone) and is enough for smoke-testing on macOS without granting Screen Recording.

### macOS Display Index

On macOS the `display` field is the avfoundation device index, which is offset *after* the video-camera devices. Find yours by running:

```bash
ffmpeg -f avfoundation -list_devices true -i ""
```

Look for a line like `[4] Capture screen 0` and pass `--input '{"display": 4}'` accordingly. On Windows and Linux the default `0` is usually correct.

### Setup

```bash
cd examples/media-processing/screen-capture
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081
   - Captured clips are written under `./output/` in this directory.

2. **Run workflows:**

   **Using CLI:**
   ```bash
   # 5-second desktop clip at 15 fps (macOS: adjust display index)
   model-compose run capture-desktop-clip --input '{"duration": "5s", "framerate": 15, "display": 0}'

   # 720p region starting 100px from the top-left, 3-second clip
   model-compose run capture-region-clip --input '{
     "duration": "3s",
     "x": 100,
     "y": 100,
     "width": 1280,
     "height": 720
   }'

   # 3-second microphone clip
   model-compose run capture-microphone-clip --input '{"duration": "3s"}'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow": "capture-desktop-clip", "input": {"duration": "5s"}}'
   ```

3. **Inspect the output:**

   ```bash
   ls -lh output/
   ffprobe output/desktop-*.ts
   ```

## Component Details

### Screen Capture Component

- **Type**: `screen-capture`
- **Purpose**: Live capture of the local display and system/microphone audio
- **Driver**: `ffmpeg` (auto-detects the OS: avfoundation / gdigrab / x11grab for video, avfoundation / dshow / pulse for microphone)

### File Store Component

- **Type**: `file-store`
- **Purpose**: Persist the encoded stream chunks to a local file as they arrive

## Workflow Details

### 1. Capture Desktop Clip

**ID**: `capture-desktop-clip`
**Description**: Full-display capture for a bounded duration, saved as MPEG-TS.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `duration` | string | No | `5s` | Capture length (e.g. `5s`, `30s`, `2m`) |
| `framerate` | number | No | `15` | Video framerate |
| `display` | integer | No | `0` | Display / avfoundation device index (see macOS note above) |
| `filename` | string | No | timestamp | Optional filename stem (without extension) |

#### Output

```json
{ "file": "output/desktop-1730000000.ts" }
```

---

### 2. Capture Screen Region

**ID**: `capture-region-clip`
**Description**: Region-only capture. Windows `gdigrab` and Linux `x11grab` accept region flags natively; macOS applies a `-vf crop` filter after decode.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `duration` | string | No | `5s` | Capture length |
| `framerate` | number | No | `15` | Video framerate |
| `display` | integer | No | `0` | Display / avfoundation device index |
| `x` | integer | No | `0` | Region left edge (pixels) |
| `y` | integer | No | `0` | Region top edge (pixels) |
| `width` | integer | No | `640` | Region width (pixels) |
| `height` | integer | No | `480` | Region height (pixels) |
| `filename` | string | No | timestamp | Optional filename stem |

#### Output

```json
{ "file": "output/region-1730000000.ts" }
```

---

### 3. Capture Microphone Audio

**ID**: `capture-microphone-clip`
**Description**: Audio-only capture. Bypasses Screen Recording permission, so it's the easiest way to smoke-test the pipeline.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `duration` | string | No | `3s` | Capture length |
| `filename` | string | No | timestamp | Optional filename stem |

#### Output

```json
{ "file": "output/mic-1730000000.aac" }
```

## Customization

### Changing the Container Format

The default MPEG-TS container is chosen for low first-byte latency and interruption tolerance. To emit MP4 or WebM instead, set an `encoding.format` on the action:

```yaml
- id: desktop
  video_source: display
  encoding:
    format: mp4         # fragmented mp4 flags are added automatically for pipe output
    video:
      codec: libx264
      bitrate: 6M
```

Remember to update the `path` extension in the `save` job accordingly.

### Unbounded Capture

Drop `duration` to stream indefinitely until the consumer (in this example, `file-store`) is closed. Useful when another job downstream decides when to stop; less useful for the file-writing demo here because the workflow only completes when the capture stops.

### System Audio (macOS)

macOS blocks direct system-audio loopback in ffmpeg. To capture what your speakers are playing, install [`audiotee`](https://github.com/makeusabrew/audiotee), then set `audio_source: system` on the action. Startup latency is ~4–5 seconds because that's how long the Core Audio process-tap API needs to open a tap.
