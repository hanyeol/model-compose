# Music Score Loader Component

The music score loader component reads a **symbolic music score file** — MIDI or MusicXML — and emits a normalized notes list plus tempo/time-signature metadata. Use it to feed a reference melody into [`music-pitch-corrector`](music-pitch-corrector.md), align lyrics to a score, or drive any pipeline that needs structured note data from a score file.

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
| `track` | integer | `null` | Track/part index to extract; defaults to the first track containing notes |
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
| MIDI | `.mid`, `.midi` | Type-0 and Type-1 (multi-track). Tempo map is folded across tracks so note times are consistent. |
| MusicXML | `.xml`, `.musicxml` | Score-partwise layout only. Score-timewise is rejected (used by <5% of real-world files). |
| MusicXML (compressed) | `.mxl` | ZIP container; reads the root score from `META-INF/container.xml`. |

#### Format Detection

The driver sniffs the file in this order:

1. **Magic bytes** — `MThd` for MIDI, `<?xml` prolog for MusicXML, `PK\x03\x04` ZIP header for `.mxl`.
2. **File extension** — fallback when magic bytes are absent (streams, uploads without extension).
3. **Explicit `format:`** — set when both of the above fail.

## Output Format

```python
{
  "notes": [
    {
      "start_time": 0.0,        # seconds from the start of the score
      "end_time":   0.5,         # seconds
      "pitch":      60,          # MIDI note number (0-127; middle C = 60)
      "velocity":   0.787,       # 0.0 to 1.0; MusicXML files default to 0.75
    },
    ...
  ],
  "tempo":          120.0,       # BPM (first tempo in the file)
  "time_signature": [4, 4],      # [numerator, denominator] or null if unspecified
  "format":         "midi",      # 'midi' or 'musicxml'
  "duration":       32.0,        # seconds; end_time of the last note
}
```

### Notes

- `pitch` is always a MIDI note number (integer). Microtonal MusicXML (`<alter>` with fractional values) is quantized to the nearest semitone.
- `velocity` is normalized to `[0.0, 1.0]`. MIDI velocities (0-127) are scaled; MusicXML — which lacks a universal dynamic — defaults to 0.75 (mf).
- `tempo` reports only the first tempo marker. Scores with tempo changes should be re-parsed by downstream consumers if the full tempo map is needed.
- `time_signature` reports only the first meter.

### Multi-Track Handling

By default, the loader picks the **first track that contains note-on events**. This matches the common structure of DAW-exported MIDI (track 0 is tempo map, track 1 is the lead melody).

To extract a specific track, set `track:`:

```yaml
action:
  source: ${input.score as file}
  track: 2            # 0-indexed
```

For MusicXML, `track` is the 0-indexed part number.

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
        melody: ${jobs.score.output.notes}

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

- [`music-pitch-corrector`](music-pitch-corrector.md) — Primary downstream consumer; `melody` field accepts this component's `notes` output
- [`subtitle-loader`](subtitle-loader.md) — Analogous component for subtitle files (SRT/VTT/ASS)
- [`music-transcription`](model.md) — For extracting notes from **audio** (basic-pitch, piano-transcription); use when you have a guide vocal rather than a score file

## Known Limitations

- Only **score-partwise** MusicXML is supported. Score-timewise files raise `ValueError`.
- **Tempo changes** are not preserved in the output; only the first tempo is reported.
- **ABC**, **MEI**, **Guido**, and other symbolic music formats are not implemented.
- MusicXML **articulations, slurs, dynamics, and lyrics** are discarded — only pitch and timing are kept.
