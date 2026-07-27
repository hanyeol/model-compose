# RTMP Publisher Component

The RTMP publisher component sends video, frame sequences, or audio to one or more RTMP endpoints. It wraps the `ffmpeg` binary and produces the FLV/H.264/AAC stream that RTMP servers expect, which makes it suitable for pushing to YouTube Live, Twitch, Facebook Live, or any RTMP-compatible ingest. The action does not return a value; it blocks until the publish stream ends.

## Basic Configuration

```yaml
component:
  type: rtmp-publisher
  action:
    url: rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
    video: ${input.video}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `rtmp-publisher` |
| `driver` | string | `ffmpeg` | Publisher backend. Currently only `ffmpeg` is supported (requires the `ffmpeg` binary on `PATH`). |
| `actions` | array | `[]` | List of publish actions |

### Common Action Configuration

All RTMP publisher actions share these settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string / array | **required** | RTMP endpoint URL, or a list of URLs to broadcast to in parallel |
| `video` | string / array | `null` | Existing video source(s) to publish. Mutually exclusive with `frames`. |
| `frames` | string / array | `null` | PIL image sequence(s) to publish. Mutually exclusive with `video`. |
| `frame_rate` | integer / string | `null` | Frame rate for `frames` input (defaults to 30 fps if unspecified). Only valid with `frames`. |
| `audio` | string / array | `null` | Audio source(s). May be used on its own or paired with `video` / `frames`. |
| `encoding` | object | `null` | Video/audio encoding settings. See [Encoding](#encoding). |
| `batch_size` | integer / string | `null` | Number of publishes to fan out in parallel per tick. Defaults to `1` (sequential). |
| `continuous` | boolean / string | `true` | Keep the RTMP session open across clips (one long-lived ffmpeg process per URL). Set to `false` to run one ffmpeg process per clip. See [Continuous Mode](#continuous-mode). |
| `output` | any | `null` | Output variable mapping. The action itself returns no value. |

At least one of `video`, `frames`, or `audio` must be provided. Specifying both `video` and `frames` is an error, and `frame_rate` is rejected unless `frames` is set.

## Input Modes

The publisher picks a mode from the fields you set on the action.

### Publishing an Existing Video

Use `video` to stream a pre-existing video source (file path, bytes, or a reference to a prior job's output).

```yaml
component:
  type: rtmp-publisher
  action:
    url: rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
    video: ${input.video}
```

If the input video already has an audio track, it is preserved. If you also set the `audio` field, the built-in audio is discarded and replaced by the separate audio track (`ffmpeg -map 0:v -map 1:a`), and `-shortest` is applied so the stream ends when the shorter of the two runs out.

### Publishing from a Frame Sequence

Use `frames` to encode a live PIL image sequence into a video stream on the fly. This mode is intended to pair with components that emit frames (screen capture, video-to-frames, generation loops, and so on).

```yaml
component:
  type: rtmp-publisher
  action:
    url: rtmp://live.twitch.tv/app/${env.TWITCH_STREAM_KEY}
    frames: ${jobs.capture.output.frames}
    frame_rate: 30
    audio: ${input.microphone}
```

**Frame Sequence Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frames` | string / array | **required** | Frame sequence variable reference (evaluated as an image array) |
| `frame_rate` | integer / string | `30` | Frame rate to encode at. Applied via ffmpeg's `-framerate` on `image2pipe`. |
| `audio` | string / array | `null` | Optional audio track to mux in |

Frames are streamed as PNG-encoded bytes into ffmpeg over stdin.

### Publishing Audio Only

Omit `video` and `frames` to send an audio-only stream. The publisher still uses the FLV container, so downstream ingest sees a valid (video-less) RTMP session.

```yaml
component:
  type: rtmp-publisher
  action:
    url: rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
    audio: ${input.audio}
    encoding:
      audio:
        codec: aac
        bitrate: 192k
```

## Encoding

The `encoding` field configures the container format and codecs. RTMP defaults are chosen for maximum compatibility: FLV container, `libx264` video, and `aac` audio.

```yaml
component:
  type: rtmp-publisher
  action:
    url: rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
    video: ${input.video}
    encoding:
      format: flv
      video:
        codec: libx264
        bitrate: 4500k
        resolution: 1920x1080
        fps: 30
      audio:
        codec: aac
        bitrate: 160k
```

**Encoding Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string | `flv` | Container format passed to ffmpeg's `-f`. Should stay `flv` for RTMP. |
| `video.codec` | string | `libx264` | Video codec |
| `video.bitrate` | string | `null` | Video bitrate (e.g. `2M`, `4500k`) |
| `video.resolution` | string | `null` | Output resolution (e.g. `1920x1080`) |
| `video.fps` | string / integer / number | `null` | Output frame rate |
| `audio.codec` | string | `aac` | Audio codec |
| `audio.bitrate` | string | `null` | Audio bitrate (e.g. `128k`) |

When the video codec resolves to `libx264` or `libx265`, `-pix_fmt yuv420p` is added automatically so the resulting stream plays in Flash-era ingest, browser HTML5 video, and mobile players.

## Multi-Target Broadcasting

Pass a list of URLs to publish the same input to several endpoints. `batch_size` bounds how many endpoints are pushed to in parallel per tick; the remainder run in subsequent ticks.

```yaml
component:
  type: rtmp-publisher
  action:
    url:
      - rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
      - rtmp://live.twitch.tv/app/${env.TWITCH_STREAM_KEY}
      - rtmps://live-api-s.facebook.com:443/rtmp/${env.FACEBOOK_STREAM_KEY}
    video: ${input.video}
    batch_size: 3
```

**Broadcasting Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | array | **required** | List of RTMP endpoint URLs |
| `batch_size` | integer / string | `1` | Number of endpoints to publish to concurrently per tick |

With `batch_size: 1` (the default), each endpoint is published to in sequence. Setting `batch_size` to the list length publishes to every endpoint concurrently. This is also the throttle that applies when a streaming input feeds multiple destinations.

## Multiple Actions Configuration

Define several publish actions on the same component and select them per workflow job:

```yaml
component:
  type: rtmp-publisher
  actions:
    - id: to-youtube
      url: rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
      video: ${input.video}

    - id: to-twitch
      url: rtmp://live.twitch.tv/app/${env.TWITCH_STREAM_KEY}
      video: ${input.video}
      encoding:
        video:
          bitrate: 6000k

    - id: audio-only
      url: rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
      audio: ${input.audio}
```

## Usage Examples

### Live Screen Share to YouTube

Capture the screen as frames and publish them to a YouTube Live ingest:

```yaml
workflows:
  - id: stream-screen
    jobs:
      - id: capture
        component: screen-capture
        action: capture-frames
        output:
          frames: ${output}

      - id: publish
        component: rtmp-publisher
        action: to-youtube
        input:
          frames: ${jobs.capture.output.frames}
        depends_on: [ capture ]

components:
  - id: screen-capture
    type: screen-capture
    actions:
      - id: capture-frames
        # ...

  - id: rtmp-publisher
    type: rtmp-publisher
    actions:
      - id: to-youtube
        url: rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
        frames: ${input.frames}
        frame_rate: 30
        encoding:
          video:
            bitrate: 4500k
            resolution: 1920x1080
```

### Restream to Multiple Platforms

Fan a single video source out to YouTube, Twitch, and Facebook Live in parallel:

```yaml
workflows:
  - id: restream
    jobs:
      - id: broadcast
        component: rtmp-publisher
        action: fan-out
        input:
          video: ${input.video}

components:
  - id: rtmp-publisher
    type: rtmp-publisher
    actions:
      - id: fan-out
        url:
          - rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
          - rtmp://live.twitch.tv/app/${env.TWITCH_STREAM_KEY}
          - rtmps://live-api-s.facebook.com:443/rtmp/${env.FACEBOOK_STREAM_KEY}
        video: ${input.video}
        batch_size: 3
```

### Video With Overridden Audio Track

Publish an existing video but swap its built-in audio for a separate voiceover track:

```yaml
component:
  type: rtmp-publisher
  action:
    url: rtmp://a.rtmp.youtube.com/live2/${env.YOUTUBE_STREAM_KEY}
    video: ${input.silent_video}
    audio: ${input.voiceover}
    encoding:
      audio:
        codec: aac
        bitrate: 192k
```

## Notes

- The ffmpeg driver currently spools streaming inputs to a temporary file before publishing, so live sources incur an upfront buffering step rather than pure realtime pass-through.
- The action returns `None`; use `depends_on` to sequence downstream jobs on completion rather than reading an output value.
- Errors from ffmpeg (network failures, rejected stream keys, codec issues) surface as a `RuntimeError` containing the ffmpeg stderr output and its exit code.

## Supported Endpoints

Any RTMP or RTMPS ingest that accepts FLV-wrapped H.264/AAC works, including:

- **YouTube Live** — `rtmp://a.rtmp.youtube.com/live2/<STREAM_KEY>`
- **Twitch** — `rtmp://live.twitch.tv/app/<STREAM_KEY>`
- **Facebook Live** — `rtmps://live-api-s.facebook.com:443/rtmp/<STREAM_KEY>`
- Self-hosted RTMP servers (nginx-rtmp, MediaMTX, SRS, etc.)
