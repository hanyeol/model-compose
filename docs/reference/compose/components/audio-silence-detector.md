# Audio Silence Detector Component

The audio silence detector component locates **silent regions** in an audio track using ffmpeg's `silencedetect` filter. It returns an ordered timeline of `silence` and `audible` runs spanning the whole audio, which downstream steps can use to trim leading/trailing dead air, split long recordings on quiet gaps, or drive silence-based cue points.

Silence here means "energy below a threshold," not "no voice." For speech vs. non-speech classification use a model-based VAD (`model` with `task: voice-activity-detection`); for music structural analysis (intro/verse/chorus) use `music-segment-detector`.

## Basic Configuration

```yaml
component:
  type: audio-silence-detector
  action:
    audio: ${input.audio as file}
    silence_threshold: -30
    min_silence_duration: 500ms
    output: ${result as json}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `audio-silence-detector` |
| `driver` | string | `ffmpeg` | Detection backend (currently only `ffmpeg`) |
| `actions` | array | `[]` | List of detection actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | string \| list | **required** | Audio source or list of sources to scan |
| `silence_threshold` | number | `-30.0` | Loudness in dBFS below which a sample counts as silent. More negative = quieter, so `-40` requires a quieter signal than `-30` |
| `min_silence_duration` | duration | `500ms` | Minimum length of a quiet run before it is reported as silence. Shorter dips (breaths, brief pauses) are ignored |
| `batch_size` | integer | `null` | Number of input audios processed per batch |
| `output` | string | `null` | Output template |

## Supported Drivers

### FFmpeg

Uses ffmpeg's built-in `silencedetect` audio filter. Requires the `ffmpeg` binary on `PATH`.

```yaml
component:
  type: audio-silence-detector
  driver: ffmpeg
  action:
    audio: ${input.audio as file}
    silence_threshold: -30
    min_silence_duration: 500ms
    output: ${result as json}
```

## Output Format

Each detection returns an ordered timeline that covers the entire audio, alternating `audible` and `silence` runs.

```json
{
  "segments": [
    { "start_time": 0.0,  "end_time": 12.3, "type": "audible" },
    { "start_time": 12.3, "end_time": 15.6, "type": "silence" },
    { "start_time": 15.6, "end_time": 47.0, "type": "audible" },
    { "start_time": 47.0, "end_time": 49.1, "type": "silence" },
    { "start_time": 49.1, "end_time": 120.0, "type": "audible" }
  ],
  "duration": 120.0
}
```

### Segment Fields

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | number | Segment start time in seconds |
| `end_time` | number | Segment end time in seconds |
| `type` | string | Either `"silence"` (quiet run detected by the filter) or `"audible"` (gap between silences) |

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `segments` | array | Ordered list of segments spanning the entire audio |
| `duration` | number | Total audio duration in seconds |

## Multiple Actions Configuration

Define multiple detection profiles on one component:

```yaml
component:
  type: audio-silence-detector
  actions:
    - id: default
      audio: ${input.audio as file}
      silence_threshold: -30
      min_silence_duration: 500ms
      output: ${result as json}

    - id: strict
      audio: ${input.audio as file}
      silence_threshold: -40
      min_silence_duration: 2s
      output: ${result as json}
```

## Integration with Workflows

### Trim Leading/Trailing Silence

Use detected silences to build clip ranges that skip dead air at the start and end of a recording:

```yaml
workflows:
  - id: trim-silence
    jobs:
      - id: detect
        component: silence-detector
        output:
          segments: ${output.segments}

      - id: audible
        input:
          segments: ${jobs.detect.output.segments}
        expression: ${input.segments | filter(type == "audible")}

      - id: clip
        component: clipper
        input:
          audio: ${input.audio}
          ranges: ${jobs.audible.output}
        depends_on: [audible]

components:
  - id: silence-detector
    type: audio-silence-detector
    action:
      audio: ${input.audio as file}
      silence_threshold: -35
      min_silence_duration: 1s
      output: ${result as json}

  - id: clipper
    type: audio-clipper
    action:
      audio: ${input.audio as file}
      ranges: ${input.ranges}
```

## Best Practices

1. **Threshold Choice**: Studio recordings usually work well at `-30` to `-40` dBFS. Field recordings with room noise may need `-25` to `-30`; go more negative only if the noise floor is quiet enough. Test on a representative sample before batch runs.
2. **Duration Filter**: `min_silence_duration` filters out breaths, plosive gaps, and syllable spacing. `500ms` is a good default; use `1s`–`2s` to only catch section breaks.
3. **Not a VAD**: `silencedetect` reacts to signal energy, not to voice. Background music or steady hum will register as "audible" even during speech pauses. For speech/non-speech classification, use `model` with `task: voice-activity-detection`.
4. **Not for Music Structure**: Quiet passages inside a song will look like silences even though the song is still playing. Use `music-segment-detector` for verse/chorus boundaries.
