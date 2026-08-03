# Video Clipper Component

The video clipper component extracts one or more time ranges out of a video file, optionally concatenating the extracted spans into a single output. Clipping is performed by FFmpeg using stream copy (`-c copy`), so the operation is fast and lossless (no re-encoding).

## Basic Configuration

```yaml
component:
  type: video-clipper
  driver: ffmpeg
  action:
    video: ${input.video as video}
    span:
      start_time: ${input.start_time | 0s}
      end_time: ${input.end_time | 10s}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `video-clipper` |
| `driver` | string | `ffmpeg` | Clipping backend driver. Currently only `ffmpeg`. |
| `actions` | array | `[]` | List of clipping actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `video` | string \| string[] | **required** | Video source(s) — file path, URL, or interpolated variable (e.g. `${input.video as video}`) |
| `span` | object \| object[] \| string | **required** | One or more time spans to clip out of each video source. A single span object yields a single clip; a list yields one clip per span. |
| `merge` | boolean \| string | `false` | If true, concatenate all clips per source into a single video; otherwise return a list of clips. |
| `batch_size` | integer \| string | `null` | Number of input sources per batch. When unset, all sources are processed together. |

### Span Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `start_time` | string \| number | **required** | Clip start time. Accepts timecodes (`"00:00:10"`), duration strings (`"10s"`, `"1m30s"`), or seconds as a number (`10.5`). |
| `end_time` | string \| number | **required** | Clip end time. Same formats as `start_time`. |

## Supported Drivers

### FFmpeg

Uses FFmpeg's stream-copy mode to slice the input without re-encoding. Only FFmpeg needs to be installed on the system; no additional Python dependencies are required.

```yaml
component:
  type: video-clipper
  driver: ffmpeg
  action:
    video: ${input.video as video}
    span:
      start_time: "00:00:10"
      end_time: "00:00:25"
```

**Requires:** `ffmpeg` binary on `PATH`.

> **Note on keyframes**: Because clips are cut without re-encoding, cut points snap to the nearest preceding keyframe. If frame-accurate cuts are required, re-encode the clips with the `video-encoder` component after clipping.

## Output Format

Behavior depends on `span` and `merge`:

| `span` | `merge` | Output per source |
|--------|---------|-------------------|
| Single object | any | A single video clip |
| List of objects | `false` | A list of video clips (one per span) |
| List of objects | `true` | A single video clip (all spans concatenated) |

When multiple video sources are supplied via `video: [...]`, results are returned as a list of the above per source.

## Multiple Actions Configuration

Define multiple clipping actions on the same component:

```yaml
component:
  type: video-clipper
  actions:
    - id: clip-single
      video: ${input.video as video}
      span:
        start_time: ${input.start_time | 0s}
        end_time: ${input.end_time | 10s}

    - id: clip-multiple
      video: ${input.video as video}
      span: ${input.spans as json}

    - id: clip-and-merge
      video: ${input.video as video}
      span: ${input.spans as json}
      merge: true
```

## Integration with Workflows

### Single-Span Clip

```yaml
workflows:
  - id: clip-single
    job:
      component: clipper
      action: clip-single
      output:
        video: ${output as video}

components:
  - id: clipper
    type: video-clipper
    action:
      video: ${input.video as video}
      span:
        start_time: ${input.start_time | 0s}
        end_time: ${input.end_time | 10s}
```

### Multi-Span Clip and Merge

```yaml
workflows:
  - id: clip-and-merge
    job:
      component: clipper
      action: clip-and-merge
      output:
        video: ${output as video}

components:
  - id: clipper
    type: video-clipper
    action:
      id: clip-and-merge
      video: ${input.video as video}
      span: ${input.spans as json}
      merge: true
```

Input example for `clip-and-merge`:

```json
{
  "video": "/path/to/input.mp4",
  "spans": [
    { "start_time": "00:00:10", "end_time": "00:00:20" },
    { "start_time": "00:01:00", "end_time": "00:01:15" }
  ]
}
```

### Pairing with Scene Detection

Chain a `video-scene-detector` and `video-clipper` to produce one clip per scene:

```yaml
workflows:
  - id: split-scenes
    jobs:
      - id: detect
        component: scene-detector
        output:
          scenes: ${output as json}

      - id: clip
        component: clipper
        action: clip-by-scenes
        input:
          video: ${input.video as video}
          spans: ${jobs.detect.output.scenes}
        depends_on: [detect]
        output:
          clips: ${output as video[]}

components:
  - id: scene-detector
    type: video-scene-detector
    driver: pyscenedetect
    action:
      video: ${input.video as video}
      detector: adaptive
      output: ${result as json}

  - id: clipper
    type: video-clipper
    action:
      id: clip-by-scenes
      video: ${input.video as video}
      span: ${input.spans as json}
```

The scene detector emits objects with `start_time`/`end_time` fields, matching the clipper's `span` schema directly — no field remapping needed.

## Best Practices

1. **Lossless by default**: FFmpeg stream copy is used, so container and codec match the input. If frame-accurate cuts are required, follow up with `video-encoder` to re-encode.
2. **Time formats**: Prefer `HH:MM:SS(.ms)` or duration strings (`"10s"`, `"1m30s"`) for readability; numeric seconds are also accepted.
3. **Batch clipping from a detector**: Pass a full list of `{start_time, end_time}` spans in one action rather than issuing a separate call per span — the input is materialized once and each clip seeks independently.
4. **Merge vs. list**: Use `merge: true` when the downstream job needs one concatenated file (e.g. a highlight reel); leave it `false` when clips should stay individually addressable.
5. **Container compatibility**: When merging, all spans come from the same input, so codecs and container settings match by construction. Mixing sources with different codecs into one merged output requires re-encoding via `video-encoder`.
