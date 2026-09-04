# Music Analyzer Component

The music analyzer component extracts **music-domain properties** from an audio file — rhythm (beats, onsets, tempogram), active regions, tonality (key, chroma, tonnetz), spectral character (brightness, flatness), and the harmonic-vs-percussive balance. Use it to drive edit synchronization, chord/key-aware workflows, mood classification, and any pipeline that needs to *understand* what the music is doing.

For signal-level metrics (loudness/peak/gain/clipping/silence), use [`audio-analyzer`](audio-analyzer.md) instead. For raw feature matrices (spectrogram, waveform), use [`audio-feature-extractor`](audio-feature-extractor.md).

## Basic Configuration

```yaml
component:
  type: music-analyzer
  action:
    metric: beats
    audio: ${input.audio}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `music-analyzer` |
| `driver` | string | `native` | Analysis backend (currently only `native`) |
| `actions` | array | `[]` | List of measurement actions |

### Action Configuration (Common)

Exactly one of `audio` or `spectrum` must be provided.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric` | string | **required** | Measurement to run: `beats`, `onsets`, `tempogram`, `activity`, `key`, `chroma`, `tonnetz`, `brightness`, `flatness`, `harmonicity` |
| `audio` | any | — | Audio source: file path, variable reference, or upload stream. Mutually exclusive with `spectrum` |
| `spectrum` | dict \| string | — | Pre-computed spectrum from [`audio-feature-extractor`](audio-feature-extractor.md); provide instead of `audio` to reuse features across metrics. Only accepted by rhythm/activity metrics — see below |
| `sample_rate` | integer | `null` | Optional resample target for `audio` input; when omitted the file's native rate is used. Ignored for `spectrum` inputs |
| `batch_size` | integer | `null` | Number of input audios processed per batch |
| `output` | string | `null` | Output template applied to the collected result |

### Rhythm / Time-Axis Metrics

Accept either `audio` or `spectrum` input.

#### `metric: beats`

Beat times with tempo (BPM) and a confidence score derived from the tempo-band autocorrelation peak.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_bpm` | float | `60.0` | Lowest BPM considered when tracking beats |
| `max_bpm` | float | `200.0` | Highest BPM considered when tracking beats |

#### `metric: onsets`

Note-attack timestamps with peak-normalized strengths in `[0, 1]`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_gap` | duration | `30ms` | Minimum time between adjacent onsets; closer peaks are suppressed |

#### `metric: tempogram`

Local tempo distribution over time — a `(n_frames, n_bpm_bins)` matrix aligned to the audio's frame grid, useful when BPM changes across the track.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_bpm` | float | `60.0` | Lowest BPM axis value in the tempogram |
| `max_bpm` | float | `200.0` | Highest BPM axis value in the tempogram |

#### `metric: activity`

Contiguous regions where the song is louder than its own quiet-to-loud threshold — the semantic inverse of [`audio-silence-detector`](audio-silence-detector.md), but derived from the song's own dynamic range instead of an absolute dBFS floor.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_duration` | duration | `0.3s` | Minimum duration of an active region; shorter runs are dropped as noise |
| `level` | float | `0.35` | Threshold within the song's quiet-to-loud range above which audio is considered active. `0.0` = quiet floor, `1.0` = loud ceiling |

### Tonal Metrics

Require raw audio (`audio: ...`). Providing `spectrum: ...` raises `ValueError` because chroma and tonnetz need pitch-aware features the extractor's log-band spectrum cannot supply.

#### `metric: key`

Estimated musical key (tonic + mode) with a confidence score from the winning correlation minus the runner-up.

No configurable fields beyond the common ones.

#### `metric: chroma`

12-dimensional pitch-class energy over time — the raw material for chord/key analysis and harmonic similarity.

No configurable fields beyond the common ones.

#### `metric: tonnetz`

Six-dimensional tonal centroid features (Harte's Riemannian tonnetz), useful for visualizing harmonic changes and as a feature for segmentation models.

No configurable fields beyond the common ones.

### Spectral Character Metrics

Require raw audio.

#### `metric: brightness`

Spectral centroid — the "center of mass" of the spectrum in Hz. Higher values mean brighter, thinner sound; lower values mean darker, warmer sound.

No configurable fields beyond the common ones.

#### `metric: flatness`

Spectral flatness in `[0, 1]`. `0.0` for pure tones (single sine), `1.0` for white noise. Useful for distinguishing tonal from noise-like passages.

No configurable fields beyond the common ones.

### Source Separation Metric

Requires raw audio.

#### `metric: harmonicity`

Ratio of harmonic-to-total energy after `librosa.effects.hpss` separates the signal. `1.0` means fully harmonic (drone, string ensemble); `0.0` means fully percussive (drum solo).

No configurable fields beyond the common ones.

## Supported Drivers

### Native

Pure-Python analysis using [librosa](https://librosa.org/) and [soundfile](https://python-soundfile.readthedocs.io/). No FFmpeg binary required.

```yaml
component:
  type: music-analyzer
  driver: native
  action:
    metric: beats
    audio: ${input.audio}
```

**Auto-installed dependencies:** `librosa`, `numpy`, `soundfile`

#### Notes

- Input decoding relies on **libsndfile** via `soundfile`. WAV/FLAC/OGG work out of the box; MP3/M4A require libsndfile 1.1+ (bundled with modern `soundfile` wheels).
- Non-file inputs (streams) are spooled to a temporary file before decoding.
- Multi-channel inputs are downmixed to mono; the signal is resampled only when `sample_rate` is set explicitly.
- All analysis runs on a background thread so it does not block the event loop.

## Output Format

### `beats`

```python
{
  "bpm":        137.2,
  "confidence": 8.94,       # 1.0 ≈ no periodicity; typical music sits at 3+
  "beats": [
    {"time": 0.44},
    {"time": 0.88},
    ...
  ],
}
```

### `onsets`

```python
{
  "onsets": [
    {"time": 0.44, "strength": 0.82},
    {"time": 1.17, "strength": 0.65},
    ...
  ],
}
```

### `tempogram`

```python
{
  "frames":      [[0.12, 0.08, ...], ...],   # (n_frames, n_bpm_bins), low → high BPM
  "bpm_axis":    [60.0, 62.4, ..., 200.0],
  "fps":         86.13,
  "sample_rate": 44100,
}
```

### `activity`

```python
{
  "activity": [
    {"start_time": 3.0,  "end_time":  7.04},
    {"start_time": 12.5, "end_time": 44.8},
    ...
  ],
}
```

An empty list means the song had no dynamic range to threshold against (silence, or a constant-loudness signal).

### `key`

```python
{
  "key":        "C",         # C, C#, D, ..., B
  "mode":       "major",     # "major" or "minor"
  "confidence":  0.10,       # correlation gap between the winner and runner-up
}
```

### `chroma`

```python
{
  "frames":      [[c, cs, d, ..., b], ...],   # (n_frames, 12) pitch-class energy
  "fps":         86.13,
  "sample_rate": 44100,
}
```

### `tonnetz`

```python
{
  "frames":      [[t0, t1, t2, t3, t4, t5], ...],   # (n_frames, 6) tonal centroid
  "fps":         86.30,
  "sample_rate": 44100,
}
```

### `brightness`

```python
{
  "brightness_hz": 2140.5,
  "frames":        [2130.1, 2145.3, ...],   # per-frame centroid in Hz
  "fps":           86.13,
  "sample_rate":   44100,
}
```

### `flatness`

```python
{
  "flatness":     0.12,           # summary
  "frames":      [0.10, 0.13, ...],
  "fps":          86.13,
  "sample_rate":  44100,
}
```

### `harmonicity`

```python
{
  "harmonicity":  0.72,
  "percussivity": 0.28,
}
```

## Multiple Actions Configuration

Multiple metrics can share a single component. When calling several rhythm metrics on the same audio, feed a pre-computed spectrum from [`audio-feature-extractor`](audio-feature-extractor.md) to avoid redundant FFT work.

```yaml
components:
  - id: extractor
    type: audio-feature-extractor
    driver: native
    action:
      feature: spectrum
      audio: ${input.audio}
      fps: 100
      band_count: 128

  - id: analyzer
    type: music-analyzer
    driver: native
    actions:
      - id: beats
        metric: beats
        spectrum: ${extractor.result}

      - id: onsets
        metric: onsets
        spectrum: ${extractor.result}
        min_gap: 50ms

      - id: activity
        metric: activity
        spectrum: ${extractor.result}
        min_duration: 0.5s

      # Tonal metrics need raw audio, not a spectrum:
      - id: key
        metric: key
        audio: ${input.audio}
```

## Integration with Workflows

### BPM-Gated Video Editing

Only run downstream cut synchronization when the tempo is stable enough to trust:

```yaml
workflows:
  - id: sync-cuts
    jobs:
      - id: analyze
        component: rhythm
        action: beats
        input:
          audio: ${input.audio}

      - id: cut
        component: video-clipper
        when: ${analyze.result.confidence > 3.0}
        input:
          video: ${input.video}
          cuts: ${analyze.result.beats}

components:
  - id: rhythm
    type: music-analyzer
    action:
      metric: beats
      audio: ${input.audio}
```

### Key-Aware Track Grouping

Group a playlist by tonal centre for smooth harmonic transitions:

```yaml
components:
  - id: key-detector
    type: music-analyzer
    action:
      metric: key
      audio: ${input.audio}
```

### Active-Region Trimming

Find the loud portion of a track for a preview clip:

```yaml
components:
  - id: activity-scanner
    type: music-analyzer
    action:
      metric: activity
      audio: ${input.audio}
      level: 0.5
      min_duration: 2s
```

## Best Practices

1. **Prefer the audio's native sample rate**: leave `sample_rate` unset. `librosa` handles arbitrary rates and the resample step is only worth its cost when you have a specific bandwidth or throughput reason.
2. **Reuse a spectrum across rhythm metrics**: `beats`, `onsets`, `tempogram`, and `activity` all consume the same onset envelope. Extract the spectrum once with `audio-feature-extractor` (`fps: 100`, `band_count: 128` is a solid default) and feed it to each metric.
3. **Gate on `confidence`, not just BPM**: `librosa.beat.beat_track` returns a plausible BPM even for arrhythmic input. Use `confidence < 2.0` as a downstream cutoff.
4. **Tonal metrics need raw audio**: `key`, `chroma`, `tonnetz`, `brightness`, `flatness`, `harmonicity` cannot be computed from the extractor's log-band spectrum — pass `audio: ...` directly.
5. **`activity` reads dynamics, not level**: it maps the song's quiet-to-loud percentiles to `[0, 1]` and thresholds against that, so a consistently loud track produces no regions. Use [`audio-silence-detector`](audio-silence-detector.md) when an absolute dBFS floor is what you want.
6. **This component is read-only**: pair with [`audio-clipper`](audio-clipper.md) or [`video-clipper`](video-clipper.md) to act on the timestamps it produces.
</content>
</invoke>