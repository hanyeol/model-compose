# Audio Synchronizer Component

The audio synchronizer component measures time offsets between multiple recordings that share the same audio — a common scenario for multi-camera shoots, mirrored streams, or the same event captured on different devices. It decodes each source through ffmpeg and runs FFT-based cross-correlation against the first source, returning one `{offset, confidence}` entry per input. It does *not* produce aligned media itself; use the offsets to drive downstream trimming, padding, or muxing.

## Basic Configuration

```yaml
component:
  type: audio-synchronizer
  driver: ffmpeg
  action:
    sources:
      - ${input.reference}
      - ${input.target}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `audio-synchronizer` |
| `driver` | string | `ffmpeg` | Synchronization backend. Currently: `ffmpeg` |
| `actions` | array | `[]` | List of synchronization actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sources` | array \| string | **required** | Media sources (audio or video) to align. The first entry is the reference; every other source is measured against it |
| `batch_size` | integer | `null` | Number of source arrays processed in parallel when `sources` is a list of lists or a stream |
| `output` | string | `null` | Output template applied to the collected result |

Video containers are accepted alongside audio files — the video track is dropped during decoding, so `.mp4`, `.mov`, `.wav`, `.mp3` can be mixed freely in one `sources` list.

## Supported Drivers

### FFmpeg

Decodes each source to 8 kHz mono PCM through ffmpeg (`-vn -ac 1 -ar 8000`), then runs cross-correlation in numpy. 8 kHz keeps enough bandwidth for typical speech and music transients while shrinking FFT cost versus full sample rate. Sub-sample precision comes from parabolic interpolation around the correlation peak, so lag resolution is not limited to 1/8000 s.

```yaml
component:
  type: audio-synchronizer
  driver: ffmpeg
  action:
    sources: ${input.sources}
```

**Requires:** `ffmpeg` binary on the system path, and `numpy` (`pip install numpy`)

## Output Format

The action returns a list of `{offset, confidence}` entries in the same order as `sources`. The first entry — the reference — is always `{offset: 0.0, confidence: 1.0}`.

```python
[
  {"offset":  0.0000, "confidence": 1.000},  # reference
  {"offset":  1.2345, "confidence": 0.987},  # 1.2345 s later than the reference
  {"offset": -0.5000, "confidence": 0.972},  # 0.5 s earlier than the reference
]
```

| Field | Type | Description |
|-------|------|-------------|
| `offset` | float (seconds) | Time offset that aligns the source with the reference. Positive means the source starts *later* than the reference; negative means it starts *earlier* |
| `confidence` | float 0..1 | Normalized peak correlation between the source and the reference. Values near 1.0 indicate a clean match; values near 0 mean the two recordings likely do not share the same audio |

### Batch Output

When `sources` is a list of lists (or a stream of source arrays), the action returns a list of offset lists — one per alignment task, in input order.

```python
[
  [{"offset": 0.0, "confidence": 1.0}, {"offset": 1.23, "confidence": 0.98}],  # first alignment
  [{"offset": 0.0, "confidence": 1.0}, {"offset": 0.45, "confidence": 0.95}],  # second alignment
]
```

## Integration with Workflows

### Two-Way Alignment

Compute the offset of a target recording against a reference:

```yaml
workflows:
  - id: align-two
    job:
      component: sync
      action: align-two
      output:
        offsets: ${output}

components:
  - id: sync
    type: audio-synchronizer
    action:
      id: align-two
      sources:
        - ${input.reference as file}
        - ${input.target as file}
```

### Multi-Source Alignment

Align an arbitrary number of recordings against the first one:

```yaml
components:
  - id: sync
    type: audio-synchronizer
    action:
      sources: ${input.sources as file}
```

### Feeding Offsets Into a Clipper

Chain the synchronizer with `audio-clipper` or `video-clipper` to trim each source onto a common timeline. Positive offsets are trimmed off the start; negative offsets typically need upstream padding.

## Best Practices

1. **Pick the reference intentionally**: The first source is the time origin. Place the recording whose timeline you want to keep unchanged first — offsets can then be applied directly to the other sources.
2. **Positive offset means "starts later"**: To align a source with the reference, drop `offset` seconds from its beginning. If you expected the opposite sign, you probably want to trim the *reference* by that amount instead.
3. **Use confidence as a sanity check**: Real-world matches usually land above ~0.5. Values below ~0.2 typically mean the two recordings do not actually share the same audio — treat those offsets as unreliable.
4. **Prefer segments with a sharp transient**: If a section of the reference has no distinctive content (long silence, a repeating beat), the correlation peak can land on the wrong copy of the pattern. A clap, a door slam, or a spoken word makes alignment robust.
5. **Recordings do not need to be the same length**: Cross-correlation scans every lag between the two, so a 30-minute recording can be aligned against a 5-minute one from the middle of the event.
6. **Clock drift is out of scope**: The component reports a single offset per source and assumes the recording clocks run at the same rate. For hours-long recordings from cheap hardware, split into shorter segments and align each segment separately.
7. **Batch with `batch_size`**: When aligning independent source groups (e.g., many takes), pass a list of lists and set `batch_size` to parallelize the alignment tasks.
