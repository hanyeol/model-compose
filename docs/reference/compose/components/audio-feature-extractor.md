# Audio Feature Extractor Component

The audio feature extractor component decodes audio and emits per-frame feature arrays for visualization pipelines. Two features are supported: **spectrum** (FFT-based frequency bands, for equalizer displays) and **waveform** (time-domain amplitudes, for oscilloscope displays). The output is renderer-agnostic JSON — usable by Remotion, SVG, canvas, or any downstream visual layer.

## Basic Configuration

```yaml
component:
  type: audio-feature-extractor
  driver: ffmpeg
  action:
    feature: spectrum
    audio: ${input.audio}
    fps: 30
    band_count: 32
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `audio-feature-extractor` |
| `driver` | string | `ffmpeg` | Feature extraction backend. Currently: `ffmpeg` |
| `actions` | array | `[]` | List of feature extraction actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `feature` | string | **required** | Feature to extract: `spectrum`, `waveform` |
| `audio` | any | **required** | Audio source: file path, variable reference, or upload stream |
| `fps` | integer | `30` | Output frames per second |
| `sample_rate` | integer | `22050` | Sample rate used for internal PCM decoding (mono) |
| `batch_size` | integer | `null` | Number of input audios to process in a single batch |
| `output` | string | `null` | Output template applied to the collected result |

### Spectrum Feature Fields (`feature: spectrum`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `band_count` | integer | `32` | Number of frequency bands per frame |
| `min_frequency` | float | `40.0` | Lowest frequency (Hz) in the band grid |
| `max_frequency` | float | Nyquist | Highest frequency (Hz). Defaults to `sample_rate / 2` |
| `window_size` | integer | `2048` | FFT window size in samples |
| `window_type` | string | `hann` | FFT window type: `hann`, `hamming`, `blackman` |
| `frequency_scale` | string | `log` | Frequency band distribution scale: `log`, `linear` |
| `normalize_mode` | string | `peak-percentile` | Amplitude normalization: `peak-percentile`, `none` |
| `percentile` | float | `99.0` | Percentile used by `peak-percentile` normalization |

### Waveform Feature Fields (`feature: waveform`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `point_count` | integer | `100` | Number of data points per frame (visualization resolution) |
| `window_duration` | string \| float | `40ms` | Window duration per frame (e.g., `40ms`, `0.04s`, or seconds as a number) |
| `summary_mode` | string | `peak` | Bucket summary statistic: `peak`, `rms` |
| `rectify` | boolean | `true` | If `true`, return absolute magnitudes (0..1). If `false`, keep signed values (-1..1) |

## Supported Drivers

### FFmpeg

Audio is decoded to mono float32 PCM via FFmpeg (`ffmpeg -f s16le`), and features are computed with NumPy in a thread executor to avoid blocking the event loop. Requires the `ffmpeg` binary on the system; NumPy is auto-installed on first run.

```yaml
component:
  type: audio-feature-extractor
  driver: ffmpeg
  action:
    feature: spectrum
    audio: ${input.audio}
```

**Requires:** `ffmpeg` binary on the system path
**Auto-installed dependency:** `numpy`

## Output Format

### Spectrum Output

```python
{
  "frames": [[0.22, 0.10, ...], [0.24, 0.13, ...], ...],
  "fps": 30,
  "band_count": 32,
  "frame_count": 5400,
  "duration": 180.0,
  "sample_rate": 22050
}
```

Each entry in `frames` is one video frame; each value in that entry is the magnitude of one frequency band (0..1 when normalized). Low indices are bass, high indices are treble.

### Waveform Output

```python
{
  "frames": [[0.02, 0.15, 0.34, ...], ...],
  "fps": 30,
  "point_count": 100,
  "frame_count": 5400,
  "duration": 180.0,
  "sample_rate": 22050
}
```

Each entry in `frames` is one video frame; each value is one data point (peak or RMS) summarizing a bucket of that frame's window.

### Output Fields

| Field | Type | Description |
|-------|------|-------------|
| `frames` | array | Per-frame feature arrays |
| `fps` | integer | Output frames per second |
| `band_count` \| `point_count` | integer | Values per frame (spectrum: bands, waveform: points) |
| `frame_count` | integer | Total number of frames emitted |
| `duration` | float | Total duration in seconds (`frame_count / fps`) |
| `sample_rate` | integer | Sample rate used for internal decoding |

## Multiple Actions Configuration

```yaml
component:
  type: audio-feature-extractor
  driver: ffmpeg
  actions:
    - id: equalizer
      feature: spectrum
      audio: ${input.audio}
      band_count: 32
      frequency_scale: log

    - id: waveform
      feature: waveform
      audio: ${input.audio}
      point_count: 200
      summary_mode: rms
```

## Integration with Workflows

### Generate a Bar-Equalizer Video

Combine with an external renderer (e.g., Remotion) to produce a music visualization:

```yaml
workflows:
  - id: song-to-viz
    jobs:
      - id: analyze
        component: viz-features
        input: ${input.audio}
        output: ${output as json}

      - id: render
        component: remotion
        input:
          composition: Bars
          props: ${jobs.analyze.output}
        depends_on: [analyze]

components:
  - id: viz-features
    type: audio-feature-extractor
    action:
      feature: spectrum
      audio: ${input.audio}
      fps: 30
      band_count: 32

  - id: remotion
    type: shell
    action:
      command: [npx, remotion, render, src/index.tsx, "${input.composition}",
                "out/${run.id}.mp4", "--props", "${input.props}"]
```

### Batch Analysis for a Playlist

```yaml
workflows:
  - id: analyze-playlist
    job:
      component: viz-features
      input:
        audio: ${input.tracks}
      output: ${output as json}

components:
  - id: viz-features
    type: audio-feature-extractor
    action:
      feature: waveform
      audio: ${input.audio}
      point_count: 200
      batch_size: 4
```

## Best Practices

1. **Match `fps` to your target video's frame rate**: rendering at 30 fps? Use `fps: 30` so each output entry maps to one video frame.
2. **Choose `band_count` for the intended display**: 16–32 bands work well for a compact bar equalizer; 64+ for finer resolution.
3. **Use `frequency_scale: log` for music visualization**: perceptual octave spacing matches how the ear hears sound. `linear` is best for scientific/technical displays.
4. **Keep `sample_rate` low if possible**: 22050 Hz (default) is enough for visualization up to ~11 kHz. Higher rates only help for analysis above that range.
5. **Batch multiple songs with `batch_size`**: parallelizes independent FFT computations when analyzing playlists.
6. **`window_duration` accepts human strings**: prefer `40ms` over `0.04` for readability; both parse to the same value.
