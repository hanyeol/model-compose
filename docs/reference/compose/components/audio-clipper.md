# Audio Clipper Component

The audio clipper component extracts one or more time ranges out of an audio file, optionally concatenating the extracted spans into a single output. Clipping is performed by FFmpeg using stream copy (`-c copy`), so the operation is fast and lossless (no re-encoding).

## Basic Configuration

```yaml
component:
  type: audio-clipper
  driver: ffmpeg
  action:
    audio: ${input.audio as audio}
    span:
      start_time: ${input.start_time | 0s}
      end_time: ${input.end_time | 10s}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `audio-clipper` |
| `driver` | string | `ffmpeg` | Clipping backend driver. Currently only `ffmpeg`. |
| `actions` | array | `[]` | List of clipping actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | string \| string[] | **required** | Audio source(s) — file path, URL, or interpolated variable (e.g. `${input.audio as audio}`) |
| `span` | object \| object[] \| string | **required** | One or more time spans to clip out of each audio source. A single span object yields a single clip; a list yields one clip per span. |
| `merge` | boolean \| string | `false` | If true, concatenate all clips per source into a single audio; otherwise return a list of clips. |
| `return_timestamp` | boolean \| string | `false` | If true, each clip carries its source span alongside the audio (see [Output Format](#output-format)). |
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
  type: audio-clipper
  driver: ffmpeg
  action:
    audio: ${input.audio as audio}
    span:
      start_time: "00:00:10"
      end_time: "00:00:25"
```

**Requires:** `ffmpeg` binary on `PATH`.

**Output containers streamable to stdout** (no post-write seek): `mp3`, `wav`, `flac`, `ogg`, `opus`, `aac`. Other formats are written to a temporary file and streamed back.

## Output Format

Behavior depends on `span` and `merge`:

| `span` | `merge` | Output per source |
|--------|---------|-------------------|
| Single object | any | A single audio clip |
| List of objects | `false` | A list of audio clips (one per span) |
| List of objects | `true` | A single audio clip (all spans concatenated) |

When multiple audio sources are supplied via `audio: [...]`, results are returned as a list of the above per source.

### With `return_timestamp: true`

Each clip is wrapped in an object that carries the source span, so downstream jobs can recover per-input positions:

| `span` | `merge` | Output shape per source |
|--------|---------|-------------------------|
| Single object | any | `{ audio, start_time, end_time }` |
| List of objects | `false` | List of `{ audio, start_time, end_time }` (one per span) |
| List of objects | `true` | `{ audio, times: [{ start_time, end_time }, ...] }` where `times` lists all covered spans |

When the resolved span list is empty, the per-clip form yields `null` and the merged form yields `{ audio: null, times: [] }`.

## Multiple Actions Configuration

Define multiple clipping actions on the same component:

```yaml
component:
  type: audio-clipper
  actions:
    - id: clip-single
      audio: ${input.audio as audio}
      span:
        start_time: ${input.start_time | 0s}
        end_time: ${input.end_time | 10s}

    - id: clip-multiple
      audio: ${input.audio as audio}
      span: ${input.spans as json}

    - id: clip-and-merge
      audio: ${input.audio as audio}
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
        audio: ${output as audio}

components:
  - id: clipper
    type: audio-clipper
    action:
      audio: ${input.audio as audio}
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
        audio: ${output as audio}

components:
  - id: clipper
    type: audio-clipper
    action:
      id: clip-and-merge
      audio: ${input.audio as audio}
      span: ${input.spans as json}
      merge: true
```

Input example for `clip-and-merge`:

```json
{
  "audio": "/path/to/input.mp3",
  "spans": [
    { "start_time": "00:00:10", "end_time": "00:00:20" },
    { "start_time": "00:01:00", "end_time": "00:01:15" }
  ]
}
```

### Pairing with Scene / Segment Detection

Feed spans from an upstream detector (e.g. speaker diarization or voice activity detection) directly into the clipper:

```yaml
workflows:
  - id: extract-speech-clips
    jobs:
      - id: detect
        component: vad
        output:
          segments: ${output as json}

      - id: clip
        component: clipper
        action: clip-by-spans
        input:
          audio: ${input.audio as audio}
          spans: ${jobs.detect.output.segments}
        depends_on: [detect]
        output:
          clips: ${output as audio[]}

components:
  - id: clipper
    type: audio-clipper
    action:
      id: clip-by-spans
      audio: ${input.audio as audio}
      span: ${input.spans as json}
```

## Best Practices

1. **Lossless by default**: FFmpeg stream copy is used, so output codec matches input. Convert with `audio-converter` afterwards if a different codec is needed.
2. **Time formats**: Prefer `HH:MM:SS(.ms)` or duration strings (`"10s"`, `"1m30s"`) for readability; numeric seconds are also accepted.
3. **Batch clipping from a detector**: Pass a full list of `{start_time, end_time}` spans in one action rather than issuing a separate call per span — the input is materialized once and each clip seeks independently.
4. **Merge vs. list**: Use `merge: true` when the downstream job needs one concatenated file (e.g. highlight reel); leave it `false` when clips should stay individually addressable.
