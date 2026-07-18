# Screen Capture Component

The screen capture component records the local display and (optionally) system or microphone audio, emitting each track as a continuous encoded byte stream. Unlike media components that read from a file, this one is a **live source**: with no `duration` set, it streams indefinitely until the consumer stops reading.

Typical uses include feeding a live desktop into an analysis pipeline (STT, scene detection, vision models) without going through a browser player, and capturing a broadcast preview window as an authoritative source that is not affected by viewer-side ad injection.

## Basic Configuration

```yaml
component:
  id: screen
  type: screen-capture
  driver: ffmpeg
  action:
    framerate: 15
    include_video: true
    include_audio: true
    audio_source: system
    duration: 30s
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `screen-capture` |
| `driver` | string | `ffmpeg` | Capture backend; currently only `ffmpeg` |
| `actions` | array | `[]` | List of capture actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | `capture` | Only `capture` is defined today |
| `video_source` | string | `display` | Capture target kind: `display`, `region` |
| `audio_source` | string | `system` | Which audio to capture: `system` loopback, `microphone`, or `none` |
| `display` | integer | `0` | Display index when `video_source` is `display` or `region` |
| `region` | object | `null` | Region rectangle on the target display; required when `video_source: region` |
| `include_video` | boolean | `true` | Include a video track in the capture |
| `include_audio` | boolean | `true` | Include an audio track in the capture |
| `framerate` | number | `30` | Video framerate (frames per second) |
| `encoding` | object | `null` | Video/audio encoding settings (see below) |
| `duration` | string \| number | `null` | Total capture duration (e.g. `30s`, `2m`). `null` = capture until stopped |
| `output` | string | `null` | Output template applied to the captured result |

### Region Object

Required when `video_source: region`. All coordinates are pixels relative to the top-left of the target display.

| Field | Type | Description |
|-------|------|-------------|
| `x` | integer | Left edge |
| `y` | integer | Top edge |
| `width` | integer | Region width |
| `height` | integer | Region height |

### Encoding Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string | `ts` (video), `aac` (audio) | Container format for the emitted stream |
| `video.codec` | string | `libx264` | Video codec passed to ffmpeg `-c:v` |
| `video.bitrate` | string | `null` | Video bitrate (e.g. `6M`, `2000k`) |
| `audio.codec` | string | `aac` | Audio codec passed to ffmpeg `-c:a` |
| `audio.bitrate` | string | `null` | Audio bitrate (e.g. `160k`) |

The default video container is MPEG-TS (`ts`) because each packet is self-contained, so encoded chunks are available with sub-second latency. `mp4` also works (fragmented-mp4 flags are added automatically) but has higher first-byte latency over a pipe.

## Supported Drivers

### FFmpeg

The FFmpeg driver auto-detects the platform and picks the right capture backend for each track:

| Track | macOS | Windows | Linux |
|-------|-------|---------|-------|
| Video | `avfoundation` | `gdigrab` | `x11grab` |
| Audio (system) | Core Audio process-tap via `audiotee` sidecar | WASAPI loopback (`dshow`) | PulseAudio monitor (`pulse`) |
| Audio (microphone) | `avfoundation` | `dshow` | `pulse` |

**Requires:** `ffmpeg` binary on the system path.

**macOS system audio also requires:** the `audiotee` CLI on the system path. macOS blocks direct system-audio loopback in ffmpeg, so the driver pipes PCM from `audiotee` (Core Audio process-tap) into an ffmpeg encoder. See [makeusabrew/audiotee](https://github.com/makeusabrew/audiotee).

**Permissions:**
- macOS asks for Screen Recording permission the first time either the video capture or `audiotee` runs. Denying the prompt yields empty streams, not an exception.
- Linux Wayland captures go through PipeWire portals and prompt the user each session.

## Output Format

Each capture returns a dict containing two independent stream resources plus a shared timestamp anchor:

```python
{
  "video": <VideoStreamResource | None>,
  "audio": <AudioStreamResource | None>,
  "capture_pts": 1427085.607881958
}
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `video` | VideoStreamResource | Encoded video chunks; `None` if `include_video: false` |
| `audio` | AudioStreamResource | Encoded audio chunks; `None` if `include_audio: false` or `audio_source: none` |
| `capture_pts` | float | `time.monotonic()` value recorded when the capture started, shared by both tracks so downstream code can align chunks to an absolute broadcast timeline |

Each `*StreamResource` iterates encoded byte chunks as they are produced. Reading the resource drives the capture forward; closing it or breaking out of the loop stops the underlying ffmpeg (and, on macOS system audio, `audiotee`) processes.

## Multiple Actions Configuration

```yaml
component:
  id: screen
  type: screen-capture
  driver: ffmpeg
  actions:
    - id: preview
      framerate: 5
      include_audio: false
      duration: 10s

    - id: broadcast
      framerate: 30
      audio_source: system
      encoding:
        format: ts
        video:
          codec: libx264
          bitrate: 6M
        audio:
          codec: aac
          bitrate: 160k

    - id: window-preview
      video_source: region
      region:
        x: ${input.x}
        y: ${input.y}
        width: 1280
        height: 720
      include_audio: false
```

## Integration with Workflows

### Live Desktop → STT Pipeline

```yaml
workflows:
  - id: transcribe-desktop
    jobs:
      - id: capture
        component: screen
        action: broadcast
        output:
          audio: ${output.audio}
          pts: ${output.capture_pts}

      - id: transcribe
        component: stt
        input:
          audio: ${jobs.capture.output.audio}
        depends_on: [capture]

components:
  - id: screen
    type: screen-capture
    action:
      framerate: 10
      include_video: false
      audio_source: system

  - id: stt
    type: model
    task: automatic-speech-recognition
    model: openai/whisper-large-v3
```

### Region Capture for Broadcast Preview

```yaml
components:
  - id: obs-preview
    type: screen-capture
    action:
      video_source: region
      region:
        x: 100
        y: 200
        width: 1920
        height: 1080
      framerate: 30
      include_audio: false
```

## Platform Notes

### macOS

- The `display` field is really the avfoundation device index, which starts *after* the list of video cameras. Run `ffmpeg -f avfoundation -list_devices true -i ""` to find the correct index for your display (often `2`–`5` depending on how many cameras are attached).
- The Core Audio process-tap API used by `audiotee` needs macOS 14.2 or newer.
- The first system-audio chunk can take ~4–5 seconds to arrive; this is a startup characteristic of the process-tap API, not the driver.

### Windows

- `gdigrab` cannot capture windows that are minimized. The `region` path works against the whole desktop, so windows partially obscured by others are still captured cleanly.

### Linux

- X11 sessions work out of the box via `x11grab`. Wayland sessions require PipeWire portals with per-session user permission.
- System audio requires PulseAudio or PipeWire's PulseAudio compatibility layer. The default monitor source (`default.monitor`) is used automatically.

## Best Practices

1. **Match `framerate` to what the downstream consumer actually needs.** 5–10 fps is plenty for scene/face analysis and dramatically cuts CPU load compared with a 30 fps capture.
2. **Prefer `ts` for pipeline consumers, `mp4` for file writes.** The default `ts` container yields chunks with sub-second latency; `mp4` is easier for downstream tools that expect a seekable file.
3. **Use `region` to isolate a broadcast preview window.** Capturing the whole display and cropping downstream wastes encoder work; letting ffmpeg / gdigrab / x11grab crop at the source is much cheaper.
4. **Anchor timelines with `capture_pts`.** When you stream video and audio through independent processes, the shared `capture_pts` is what lets you re-align them without decoding timestamps back out of the encoded stream.
5. **Set `duration` in short-lived tests, leave it `null` in production sources.** An unbounded stream stops the moment the consumer closes the resource, so long-running captures don't need an explicit timeout.
