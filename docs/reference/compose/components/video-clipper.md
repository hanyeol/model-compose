# Video Clipper Component

The video clipper component extracts one or more time ranges out of a video file, optionally concatenating the extracted spans into a single output. Clipping is performed by FFmpeg either via stream copy (`-c copy`, keyframe-aligned; the default) or with re-encoding for frame-accurate cuts.

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
| `precision` | string | `fast` | Cut precision: `fast` snaps to the nearest keyframe (stream copy); `accurate` re-encodes to the requested frame (±1 frame). |
| `return_timestamp` | boolean \| string | `false` | If true, each clip carries its actual cut span alongside the video — `start_time`/`end_time` reflect what was cut, not what was requested (see [Output Format](#output-format)). |
| `batch_size` | integer \| string | `null` | Number of input sources per batch. When unset, all sources are processed together. |

### Span Object

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `start_time` | string \| number | **required** | Clip start time. Accepts timecodes (`"00:00:10"`), duration strings (`"10s"`, `"1m30s"`), or seconds as a number (`10.5`). |
| `end_time` | string \| number | **required** | Clip end time. Same formats as `start_time`. |

## Supported Drivers

### FFmpeg

Uses FFmpeg to slice the input. In `fast` mode (default) the input is stream-copied, so cuts are lossless and near-instant; in `accurate` mode the clip is re-encoded so cuts land on the requested frame. Only FFmpeg needs to be installed on the system; no additional Python dependencies are required.

```yaml
component:
  type: video-clipper
  driver: ffmpeg
  action:
    video: ${input.video as video}
    span:
      start_time: "00:00:10"
      end_time: "00:00:25"
    precision: fast   # or 'accurate' for frame-accurate cuts (re-encodes)
```

**Requires:** `ffmpeg` binary on `PATH`.

> **On keyframe snapping (`fast`)**: The cut is aligned to the nearest keyframe at or before the requested `start_time`. When `return_timestamp` is enabled, the emitted `start_time` reflects that keyframe — not the originally requested value — so downstream jobs see the clip's real starting position.
>
> **When to use `accurate`**: Choose `accurate` when downstream processing depends on exact frame boundaries (e.g. sub-second edits, syncing to a script). Re-encoding uses the source video codec by default, falling back to the container's default codec when the source codec is unknown; expect it to be materially slower than `fast` and to produce a re-encoded (not bit-exact) output.

## Output Format

Behavior depends on `span` and `merge`:

| `span` | `merge` | Output per source |
|--------|---------|-------------------|
| Single object | any | A single video clip |
| List of objects | `false` | A list of video clips (one per span) |
| List of objects | `true` | A single video clip (all spans concatenated) |

When multiple video sources are supplied via `video: [...]`, results are returned as a list of the above per source.

### With `return_timestamp: true`

Each clip is wrapped in an object that carries the source span, so downstream jobs can recover per-input positions:

| `span` | `merge` | Output shape per source |
|--------|---------|-------------------------|
| Single object | any | `{ video, start_time, end_time }` |
| List of objects | `false` | List of `{ video, start_time, end_time }` (one per span) |
| List of objects | `true` | `{ video, times: [{ start_time, end_time }, ...] }` where `times` lists all covered spans |

When the resolved span list is empty, the per-clip form yields `null` and the merged form yields `{ video: null, times: [] }`.

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

1. **Lossless by default**: `precision: fast` uses FFmpeg stream copy, so container and codec match the input. For frame-accurate cuts set `precision: accurate` (re-encodes with the input codec).
2. **Time formats**: Prefer `HH:MM:SS(.ms)` or duration strings (`"10s"`, `"1m30s"`) for readability; numeric seconds are also accepted.
3. **Batch clipping from a detector**: Pass a full list of `{start_time, end_time}` spans in one action rather than issuing a separate call per span — the input is materialized once and each clip seeks independently.
4. **Merge vs. list**: Use `merge: true` when the downstream job needs one concatenated file (e.g. a highlight reel); leave it `false` when clips should stay individually addressable.
5. **Container compatibility**: When merging, all spans come from the same input, so codecs and container settings match by construction. Mixing sources with different codecs into one merged output requires re-encoding via `video-encoder`.
