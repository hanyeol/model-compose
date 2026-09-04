# Music Analyzer Example

This example demonstrates how to use model-compose with the `music-analyzer` component to extract music-domain properties from an audio file — rhythm, tonality, spectral character, and the harmonic-vs-percussive balance.

## Overview

This example provides 10 workflows, one per metric:

1. **Detect Beats and BPM** (default) — tempo estimation with beat times and a periodicity-based confidence score.
2. **Detect Note Onsets** — attack timestamps with peak-normalized strengths.
3. **Compute Local Tempo Distribution** — per-frame tempogram; useful when BPM changes across the track.
4. **Detect Active Regions** — loud stretches derived from the song's own dynamic range (semantic inverse of silence detection).
5. **Detect Musical Key** — tonic + mode via Krumhansl profile correlation.
6. **Extract Chroma** — 12-dimensional pitch-class energy over time.
7. **Extract Tonnetz** — 6-dimensional Harte tonal-centroid features.
8. **Measure Spectral Brightness** — spectral centroid in Hz.
9. **Measure Spectral Flatness** — tonal-vs-noise ratio in [0, 1].
10. **Measure Harmonic vs Percussive Ratio** — HPSS-based energy split.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python dependencies are automatically installed on first run:
  - `librosa`, `numpy`, `soundfile` (used by the `native` driver)

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/music-analyzer
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   The service will start:
   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run workflows:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select a workflow from the dropdown
   - Upload an audio file
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Beats and BPM (default)
   model-compose run detect-beats --input '{"audio": "/path/to/track.mp3"}'

   # Custom BPM search range
   model-compose run detect-beats --input '{
     "audio": "/path/to/track.mp3",
     "min_bpm": 80,
     "max_bpm": 160
   }'

   # Onset detection with tighter minimum gap
   model-compose run detect-onsets --input '{
     "audio": "/path/to/track.mp3",
     "min_gap": "50ms"
   }'

   # Key detection
   model-compose run detect-key --input '{"audio": "/path/to/track.mp3"}'

   # Active regions with a stricter threshold
   model-compose run detect-activity --input '{
     "audio": "/path/to/track.mp3",
     "level": 0.5,
     "min_duration": "1s"
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-beats" \
     -F "audio=@/path/to/track.mp3"
   ```

## Component Details

### Music Analyzer Component

- **Type**: `music-analyzer`
- **Purpose**: Extract music-domain properties from audio — rhythm, tonality, spectral character, and source-separation ratios.
- **Drivers**:
  - `native` — librosa-based analysis (default)

For signal-level metrics (loudness/peak/gain/clipping/silence), use [`audio-analyzer`](../audio-analyzer/) instead. For raw feature matrices (spectrogram, waveform), use [`audio-feature-extractor`](../audio-feature-extractor/).

## Workflow Details

### 1. Detect Beats and BPM

**ID**: `detect-beats`
**Metric**: `beats`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `min_bpm` | number | No | `60.0` | Lowest BPM considered when tracking beats |
| `max_bpm` | number | No | `200.0` | Highest BPM considered when tracking beats |

#### Example Output

```json
{
  "bpm": 137.2,
  "confidence": 8.94,
  "beats": [
    { "time": 0.44 },
    { "time": 0.88 }
  ]
}
```

`confidence` near 1.0 means the input has no dominant periodicity; typical music sits at 3+.

---

### 2. Detect Note Onsets

**ID**: `detect-onsets`
**Metric**: `onsets`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `min_gap` | duration | No | `30ms` | Minimum time between adjacent onsets |

#### Example Output

```json
{
  "onsets": [
    { "time": 0.44, "strength": 0.82 },
    { "time": 1.17, "strength": 0.65 }
  ]
}
```

---

### 3. Compute Local Tempo Distribution

**ID**: `compute-tempogram`
**Metric**: `tempogram`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `min_bpm` | number | No | `60.0` | Lowest BPM axis value |
| `max_bpm` | number | No | `200.0` | Highest BPM axis value |

#### Example Output

```json
{
  "frames": [[0.12, 0.08, "..."], "..."],
  "bpm_axis": [60.0, 62.4, "...", 200.0],
  "fps": 86.13,
  "sample_rate": 44100
}
```

---

### 4. Detect Active Regions

**ID**: `detect-activity`
**Metric**: `activity`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |
| `min_duration` | duration | No | `0.3s` | Minimum duration of an active region |
| `level` | number | No | `0.35` | Threshold within the song's quiet-to-loud range (0.0 = quiet floor, 1.0 = loud ceiling) |

#### Example Output

```json
{
  "activity": [
    { "start_time": 3.0,  "end_time": 7.04 },
    { "start_time": 12.5, "end_time": 44.8 }
  ]
}
```

An empty list means the song had no dynamic range to threshold against.

---

### 5. Detect Musical Key

**ID**: `detect-key`
**Metric**: `key`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |

#### Example Output

```json
{
  "key": "C",
  "mode": "major",
  "confidence": 0.10
}
```

`confidence` is the correlation gap between the winning key/mode and the runner-up.

---

### 6. Extract Chroma

**ID**: `extract-chroma`
**Metric**: `chroma`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |

#### Example Output

```json
{
  "frames": [[0.1, 0.05, "...", 0.3], "..."],
  "fps": 86.13,
  "sample_rate": 44100
}
```

Each frame is 12 pitch-class energies in order `C, C#, D, D#, E, F, F#, G, G#, A, A#, B`.

---

### 7. Extract Tonnetz

**ID**: `extract-tonnetz`
**Metric**: `tonnetz`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |

#### Example Output

```json
{
  "frames": [[0.1, -0.05, "...", 0.2], "..."],
  "fps": 86.30,
  "sample_rate": 44100
}
```

Each frame is 6 tonal-centroid coordinates on the Harte tonnetz.

---

### 8. Measure Spectral Brightness

**ID**: `measure-brightness`
**Metric**: `brightness`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |

#### Example Output

```json
{
  "brightness_hz": 2140.5,
  "frames": [2130.1, 2145.3, "..."],
  "fps": 86.13,
  "sample_rate": 44100
}
```

---

### 9. Measure Spectral Flatness

**ID**: `measure-flatness`
**Metric**: `flatness`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |

#### Example Output

```json
{
  "flatness": 0.12,
  "frames": [0.10, 0.13, "..."],
  "fps": 86.13,
  "sample_rate": 44100
}
```

---

### 10. Measure Harmonic vs Percussive Ratio

**ID**: `measure-harmonicity`
**Metric**: `harmonicity`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio file to analyze |

#### Example Output

```json
{
  "harmonicity": 0.72,
  "percussivity": 0.28
}
```

## Customization

### Reusing a Spectrum Across Rhythm Metrics

`beats`, `onsets`, `tempogram`, and `activity` all consume the same onset envelope internally. When running several of them on the same track, precompute the spectrum once with the `audio-feature-extractor` component and pass it into every metric to skip redundant FFTs:

```yaml
components:
  - id: extractor
    type: audio-feature-extractor
    driver: native
    action:
      feature: spectrum
      audio: ${input.audio as file}
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
```

Tonal and spectral-character metrics (`key`, `chroma`, `tonnetz`, `brightness`, `flatness`, `harmonicity`) require raw audio — pass `audio: ...` instead.

### Sample Rate

By default the file's native sample rate is preserved. To force a resample (usually to trade accuracy for speed on long tracks), set `sample_rate` on the action:

```yaml
actions:
  - id: beats
    metric: beats
    audio: ${input.audio as file}
    sample_rate: 22050
```

### BPM Search Range

`beats` and `tempogram` accept `min_bpm` / `max_bpm`. Narrowing the range helps when the genre's tempo band is well-known (e.g. `100`–`140` for house/techno, `60`–`90` for lo-fi):

```yaml
actions:
  - id: beats
    metric: beats
    audio: ${input.audio as file}
    min_bpm: 100
    max_bpm: 140
```

### Activity Level Threshold

`activity`'s `level` maps the song's own quiet-to-loud percentiles to `[0, 1]`. Raise it to isolate only the loudest sections (e.g. drops, choruses); lower it to catch quieter passages:

```yaml
actions:
  - id: activity
    metric: activity
    audio: ${input.audio as file}
    level: 0.6
    min_duration: 2s
```

Use [`audio-silence-detector`](../audio-silence-detector/) when you need an absolute dBFS floor instead of a relative threshold.
