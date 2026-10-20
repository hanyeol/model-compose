# Music Score Loader Example

This example demonstrates how to use model-compose with the `music-score-loader` component to parse symbolic music files — MIDI (`.mid`/`.midi`) and MusicXML (`.xml`/`.musicxml`/`.mxl`) — into a `MusicScore` modeled on MusicXML `<score-partwise>`: notes grouped into parts (plus per-part lyrics and clefs) and score-level tempos, time/key signatures, and harmonies.

Use this when you have a reference melody or lead sheet as a file and want downstream components (pitch correction, synthesis, alignment) to consume it as structured data rather than as an opaque binary.

## Overview

This example provides 4 workflows:

1. **Load a Score File** (default) — auto-detect format from header or extension, emit every part in the score.
2. **Load a Specific Part** — pass an explicit `part` index. Useful for MIDI files where the parts list spans multiple tracks/channels, or for picking a single voice from a multi-part MusicXML score.
3. **Force MIDI Format** — bypass auto-detection and parse the input as MIDI, for files with stripped headers or non-standard extensions.
4. **Force MusicXML Format** — same, for MusicXML. Accepts both the uncompressed XML variant and the compressed `.mxl` ZIP container.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python dependencies are automatically installed on first run:
  - `mido` (used by the `local` driver for MIDI parsing). MusicXML parsing uses the Python standard library and needs no extra install.

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/music-score-loader
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
   - Upload a MIDI or MusicXML file
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Auto-detect format and return every part (default)
   model-compose run load-score --input '{"score": "/path/to/melody.mid"}'

   # Pick a specific part — handy when the file has multiple parts and you want just one
   model-compose run load-score-track --input '{
     "score": "/path/to/melody.mid",
     "part": 1
   }'

   # Treat an unknown-extension file as MIDI
   model-compose run load-score-as-midi --input '{"score": "/path/to/melody.bin"}'

   # Treat a compressed .mxl archive explicitly as MusicXML
   model-compose run load-score-as-musicxml --input '{"score": "/path/to/melody.mxl"}'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=load-score" \
     -F "score=@/path/to/melody.mid"
   ```

## Component Details

### Music Score Loader Component

- **Type**: `music-score-loader`
- **Purpose**: Parse MIDI/MusicXML files into a `MusicScore` — parts (notes/lyrics/clefs) plus score-level tempos, time/key signatures, and harmonies — so downstream components don't need format-specific logic.
- **Drivers**:
  - `local` — stdlib + `mido` based parsing (default)

For pitch estimation from *audio* (not symbolic scores), use [`pitch-estimator`](../../model-tasks/pitch-estimation/) instead. To consume the output of this loader as a reference melody during pitch correction, see [`music-pitch-corrector`](../music-pitch-corrector/).

## Workflow Details

### 1. Load a Score File

**ID**: `load-score`

Auto-detects the format from the file's magic bytes (`MThd` → MIDI, `<?xml` → MusicXML, `PK` → compressed `.mxl`) and falls back to the extension when the header is ambiguous. Every part in the file is returned — for MIDI, each `(track, channel)` combination with note activity becomes one part.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `score` | file | Yes | - | MIDI or MusicXML file to parse |

#### Example Output

```json
{
  "format": "midi",
  "duration": 1.5,
  "parts": [
    {
      "id": "T0_C0",
      "part_name": "Melody",
      "part_abbreviation": null,
      "midi_channel": 0,
      "midi_program": null,
      "notes": [
        { "start_time": 0.0, "end_time": 0.5, "pitch": 60, "velocity": 0.787 },
        { "start_time": 1.0, "end_time": 1.5, "pitch": 64, "velocity": 0.630 }
      ],
      "lyrics": [],
      "clefs": []
    }
  ],
  "tempos":          [{ "time": 0.0, "beats_per_minute": 120.0 }],
  "time_signatures": [{ "time": 0.0, "beats": 4, "beat_type": 4 }],
  "key_signatures":  [],
  "harmonies":       []
}
```

- `pitch` is a MIDI number (middle C = 60).
- `velocity` is normalized to [0, 1]; MusicXML lacks a universal dynamic and falls back to a fixed mezzo-forte value.
- `tempos`, `time_signatures`, `key_signatures` list every change point in order.
- `harmonies`, `clefs`, and lyric `syllabic`/`number` are MusicXML-only. MIDI loads leave them empty / `null`.

---

### 2. Load a Specific Part

**ID**: `load-score-track`

Picks exactly one part by zero-based index. Out-of-range indices raise an error rather than silently falling back.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `score` | file | Yes | - | MIDI or MusicXML file to parse |
| `part` | number | No | `0` | Zero-based part index |

Common cases:
- **Multi-channel MIDI**: each `(track, channel)` with note activity is a separate part — pick the index of the one you need.
- **MusicXML lead sheets**: usually a single `<part>`, so `part=0` is correct.
- **Multi-part MusicXML scores**: higher indices select additional voices (e.g. bass, harmony).

#### Example Output

Same shape as *Load a Score File*, with `parts` scoped to the chosen index.

---

### 3. Force MIDI Format

**ID**: `load-score-as-midi`

Skips format sniffing and parses the input as a Standard MIDI File. Fails loudly if the file is not actually MIDI, which is often preferable to a silent misdetection when you know the input contract.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `score` | file | Yes | - | File to parse as MIDI |

---

### 4. Force MusicXML Format

**ID**: `load-score-as-musicxml`

Skips format sniffing and parses the input as MusicXML. Both uncompressed (`.xml`/`.musicxml`) and compressed (`.mxl` ZIP) inputs are accepted — for `.mxl`, the loader reads the rootfile pointer in `META-INF/container.xml` and falls back to the first non-meta XML entry when that file is missing.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `score` | file | Yes | - | File to parse as MusicXML |

Only `score-partwise` layouts are supported — `score-timewise` is rejected with an error (fewer than 5% of real-world files use timewise).
