# Video Mixer Example

This example demonstrates the `video-mixer` component, which composites multiple videos into a single output using ffmpeg. Two mixing methods are covered:

- **concat**: join videos end-to-end into one longer video
- **overlay**: composite one or more videos on top of a base video (watermarks, picture-in-picture, side-by-side layouts, etc.)

## Overview

This example exposes three workflows built on the same `video-mixer` component:

1. **Concatenate Videos**: Stitch a list of videos into a single output
2. **Overlay Single Video**: Composite one overlay (watermark / PIP) onto a base video
3. **Overlay Multiple Videos**: Stack several overlays on a base video, each with its own placement

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- [ffmpeg](https://ffmpeg.org/) installed and available in your PATH

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/video-mixer
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
   - Upload the required video files and set any placement fields
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Concatenate two clips into one video
   model-compose run concat --input '{
     "first": "/path/to/intro.mp4",
     "second": "/path/to/main.mp4"
   }'

   # Composite a picture-in-picture onto a base video
   model-compose run overlay-single --input '{
     "base": "/path/to/lecture.mp4",
     "overlay": "/path/to/webcam.mp4",
     "x": 20,
     "y": 20,
     "width": 320
   }'

   # Stack two overlays on a base video, each with a distinct placement
   model-compose run overlay-multiple --input '{
     "base": "/path/to/main.mp4",
     "overlay_a": "/path/to/left.mp4",
     "overlay_b": "/path/to/right.mp4"
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=overlay-single" \
     -F "base=@/path/to/lecture.mp4" \
     -F "overlay=@/path/to/webcam.mp4" \
     -F "x=20" \
     -F "y=20" \
     -F "width=320"
   ```

## Component Details

### Video Mixer Component

- **Type**: `video-mixer`
- **Driver**: `ffmpeg`
- **Purpose**: Combine multiple videos into a single output using ffmpeg filters (`concat` for join, `overlay` for composite).

Videos are re-encoded during mixing because ffmpeg filter graphs cannot operate on stream-copied inputs. The `encoding` field controls the output container/codecs; if omitted, sensible defaults are picked per format (mp4 → libx264 + aac, webm → libvpx-vp9 + libopus, ...).

### Concat Method

Joins videos end-to-end using ffmpeg's `concat` filter. All inputs must share the same resolution, SAR, pixel format, framerate, audio sample rate, and channel layout — the concat filter fails with `Input link ... parameters do not match` when they don't. Normalize the inputs upstream (for example with the `video-converter` component) before feeding them into `concat`.

Re-encoding via the `encoding` field controls the output stream only; it does not reconcile mismatched inputs. Both video and audio tracks are joined; inputs without audio contribute silence.

#### Key Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `videos` | list of video sources | Yes | - | Videos to concatenate, in order (minimum 2) |
| `crossfade` | duration | No | - | Reserved for future support; currently not implemented |
| `encoding` | object | No | mp4 defaults | Output container/codecs |
| `batch_size` | integer | No | `1` | Number of input *sets* processed per batch when `videos` is a list of lists or a stream |
| `streaming` | boolean | No | `false` | Emit the output as a byte stream instead of a temporary file |

### Overlay Method

Composites one or more overlay videos on top of a base video. Overlays are stacked in list order — the first overlay lands on the base, the second on that result, and so on — so higher-index overlays appear on top.

#### Key Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `video` | video source or list | Yes | - | Base video (a list turns on batch mode: one output per base) |
| `overlay` | string or list of strings | Yes | - | Overlay video(s). A single string is auto-wrapped into a one-element list |
| `placement` | object or list of objects | No | one default placement | One placement per overlay. A single object broadcasts to all overlays; a list matches by position |
| `audio_mode` | `base` \| `overlay` \| `mix` \| `none` | No | `base` | Which audio track(s) the output carries |
| `duration_mode` | `base` \| `longest` \| `shortest` | No | `base` | How long the output runs relative to the base and overlays |
| `encoding` | object | No | mp4 defaults | Output container/codecs |
| `batch_size` | integer | No | `1` | Number of base videos processed per batch when `video` is a list/stream |
| `streaming` | boolean | No | `false` | Emit the output as a byte stream instead of a temporary file |

#### Placement Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | integer | `0` | X coordinate on the base video where the overlay is placed |
| `y` | integer | `0` | Y coordinate on the base video where the overlay is placed |
| `width` | integer | - | Resize the overlay to this width in pixels (aspect-preserving when only one dimension is set) |
| `height` | integer | - | Resize the overlay to this height in pixels |
| `anchor` | `top-left` \| `top-center` \| `top-right` \| `center-left` \| `center` \| `center-right` \| `bottom-left` \| `bottom-center` \| `bottom-right` | `top-left` | Point of the overlay aligned at `(x, y)` |
| `opacity` | float 0..1 | `1.0` | Alpha multiplier |
| `start` | duration | - | Time the overlay appears at (`0s` by default) |
| `end` | duration | - | Time the overlay disappears at (runs to the end of the base by default) |

`start`/`end` accept:
- Numbers (seconds): `10`, `10.5`
- Duration strings: `"10s"`, `"1m"`, `"250ms"`
- Timecodes: `"00:00:10"`, `"01:23:45"`

#### Audio Policy

- **base**: keep only the base video's audio track (typical for watermarks / PIP)
- **overlay**: keep only the overlay's audio track(s); with multiple overlays their audio is mixed
- **mix**: mix the base and all overlays' audio tracks
- **none**: strip audio from the output

#### Duration Policy

- **base** (default): the output stops when the base video ends. Overlays that end earlier disappear; overlays that outlast the base are cut off.
- **longest**: the output runs until the last stream ends. The base is extended past its own end by cloning its final frame (`tpad`) so the overlay filter can keep compositing.
- **shortest**: the output stops as soon as any input (base or overlay) ends. Useful when overlays need to gate the total duration.

`base` runs one `ffprobe` on the base to cap the output length; `longest` probes every input to compute the pad length; `shortest` doesn't probe.

## Workflow Details

### 1. Concatenate Videos

**Description**: Join two videos into one by re-encoding through ffmpeg's `concat` filter.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `first` | file | Yes | Video that appears first in the output |
| `second` | file | Yes | Video that appears second in the output |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The concatenated result |

### 2. Overlay Single Video

**Description**: Place a single overlay (watermark, picture-in-picture, etc.) on top of a base video.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `base` | file | Yes | - | Base video |
| `overlay` | file | Yes | - | Overlay video |
| `x` | integer | No | `20` | X coordinate on the base video |
| `y` | integer | No | `20` | Y coordinate on the base video |
| `width` | integer | No | `320` | Resize the overlay to this width |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | Base video with the overlay composited on top |

### 3. Overlay Multiple Videos

**Description**: Composite two overlays on top of a base video, each with its own placement. Overlays are stacked in list order.

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `base` | file | Yes | Base video |
| `overlay_a` | file | Yes | First overlay (rendered below `overlay_b` if they intersect) |
| `overlay_b` | file | Yes | Second overlay (rendered above `overlay_a` if they intersect) |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | Base video with both overlays composited on top |

## Tips

- **Re-encoding is unavoidable**: Mixing operations run through ffmpeg's filter graph, which cannot operate on stream-copied inputs. Provide `encoding` if the defaults don't match your target container.
- **Placement broadcast**: A single `placement` object applies to every overlay. Use a list only when the overlays need different coordinates, sizes, or timing.
- **Overlay stacking**: The first overlay in the list is composited first, so later overlays appear on top when their regions overlap. Order the list from bottom to top.
- **Anchor semantics**: `anchor` shifts the overlay relative to `(x, y)`. For example, `anchor: center` places the *center* of the overlay at `(x, y)` instead of the top-left corner.
- **Time-gated overlays**: `start`/`end` make an overlay visible only within a time window — useful for lower-thirds that appear for a few seconds or watermarks that fade in later.
- **Batch mode**: Passing a list of base videos runs one overlay operation per base and returns a list of outputs. The same overlay set is broadcast to every base unless you also parameterize per-base.
- **Streaming input**: Non-file video sources (bytes, HTTP uploads) are spooled to temporary files before mixing so ffmpeg can seek them.

## Troubleshooting

### Common Issues

1. **ffmpeg not found**: Ensure ffmpeg is installed and available in your `PATH`.
2. **`'videos' must contain at least two entries for concat`**: Concat requires at least two inputs. Use `overlay` or another component for single-video operations.
3. **`Input link ... parameters do not match` on concat**: The ffmpeg concat filter requires every input to share resolution, SAR, pixel format, framerate, audio sample rate, and channel layout. Pre-process inputs with a component like `video-converter` to normalize them before concatenating.
4. **`overlay/placement cardinality mismatch`**: When `placement` is a list, its length must equal the number of overlays. A single placement object is broadcast to every overlay instead.
5. **Wrong z-order in overlay-multiple**: Overlays are stacked in list order (first is drawn first, last appears on top). Reorder the list to change stacking.
6. **Silent output when using `audio_mode: overlay`**: The overlay video may lack an audio track. Switch to `audio_mode: base` or `audio_mode: mix` if the base has audio you want to keep.
7. **Format mismatch after concat**: The output format is taken from `encoding.format` (default: `mp4`). If inputs have exotic codecs, set `encoding.video.codec` / `encoding.audio.codec` explicitly.
