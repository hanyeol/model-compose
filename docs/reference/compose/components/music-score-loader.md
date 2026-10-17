# Music Score Loader Component

The music score loader component reads a **symbolic music score file** — MIDI or MusicXML — and emits a `MusicScore`: notes grouped into parts plus score-level tempos, time/key signatures, and harmonies, modeled on MusicXML `<score-partwise>`. Use it to feed a reference melody into [`music-pitch-corrector`](music-pitch-corrector.md), align lyrics to a score, or drive any pipeline that needs structured note data from a score file.

For audio-level transcription (audio → notes), use the `music-transcription` model task (basic-pitch, piano-transcription) instead. This component is purely for parsing already-symbolic data.

## Basic Configuration

```yaml
component:
  type: music-score-loader
  action:
    source: ${input.score as file}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `music-score-loader` |
| `driver` | string | `local` | Loader backend (currently only `local`) |
| `actions` | array | `[]` | List of load actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | any | **required** | Score file source: file path, upload stream, raw bytes, or variable reference |
| `format` | string | `null` | Score format (`midi` or `musicxml`); inferred from file content/extension when omitted |
| `part` | integer | `null` | Part index to extract; defaults to all parts in the score |
| `batch_size` | integer | `null` | Number of sources processed per batch |
| `output` | string | `null` | Output template applied to the parsed result |

## Supported Drivers

### Local

Reads score files directly from disk or an upload stream. MIDI parsing uses [mido](https://mido.readthedocs.io/); MusicXML parsing uses stdlib `xml.etree` (no music21 dependency).

```yaml
component:
  type: music-score-loader
  driver: local
```

**Auto-installed dependencies:** `mido`

#### Supported Formats

| Format | Extensions | Notes |
|--------|------------|-------|
| MIDI | `.mid`, `.midi` | Type-0 and Type-1 (multi-track). Each `(track, channel)` with note activity becomes one part; tempo/time-signature/key-signature maps are folded across tracks so per-part note times stay consistent. |
| MusicXML | `.xml`, `.musicxml` | Score-partwise layout only. Score-timewise is rejected (used by <5% of real-world files). |
| MusicXML (compressed) | `.mxl` | ZIP container; reads the root score from `META-INF/container.xml`. |

#### Format Detection

The driver sniffs the file in this order:

1. **Magic bytes** — `MThd` for MIDI, `<?xml` prolog for MusicXML, `PK\x03\x04` ZIP header for `.mxl`.
2. **File extension** — fallback when magic bytes are absent (streams, uploads without extension).
3. **Explicit `format:`** — set when both of the above fail.

## Output Format

The loader emits a `MusicScore` dict modeled on MusicXML `<score-partwise>`. MIDI loads populate the subset of fields MIDI can carry; MusicXML-only fields (`harmonies`, lyric `syllabic`/`number`, `clefs`) are left as `[]` or `null`.

```python
{
  "format":   "midi",            # 'midi' or 'musicxml'
  "duration": 32.0,              # seconds; end_time of the last note across all parts
  "parts": [
    {
      "id":                "P1",            # <score-part id> or synthesized "T{track}_C{channel}" for MIDI
      "part_name":         "Melody",        # <part-name> or MIDI track name
      "part_abbreviation": None,
      "midi_channel":      0,
      "midi_program":      53,
      "notes": [
        {
          "start_time": 0.0,     # seconds from the start of the score
          "end_time":   0.5,
          "pitch":      60,      # MIDI note number (0-127; middle C = 60)
          "velocity":   0.787,   # 0.0 to 1.0; MusicXML files default to 0.75
        },
        ...
      ],
      "lyrics": [                # per-note; MIDI loads leave `syllabic`/`number` as None
        {"note_index": 0, "text": "do", "syllabic": "single", "number": 1},
      ],
      "clefs": [                 # [] for MIDI loads
        {"time": 0.0, "sign": "G", "line": 2, "staff": 1},
      ],
    },
  ],
  "tempos":          [{"time": 0.0, "beats_per_minute": 120.0}, ...],
  "time_signatures": [{"time": 0.0, "beats": 4, "beat_type": 4}, ...],
  "key_signatures":  [{"time": 0.0, "fifths": 0, "mode": "major"}, ...],
  "harmonies": [                 # [] for MIDI loads
    {"time": 0.0, "part_id": "P1",
     "root_step": "C", "root_alter": 0, "kind": "major",
     "bass_step": None, "bass_alter": None},
  ],
}
```

### Notes

- `pitch` is always a MIDI note number (integer). Microtonal MusicXML (`<alter>` with fractional values) is quantized to the nearest semitone.
- `velocity` is normalized to `[0.0, 1.0]`. MIDI velocities (0-127) are scaled; MusicXML — which lacks a universal dynamic — defaults to 0.75 (mf).
- `tempos`, `time_signatures`, `key_signatures` list every change point, in order. `tempos` always has at least one entry (defaulting to 120 BPM when the file is silent).
- `harmonies`, `clefs`, and lyric `syllabic`/`number` are MusicXML-only. MIDI loads leave them empty / `None`.

### Multi-Part Handling

By default, the loader returns **every part** in the score. For MIDI, each `(track, channel)` combination with note activity becomes one part — this preserves GM conventions (channel 10 = drums) and handles Format-0 (one track, many channels) and Format-1 (one track per instrument) uniformly.

To extract a single part, set `part:` to its index in the parts list:

```yaml
action:
  source: ${input.score as file}
  part: 2             # 0-indexed part
```

## Example Workflow

Load a MIDI melody and feed it to [`music-pitch-corrector`](music-pitch-corrector.md):

```yaml
workflow:
  jobs:
    - id: pitch
      component: pitch-estimator
      input:
        audio: ${input.vocal as audio}

    - id: score
      component: score-loader
      input:
        source: ${input.melody as file}

    - id: tune
      component: tuner
      action: correct
      depends_on: [ pitch, score ]
      input:
        audio: ${input.vocal as audio}
        pitch: ${jobs.pitch.output.frames}
        mode: melody
        melody: ${jobs.score.output.parts[0].notes}

components:
  - id: pitch-estimator
    type: model
    task: music-pitch-estimation
    driver: custom
    family: pesto
    model: mir-1k_g7

  - id: score-loader
    type: music-score-loader
    driver: local
    action:
      source: ${input.source as file}

  - id: tuner
    type: music-pitch-corrector
    driver: world
```

## Related Components

- [`music-pitch-corrector`](music-pitch-corrector.md) — Primary downstream consumer; `melody` field accepts a part's `notes` list
- [`subtitle-loader`](subtitle-loader.md) — Analogous component for subtitle files (SRT/VTT/ASS)
- [`music-transcription`](model.md) — For extracting notes from **audio** (basic-pitch, piano-transcription); use when you have a guide vocal rather than a score file

## Known Limitations

- Only **score-partwise** MusicXML is supported. Score-timewise files raise `ValueError`.
- **ABC**, **MEI**, **Guido**, and other symbolic music formats are not implemented.
- MusicXML **articulations, slurs, dynamics, and ties** are discarded — notes carry only pitch, timing, and lyrics.
- MIDI loads leave MusicXML-only fields (`harmonies`, `clefs`, lyric `syllabic`/`number`) empty; MIDI's `key_signature` meta is translated into `key_signatures` entries.
