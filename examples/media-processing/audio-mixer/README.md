# Audio Mixer Example

This example demonstrates the `audio-mixer` component, which combines multiple audio sources into a single output using ffmpeg. Two mixing methods are covered:

- **concat**: join audios end-to-end into one longer audio
- **overlay**: mix one or more overlay audios into a base audio (background music under narration, layered sound effects, etc.)

## Overview

This example exposes three workflows built on the same `audio-mixer` component:

1. **Concatenate Audios**: Stitch a list of audios into a single output
2. **Overlay Single Audio**: Mix one overlay onto a base audio with configurable start time, gain, and fade
3. **Overlay Multiple Audios**: Layer several overlays into a base audio, each with its own timing, gain, pan, and fade

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- [ffmpeg](https://ffmpeg.org/) installed and available in your PATH

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/audio-mixer
```

Verify ffmpeg is installed:
```bash
ffmpeg -version
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   The service will start:
   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run workflows:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select a workflow from the dropdown
   - Upload the required audio files and set any placement fields
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Concatenate two clips into one audio
   model-compose run concat --input '{
     "first": "/path/to/intro.mp3",
     "second": "/path/to/main.mp3"
   }'

   # Mix a narration on top of a background track
   model-compose run overlay-single --input '{
     "base": "/path/to/background.mp3",
     "overlay": "/path/to/narration.mp3",
     "start_time": "2s",
     "gain": 0.8
   }'

   # Layer a narration and a sound effect on top of a base track
   model-compose run overlay-multiple --input '{
     "base": "/path/to/background.mp3",
     "narration": "/path/to/narration.mp3",
     "sfx": "/path/to/effect.mp3"
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=overlay-single" \
     -F "base=@/path/to/background.mp3" \
     -F "overlay=@/path/to/narration.mp3" \
     -F "start_time=2s" \
     -F "gain=0.8"
   ```

## Component Details

### Audio Mixer Component

- **Type**: `audio-mixer`
- **Driver**: `ffmpeg`
- **Purpose**: Combine multiple audios into a single output using ffmpeg filters (`concat` for join, `amix` for overlay).

Audios are re-encoded during mixing because ffmpeg filter graphs cannot operate on stream-copied inputs. The `format` field sets the output container (default `wav`); the `encoding` field controls codec, bitrate, sample rate, and channel count. When `encoding` is omitted, sensible defaults are picked per format (mp3 → libmp3lame, wav → pcm_s16le, aac/m4a → aac, opus → libopus, ...).

### Concat Method

Joins audios end-to-end using ffmpeg's `concat` filter. All inputs must share the same sample rate and channel layout — the concat filter fails with `Input link ... parameters do not match` when they don't. Normalize the inputs upstream (for example with the `audio-converter` component) before feeding them into `concat`.

#### Key Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `audios` | list of audio sources | Yes | - | Audios to concatenate, in order (minimum 2) |
| `crossfade` | duration | No | - | Reserved for future support; currently not implemented |
| `format` | string | No | `wav` | Output container format |
| `encoding` | object | No | format defaults | Output codec / bitrate / sample rate / channels |
| `batch_size` | integer | No | `1` | Number of input *sets* processed per batch when `audios` is a list of lists or a stream |
| `streaming` | boolean | No | `false` | Emit the output as a byte stream instead of a temporary file |

### Overlay Method

Mixes one or more overlay audios with a base audio. All overlays play simultaneously with the base — timing is controlled per-overlay via `start_time`/`end_time`. Overlays are combined through ffmpeg's `amix` filter after each one goes through its own preparation chain (delay → trim → gain → pan → fade).

#### Key Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `audio` | audio source or list | Yes | - | Base audio (a list turns on batch mode: one output per base) |
| `overlay` | string or list of strings | Yes | - | Overlay audio(s). A single string is auto-wrapped into a one-element list |
| `placement` | object or list of objects | No | one default placement | One placement per overlay. A single object broadcasts to all overlays; a list matches by position |
| `duration_mode` | `base` \| `longest` \| `shortest` | No | `base` | How long the output runs relative to the base and overlays |
| `format` | string | No | `wav` | Output container format |
| `encoding` | object | No | format defaults | Output codec / bitrate / sample rate / channels |
| `batch_size` | integer | No | `1` | Number of base audios processed per batch when `audio` is a list/stream |
| `streaming` | boolean | No | `false` | Emit the output as a byte stream instead of a temporary file |

#### Placement Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `start_time` | duration | - | Time the overlay first plays (measured on the base's timeline; `0s` by default) |
| `end_time` | duration | - | Time the overlay stops playing (runs to the overlay's natural end by default) |
| `gain` | float | `1.0` | Linear volume multiplier (1.0 = unchanged, 0.5 = -6dB, 2.0 = +6dB) |
| `pan` | float -1..1 | `0.0` | Stereo pan (-1.0 = full left, 0.0 = center, +1.0 = full right) |
| `fade_in` | duration | - | Fade-in duration applied at `start_time` |
| `fade_out` | duration | - | Fade-out duration ending at `end_time` (requires `end_time`) |

`start_time`, `end_time`, `fade_in`, `fade_out` accept:
- Numbers (seconds): `10`, `10.5`
- Duration strings: `"10s"`, `"1m"`, `"250ms"`
- Timecodes: `"00:00:10"`, `"01:23:45"`

#### Duration Policy

- **base** (default): the output stops when the base audio ends. Overlays that end earlier disappear; overlays that outlast the base are cut off.
- **longest**: the output runs until the last stream ends. Useful when a delayed overlay needs to keep playing after the base ends.
- **shortest**: the output stops as soon as any input (base or overlay) ends. Useful when overlays need to gate the total duration.

`base` runs one `ffprobe` on the base to cap the output length; `longest`/`shortest` are handled directly by `amix`'s `duration` option.

## Workflow Details

### 1. Concatenate Audios

**Description**: Join two audios into one by re-encoding through ffmpeg's `concat` filter.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `first` | file | Yes | Audio that appears first in the output |
| `second` | file | Yes | Audio that appears second in the output |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `audio` | audio | The concatenated result |

### 2. Overlay Single Audio

**Description**: Mix a single overlay (narration, sound effect, etc.) into a base audio.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `base` | file | Yes | - | Base audio |
| `overlay` | file | Yes | - | Overlay audio |
| `start_time` | duration | No | `2s` | Time the overlay first plays on the base's timeline |
| `gain` | float | No | `0.8` | Linear volume multiplier for the overlay |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `audio` | audio | Base audio with the overlay mixed in |

### 3. Overlay Multiple Audios

**Description**: Layer a narration and a sound effect on top of a base track, each with its own timing and gain.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base` | file | Yes | Base audio |
| `narration` | file | Yes | Narration overlay, plays from `1s` |
| `sfx` | file | Yes | Sound effect overlay, plays between `5s` and `7s` panned right |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `audio` | audio | Base audio with both overlays mixed in |

## Tips

- **Re-encoding is unavoidable**: Mixing operations run through ffmpeg's filter graph, which cannot operate on stream-copied inputs. Provide `encoding` if the defaults don't match your target output.
- **Placement broadcast**: A single `placement` object applies to every overlay. Use a list only when the overlays need different timing, gain, or pan.
- **Overlay simultaneity**: Unlike video overlays there is no z-order — every overlay plays at once and is summed into the base. Order in the `overlay` list does not affect the result.
- **Timing semantics**: `start_time` is measured on the base's timeline, so `start_time: 5s` delays the overlay by 5 seconds. `end_time` cuts the overlay at that absolute time along the delayed timeline.
- **Fade-out needs `end_time`**: Because a fade-out ends at `end_time`, omitting `end_time` disables `fade_out`. Set both when you want a tail fade.
- **Batch mode**: Passing a list of base audios runs one overlay operation per base and returns a list of outputs. The same overlay set is broadcast to every base unless you also parameterize per-base.
- **Streaming input**: Non-file audio sources (bytes, HTTP uploads) are spooled to temporary files before mixing so ffmpeg can seek them.

## Troubleshooting

### Common Issues

1. **ffmpeg not found**: Ensure ffmpeg is installed and available in your `PATH`.
2. **`'audios' must contain at least two entries for concat`**: Concat requires at least two inputs. Use `overlay` or another component for single-audio operations.
3. **`Input link ... parameters do not match` on concat**: The ffmpeg concat filter requires every input to share sample rate and channel layout. Pre-process inputs with a component like `audio-converter` to normalize them before concatenating.
4. **`overlay/placement cardinality mismatch`**: When `placement` is a list, its length must equal the number of overlays. A single placement object is broadcast to every overlay instead.
5. **Overlay is too quiet or too loud after mixing**: `amix` sums inputs without normalization here (`normalize=0`), so raw levels are preserved. Adjust each overlay's `gain` — or lower the base upstream — until the balance sounds right.
6. **Fade-out has no effect**: `fade_out` requires an `end_time` to anchor the fade tail. Set both.
7. **Format mismatch after concat**: The output format is taken from the action's `format` field (default: `wav`). Set `encoding.codec` explicitly when the default codec for that format doesn't match your target.
