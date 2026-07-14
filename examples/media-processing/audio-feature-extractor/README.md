# Audio Feature Extractor Example

This example demonstrates the `audio-feature-extractor` component, showing how model-compose can turn an audio file into per-frame feature arrays suitable for driving visualizations (equalizer bars, oscilloscope waveforms, and similar).

## Overview

Two workflows are provided:

1. **Spectrum**: FFT-based frequency-band magnitudes per frame — the classic bar equalizer look.
2. **Waveform**: Downsampled time-domain amplitudes per frame — the SoundCloud-style waveform look.

The output is a JSON payload with a `frames` array. Each entry is one video frame's feature vector. Downstream renderers (Remotion, D3, canvas, SVG) can consume it directly without knowing anything about audio.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- [ffmpeg](https://ffmpeg.org/) installed and available in your PATH
- numpy (installed automatically on first component run)

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/audio-feature-extractor
   ```

2. Verify ffmpeg is installed:
   ```bash
   ffmpeg -version
   ```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run a workflow:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Pick the **Spectrum** or **Waveform** workflow
   - Upload an audio file
   - Adjust the parameters
   - Click **Run Workflow**
   - Inspect the JSON output

   **Using API:**
   ```bash
   # Spectrum (default workflow)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: multipart/form-data" \
     -F "audio=@song.mp3" \
     -F "fps=30" \
     -F "band_count=32"

   # Waveform
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: multipart/form-data" \
     -F "workflow_id=waveform" \
     -F "audio=@song.mp3" \
     -F "fps=30" \
     -F "point_count=100"
   ```

   **Using CLI:**
   ```bash
   model-compose run spectrum --input '{"audio": "path/to/song.mp3", "band_count": 32}'
   model-compose run waveform --input '{"audio": "path/to/song.mp3", "point_count": 100}'
   ```

## Component Details

### Audio Feature Extractor Component
- **Type**: `audio-feature-extractor`
- **Driver**: `ffmpeg` (used for decoding the input to mono PCM)
- **Compute**: numpy (installed lazily on first run)
- **Purpose**: Emit per-frame feature vectors from an audio source

The component picks a compute path based on the `feature` field on the action:
- `feature: spectrum` — FFT + log-scaled frequency bands + peak-percentile normalization
- `feature: waveform` — sliding window summarized into N data points via peak or RMS per bucket

## Workflow Details

### "Spectrum" Workflow (Default)

**Description**: Extract frequency-band spectra suitable for bar equalizer visualizations.

#### Job Flow

```mermaid
graph TD
    J1((Default<br/>job))
    C1[Spectrum<br/>extractor]
    J1 --> C1
    C1 -.-> |frames: number[][]| J1
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio source (mp3, wav, flac, aac, m4a, opus, ogg, ...) |
| `fps` | int | No | `30` | Output frames per second |
| `band_count` | int | No | `32` | Number of frequency bands per frame |
| `min_frequency` | float | No | `40.0` | Lowest frequency (Hz) included in the band grid |
| `window_size` | select | No | `2048` | FFT window size in samples: 512, 1024, 2048, 4096 |
| `window_type` | select | No | `hann` | FFT window type: hann, hamming, blackman |
| `frequency_scale` | select | No | `log` | Frequency band distribution scale: log, linear |
| `normalize_mode` | select | No | `peak-percentile` | Amplitude normalization: peak-percentile, none |

#### Output Format

```json
{
  "fps": 30,
  "band_count": 32,
  "frame_count": 5400,
  "duration": 180.0,
  "sample_rate": 22050,
  "frames": [[0.22, 0.10, ...], [0.24, 0.13, ...], ...]
}
```

Each entry in `frames` is one video frame; each value in that entry is the magnitude of one frequency band (0..1 when normalized). Low indices are bass, high indices are treble.

### "Waveform" Workflow

**Description**: Extract time-domain amplitude waveforms suitable for oscilloscope-style visualizations.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Audio source |
| `fps` | int | No | `30` | Output frames per second |
| `point_count` | int | No | `100` | Number of data points per frame (waveform display resolution) |
| `window_duration` | string | No | `40ms` | Analysis window per frame (e.g. `40ms`, `0.04s`, `1s`) |
| `summary_mode` | select | No | `peak` | Bucket summary statistic: `peak` (max\|amplitude\|) or `rms` |
| `rectify` | bool | No | `true` | If true, return magnitudes (0..1); if false, keep signed values (-1..1) |

#### Output Format

```json
{
  "fps": 30,
  "point_count": 100,
  "frame_count": 5400,
  "duration": 180.0,
  "sample_rate": 22050,
  "frames": [[0.02, 0.15, 0.34, ...], ...]
}
```

Each entry in `frames` is one video frame; each value in that entry is one waveform data point (peak or RMS) summarizing a bucket of that frame's window.

## Rendering the Output

The JSON output is intentionally renderer-agnostic. A few options for turning it into video:

- **Remotion (React)**: pass `frames` as props to a `<Composition>` and render bars/paths per `useCurrentFrame()`. Good for offline batch renders.
- **SVG / HTML canvas**: draw bars or a polyline per frame using the array directly.
- **Any other tool**: the JSON is small enough to embed inline for short clips (a few MB for a 3-minute song at 30 fps × 32 bands).

## Tips

- **Choosing `band_count`**: 16–64 works well for bar equalizers. VoyagerFM uses 32.
- **Choosing `window_size` (spectrum)**: 2048 is a good balance. Larger values give finer frequency resolution but blur time; smaller values do the opposite.
- **`min_frequency` and `max_frequency`**: `max_frequency` defaults to Nyquist (`sample_rate / 2`). Raise `min_frequency` above 20–40 Hz to skip inaudible rumble.
- **`normalize_mode: peak-percentile`**: uses the 99th percentile as the scale. Good default. Set `normalize_mode: none` if you want raw magnitudes.
- **`window_duration` (waveform)**: 20–60 ms typical. Longer windows smooth out fast transients.

## Troubleshooting

### Common Issues

1. **ffmpeg Not Found**: Ensure ffmpeg is installed and on your PATH — the component invokes it to decode the audio to PCM.
2. **numpy Not Installed**: The component declares numpy as a lazy requirement; the first run will install it via pip. If the install fails, install manually: `pip install numpy`.
3. **`window_duration` value rejected**: Use one of `"40ms"`, `"0.04s"`, or a bare number (interpreted as seconds).
4. **Zero frames returned**: The audio is shorter than one window. Reduce `window_size` (spectrum) or `window_duration` (waveform), or use a longer input.
