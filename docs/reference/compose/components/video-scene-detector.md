# Video Scene Detector Component

The video scene detector component analyzes video files to detect scene changes and transitions. It supports multiple detection backends (drivers) including PySceneDetect and FFmpeg.

> **Looking for TransNetV2?** The deep-learning TransNetV2 detector is now provided as the `shot-boundary-detection` model task. See [model.md](model.md#shot-boundary-detection) for its configuration.

## Basic Configuration

```yaml
component:
  type: video-scene-detector
  driver: pyscenedetect
  action:
    video: ${input.video as file}
    detector: adaptive
    threshold: 27.0
    output: ${result as json}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-scene-detector` |
| `driver` | string | `pyscenedetect` | Detection backend: `pyscenedetect`, `ffmpeg` |
| `actions` | array | `[]` | List of scene detection actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | string | **required** | Video file path or `${input.video as file}` |
| `detector` | string | `adaptive` | Detector type (pyscenedetect only): `adaptive`, `content`, `threshold`, `histogram`, `hash` |
| `threshold` | number | varies | Detection sensitivity threshold |
| `start_time` | string | `null` | Start time for analysis (e.g., `00:01:00`) |
| `end_time` | string | `null` | End time for analysis (e.g., `00:05:00`) |
| `output` | string | `null` | Output template |

## Supported Drivers

### PySceneDetect

Python-based scene detection with multiple detector algorithms:

```yaml
component:
  type: video-scene-detector
  driver: pyscenedetect
  action:
    video: ${input.video as file}
    detector: adaptive
    threshold: 27.0
    output: ${result as json}
```

**Auto-installed dependency:** `scenedetect[opencv]`

#### Detector Types

| Detector | Description | Default Threshold |
|----------|-------------|-------------------|
| `adaptive` | Adaptive content detection based on rolling average (recommended) | 27.0 |
| `content` | Content-aware detection using frame-by-frame HSV difference | 27.0 |
| `threshold` | Fade-in/fade-out detection based on average pixel intensity | 12.0 |
| `histogram` | HSV histogram comparison between frames | 0.05 |
| `hash` | Perceptual hash-based detection for similar frame matching | 0.395 |

### FFmpeg

Scene detection using FFmpeg's built-in scene change filter. No additional Python dependencies required — only FFmpeg needs to be installed on the system.

```yaml
component:
  type: video-scene-detector
  driver: ffmpeg
  action:
    video: ${input.video as file}
    threshold: 0.3
    output: ${result as json}
```

**Threshold range:** `0.0` to `1.0`
- `0.1` — Very sensitive (detects minor changes)
- `0.3` — Default (balanced detection)
- `0.5` — Less sensitive (major scene changes only)

### TransNetV2 (moved)

The deep-learning TransNetV2 detector has moved to the `shot-boundary-detection` model task. Use `type: model` with `task: shot-boundary-detection` and `family: transnetv2` — see [model.md](model.md#shot-boundary-detection).

## Output Format

All drivers return a flat list of detected scenes. In streaming mode each scene is emitted as a single chunk.

```json
[
  {
    "index": 0,
    "start_time": "00:00:00.000",
    "end_time": "00:00:12.345",
    "start_frame": 0,
    "end_frame": 370,
    "duration": "00:00:12.345"
  },
  {
    "index": 1,
    "start_time": "00:00:12.345",
    "end_time": "00:00:28.678",
    "start_frame": 370,
    "end_frame": 860,
    "duration": "00:00:16.333"
  }
]
```

### Scene Fields

| Field | Type | Description |
|-------|------|-------------|
| `index` | integer | Scene index (0-based) |
| `start_time` | string | Scene start timecode (HH:MM:SS.mmm) |
| `end_time` | string | Scene end timecode (HH:MM:SS.mmm) |
| `start_frame` | integer | Scene start frame number |
| `end_frame` | integer | Scene end frame number |
| `duration` | string | Scene duration timecode |

## Multiple Actions Configuration

Define multiple detection configurations:

```yaml
component:
  type: video-scene-detector
  driver: pyscenedetect
  actions:
    - id: adaptive
      video: ${input.video as file}
      detector: adaptive
      threshold: ${input.threshold as number | 27.0}
      output: ${result as json}

    - id: content
      video: ${input.video as file}
      detector: content
      threshold: ${input.threshold as number | 27.0}
      output: ${result as json}

    - id: with-range
      video: ${input.video as file}
      detector: ${input.detector | adaptive}
      threshold: ${input.threshold as number}
      start_time: ${input.start_time}
      end_time: ${input.end_time}
      output: ${result as json}
```

## Integration with Workflows

### Basic Scene Detection

```yaml
workflows:
  - id: detect-scenes
    job:
      component: scene-detector
      output:
        scenes: ${output as json}

components:
  - id: scene-detector
    type: video-scene-detector
    driver: pyscenedetect
    action:
      video: ${input.video as file}
      detector: adaptive
      output: ${result as json}
```

### Scene Detection with Post-Processing

```yaml
workflows:
  - id: analyze-video
    jobs:
      - id: detect
        component: scene-detector
        output:
          scenes: ${output as json}

      - id: summarize
        component: chat-model
        input:
          messages:
            - role: user
              content: |
                Analyze the following scene data and provide a summary:
                ${jobs.detect.output}
        depends_on: [detect]

components:
  - id: scene-detector
    type: video-scene-detector
    driver: pyscenedetect
    action:
      video: ${input.video as file}
      detector: adaptive
      output: ${result as json}

  - id: chat-model
    type: http-client
    action:
      endpoint: https://api.openai.com/v1/chat/completions
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages: ${input.messages}
      output: ${response.choices[0].message.content}
```

## Driver Comparison

| Feature | PySceneDetect | FFmpeg |
|---------|--------------|--------|
| Detection method | Classical CV | Scene filter |
| Detector variety | 5 types | 1 type |
| Time range support | Yes | Yes |
| Dependencies | scenedetect[opencv] | FFmpeg binary |
| GPU acceleration | No | No |
| Best for | General use | Lightweight/no Python deps |

For deep-learning-based cut detection (higher accuracy on modern edited content, GPU-accelerated), use the [`shot-boundary-detection`](model.md#shot-boundary-detection) model task instead.

## Best Practices

1. **Driver Selection**: Use `pyscenedetect` for most cases; `ffmpeg` when no Python deps are desired. For deep-learning accuracy, use the `shot-boundary-detection` model task.
2. **Threshold Tuning**: Start with defaults and adjust based on video content — lower thresholds detect more scenes
3. **Time Ranges**: Use `start_time`/`end_time` to analyze specific segments of long videos
4. **Detector Choice**: `adaptive` works well for most content; use `threshold` for fade transitions
