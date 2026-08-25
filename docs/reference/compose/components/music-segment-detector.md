# Audio Segment Detector Component

The audio segment detector component analyzes an audio file to detect **structural segment boundaries** — the points where a song moves from one section to another (e.g., intro → verse → chorus). It uses chroma-CQT features and either Laplacian or agglomerative segmentation to derive boundaries and clusters segments into repeating structural labels (A/B/C…) so recurring sections share the same label.

Best suited for music. For speech (sentence/utterance boundaries) or environment sound classification, prefer other components.

## Basic Configuration

```yaml
component:
  type: music-segment-detector
  action:
    audio: ${input.audio as file}
    strategy: laplacian
    output: ${result as json}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `music-segment-detector` |
| `driver` | string | `native` | Detection backend (currently only `native`) |
| `actions` | array | `[]` | List of segmentation actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `audio` | string \| list | **required** | Audio source or list of sources to segment |
| `strategy` | string | `laplacian` | Segmentation algorithm: `laplacian` or `agglomerative` |
| `min_segment_duration` | duration | `2s` | Minimum duration of a segment; shorter segments are merged into a neighbor. Acts as a post-processing safety net — the algorithm's beat-sync, majority filter, and label-collapse already suppress most spurious short segments |
| `sample_rate` | integer | `22050` | Target mono PCM sample rate used for analysis |
| `batch_size` | integer | `null` | Number of input audios processed per batch |
| `output` | string | `null` | Output template |

## Supported Drivers

### Native

Pure-Python segmentation using [librosa](https://librosa.org/) and [soundfile](https://python-soundfile.readthedocs.io/). No FFmpeg binary required.

```yaml
component:
  type: music-segment-detector
  driver: native
  action:
    audio: ${input.audio as file}
    strategy: laplacian
    output: ${result as json}
```

**Auto-installed dependencies:** `librosa`, `numpy`, `soundfile`

#### Strategy Comparison

| Strategy | How it works | When to use |
|----------|--------------|-------------|
| `laplacian` | Beat-synchronized chroma-CQT + MFCC → combined recurrence matrix → symmetric normalized Laplacian → first k eigenvectors as spectral embedding → k-means. k is chosen by the eigengap heuristic within [2, 8]. Boundaries fall on beat positions where the per-beat cluster label changes | General-purpose music segmentation (recommended). Repeating sections (verse, chorus) receive the same structural label because the embedding groups them together |
| `agglomerative` | Chroma-CQT features clustered via `librosa.segment.agglomerative` with a data-driven segment count (roughly one segment per 10 seconds, clamped to [2, 12]) | When a bounded, roughly-uniform number of segments is preferred, or when the laplacian output looks unstable on very short clips |

#### Notes

- Input decoding relies on **libsndfile** via `soundfile`. WAV/FLAC/OGG work out of the box; MP3/M4A require libsndfile 1.1+ (bundled with modern `soundfile` wheels).
- Non-file inputs (streams) are spooled to a temporary file before decoding.
- Multi-channel inputs are downmixed to mono; the signal is resampled to `sample_rate` if needed.
- All analysis runs on a background thread so it does not block the event loop.

## Output Format

Each detection returns an object with the segment list, total audio duration, and the sample rate used for analysis.

```json
{
  "segments": [
    { "start_time": 0.0,   "end_time": 12.4,  "label": "A" },
    { "start_time": 12.4,  "end_time": 45.2,  "label": "B" },
    { "start_time": 45.2,  "end_time": 78.1,  "label": "A" },
    { "start_time": 78.1,  "end_time": 120.0, "label": "C" }
  ],
  "duration": 120.0,
  "sample_rate": 22050
}
```

### Segment Fields

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | number | Segment start time in seconds |
| `end_time` | number | Segment end time in seconds |
| `label` | string | Structural cluster label (A, B, C…). Same label = same structural role |

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `segments` | array | Ordered list of segments spanning the entire audio |
| `duration` | number | Total audio duration in seconds |
| `sample_rate` | integer | Sample rate used for analysis |

## Multiple Actions Configuration

Define multiple segmentation configurations on one component:

```yaml
component:
  type: music-segment-detector
  actions:
    - id: laplacian
      audio: ${input.audio as file}
      strategy: laplacian
      output: ${result as json}

    - id: agglomerative
      audio: ${input.audio as file}
      strategy: agglomerative
      output: ${result as json}
```

## Integration with Workflows

### Basic Segmentation

```yaml
workflows:
  - id: detect-segments
    job:
      component: segment-detector
      output:
        segments: ${output as json}

components:
  - id: segment-detector
    type: music-segment-detector
    action:
      audio: ${input.audio as file}
      strategy: laplacian
      output: ${result as json}
```

### Segment Boundaries → Audio Clipper

Feed detected boundaries into `audio-clipper` to cut a song into its structural parts:

```yaml
workflows:
  - id: split-song
    jobs:
      - id: detect
        component: segment-detector
        output:
          segments: ${output.segments}

      - id: split
        component: clipper
        input:
          audio: ${input.audio}
          ranges: ${jobs.detect.output.segments}
        depends_on: [detect]

components:
  - id: segment-detector
    type: music-segment-detector
    action:
      audio: ${input.audio as file}
      strategy: laplacian
      output: ${result as json}

  - id: clipper
    type: audio-clipper
    action:
      audio: ${input.audio as file}
      ranges: ${input.ranges}
```

## Best Practices

1. **Strategy Selection**: Start with `laplacian` — it adapts to the song's structure. Switch to `agglomerative` when you need a predictable number of segments.
2. **Minimum Duration**: The default `2s` catches the residual sub-second outliers the algorithm's internal smoothing lets through, without erasing genuinely short sections (bridges, outros). Raise to `4s`–`8s` only when you want a coarser view of the song — larger values will merge real short sections into their neighbors.
3. **Using Labels vs. Boundaries Only**: Every segment carries a `label`. If your downstream step only needs cut points (e.g. feeding an `audio-clipper`), read `start_time`/`end_time` and ignore `label`; the labeling cost is negligible.
4. **Sample Rate**: The default `22050` Hz is sufficient for structural analysis. Higher rates increase memory/CPU cost without improving segmentation quality.
5. **Music vs. Speech**: This component is tuned for musical structure. For speech segmentation (sentence, utterance) use a VAD-based approach with `speech-to-text` timestamps instead.
