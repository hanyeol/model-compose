# Video Processor Example

This example demonstrates the `video-processor` component, which applies per-frame transforms (resize, crop, pad, flip, rotate, speed, zoom) to a video using ffmpeg. Because every method installs an ffmpeg video filter, the video track is always re-encoded; the audio track is stream-copied by default so it stays lossless.

## Overview

This example exposes seven workflows built on the same `video-processor` component:

1. **Resize Video**: Rescale a video with `fit`, `fill`, or `stretch` semantics
2. **Crop Video**: Cut a rectangular region out of every frame
3. **Pad Video**: Add solid-color borders around a video
4. **Flip Video**: Mirror a video horizontally or vertically
5. **Rotate Video**: Rotate a video by an arbitrary angle, optionally expanding the canvas
6. **Change Speed**: Speed a video up or down while keeping the audio track in sync
7. **Zoom Animation**: Animate between two regions (zoom-in, zoom-out, or an arbitrary move) in a single pass

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- [ffmpeg](https://ffmpeg.org/) installed and available in your PATH

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/video-processor
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
   - Upload a video file and fill in the parameters
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Resize to 960x540 preserving aspect ratio inside the box
   model-compose run resize --input '{
     "video": "/path/to/input.mp4",
     "width": 960,
     "height": 540,
     "scale_mode": "fit"
   }'

   # Crop a 640x360 region starting at (100, 50)
   model-compose run crop --input '{
     "video": "/path/to/input.mp4",
     "x": 100,
     "y": 50,
     "width": 640,
     "height": 360
   }'

   # Add a 20px red border on every side
   model-compose run pad --input '{
     "video": "/path/to/input.mp4",
     "left": 20, "right": 20, "top": 20, "bottom": 20,
     "color": "red"
   }'

   # Flip vertically
   model-compose run flip --input '{
     "video": "/path/to/input.mp4",
     "direction": "vertical"
   }'

   # Rotate 90 degrees counter-clockwise and grow the canvas to fit
   model-compose run rotate --input '{
     "video": "/path/to/input.mp4",
     "angle": 90,
     "expand": true
   }'

   # Play at 1.5x speed with the audio track kept in sync (pitch preserved)
   model-compose run speed --input '{
     "video": "/path/to/input.mp4",
     "speed": 1.5
   }'

   # Zoom out: open on a 640x360 inner region and widen to the full frame over 0.6s
   model-compose run zoom --input '{
     "video": "/path/to/input.mp4",
     "from_x": 320, "from_y": 120, "from_width": 640, "from_height": 360,
     "duration": 0.6,
     "easing": "ease-out"
   }'

   # Zoom in: open on the full frame and tighten into a 640x360 region over 0.8s
   model-compose run zoom --input '{
     "video": "/path/to/input.mp4",
     "to_x": 320, "to_y": 120, "to_width": 640, "to_height": 360,
     "duration": 0.8,
     "easing": "ease-in"
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=resize" \
     -F "video=@/path/to/input.mp4" \
     -F "width=960" \
     -F "height=540" \
     -F "scale_mode=fit"
   ```

## Component Details

### Video Processor Component

- **Type**: `video-processor`
- **Driver**: `ffmpeg`
- **Purpose**: Apply per-frame transforms (resize, crop, pad, flip, rotate, speed, zoom) to a video via ffmpeg video filters. The video track is re-encoded; the audio track is stream-copied by default.

#### Common Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `method` | string | Yes | - | One of `resize`, `crop`, `pad`, `flip`, `rotate`, `speed`, `zoom` |
| `video` | video source | Yes | - | The input video (path, upload, or upstream video reference) |
| `encoding` | object | No | - | Output encoding overrides (`format`, `video.codec`, `video.bitrate`, etc.). When unset, the container follows the input format and the audio track is stream-copied |
| `batch_size` | integer | No | `1` | Number of input videos processed per batch when the input is a list/stream; the batch runs concurrently |

If no `encoding` is supplied, the container is inherited from the input format (falling back to `mp4`), the video codec is picked from the container's default (e.g. `libx264` for `mp4`, `libvpx-vp9` for `webm`), and the audio track is copied verbatim.

## Workflow Details

### 1. Resize Video

**Description**: Rescale a video to a target `(width, height)` box with configurable scaling behavior.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Source video file |
| `width` | integer | Yes | - | Target width in pixels |
| `height` | integer | Yes | - | Target height in pixels |
| `scale_mode` | select | No | `fit` | `fit` (letterbox to fit inside), `fill` (cover and center-crop), or `stretch` (ignore aspect ratio) |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The resized video |

### 2. Crop Video

**Description**: Extract a rectangular region from every frame.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Source video file |
| `x` | integer | No | `0` | X coordinate of the crop's top-left corner |
| `y` | integer | No | `0` | Y coordinate of the crop's top-left corner |
| `width` | integer | Yes | - | Crop width in pixels |
| `height` | integer | Yes | - | Crop height in pixels |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The cropped video |

### 3. Pad Video

**Description**: Add solid-color borders around a video without changing frame content.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Source video file |
| `left` | integer | No | `0` | Left padding in pixels |
| `right` | integer | No | `0` | Right padding in pixels |
| `top` | integer | No | `0` | Top padding in pixels |
| `bottom` | integer | No | `0` | Bottom padding in pixels |
| `color` | string | No | `black` | Border color. Accepts ffmpeg color names (`black`, `red`, `white`), hex strings (`#ff0000`, `#00ff00ff`), or RGBA tuples |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The padded video |

### 4. Flip Video

**Description**: Mirror the video along the requested axis.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Source video file |
| `direction` | select | No | `horizontal` | Flip axis: `horizontal` or `vertical` |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The flipped video |

### 5. Rotate Video

**Description**: Rotate every frame by `angle` degrees counter-clockwise.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Source video file |
| `angle` | number | Yes | - | Rotation angle in degrees, counter-clockwise |
| `expand` | boolean | No | `true` | When `true`, grow the canvas so the rotated frame fits with a transparent background; when `false`, keep the original frame size and crop the overflow |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The rotated video |

### 6. Change Speed

**Description**: Speed the video up or down. Video frames are re-timed via `setpts`, and the audio track is compressed/stretched with `atempo` in the same ratio so it stays in sync. `atempo` preserves the audio pitch; for speeds far outside `0.5..2.0` the driver chains multiple `atempo` stages automatically.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Source video file |
| `speed` | number | Yes | - | Playback speed multiplier (e.g., `2.0` for double speed, `0.5` for half) |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The time-scaled video with audio kept in sync |

### 7. Zoom Animation

**Description**: Animate between two regions of the input in a single ffmpeg pass. Both `from` and `to` default to the full input frame, so you specify one, the other, or both:

- **Zoom-out**: fill in the `from_*` fields, leave `to_*` empty. The clip opens on the inner region and widens to the full frame.
- **Zoom-in**: fill in the `to_*` fields, leave `from_*` empty. The clip opens on the full frame and tightens into the inner region.
- **Arbitrary move**: fill in both for a "crop-to-crop" push across subjects.

After the animation finishes, the output stays on the `to` framing for the rest of the clip. Driving this with a single `zoompan` pass keeps the move continuous (no visible stepping) and avoids per-step encoding.

Each region is **all four fields or none** — supplying `from_x` without `from_y`/`from_width`/`from_height` is rejected by schema validation (and similarly for `to`). At least one of `from` / `to` must be specified.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video` | file | Yes | - | Source video file |
| `from_x` / `from_y` / `from_width` / `from_height` | integer | No | *full input frame* | Starting region (in input pixels). Supply all four or none |
| `to_x` / `to_y` / `to_width` / `to_height` | integer | No | *full input frame* | Target region (in input pixels). Supply all four or none |
| `duration` | number | No | `0.6` | Animation length in seconds |
| `easing` | select | No | `linear` | `linear`, `constant-pixels`, `ease-in`, or `ease-out` |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `video` | video | The zoomed video. The output pixel aspect ratio is normalized (`setsar=1`), so clips concatenate cleanly even when sources had non-square SAR |

## Tips

- **Video is re-encoded, audio is not**: Filter graphs decode frames, so `-c:v copy` is impossible; the video track is always re-encoded. The audio track is `-c:a copy` unless you override it via `encoding.audio.codec`.
- **Output container**: Without an explicit `encoding.format`, the output container follows the input format (falling back to `mp4`). Supplying `encoding` lets you switch container (`mp4` → `webm`), codec (`libx264` → `libvpx-vp9`), bitrate, resolution, or fps in one shot.
- **Rotation direction**: `angle` is counter-clockwise degrees, matching `image-processor`'s `rotate`. Under the hood the ffmpeg `rotate` filter (which is clockwise radians) is negated for you.
- **Aspect-preserving resize with one axis**: Leave either `width` or `height` unset to auto-derive the missing dimension from the source aspect ratio.
- **Batch parallelism**: When the input is a list of videos, the batch runs its ffmpeg subprocesses concurrently. Use `batch_size` to bound how many videos are in flight at a time.
- **`zoom` is a single-pass animation**: Prefer `zoom` over chaining per-step crops when you need a continuous move; `zoompan` interpolates the region every output frame and emits one encode. The output always carries `setsar=1`, so clips concatenate cleanly across source resolutions.

## Troubleshooting

### Common Issues

1. **ffmpeg not found**: Ensure ffmpeg (and ffprobe) is installed and available in your `PATH`.
2. **Unsupported codec/container combo**: Overriding `encoding` may produce combinations ffmpeg cannot mux (e.g. `vp9` in `avi`). Pick a codec that matches the target container, or leave `encoding` unset to accept the container-default codec.
3. **Rotate crops the corners**: With `expand: false` the output is the same size as the input, so the rotated frame's corners are cropped away. Set `expand: true` to keep everything.
4. **Fit / fill vs stretch**: `fit` letterboxes (adds transparent padding to preserve aspect), `fill` covers and center-crops the overflow, `stretch` ignores aspect ratio and squashes the frame to the requested size.
