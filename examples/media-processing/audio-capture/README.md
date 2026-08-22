# Audio Capture Example

This example demonstrates the `audio-capture` component: capturing the local microphone or system audio (loopback) and returning the encoded audio **directly in the HTTP response** as an AAC stream — no file store, no intermediate buffering.

## Overview

Two workflows share a single `audio-capture` component:

1. **Capture Microphone** — records the default microphone. Only microphone permission is required, so this is the fastest way to smoke-test the pipeline.
2. **Capture System Audio** — records what the OS is playing back (loopback). On macOS this requires the [`audiotee`](https://github.com/makeusabrew/audiotee) helper; Windows uses DirectShow's `virtual-audio-capturer`; Linux uses the PulseAudio monitor of the default sink.

Both workflows encode to AAC (ADTS) and stream the response as soon as bytes are available, so downstream consumers can decode without waiting for the capture to finish.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- `ffmpeg` on the system path
- **macOS system audio only**: the [`audiotee`](https://github.com/makeusabrew/audiotee) CLI on the system path. Install with `brew install audiotee`. Microphone capture does not need it.

### Platform Permissions

The first time you run each workflow:

- **macOS microphone** prompts for Microphone permission.
- **macOS system audio** additionally prompts once for `audiotee`'s Core Audio process-tap.
- **Windows / Linux** rely on the current user session and do not prompt.

### Finding Your Audio Device

Platform defaults handle the common case, but if you have multiple inputs or want to target a specific one, list the devices first:

```bash
# macOS
ffmpeg -f avfoundation -list_devices true -i ""

# Windows
ffmpeg -f dshow -list_devices true -i dummy

# Linux
pactl list sources short
```

Pass the device via `device` on the action (see [Customization](#customization) below).

### Setup

```bash
cd examples/media-processing/audio-capture
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run a workflow:**

   **Using CLI (save the streamed AAC to disk):**
   ```bash
   # 10-second microphone clip → mic.aac
   model-compose run capture-microphone \
     --input '{"duration": "10s"}' \
     --output mic.aac

   # 10-second system-audio clip → system.aac
   model-compose run capture-system-audio \
     --input '{"duration": "10s"}' \
     --output system.aac
   ```

   **Using API (curl):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow": "capture-microphone", "input": {"duration": "5s"}}' \
     --output mic.aac
   ```

   **Play the result:**
   ```bash
   open mic.aac         # macOS
   xdg-open mic.aac     # Linux
   start mic.aac        # Windows
   ```

   Or open the Web UI at http://localhost:8081 and the encoded audio plays inline in the browser.

## Component Details

### Audio Capture Component

- **Type**: `audio-capture`
- **Purpose**: Live capture of a local microphone or system-audio loopback
- **Driver**: `ffmpeg` — auto-selects `avfoundation` (macOS) / `dshow` (Windows) / `pulse` (Linux). macOS system audio also spawns an `audiotee` sidecar.
- **Default codec/container**: `aac` in ADTS

## Workflow Details

### 1. Capture Microphone

**ID**: `capture-microphone`
**Description**: Record the default microphone and stream AAC back in the response.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `duration` | string | No | `10s` | Capture length (e.g. `10s`, `30s`, `2m`) |

#### Output

The response body is the AAC (ADTS) stream. When called through `model-compose run --output`, save the bytes to a `.aac` file and play them with any media player or browser.

---

### 2. Capture System Audio

**ID**: `capture-system-audio`
**Description**: Record what the OS is playing back (loopback) and stream AAC back in the response.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `duration` | string | No | `10s` | Capture length |

#### Output

Same shape as microphone: AAC bytes in the response body.

#### Platform Notes

- **macOS** requires `audiotee` on PATH. The first system-audio chunk can take ~4–5 seconds to arrive; this is a Core Audio process-tap startup characteristic, not the driver.
- **Windows** relies on the `virtual-audio-capturer` DirectShow device. Install [screen-capture-recorder](https://github.com/rdp/screen-capture-recorder-to-video-windows-free) if it is not already present.
- **Linux** reads the default sink's PulseAudio monitor (`default.monitor`). PipeWire's PulseAudio compatibility layer works the same way.

## Customization

### Selecting a Specific Device

Add `device` to the action to target a specific input by index or name:

```yaml
- id: microphone
  source: microphone
  device: 1                          # macOS avfoundation index (see `-list_devices`)
  # device: "Microphone (USB Audio)"  # Windows: match the name exactly
  # device: "alsa_input.usb-...-mono" # Linux (from `pactl list sources short`)
  duration: ${input.duration}
```

### Changing Sample Rate or Channels

Speech-to-text pipelines commonly expect 16 kHz mono; the default lets the device pick. Downsample and downmix at the source to save bandwidth:

```yaml
- id: microphone
  source: microphone
  sample_rate: 16000
  channels: 1
  duration: ${input.duration}
```

### Overriding the Codec or Bitrate

Set `encoding` explicitly on the action:

```yaml
- id: microphone
  source: microphone
  ...
  encoding:
    format: m4a          # or ogg, mp3, wav, ...
    audio:
      codec: aac         # for ogg use libopus
      bitrate: 192k
```

Video-oriented containers (`mp4`, `webm`) are auto-mapped to their audio-only counterparts (`m4a`, `ogg`), so downstream tools always see a decodable audio stream.

### Unbounded Capture

Drop `duration` from the input (or set it to null) to stream indefinitely until the client closes the connection. Useful when the consumer decides when to stop; less useful for the "save to a file" demo above because the response only completes when capture stops.
