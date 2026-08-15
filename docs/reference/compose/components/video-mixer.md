# Video Mixer Component

The video mixer component composites multiple videos into a single output using FFmpeg. Two mixing methods are supported: `concat` joins videos end-to-end, and `overlay` composites one or more videos on top of a base (watermarks, picture-in-picture, side-by-side layouts, etc.).

## Basic Configuration

```yaml
component:
  type: video-mixer
  driver: ffmpeg
  action:
    method: concat
    videos:
      - ${input.first as video}
      - ${input.second as video}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-mixer` |
| `driver` | string | `ffmpeg` | Mixing backend driver. Currently only `ffmpeg`. |
| `actions` | array | `[]` | List of mixing actions |

### Common Action Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Mixing operation — `concat` or `overlay` |
| `encoding` | object | - | Output encoding settings (container/codec/bitrate/resolution/fps). See [Encoding](#encoding). |
| `batch_size` | integer \| string | `null` | Number of input sets processed per batch when the input is a list/stream. |
| `streaming` | boolean \| string | `false` | If true, the mixed output is emitted as a byte stream instead of a temporary file. |

Because filter graphs cannot operate on stream-copied inputs, both methods re-encode. Provide `encoding` to control the output container/codecs; if omitted, defaults are selected per format (mp4 → libx264 + aac, webm → libvpx-vp9 + libopus, ...).

## Concat Method

Joins videos end-to-end using FFmpeg's `concat` filter.

```yaml
action:
  method: concat
  videos:
    - ${input.intro as video}
    - ${input.main as video}
    - ${input.outro as video}
```

### Concat Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `videos` | string[] \| string | **required** | Videos to concatenate, in the order they appear in the output (minimum 2). |
| `crossfade` | string \| number | - | Reserved for future support; currently raises `NotImplementedError`. Omit for plain concat. |

> **All inputs must share the same resolution, SAR, pixel format, framerate, audio sample rate, and channel layout.** The concat filter fails with `Input link ... parameters do not match` when they don't. Normalize inputs upstream with `video-converter` before concatenating.

## Overlay Method

Composites one or more overlay videos on top of a base video. Overlays are stacked in list order — the first lands on the base, the second on that result, and so on — so higher-index overlays appear on top when they intersect.

```yaml
action:
  method: overlay
  video: ${input.base as video}
  overlay: ${input.watermark as video}
  placement:
    x: 20
    y: 20
    width: 320
  audio_mode: base
  duration_mode: base
```

### Overlay Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | string \| string[] | **required** | Base video the overlays are composited on. A list runs one output per base (batch mode). |
| `overlay` | string \| string[] | **required** | Overlay video(s). A single string is auto-wrapped into a one-element list. |
| `placement` | object \| object[] \| string | one default placement | Placement per overlay. A single object broadcasts to every overlay; a list matches overlays by position. |
| `audio_mode` | `base` \| `overlay` \| `mix` \| `none` | `base` | Which audio track(s) the output carries. See [Audio Mode](#audio-mode). |
| `duration_mode` | `base` \| `longest` \| `shortest` | `base` | How long the output runs relative to the base and overlays. See [Duration Mode](#duration-mode). |

### Placement Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | integer \| string | `0` | X coordinate on the base video where the overlay is placed, in pixels. |
| `y` | integer \| string | `0` | Y coordinate on the base video where the overlay is placed, in pixels. |
| `width` | integer \| string | - | Resize the overlay to this width in pixels (aspect-preserving when only one dimension is set). |
| `height` | integer \| string | - | Resize the overlay to this height in pixels. |
| `anchor` | string | `top-left` | Point of the overlay aligned at `(x, y)` — one of `top-left`, `top-center`, `top-right`, `center-left`, `center`, `center-right`, `bottom-left`, `bottom-center`, `bottom-right`. |
| `opacity` | number \| string | `1.0` | Alpha multiplier for the overlay, from `0.0` (transparent) to `1.0` (opaque). |
| `start` | string \| number | - | Time the overlay first appears, as a duration string (e.g. `"2s"`) or seconds. Omit to start at 0. |
| `end` | string \| number | - | Time the overlay disappears, as a duration string (e.g. `"5s"`) or seconds. Omit to run to the base video's end. |

### Audio Mode

- **base**: keep only the base video's audio track (typical for watermarks / PIP).
- **overlay**: keep only the overlay's audio track. With multiple overlays their audio tracks are mixed.
- **mix**: mix the base and all overlays' audio tracks.
- **none**: strip audio from the output.

The mix uses FFmpeg's `amix` filter with `duration=` matching `duration_mode` so audio doesn't cut early.

### Duration Mode

- **base** (default): the output stops when the base video ends. Overlays that end earlier disappear; overlays that outlast the base are cut off. Runs one `ffprobe` on the base to derive the output cap (`-t <base_duration>`).
- **longest**: the output runs until the last stream ends. The base is extended past its own end by cloning its final frame (`tpad=stop_mode=clone`) so the overlay filter can keep compositing. Runs one `ffprobe` per input to compute the pad length.
- **shortest**: the output stops as soon as any input (base or overlay) ends. Adds `shortest=1` to the overlay filter. No probe needed.

### Cardinality Rules

`video` decides the batch axis:

- **`video: str`** — single execution. `overlay` is a list of overlays composited on the one base.
- **`video: str[]`** — batch execution. One output per base, with the overlay set (and placements) broadcast across every base.

`placement` cardinality inside a single execution:

- **1 placement + N overlays** → the placement broadcasts to every overlay.
- **N placements + N overlays** → placements match overlays by position.
- **Any other combination** → `overlay/placement cardinality mismatch` error.

## Encoding

Both methods share the `encoding` block (`VideoAudioEncodingConfig`):

```yaml
encoding:
  format: mp4              # container
  video:
    codec: libx264         # video codec
    bitrate: 4M            # target video bitrate
    resolution: 1920x1080  # output resolution
    fps: 30                # output frame rate
  audio:
    codec: aac             # audio codec
    bitrate: 192k          # target audio bitrate
    sample_rate: 48000     # output sample rate
    channels: 2            # output channel count
```

If `encoding` is omitted, sensible defaults are picked per format:

| Format | Video codec | Audio codec |
|--------|-------------|-------------|
| mp4 / m4v / mov / mkv | libx264 | aac |
| webm | libvpx-vp9 | libopus |
| avi | mpeg4 | libmp3lame |
| ogv | libtheora | libvorbis |

Default output format is `mp4`.

## Supported Drivers

### FFmpeg

Uses FFmpeg's `concat` and `overlay` filters (and `amix`/`tpad` where needed). Requires the `ffmpeg` and `ffprobe` binaries on `PATH`.

## Multiple Actions Configuration

Define multiple mixing actions on the same component:

```yaml
component:
  type: video-mixer
  actions:
    - id: concat
      method: concat
      videos:
        - ${input.first as video}
        - ${input.second as video}

    - id: overlay-single
      method: overlay
      video: ${input.base as video}
      overlay: ${input.pip as video}
      placement:
        x: 20
        y: 20
        width: 320

    - id: overlay-multiple
      method: overlay
      video: ${input.base as video}
      overlay:
        - ${input.a as video}
        - ${input.b as video}
      placement:
        - { x: 20, y: 20, width: 240 }
        - { x: 20, y: 280, width: 240, opacity: 0.75 }
```

## Integration with Workflows

### Concat Two Clips

```yaml
workflows:
  - id: join-clips
    job:
      component: mixer
      action: concat
      output:
        video: ${output as video}

components:
  - id: mixer
    type: video-mixer
    action:
      id: concat
      method: concat
      videos:
        - ${input.first as video}
        - ${input.second as video}
```

### Watermark with Duration Cap

```yaml
workflows:
  - id: watermark
    job:
      component: mixer
      action: watermark
      output:
        video: ${output as video}

components:
  - id: mixer
    type: video-mixer
    action:
      id: watermark
      method: overlay
      video: ${input.video as video}
      overlay: ${input.logo as video}
      placement:
        x: 20
        y: 20
        width: 160
        anchor: top-right
        opacity: 0.8
      audio_mode: base
      duration_mode: base
```

### Picture-in-Picture with Longest Duration

```yaml
components:
  - id: mixer
    type: video-mixer
    action:
      id: pip
      method: overlay
      video: ${input.lecture as video}
      overlay: ${input.webcam as video}
      placement:
        x: 40
        y: 40
        width: 320
        anchor: top-right
      audio_mode: mix
      duration_mode: longest
```

## Best Practices

1. **Concat requires matching inputs**: The `concat` filter needs identical resolution, SAR, pixel format, framerate, audio sample rate, and channel layout. Pre-process with `video-converter` when inputs differ.
2. **Overlay stacking order**: The first overlay is drawn first, the last appears on top. Order the list from bottom to top.
3. **Placement broadcast**: A single `placement` object applies to every overlay in a single execution. Use a list only when overlays need different coordinates, sizes, or timing.
4. **Time-gated overlays**: `placement.start` / `placement.end` make an overlay visible only within a time window — useful for lower-thirds or watermarks that fade in later.
5. **Anchor semantics**: `anchor` shifts the overlay relative to `(x, y)`. For example, `anchor: center` places the *center* of the overlay at `(x, y)` instead of the top-left corner.
6. **Batch mode**: Passing a list of base videos runs one overlay operation per base and returns a list of outputs. The same overlay set is broadcast to every base.
7. **Streaming input**: Non-file video sources (bytes, HTTP uploads) are spooled to temporary files before mixing so FFmpeg can seek them.
