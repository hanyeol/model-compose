# Audio Capture Component

The audio capture component records from a local audio input — either the microphone or the system output loopback — and emits the encoded audio as a continuous byte stream. Unlike media components that read from a file, this one is a **live source**: with no `duration` set, it streams indefinitely until the consumer stops reading.

Typical uses include piping the microphone into a speech-to-text model, capturing a meeting's system audio for offline transcription, and recording narration for later mixing without going through a separate DAW.

## Basic Configuration

```yaml
component:
  id: mic
  type: audio-capture
  driver: ffmpeg
  action:
    source: microphone
    duration: 30s
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `audio-capture` |
| `driver` | string | `ffmpeg` | Capture backend; currently only `ffmpeg` |
| `actions` | array | `[]` | List of capture actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | `capture` | Only `capture` is defined today |
| `source` | string | `microphone` | Audio input: `microphone` or `system` loopback |
| `device` | integer \| string | `null` | Device index (avfoundation) or name (dshow/pulse); when unset the platform default is used |
| `sample_rate` | integer | `null` | Output sample rate in Hz; when unset the device's native rate is used |
| `channels` | integer | `null` | Output channel count; when unset the device's native channel count is used |
| `encoding` | object | `null` | Audio encoding settings (see below) |
| `duration` | string \| number | `null` | Total capture duration (e.g. `30s`, `2m`). `null` = capture until stopped |
| `output` | string | `null` | Output template applied to the captured result |

### Encoding Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string | `aac` | Container format for the emitted stream |
| `audio.codec` | string | `aac` (or `libopus` for ogg/opus) | Audio codec passed to ffmpeg `-c:a` |
| `audio.bitrate` | string | `null` | Audio bitrate (e.g. `160k`) |

Video-oriented containers passed to `format` are auto-mapped to their audio-only counterparts (`mp4` / `mov` → `m4a`, `webm` → `ogg`) so downstream decoders can consume the audio stream in isolation.

## Supported Drivers

### FFmpeg

The FFmpeg driver picks the right backend per platform and source:

| Source | macOS | Windows | Linux |
|--------|-------|---------|-------|
| `microphone` | `avfoundation` | `dshow` | `pulse` |
| `system` | Core Audio process-tap via `audiotee` sidecar | WASAPI loopback (`dshow`) | PulseAudio monitor (`pulse`) |

**Requires:** `ffmpeg` binary on the system path.

**macOS system audio also requires:** the `audiotee` CLI on the system path. macOS blocks direct system-audio loopback in ffmpeg, so the driver pipes PCM from `audiotee` (Core Audio process-tap) into an ffmpeg encoder. See [makeusabrew/audiotee](https://github.com/makeusabrew/audiotee).

**Permissions:**
- macOS asks for Microphone permission the first time an avfoundation input runs, and again for the `audiotee` process-tap.
- Windows `dshow` capture works without extra permission prompts on most systems.
- Linux captures rely on the PulseAudio / PipeWire session belonging to the current user; no extra prompts.

## Output Format

Each capture returns a dict with the encoded audio stream and a monotonic timestamp anchor:

```python
{
  "audio": <AudioStreamResource>,
  "capture_pts": 1427085.607881958
}
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `audio` | AudioStreamResource | Encoded audio chunks |
| `capture_pts` | float | `time.monotonic()` value recorded when the capture started, useful for aligning the audio track with an absolute broadcast timeline |

Reading the resource drives the capture forward; closing it or breaking out of the loop stops the underlying ffmpeg (and, on macOS system audio, `audiotee`) processes.

## Multiple Actions Configuration

```yaml
component:
  id: mic
  type: audio-capture
  driver: ffmpeg
  actions:
    - id: voice-memo
      source: microphone
      sample_rate: 16000
      channels: 1
      duration: 30s

    - id: meeting
      source: system
      encoding:
        format: m4a
        audio:
          codec: aac
          bitrate: 128k
```

## Integration with Workflows

### Microphone → Speech-to-Text

```yaml
workflows:
  - id: transcribe-mic
    jobs:
      - id: capture
        component: mic
        action: voice-memo

      - id: transcribe
        component: stt
        input:
          audio: ${jobs.capture.output.audio}
        depends_on: [capture]

components:
  - id: mic
    type: audio-capture
    action:
      source: microphone
      sample_rate: 16000
      channels: 1
      duration: 30s

  - id: stt
    type: model
    task: automatic-speech-recognition
    model: openai/whisper-large-v3
```

### System Audio → File

```yaml
components:
  - id: system-audio
    type: audio-capture
    action:
      source: system
      encoding:
        format: m4a
        audio:
          codec: aac
          bitrate: 160k
```

## Platform Notes

### macOS

- The Core Audio process-tap API used by `audiotee` needs macOS 14.2 or newer.
- The first system-audio chunk can take ~4–5 seconds to arrive; this is a startup characteristic of the process-tap API, not the driver.
- The microphone input defaults to the system's default input device; select a specific device with `device: 0`, `device: 1`, etc. Discover indices with `ffmpeg -f avfoundation -list_devices true -i ""`.

### Windows

- System-audio loopback relies on the `virtual-audio-capturer` dshow device. Install [screen-capture-recorder](https://github.com/rdp/screen-capture-recorder-to-video-windows-free) if it is not already present.
- Select a specific microphone with a dshow name, e.g. `device: "Microphone (USB Audio)"`. Enumerate devices with `ffmpeg -f dshow -list_devices true -i dummy`.

### Linux

- System audio requires PulseAudio or PipeWire's PulseAudio compatibility layer. The default monitor source (`default.monitor`) is used automatically; override with `device: alsa_output.pci-0000_00_1f.3.analog-stereo.monitor` (or similar) to target a specific sink.
- List available sources with `pactl list sources short`.

## Best Practices

1. **Match `sample_rate` to the downstream consumer.** Speech-to-text models expect 16 kHz mono; sending 48 kHz stereo wastes bandwidth and forces the model to resample.
2. **Prefer `m4a` for file writes, keep the default `aac` for pipeline consumers.** The default `aac` (ADTS) container is packetized and works well over pipes; `m4a` is easier for downstream tools that expect a seekable file.
3. **Anchor timelines with `capture_pts`.** When you run audio capture in parallel with another live source (e.g. `video-capture` or `screen-capture`), the shared `capture_pts` is what lets you re-align them without decoding timestamps back out of the encoded stream.
4. **Set `duration` in short-lived tests, leave it `null` in production sources.** An unbounded stream stops the moment the consumer closes the resource, so long-running captures don't need an explicit timeout.
