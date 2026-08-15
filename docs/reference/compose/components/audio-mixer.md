# Audio Mixer Component

The audio mixer component combines multiple audio sources into a single output using FFmpeg. Two mixing methods are supported: `concat` joins audios end-to-end, and `overlay` mixes one or more audios into a base (background music under narration, layered sound effects, etc.).

## Basic Configuration

```yaml
component:
  type: audio-mixer
  driver: ffmpeg
  action:
    method: concat
    audios:
      - ${input.first as audio}
      - ${input.second as audio}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `audio-mixer` |
| `driver` | string | `ffmpeg` | Mixing backend driver. Currently only `ffmpeg`. |
| `actions` | array | `[]` | List of mixing actions |

### Common Action Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Mixing operation — `concat` or `overlay` |
| `format` | string | `wav` | Output container format (e.g., `wav`, `mp3`, `aac`, `flac`, `opus`). |
| `encoding` | object | - | Output audio encoder settings (codec/bitrate/sample_rate/channels). See [Encoding](#encoding). |
| `batch_size` | integer \| string | `null` | Number of input sets processed per batch when the input is a list/stream. |
| `streaming` | boolean \| string | `false` | If true, the mixed output is emitted as a byte stream instead of a temporary file. |

Because filter graphs cannot operate on stream-copied inputs, both methods re-encode. Set `format` to pick the output container; `encoding` overrides codec/bitrate/sample rate/channels when the format's defaults don't fit.

## Concat Method

Joins audios end-to-end using FFmpeg's `concat` filter.

```yaml
action:
  method: concat
  audios:
    - ${input.intro as audio}
    - ${input.main as audio}
    - ${input.outro as audio}
  format: mp3
```

### Concat Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audios` | string[] \| string | **required** | Audios to concatenate, in the order they appear in the output (minimum 2). |
| `crossfade` | string \| number | - | Reserved for future support; currently raises `NotImplementedError`. Omit for plain concat. |

> **All inputs must share the same sample rate and channel layout.** The concat filter fails with `Input link ... parameters do not match` when they don't. Normalize inputs upstream with `audio-converter` before concatenating.

## Overlay Method

Mixes one or more overlay audios into a base audio. Every overlay plays simultaneously with the base — timing is controlled per-overlay via `start_time`/`end_time`. Each overlay goes through its own preparation chain (`adelay → atrim → volume → pan → afade`) before ffmpeg's `amix` filter combines the base and all overlays.

```yaml
action:
  method: overlay
  audio: ${input.background as audio}
  overlay: ${input.narration as audio}
  placement:
    start_time: 2s
    gain: 0.8
    fade_in: 500ms
  duration_mode: base
  format: mp3
```

### Overlay Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | string \| string[] | **required** | Base audio the overlays are mixed on. A list runs one output per base (batch mode). |
| `overlay` | string \| string[] | **required** | Overlay audio(s). A single string is auto-wrapped into a one-element list. |
| `placement` | object \| object[] \| string | one default placement | Placement per overlay. A single object broadcasts to every overlay; a list matches overlays by position. |
| `duration_mode` | `base` \| `longest` \| `shortest` | `base` | How long the output runs relative to the base and overlays. See [Duration Mode](#duration-mode). |

### Placement Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `start_time` | string \| number | - | Time the overlay first plays, as a duration string (e.g. `"2s"`) or seconds. Omit to start at 0. |
| `end_time` | string \| number | - | Time the overlay stops playing, as a duration string or seconds. Omit to run to the overlay's natural end. |
| `gain` | number \| string | `1.0` | Linear volume multiplier for the overlay (`1.0` = unchanged, `0.5` ≈ -6 dB, `2.0` ≈ +6 dB). |
| `pan` | number \| string | `0.0` | Stereo pan for the overlay, from `-1.0` (full left) to `1.0` (full right). |
| `fade_in` | string \| number | - | Fade-in duration applied at `start_time`. |
| `fade_out` | string \| number | - | Fade-out duration ending at `end_time`. Requires `end_time`; ignored otherwise. |

### Duration Mode

- **base** (default): the output stops when the base audio ends. Overlays that end earlier disappear; overlays that outlast the base are cut off. Runs one `ffprobe` on the base to derive the output cap (`-t <base_duration>`).
- **longest**: the output runs until the last stream ends. Useful when a delayed overlay needs to keep playing after the base ends.
- **shortest**: the output stops as soon as any input (base or overlay) ends. Useful when overlays need to gate the total duration.

`longest` and `shortest` are handled directly by `amix`'s `duration` option; `base` uses the `-t` cap to override `amix`'s trailing behavior.

### Cardinality Rules

`audio` decides the batch axis:

- **`audio: str`** — single execution. `overlay` is a list of overlays mixed into the one base.
- **`audio: str[]`** — batch execution. One output per base, with the overlay set (and placements) broadcast across every base.

`placement` cardinality inside a single execution:

- **1 placement + N overlays** → the placement broadcasts to every overlay.
- **N placements + N overlays** → placements match overlays by position.
- **Any other combination** → `overlay/placement cardinality mismatch` error.

## Encoding

Both methods share the `encoding` block (`AudioEncoderConfig`):

```yaml
format: mp3                # container
encoding:
  codec: libmp3lame        # audio codec
  bitrate: 192k            # target bitrate
  sample_rate: 44100       # output sample rate
  channels: 2              # output channel count
```

If `encoding` is omitted, sensible defaults are picked per format:

| Format | Audio codec |
|--------|-------------|
| wav | pcm_s16le |
| mp3 | libmp3lame |
| flac | flac |
| aac / m4a | aac |
| opus | libopus |
| ogg | libvorbis |

Default output format is `wav`.

## Supported Drivers

### FFmpeg

Uses FFmpeg's `concat`, `amix`, `adelay`, `atrim`, `volume`, `pan`, and `afade` filters. Requires the `ffmpeg` and `ffprobe` binaries on `PATH`.

## Multiple Actions Configuration

Define multiple mixing actions on the same component:

```yaml
component:
  type: audio-mixer
  actions:
    - id: concat
      method: concat
      audios:
        - ${input.first as audio}
        - ${input.second as audio}
      format: mp3

    - id: narrated-bg
      method: overlay
      audio: ${input.background as audio}
      overlay: ${input.narration as audio}
      placement:
        start_time: 2s
        gain: 0.8
        fade_in: 500ms
      format: mp3

    - id: layered-sfx
      method: overlay
      audio: ${input.background as audio}
      overlay:
        - ${input.narration as audio}
        - ${input.sfx as audio}
      placement:
        - { start_time: 1s, gain: 1.0, fade_in: 300ms, fade_out: 500ms }
        - { start_time: 5s, end_time: 7s, gain: 0.6, pan: 0.5 }
      format: mp3
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
        audio: ${output as audio}

components:
  - id: mixer
    type: audio-mixer
    action:
      id: concat
      method: concat
      audios:
        - ${input.first as audio}
        - ${input.second as audio}
      format: mp3
```

### Narration Over Background Music

```yaml
workflows:
  - id: narrated-track
    job:
      component: mixer
      action: narrate
      output:
        audio: ${output as audio}

components:
  - id: mixer
    type: audio-mixer
    action:
      id: narrate
      method: overlay
      audio: ${input.background as audio}
      overlay: ${input.narration as audio}
      placement:
        start_time: ${input.start | 2s}
        gain: 0.9
        fade_in: 500ms
      duration_mode: base
      format: mp3
```

### Layered Sound Effects (Longest Duration)

```yaml
components:
  - id: mixer
    type: audio-mixer
    action:
      id: layered
      method: overlay
      audio: ${input.base as audio}
      overlay:
        - ${input.narration as audio}
        - ${input.sfx as audio}
      placement:
        - start_time: 1s
          gain: 1.0
          fade_in: 300ms
        - start_time: 5s
          end_time: 7s
          gain: 0.6
          pan: 0.5
      duration_mode: longest
      format: mp3
```

## Best Practices

1. **Concat requires matching inputs**: The `concat` filter needs identical sample rate and channel layout. Pre-process with `audio-converter` when inputs differ.
2. **Overlay is simultaneous, not stacked**: Unlike video overlays there is no z-order — every overlay plays at once and is summed into the base. Order in the `overlay` list does not affect the result.
3. **Placement broadcast**: A single `placement` object applies to every overlay in a single execution. Use a list only when overlays need different timing, gain, or pan.
4. **Timing semantics**: `start_time` is measured on the base's timeline, so `start_time: 5s` delays the overlay by 5 seconds. `end_time` cuts the overlay at that absolute time along the delayed timeline.
5. **Fade-out needs `end_time`**: Because a fade-out ends at `end_time`, omitting `end_time` disables `fade_out`. Set both when you want a tail fade.
6. **Levels are preserved, not normalized**: `amix` sums inputs without normalization here (`normalize=0`), so raw levels are kept. Adjust each overlay's `gain` — or lower the base upstream — until the balance sounds right.
7. **Batch mode**: Passing a list of base audios runs one overlay operation per base and returns a list of outputs. The same overlay set is broadcast to every base.
8. **Streaming input**: Non-file audio sources (bytes, HTTP uploads) are spooled to temporary files before mixing so FFmpeg can seek them.
