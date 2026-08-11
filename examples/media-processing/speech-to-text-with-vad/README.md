# Speech to Text with VAD Pre-Segmentation

Split a long audio file into speech regions with a local Silero VAD
model, clip out each region, and transcribe them with Whisper — all in
a single streaming pipeline. Each segment is emitted with an absolute
timestamp in the original audio, so the output is directly usable for
subtitles or timed transcripts.

## Overview

The workflow is three jobs stitched together with two streaming
operators (`return_timestamp` on the clipper, `+` on the transcribe
job):

1. **`detect`** — Silero VAD in streaming mode. Emits a stream of
   `{start_time, end_time, confidence}` dicts as speech regions are
   confirmed.
2. **`clip`** — `audio-clipper` (ffmpeg driver) consumes the VAD
   stream. With `return_timestamp: true` each output clip is wrapped
   as `{audio, start_time, end_time}` so the source span travels
   downstream.
3. **`transcribe`** — a `for-each` job iterates the clip stream. For
   every clip it runs Whisper with the clip's VAD `start_time` set as
   STT's `time_offset`, so the segments Whisper returns already carry
   absolute timestamps in the original audio. The job's `+` operator
   flattens Whisper's per-clip segment streams into one continuous
   segment stream.

The workflow output is that flattened stream serialized as JSON, so
callers see `{text, start_time, end_time}` dicts arrive one by one
without waiting for the whole audio.

Typical use cases:
- Producing subtitle files from long-form recordings (podcasts,
  lectures, interviews) with accurate segment timings.
- Avoiding Whisper's 30 s chunking limits on long audio by
  pre-segmenting with VAD.
- Skipping long silent stretches so Whisper time is spent only on
  actual speech.

## Preparation

### Prerequisites

- model-compose installed and available on `PATH`.
- `ffmpeg` on `PATH` (for the clipper).
- Whisper runs on **CPU**, **CUDA**, or **MPS** (Apple Silicon). The
  default config uses `device: mps`; switch to `cpu` or `cuda` if you
  are elsewhere.
- Python dependencies are installed automatically on first run:
  - `silero-vad`, `torch`, `torchaudio`, `soxr` — VAD.
  - `transformers`, `torch` — Whisper.

### Setup

Navigate to this example directory:

```bash
cd examples/media-processing/speech-to-text-with-vad
```

## How to Run

1. **Start the service:**

   ```bash
   model-compose up
   ```

   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run the workflow:**

   **Using Web UI:**
   - Open http://localhost:8081.
   - Upload an audio file and pick a language.
   - Click **Run Workflow**. Segments stream in as Whisper finishes
     each clip.

   **Using CLI:**

   ```bash
   model-compose run --input '{
     "audio": "/path/to/lecture.mp3",
     "language": "en"
   }'
   ```

   **Using API (SSE stream):**

   ```bash
   curl -N -X POST http://localhost:8080/api/workflows/runs \
     -F "audio=@/path/to/lecture.mp3" \
     -F "language=en"
   ```

## Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `audio` | file | Yes | Audio to transcribe (wav, mp3, flac, m4a, ...). |
| `language` | string | No | ISO code (`en`, `ko`, `ja`, `zh`). Defaults to `en`. |

## Output Format

A JSON stream where each line is one segment. Timestamps are absolute
positions in the original audio (VAD clip start + Whisper's
clip-relative time).

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Recognized text for this segment. |
| `start_time` | number | Segment start (seconds), absolute. |
| `end_time` | number | Segment end (seconds), absolute. |

### Example

```json
{"text": "Welcome back to the show.",        "start_time":   0.42, "end_time":   2.15}
{"text": "Today we're talking about VAD.",   "start_time":   2.60, "end_time":   5.30}
{"text": "It splits audio into speech runs.","start_time": 224.44, "end_time": 226.76}
```

## Component Details

### `vad` — Voice Activity Detection

- Type: `model` (`task: voice-activity-detection`)
- Driver: `custom`, family `silero`
- Device: `cpu` (Silero is small and CPU is fine; MPS is not
  supported).
- `sample_rate: 16000` — matches Whisper's native rate so the
  clip → STT path avoids an extra resample. Silero also supports
  8000 Hz.
- `streaming: true` — segments are emitted as they are confirmed, so
  the downstream clipper and STT can start work immediately.
- Key `params`:
  - `threshold: 0.5` — speech probability required to enter a segment.
  - `min_speech_duration: 250ms`, `min_silence_duration: 500ms` —
    hysteresis boundaries.
  - `max_speech_duration: 30s` — caps a single burst so it fits
    Whisper's 30 s window.
  - `speech_padding_time: 100ms` — extra audio around each detected
    region to avoid clipping word edges.

### `clipper` — Audio Clipper

- Type: `audio-clipper`
- Driver: `ffmpeg`
- `return_timestamp: true` — each clip is emitted as
  `{audio, start_time, end_time}` so the for-each downstream can pipe
  both audio and span to STT.

### `stt` — Speech to Text

- Type: `model` (`task: speech-to-text`)
- Driver: `huggingface`, architecture `whisper`
- Model: `openai/whisper-large-v3-turbo` — fast and accurate; switch to
  `openai/whisper-{tiny,base,small,medium,large-v3}` for other
  size/speed trade-offs.
- Device: `mps` — Apple Silicon GPU. Use `cuda` on NVIDIA or `cpu`
  elsewhere.
- `return_timestamps: true` — emit per-segment `start_time` /
  `end_time`.
- `streaming: true` — segments stream out as Whisper produces them,
  which combined with the `+` operator lets the workflow output a flat
  segment stream.
- `time_offset: ${input.time_offset}` — the for-each passes each
  clip's VAD start as this offset, and STT adds it to every returned
  segment's `start_time` / `end_time` so the results carry absolute
  positions in the original audio.

## Customization

### Running on CPU or CUDA

```yaml
components:
  - id: stt
    ...
    device: cpu   # or 'cuda' on NVIDIA
```

### Smaller / faster Whisper

```yaml
    model: openai/whisper-small       # or -base, -medium, -large-v3, etc.
```

### Tuning VAD sensitivity

```yaml
  - id: vad
    ...
    action:
      params:
        threshold: 0.3               # more permissive; picks up quieter speech
        min_speech_duration: 100ms   # keep shorter bursts
        min_silence_duration: 300ms  # split on shorter pauses
```

### Keeping timestamps relative to each clip

Drop `time_offset` from the STT input and each segment will start from
0 within its own clip:

```yaml
    - id: transcribe
      type: for-each
      input: ${jobs.clip.output}
      do:
        component: stt
        input:
          audio: ${item.audio}
          language: ${input.language}
      output:
        "+": ${output}
```
