# Video Encoder Component

The video encoder component turns video sources or image frame sequences into encoded video files. It wraps the `ffmpeg` binary to handle container muxing, codec selection, resolution and bitrate control, and optional audio track injection. It supports single inputs, batched lists, and streaming iterators, and can either write results to a temporary file or emit them as a byte stream.

## Basic Configuration

```yaml
component:
  type: video-encoder
  action:
    frames: ${input.frames}
    frame_rate: 30
    encoding:
      format: mp4
      video:
        codec: libx264
        bitrate: 2M
        resolution: 1280x720
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-encoder` |
| `driver` | string | `ffmpeg` | Video encoding backend. Currently only `ffmpeg` is supported. Requires the `ffmpeg` binary on `PATH`. |
| `actions` | array | `[]` | List of video encoding actions |

### Common Action Configuration

All video encoder actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | string / array | `null` | Existing video source(s) to re-encode. Mutually exclusive with `frames`. |
| `frames` | string / array | `null` | PIL image sequence(s) to encode into video. Mutually exclusive with `video`. |
| `frame_rate` | integer / string | `null` | Input frame rate for `frames`. Defaults to `30` when omitted. Only valid with `frames` input. |
| `audio` | string / array | `null` | Optional audio source(s) to mux into the output. |
| `encoding` | object | `null` | Container format and codec settings (see [Encoding Configuration](#encoding-configuration)). |
| `batch_size` | integer / string | `null` | Number of inputs to encode per batch. Defaults to `1`. |
| `streaming` | boolean / string | `false` | Emit the encoded output as a byte stream instead of writing to a temporary file. |
| `output` | any | `null` | Output variable mapping |

Exactly one of `video` or `frames` must be set. Providing both, or neither, is a configuration error. When `video` is supplied, `frame_rate` must not be set.

## Input Modes

### Video Re-encoding

Pass an existing video through ffmpeg to change its format, codecs, resolution, bitrate, or frame rate:

```yaml
component:
  type: video-encoder
  action:
    video: ${input.video}
    encoding:
      format: webm
      video:
        codec: libvpx-vp9
        bitrate: 3M
        resolution: 1920x1080
        fps: 30
      audio:
        codec: libopus
        bitrate: 128k
    output: ${output}
```

**Video Input Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | string / array | **required** | Video source(s). May be a single value or a list for batching. |
| `audio` | string / array | `null` | Optional audio source(s) to add or replace the video's audio track. |

### Frame Sequence Encoding

Assemble an ordered list of PIL images into a video. Frames are piped to ffmpeg as PNG-encoded `image2pipe` input:

```yaml
component:
  type: video-encoder
  action:
    frames: ${input.frames}
    frame_rate: 24
    encoding:
      format: mp4
      video:
        codec: libx264
        bitrate: 4M
    output: ${output}
```

**Frames Input Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | string / array | **required** | Image sequence(s). Each sequence is a list of PIL images. |
| `frame_rate` | integer / string | `30` | Frame rate to apply to the input frames. |
| `audio` | string / array | `null` | Optional audio source(s) to mux into the output. |

## Encoding Configuration

The `encoding` field controls container format and codec selection. Any field left unset falls back to a default derived from the container format.

```yaml
encoding:
  format: mp4
  video:
    codec: libx264
    bitrate: 2M
    resolution: 1280x720
    fps: 30
  audio:
    codec: aac
    bitrate: 128k
```

**Encoding Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string | `mp4` | Output container format (e.g. `mp4`, `webm`, `mkv`, `mov`, `avi`, `ogv`). |
| `video.codec` | string | (see table below) | Video codec (e.g. `libx264`, `libx265`, `libvpx-vp9`). |
| `video.bitrate` | string | `null` | Video bitrate (e.g. `2M`, `5000k`). |
| `video.resolution` | string | `null` | Output resolution (e.g. `1920x1080`, `1280x720`). |
| `video.fps` | string / integer / number | `null` | Output frame rate. |
| `audio.codec` | string | (see table below) | Audio codec (e.g. `aac`, `libopus`, `libmp3lame`). |
| `audio.bitrate` | string | `null` | Audio bitrate (e.g. `128k`, `192k`). |

**Default Codec Pairs by Format:**

| Format | Default Video Codec | Default Audio Codec |
|--------|---------------------|---------------------|
| `mp4`, `m4v`, `mov`, `mkv` | `libx264` | `aac` |
| `webm` | `libvpx-vp9` | `libopus` |
| `avi` | `mpeg4` | `libmp3lame` |
| `ogv` | `libtheora` | `libvorbis` |

Formats outside this table have no built-in default codec; specify `video.codec` and `audio.codec` explicitly. When the resolved video codec is `libx264` or `libx265`, `-pix_fmt yuv420p` is applied automatically for broad player compatibility.

## Audio Handling

The optional `audio` field muxes an audio track into the output:

```yaml
component:
  type: video-encoder
  action:
    video: ${input.silent_video}
    audio: ${input.soundtrack}
    encoding:
      format: mp4
    output: ${output}
```

When both a `video` input (with its own audio track) and a separate `audio` source are provided, the built-in audio is discarded and the separate `audio` becomes the output's audio track. This is implemented via ffmpeg's `-map 0:v -map 1:a`. Because durations may differ, `-shortest` is also applied so encoding stops at the end of the shorter of the two inputs.

When encoding from `frames`, the frame sequence itself has no audio, so `audio` simply adds an audio track. `-shortest` still applies, so the output ends when either the frames or the audio run out.

## Streaming Output

Setting `streaming: true` writes the encoded bytes directly to ffmpeg's stdout and returns a stream instead of a temporary file. This avoids disk I/O but is only supported for container formats that ffmpeg can write without seeking back into the output:

```yaml
component:
  type: video-encoder
  action:
    frames: ${input.frames}
    frame_rate: 30
    encoding:
      format: webm
      video:
        codec: libvpx-vp9
    streaming: true
    output: ${output}
```

**Streamable formats:** `mpegts`, `ts`, `flv`, `ogg`, `webm`.

If `streaming: true` is set with any other format (e.g. `mp4`, `mov`, `mkv`, `avi`), the encoder logs a warning and falls back to file-based output. This is because containers like MP4 need a post-write seek to place the `moov` atom, index tables, or apply `+faststart`.

File-based encoding always adds `-movflags +faststart` to the ffmpeg command so the resulting file is playable while progressively loading.

## Batch and Streaming Input

The action accepts single inputs, lists, and async iterators:

- **Single input** — `video` or `frames` resolves to one source. The result is a single `VideoStreamResource`.
- **List input** — Resolves to a list. Inputs are grouped by `batch_size` (default `1`) and processed in parallel within each batch. The result is a list of `VideoStreamResource`.
- **Streaming input** — When the resolved input is an async iterator, the action returns an async iterator of results, one per input item, still batched by `batch_size`.

When both `video`/`frames` and `audio` are lists, each output pairs the `i`-th video with the `i`-th audio.

```yaml
component:
  type: video-encoder
  action:
    frames: ${input.frame_batches}
    audio: ${input.audio_tracks}
    frame_rate: 30
    batch_size: 4
    encoding:
      format: mp4
    output: ${output}
```

## Multiple Actions Configuration

Define multiple encoding profiles under the same component:

```yaml
component:
  type: video-encoder
  actions:
    - id: mp4-1080p
      video: ${input.video}
      encoding:
        format: mp4
        video:
          codec: libx264
          bitrate: 4M
          resolution: 1920x1080
      output: ${hd}

    - id: webm-720p
      video: ${input.video}
      encoding:
        format: webm
        video:
          codec: libvpx-vp9
          bitrate: 2M
          resolution: 1280x720
      output: ${sd}

    - id: from-frames
      frames: ${input.frames}
      frame_rate: 24
      encoding:
        format: mp4
      output: ${animation}
```

## Usage Examples

### Frames to Video with Soundtrack

Encode a rendered frame sequence and attach an external audio track:

```yaml
workflows:
  - id: render-clip
    jobs:
      - id: encode
        component: video-encoder
        action: render
        input:
          frames: ${input.frames}
          audio: ${input.music}
        output:
          clip: ${output}

components:
  - id: video-encoder
    type: video-encoder
    actions:
      - id: render
        frames: ${input.frames}
        audio: ${input.audio}
        frame_rate: 30
        encoding:
          format: mp4
          video:
            codec: libx264
            bitrate: 3M
          audio:
            codec: aac
            bitrate: 192k
        output: ${output}
```

Because `audio` is provided alongside frames, `-shortest` truncates the output to whichever runs out first: the frame sequence at 30 fps, or the soundtrack.

### Transcoding to Multiple Formats

Fan out one source into several output profiles:

```yaml
workflows:
  - id: transcode
    jobs:
      - id: to-mp4
        component: video-encoder
        action: mp4
        input:
          video: ${input.source}
        output:
          mp4: ${output}

      - id: to-webm
        component: video-encoder
        action: webm
        input:
          video: ${input.source}
        output:
          webm: ${output}

components:
  - id: video-encoder
    type: video-encoder
    actions:
      - id: mp4
        video: ${input.video}
        encoding:
          format: mp4
          video:
            codec: libx264
            bitrate: 4M
        output: ${output}

      - id: webm
        video: ${input.video}
        encoding:
          format: webm
          video:
            codec: libvpx-vp9
            bitrate: 2M
        output: ${output}
```

### Streaming Live Output

Emit a webm byte stream instead of a temporary file:

```yaml
component:
  type: video-encoder
  action:
    frames: ${input.frames}
    frame_rate: 30
    encoding:
      format: webm
      video:
        codec: libvpx-vp9
        bitrate: 2M
    streaming: true
    output: ${output}
```

## Variable Interpolation

Encoding settings can be driven from workflow inputs:

```yaml
component:
  type: video-encoder
  action:
    video: ${input.video}
    encoding:
      format: ${input.format | mp4}
      video:
        codec: ${input.codec | libx264}
        bitrate: ${input.bitrate | 2M}
        resolution: ${input.resolution}
        fps: ${input.fps as integer | 30}
      audio:
        codec: ${input.audio_codec | aac}
        bitrate: ${input.audio_bitrate | 128k}
    streaming: ${input.stream as boolean | false}
    output: ${output}
```

## Audio Track Override Behavior

When a `video` input already contains an audio stream and a separate `audio` source is also supplied, the encoder does not mix the two. Instead:

1. The video track is taken from the video input (`-map 0:v`).
2. The audio track is taken from the separate audio input (`-map 1:a`), replacing the video's built-in audio.
3. `-shortest` is passed to ffmpeg, so the output ends at the end of whichever input — video or audio — finishes first.

If no separate `audio` is provided, the video's original audio track (if any) passes through unchanged and `-shortest` is not applied.

## Common Use Cases

- **Frame Sequence Assembly** — Convert model-generated or extracted frames into playable video.
- **Format Transcoding** — Re-encode video into a different container or codec.
- **Bitrate and Resolution Adjustment** — Produce downscaled or lower-bitrate variants.
- **Audio Track Replacement** — Swap the audio on an existing video for a generated or supplied track.
- **Streaming Delivery** — Emit webm or MPEG-TS byte streams for live consumption.
