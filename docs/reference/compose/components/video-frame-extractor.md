# Video Frame Extractor Component

The video frame extractor component decodes a video and yields individual frames as PIL images, with optional frame-interval sampling and time-range selection. It supports two backends — FFmpeg (default) and OpenCV.

## Basic Configuration

```yaml
component:
  type: video-frame-extractor
  driver: ffmpeg
  action:
    video: ${input.video}
    frame_interval: 2
    start_time: 00:00:10
    end_time: 00:01:00
    max_frame_count: 100
    output: ${result.frames}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-frame-extractor` |
| `driver` | string | `ffmpeg` | Frame extraction backend: `ffmpeg`, `opencv` |
| `actions` | array | `[]` | List of frame extraction actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | any | **required** | Video source: file path, variable reference, or upload stream |
| `frame_interval` | integer | `1` | Frame interval. `1` = every frame, `2` = every 2nd frame, etc. |
| `start_time` | string | `null` | Start time for extraction (e.g., `00:01:00`, `60s`) |
| `end_time` | string | `null` | End time for extraction (e.g., `00:05:00`, `300s`) |
| `max_frame_count` | integer | `null` | Maximum number of frames to extract. `null` = no limit |
| `output` | string | `null` | Output template applied to the collected result |

## Supported Drivers

### FFmpeg

Frame extraction using FFmpeg's `image2pipe` PNG output combined with the `showinfo` filter for per-frame timestamps. Requires the `ffmpeg` binary on the system but no extra Python dependencies.

```yaml
component:
  type: video-frame-extractor
  driver: ffmpeg
  action:
    video: ${input.video}
    frame_interval: 1
    output: ${result.frames}
```

**Requires:** `ffmpeg` binary on the system path

### OpenCV

Frame extraction using OpenCV's `VideoCapture`. Handles standard containers (mp4, mov, avi, mkv, webm) with codecs supported by the OpenCV build.

```yaml
component:
  type: video-frame-extractor
  driver: opencv
  action:
    video: ${input.video}
    frame_interval: 1
    output: ${result.frames}
```

**Auto-installed dependency:** `opencv-python`

## Output Format

The component decodes all matching frames and returns them together:

```python
{
  "frames": [
    {
      "frame": 0,
      "timestamp": 0.0,
      "image": <PIL.Image.Image>
    },
    {
      "frame": 1,
      "timestamp": 0.1,
      "image": <PIL.Image.Image>
    }
  ],
  "frame_count": 2
}
```

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `frames` | array | Extracted frame entries in order |
| `frames[].frame` | integer | Source frame index in the original video |
| `frames[].timestamp` | float | Frame timestamp in seconds |
| `frames[].image` | PIL.Image | Decoded RGB image |
| `frame_count` | integer | Total number of extracted frames |

## Multiple Actions Configuration

```yaml
component:
  type: video-frame-extractor
  driver: ffmpeg
  actions:
    - id: thumbnails
      video: ${input.video}
      max_frame_count: 10
      output: ${result.frames}

    - id: dense
      video: ${input.video}
      frame_interval: 1
      output: ${result.frames}

    - id: segment
      video: ${input.video}
      start_time: ${input.start_time}
      end_time: ${input.end_time}
      frame_interval: ${input.interval as integer | 1}
      output: ${result.frames}
```

## Integration with Workflows

### Extract Frames for Face Detection

```yaml
workflows:
  - id: detect-faces-in-video
    jobs:
      - id: extract
        component: extractor
        output:
          frames: ${output as json}

      - id: detect
        component: face-detector
        input:
          image: ${jobs.extract.output.frames[0].image}
        depends_on: [extract]

components:
  - id: extractor
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}
      frame_interval: 30
      max_frame_count: 60

  - id: face-detector
    type: face-detector
    driver: mediapipe
    action:
      image: ${input.image}
      model: full-range
```

### Sample Frames for Thumbnail Selection

```yaml
workflows:
  - id: pick-thumbnails
    job:
      component: extractor
      output:
        thumbnails: ${output as json}

components:
  - id: extractor
    type: video-frame-extractor
    driver: ffmpeg
    action:
      video: ${input.video}
      max_frame_count: 5
      output: ${result.frames}
```

## Driver Comparison

| Feature | FFmpeg | OpenCV |
|---------|--------|--------|
| Extraction method | `image2pipe` PNG + `showinfo` | `VideoCapture` + per-frame `read` |
| Container support | Anything FFmpeg handles | Anything the OpenCV build supports |
| Time-range seek | Fast (`-ss`/`-to`) | Frame-index based on FPS |
| Dependencies | FFmpeg binary | `opencv-python` |
| Best for | Wide codec coverage, fast seek | Pure Python install, programmatic frame indexing |

## Best Practices

1. **Use `frame_interval` to reduce memory pressure**: sampling every Nth frame is far cheaper than decoding every frame and discarding most.
2. **Always cap with `max_frame_count` for unknown videos**: long videos can produce thousands of frames; set an explicit safety limit.
3. **Combine `start_time` / `end_time` for long videos**: decode only the segment you need rather than scanning the entire file.
4. **Pass frames straight to image components**: the `image` field is a PIL Image, ready for `image-processor`, `face-detector`, or other image-consuming components without conversion.
