# Video Processor Example

This example demonstrates the `video-processor` component, which applies per-frame transforms (resize, crop, pad, flip, rotate) to a video using ffmpeg. Because every method installs an ffmpeg video filter, the video track is always re-encoded; the audio track is stream-copied by default so it stays lossless.

## Overview

This example exposes five workflows built on the same `video-processor` component:

1. **Resize Video**: Rescale a video with `fit`, `fill`, or `stretch` semantics
2. **Crop Video**: Cut a rectangular region out of every frame
3. **Pad Video**: Add solid-color borders around a video
4. **Flip Video**: Mirror a video horizontally or vertically
5. **Rotate Video**: Rotate a video by an arbitrary angle, optionally expanding the canvas

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
- **Purpose**: Apply per-frame transforms (resize, crop, pad, flip, rotate) to a video via ffmpeg video filters. The video track is re-encoded; the audio track is stream-copied by default.

#### Common Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `method` | string | Yes | - | One of `resize`, `crop`, `pad`, `flip`, `rotate` |
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

## Tips

- **Video is re-encoded, audio is not**: Filter graphs decode frames, so `-c:v copy` is impossible; the video track is always re-encoded. The audio track is `-c:a copy` unless you override it via `encoding.audio.codec`.
- **Output container**: Without an explicit `encoding.format`, the output container follows the input format (falling back to `mp4`). Supplying `encoding` lets you switch container (`mp4` → `webm`), codec (`libx264` → `libvpx-vp9`), bitrate, resolution, or fps in one shot.
- **Rotation direction**: `angle` is counter-clockwise degrees, matching `image-processor`'s `rotate`. Under the hood the ffmpeg `rotate` filter (which is clockwise radians) is negated for you.
- **Aspect-preserving resize with one axis**: Leave either `width` or `height` unset to auto-derive the missing dimension from the source aspect ratio.
- **Batch parallelism**: When the input is a list of videos, the batch runs its ffmpeg subprocesses concurrently. Use `batch_size` to bound how many videos are in flight at a time.

## Troubleshooting

### Common Issues

1. **ffmpeg not found**: Ensure ffmpeg (and ffprobe) is installed and available in your `PATH`.
2. **Unsupported codec/container combo**: Overriding `encoding` may produce combinations ffmpeg cannot mux (e.g. `vp9` in `avi`). Pick a codec that matches the target container, or leave `encoding` unset to accept the container-default codec.
3. **Rotate crops the corners**: With `expand: false` the output is the same size as the input, so the rotated frame's corners are cropped away. Set `expand: true` to keep everything.
4. **Fit / fill vs stretch**: `fit` letterboxes (adds transparent padding to preserve aspect), `fill` covers and center-crops the overflow, `stretch` ignores aspect ratio and squashes the frame to the requested size.
