# Video Processor Component

The video processor component applies per-frame video transforms (resize, crop, pad, flip, rotate, speed) via FFmpeg video filters. The video track is always re-encoded (filter graphs decode frames, so `-c:v copy` is not valid); the audio track is stream-copied by default and re-encoded only when the method requires it (e.g., `speed` uses `atempo` on the audio track).

## Basic Configuration

```yaml
component:
  type: video-processor
  action:
    method: speed
    video: ${input.video as video}
    speed: 1.5
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-processor` |
| `driver` | string | `ffmpeg` | Processing backend. Currently only `ffmpeg` is supported. |
| `actions` | array | `[]` | List of video processing actions |

### Common Action Configuration

All video processor actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Processing method: `resize`, `crop`, `pad`, `flip`, `rotate`, `speed` |
| `video` | string / array | **required** | Input video (a file path, upload, or upstream video reference — single or list) |
| `encoding` | object | `null` | Output encoding overrides (`format`, `video.codec`, `video.bitrate`, `audio.codec`, `audio.bitrate`, etc.). When unset, the container follows the input format and the audio track is stream-copied (unless the method requires an audio re-encode). |
| `batch_size` | integer / string | `null` | Number of input videos processed per batch |
| `output` | any | `null` | Output variable mapping |

When `encoding` is unset, the output container is inherited from the input format (fallback `mp4`), the video codec is picked from the container's default (e.g., `libx264` for `mp4`, `libvpx-vp9` for `webm`), and the audio track is `-c:a copy` unless a method installs an audio filter.

## Video Processing Methods

### Resize

Rescale the video with configurable scaling semantics.

```yaml
component:
  type: video-processor
  action:
    method: resize
    video: ${input.video as video}
    width: 1280
    height: 720
    scale_mode: fit
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `width` | integer | `null` | Target width in pixels (at least one of `width`/`height` required) |
| `height` | integer | `null` | Target height in pixels |
| `scale_mode` | string | `fit` | `fit` (letterbox to fit inside), `fill` (cover and centre-crop), or `stretch` (ignore aspect ratio) |

**Scale modes:**

- **`fit`**: Maintain aspect ratio, fit inside target dimensions with transparent padding
- **`fill`**: Maintain aspect ratio, cover target dimensions and centre-crop the overflow
- **`stretch`**: Ignore aspect ratio and squash the frame to exact dimensions

Leaving one axis unset (e.g., only `width`) auto-derives the other from the source aspect ratio.

### Crop

Extract a rectangular region from every frame.

```yaml
component:
  type: video-processor
  action:
    method: crop
    video: ${input.video as video}
    x: 100
    y: 50
    width: 1280
    height: 720
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | integer | **required** | X coordinate of the crop's top-left corner |
| `y` | integer | **required** | Y coordinate of the crop's top-left corner |
| `width` | integer | **required** | Crop width in pixels |
| `height` | integer | **required** | Crop height in pixels |

### Pad

Add solid-color borders around a video without changing frame content.

```yaml
component:
  type: video-processor
  action:
    method: pad
    video: ${input.video as video}
    left: 20
    right: 20
    top: 20
    bottom: 20
    color: "red"
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `left` | integer | `0` | Left padding in pixels |
| `right` | integer | `0` | Right padding in pixels |
| `top` | integer | `0` | Top padding in pixels |
| `bottom` | integer | `0` | Bottom padding in pixels |
| `color` | string / RGBA | `"#00000000"` | Border color. Accepts FFmpeg color names (`black`, `red`, `white`), hex strings (`#ff0000`, `#00ff00ff`), or RGBA tuples |

### Flip

Mirror the video along the requested axis.

```yaml
component:
  type: video-processor
  action:
    method: flip
    video: ${input.video as video}
    direction: horizontal
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `direction` | string | **required** | Flip axis: `horizontal` or `vertical` |

### Rotate

Rotate every frame by `angle` degrees counter-clockwise (matching `image-processor`'s convention).

```yaml
component:
  type: video-processor
  action:
    method: rotate
    video: ${input.video as video}
    angle: 90
    expand: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `angle` | number | **required** | Rotation angle in degrees, counter-clockwise |
| `expand` | boolean | `true` | When `true`, grow the canvas so the rotated frame fits with a transparent background; when `false`, keep the original frame size and crop the overflow |

Internally the FFmpeg `rotate` filter (clockwise radians) is negated to match the counter-clockwise degree convention.

### Speed

Speed the video up or down while keeping the audio track in sync. Video frames are re-timed via `setpts` (`1/speed * PTS`), and the audio track is compressed/stretched with `atempo` in the same ratio so pitch is preserved.

```yaml
component:
  type: video-processor
  action:
    method: speed
    video: ${input.video as video}
    speed: 1.5
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `speed` | number | **required** | Playback speed multiplier (e.g., `2.0` for double speed, `0.5` for half) |

**Audio behavior**: `speed` installs an `-af "atempo=..."` filter, which forces the audio track to be re-encoded (`-c:a copy` becomes invalid). The audio codec defaults to the container's default (e.g., `aac` for `mp4`) unless overridden via `encoding.audio.codec`. `atempo` preserves pitch; for speeds far outside `0.5..2.0` the driver chains multiple `atempo` stages automatically to keep A/V in sync.

## Multiple Actions Configuration

Define multiple video processing actions on the same component:

```yaml
component:
  type: video-processor
  actions:
    - id: downscale
      method: resize
      video: ${input.video as video}
      width: 1280
      scale_mode: fit
      output: ${output}

    - id: speed-up
      method: speed
      video: ${input.video as video}
      speed: 2.0
      output: ${output}

    - id: rotate-portrait
      method: rotate
      video: ${input.video as video}
      angle: 90
      expand: true
      output: ${output}
```

## Usage Examples

### Prepare Clip for Social Media

Downscale to 720p, speed to 1.25x, and re-encode to a target codec:

```yaml
workflows:
  - id: prepare-clip
    jobs:
      - id: downscale
        component: video
        action: downscale-720
        input:
          video: ${input.video as video}
        output:
          scaled: ${output}

      - id: speed
        component: video
        action: speed-125
        input:
          video: ${jobs.downscale.output.scaled}
        depends_on: [ downscale ]

components:
  - id: video
    type: video-processor
    actions:
      - id: downscale-720
        method: resize
        video: ${input.video}
        width: 1280
        height: 720
        scale_mode: fit
        output: ${output}

      - id: speed-125
        method: speed
        video: ${input.video}
        speed: 1.25
        output: ${output}
```

### Timelapse

Speed a long recording up by 8x:

```yaml
component:
  type: video-processor
  action:
    method: speed
    video: ${input.footage as video}
    speed: 8.0
```

The driver chains `atempo=2.0,atempo=2.0,atempo=2.0` on the audio side to keep the (very fast) audio synced.

### Portrait Rotate

Rotate a landscape clip 90° into portrait, expanding the canvas:

```yaml
component:
  type: video-processor
  action:
    method: rotate
    video: ${input.video as video}
    angle: 90
    expand: true
```

### Crop and Watermark-Ready Padding

Crop a region of interest, then pad to a fixed aspect ratio:

```yaml
workflows:
  - id: crop-and-pad
    jobs:
      - id: crop
        component: video
        action: crop-region
        input:
          video: ${input.video as video}
        output:
          cropped: ${output}

      - id: pad
        component: video
        action: pad-for-watermark
        input:
          video: ${jobs.crop.output.cropped}
        depends_on: [ crop ]

components:
  - id: video
    type: video-processor
    actions:
      - id: crop-region
        method: crop
        video: ${input.video}
        x: 200
        y: 100
        width: 1280
        height: 720
        output: ${output}

      - id: pad-for-watermark
        method: pad
        video: ${input.video}
        bottom: 120
        color: "black"
        output: ${output}
```

## Variable Interpolation

All method parameters accept `${input....}` expressions:

```yaml
component:
  type: video-processor
  action:
    method: resize
    video: ${input.video as video}
    width: ${input.width as integer | 1280}
    height: ${input.height as integer | 720}
    scale_mode: ${input.scale_mode as select/fit,fill,stretch | fit}
```

## Encoding Overrides

Every method accepts an `encoding` object to override the output container/codec:

```yaml
component:
  type: video-processor
  action:
    method: speed
    video: ${input.video as video}
    speed: 1.5
    encoding:
      format: mp4
      video:
        codec: libx264
        quality: 20        # CRF
      audio:
        codec: aac
        bitrate: 192k
```

When `encoding.format` is unset, the container follows the input format (falling back to `mp4`).

## Best Practices

1. **Video is re-encoded, audio is passthrough by default**: Filter graphs decode frames, so the video track is always re-encoded. The audio track uses `-c:a copy` unless a method (like `speed`) installs an audio filter or you override `encoding.audio.codec`.
2. **Container / codec compatibility**: Overriding `encoding` can produce combinations FFmpeg cannot mux (e.g., `vp9` in `avi`). Pick a codec that matches the target container, or leave `encoding` unset to accept the container-default codec.
3. **Rotate direction**: `angle` is counter-clockwise degrees, matching `image-processor`'s `rotate`. Under the hood the FFmpeg `rotate` filter (clockwise radians) is negated for you.
4. **Aspect-preserving resize with one axis**: Leave either `width` or `height` unset to auto-derive the missing dimension from the source aspect ratio.
5. **Batch parallelism**: When the input is a list of videos, the batch runs its FFmpeg subprocesses concurrently. Use `batch_size` to bound how many videos are in flight at a time.
6. **`speed` for A/V-synced timelapse/slowmo**: `atempo` chains automatically for speeds outside `0.5..2.0`, so 8× or 0.1× still produce correctly synced audio without extra configuration.

## Troubleshooting

1. **`ffmpeg` not found**: Ensure `ffmpeg` (and `ffprobe`) is installed and available on `PATH`.
2. **Unsupported codec/container combo**: Overriding `encoding` may produce combinations FFmpeg cannot mux. Pick a codec matching the container or leave `encoding` unset.
3. **Rotate crops the corners**: With `expand: false` the output is the same size as the input, so rotated frame corners are cropped. Set `expand: true` to keep everything.
4. **`fit` / `fill` vs `stretch`**: `fit` letterboxes (adds transparent padding to preserve aspect), `fill` covers and centre-crops the overflow, `stretch` ignores aspect ratio and distorts.
5. **`speed` audio pitch changed unexpectedly**: `atempo` should preserve pitch — if it doesn't, check that `encoding.audio.codec` isn't set to something that resamples in-place. Overriding `encoding.audio` is optional; leave it unset unless you have a specific reason.
