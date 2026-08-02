# Speech to Text with Reference Correction

Transcribe an audio file with a local Whisper model and align the STT
segments against a known reference script. Recognition typos are replaced
with the reference wording, while STT-derived timestamps are preserved —
the output is a corrected, timed transcript suitable for subtitles.

## Overview

The workflow is two jobs:

1. **`transcribe`** — Runs `large-v3-turbo` via **faster-whisper** locally
   with `return_timestamps: segment`. Produces a list of
   `{text, start_time, end_time}` segments. faster-whisper is a CTranslate2
   port of Whisper — significantly faster than the HuggingFace transformers
   backend and works on CPU or CUDA.
2. **`correct`** — Feeds those segments plus the reference script into the
   `transcript-corrector` component. Each STT segment is anchored to the
   best-matching span of the reference; matched segments have their text
   replaced by the reference wording while `start_time` / `end_time` from
   the STT are kept intact.

Typical use cases:
- Cleaning up recorded readings of a known script (podcasts, audiobooks,
  scripted narration).
- Producing accurate subtitles when the reference transcript is authored
  separately from the audio.
- Post-processing STT output to remove homophone/typo drift without
  losing timing.

## Preparation

### Prerequisites

- model-compose installed and available on `PATH`.
- faster-whisper runs on **CPU** (macOS including Apple Silicon) or
  **CUDA**. There is no Metal/MPS backend for CTranslate2; on Apple
  Silicon the model runs on the CPU (still fast on the `turbo` model).
- Python dependencies are installed automatically on first run:
  - `faster-whisper` — CTranslate2 Whisper runtime.
  - `rapidfuzz`, `regex` — alignment scoring.

### Setup

Navigate to this example directory:

```bash
cd examples/media-processing/speech-to-text-with-correction
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
   - Upload an audio file, paste the reference script, and (optionally)
     set the language code.
   - Click **Run Workflow**.

   **Using CLI:**

   ```bash
   model-compose run --input '{
     "audio": "/path/to/reading.wav",
     "reference": "The full text that the speaker was supposed to read...",
     "language": "en"
   }'
   ```

   **Using API:**

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "audio=@/path/to/reading.wav" \
     -F 'reference=The full text that the speaker was supposed to read...' \
     -F "language=en"
   ```

## Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `audio` | file | Yes | Audio to transcribe (wav, mp3, flac, m4a, ...). |
| `reference` | string | Yes | Ground-truth script the audio is based on. |
| `language` | string | No | ISO code (`en`, `ko`, `ja`, ...). Auto-detect when omitted. |

## Output Format

A flat list of corrected segments. Extra keys from the STT output are
preserved on each segment.

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Reference wording that best matches the STT segment. |
| `start_time` | number | Segment start (seconds), taken from the STT. |
| `end_time` | number | Segment end (seconds), taken from the STT. |

Segments whose best reference match falls below `match_threshold` are
skipped rather than emitted with wrong text.

### Example

Reference:

```
Alice was beginning to get very tired of sitting by her sister on the bank
and of having nothing to do. Once or twice she had peeped into the book her
sister was reading, but it had no pictures or conversations in it.
```

STT (typos in bold):

```
Alis was begining to get very tired of siting by her sister on the bank
and of having nothing to do. Once or twise she had peeped into the book her
sister was reading, but it had no pictures or convertations in it.
```

Corrected output:

```json
[
  { "text": "Alice was beginning to get very tired of sitting by her sister on the bank and of having nothing to do.", "start_time": 0.0,  "end_time": 6.2 },
  { "text": "Once or twice she had peeped into the book her sister was reading, but it had no pictures or conversations in it.", "start_time": 6.2, "end_time": 12.8 }
]
```

## Component Details

### `stt` — Speech-to-Text

- Type: `model` (`task: speech-to-text`)
- Driver: `custom`, family `faster-whisper`
- Model: `Systran/faster-whisper-base` — pre-converted CTranslate2 weights
  on HuggingFace, auto-downloaded on first run (~150 MB). Swap for a
  larger, more accurate size: `Systran/faster-whisper-{small,medium,large-v3}`.
- Device: `cpu` (CTranslate2 has no Metal/MPS backend on macOS). Switch to
  `cuda` on NVIDIA.
- `compute_type: int8` — ~2× faster on CPU with a small quality drop.
  Other options: `int8_float16`, `float16`, `float32`, `default`.
- `return_timestamps: true` and `timestamp_level: segment` are required —
  the corrector needs `start_time` / `end_time` per segment.

### `corrector` — Transcript Corrector

- Type: `transcript-corrector`
- Driver: `native` (default)
- Alignment: per-segment anchor matching against a sliding window of the
  reference, scored with character-level Levenshtein similarity via
  `rapidfuzz`.
- Key options:
  - `granularity: word` for whitespace-delimited scripts, `character` for
    CJK / scripts without spaces.
  - `match_threshold: 0.5` — segments below this similarity are skipped.
  - `case_sensitive: false`, `ignore_punctuation: true` control
    normalization used only for scoring; the visible output preserves the
    reference's original casing and punctuation.

## Customization

### Running on NVIDIA GPU

```yaml
components:
  - id: stt
    ...
    device: cuda
    compute_type: float16       # or 'int8_float16' for lower VRAM
```

### Smaller / faster Whisper

```yaml
    model: Systran/faster-whisper-tiny     # or -base, -small, -medium, -large-v3
```

### CJK scripts (Chinese, Japanese without word spacing)

```yaml
  - id: corrector
    type: transcript-corrector
    action:
      ...
      granularity: character
      min_window_tokens: 12
```

### Strict matching (drop more ambiguous segments)

```yaml
      match_threshold: 0.7
```
