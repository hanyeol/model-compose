# Music Pitch Corrector Component

The music pitch corrector component applies **offline pitch correction** to a monophonic vocal recording — it maps each sung note to a target pitch (either the nearest note in a given scale, or a reference melody) and resynthesizes the audio with the corrected f0 while preserving timbre.

Correction is split into two stages so a correction curve can be inspected or hand-edited between planning and resynthesis:

1. `plan` — takes a pitch track (from [`music-pitch-estimation`](model.md) or any compatible estimator), picks a target pitch per note, and emits a JSON correction curve.
2. `apply` — takes an audio recording plus a curve and resynthesizes it.
3. `correct` — a convenience that runs plan + apply back-to-back when no manual curve editing is needed.

Pitch estimation lives outside this component. Use [`music-pitch-estimation`](model.md) (PESTO, pYIN, etc.) to produce the pitch track and feed its `frames` output into `plan` or `correct`.

## Basic Configuration

```yaml
component:
  type: music-pitch-corrector
  action:
    method: correct
    audio: ${input.vocal}
    pitch: ${jobs.pitch.output.frames}
    key: ${jobs.key.output.key}
    scale: ${jobs.key.output.mode}
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `music-pitch-corrector` |
| `driver` | string | `world` | Resynthesis engine (currently only `world`) |
| `frame_period` | duration | `5ms` | Analysis hop for the vocoder (dio/harvest, cheaptrick, d4c) |
| `f0_estimator` | string | `dio` | WORLD F0 extractor used during resynthesis analysis: `dio` (fast) or `harvest` (robust on breathy/growling input) |
| `actions` | array | `[]` | List of correction actions |

### Action Configuration (Common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | `plan`, `apply`, or `correct` |
| `batch_size` | integer | `null` | Number of inputs processed per batch when `audio` or `pitch` is a list/stream |
| `output` | string | `null` | Output template applied to the result |

### `method: plan`

Build a correction curve from a pitch track. No audio input — the recording is only needed at `apply` time.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pitch` | dict \| string | **required** | Pitch frames from `music-pitch-estimation` (or a compatible estimator) |
| `mode` | string | `scale` | How target pitches are chosen: `scale` (snap to a key) or `melody` (follow a reference melody) |
| `key` | string | `null` | Tonic for `mode: scale` (e.g. `A`, `F#`, `Bb`). Required when `mode: scale` |
| `scale` | string \| list[int] | `major` | Scale name (`major`, `minor`, `chromatic`) or a custom pitch-class list `[0, 3, 7]`. Only used when `mode: scale` |
| `melody` | list | `null` | Reference melody as a list of `{start_time, end_time, pitch}` records. Required when `mode: melody` |
| `melody_offset` | duration | `0ms` | Start-time offset between the reference melody and the recording |
| `align` | string | `null` | Per-note time alignment strategy for `mode: melody`: `dtw` or omit for no alignment |
| `overrides` | list | `null` | Per-note or per-span manual edits applied after target selection |
| `return_frames` | bool | `true` | Include dense per-frame arrays in the emitted curve. Set to `false` for a notes-only curve |
| `params` | object | `{}` | Correction algorithm tuning (see below) |

### `method: apply`

Resynthesize a vocal from a curve. The curve must come from a `plan` run on the **same recording** — curve length and audio length must match within 5%.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `curve` | dict \| string | **required** | Correction curve from `plan`, optionally hand-edited |
| `audio` | any | **required** | Vocal recording to resynthesize |
| `sample_rate` | integer | `null` | Output sample rate; defaults to the input's native rate |
| `formant_shift` | float | `0.0` | Formant shift in semitones; `0` keeps the original timbre. Positive values stretch formants up (perceived smaller vocal tract) |

### `method: correct`

Run plan + apply in one call. Takes every `plan` field plus every `apply` field.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pitch` | dict \| string | **required** | Pitch frames (as `plan`) |
| `audio` | any | **required** | Vocal recording (as `apply`) |
| `return_curve` | bool | `false` | Also emit the computed curve alongside the audio |

Plus all `plan` fields (`mode`, `key`, `scale`, `melody`, `melody_offset`, `align`, `overrides`, `return_frames`, `params`) and `apply` fields (`sample_rate`, `formant_shift`).

### `params` — Correction Algorithm Tuning

Shared by `plan` and `correct`. All fields have sensible defaults; override only as needed.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strength` | float | `0.8` | Pull factor toward the target pitch (`0.0` leaves the note untouched; `1.0` is full correction) |
| `retune_speed` | duration | `40ms` | Time constant for the one-pole LPF that smooths per-note shifts into a frame-level curve. `0ms` is the robotic Auto-Tune effect; `40ms`–`80ms` sounds natural |
| `tolerance_cents` | float | `10.0` | Deviations within this many cents of a target are left untouched |
| `max_correction_cents` | float | `250.0` | Notes farther than this from any target are treated as out of range |
| `out_of_range` | string | `keep` | How to handle out-of-range notes: `keep` leaves them untouched; `snap` forces the nearest allowed note anyway |
| `preserve_vibrato` | bool | `true` | Move only the note's center pitch and leave intra-note vibrato (~4-8Hz) intact |
| `transition` | duration | `60ms` | Edge window at note boundaries where the representative-pitch calculation ignores the ramp |
| `min_note_duration` | duration | `80ms` | Fragments shorter than this are merged with their neighbour during segmentation |
| `min_confidence` | float | `0.5` | Pitch frames below this confidence are excluded from the plan |
| `reference_pitch` | float | `440.0` | Reference frequency for A4 in Hz |

## Supported Drivers

### World

Resynthesis via the [WORLD vocoder](https://github.com/mmorise/World) through [pyworld](https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder). WORLD decomposes a vocal into (f0, spectral envelope, aperiodicity), rewrites f0 along the correction curve, and resynthesizes — keeping formants (vowel colour, singer identity) structurally intact.

```yaml
component:
  type: music-pitch-corrector
  driver: world
  frame_period: 5ms
  f0_estimator: dio
```

**Auto-installed dependencies:** `pyworld`, `numpy`, `soxr`, `soundfile`, `librosa`

#### Notes

- `pyworld` ships as sdist and needs a C compiler if no pre-built wheel is available for your platform. Pair with `runtime: virtualenv` on compiler-less hosts.
- WORLD is a batch vocoder — the analysis step must see the whole signal — so this driver reads the entire input before emitting output. The emitted result is streamed in 1-second chunks for downstream consumers.
- Multi-channel inputs are downmixed to mono before analysis.
- `dio` is fast and accurate on clean monophonic vocals; swap to `harvest` for breathy or growling input where `dio` under-tracks the fundamental.

## Correction Curve Format

The curve emitted by `plan` is the sole handoff to `apply`. Edit the JSON between stages to override specific notes without re-planning.

```python
{
  "version":         1,
  "reference_pitch": 440.0,
  "frame_period":    0.005,
  "settings": {
    "mode":         "scale",
    "key":          "A",
    "scale":        "minor",
    "strength":     0.8,
    "retune_speed": 0.04,
  },
  "notes": [
    {
      "index":            0,
      "start_time":       12.340,
      "end_time":         12.910,
      "sung_pitch":       57.35,     # MIDI note (semitone), what the singer produced
      "target_pitch":     57.0,       # MIDI note the planner mapped them to; null to leave untouched
      "correction_cents": -35.0,
      "status":           "corrected",
    },
    {
      "index":            1,
      "start_time":       12.950,
      "end_time":         13.300,
      "sung_pitch":       61.80,
      "target_pitch":     null,
      "correction_cents": 0.0,
      "status":           "out_of_range",
    },
    ...
  ],
  "frames": {
    "time":        [0.0, 0.005, ...],
    "f0":          [57.35, 57.35, ...],   # per-frame observed pitch (MIDI note)
    "shift_cents": [-35.0, -34.8, ...],   # per-frame correction, after smoothing
  },
}
```

### Note Status Values

| Status | Meaning |
|--------|---------|
| `corrected` | Note was shifted toward a target pitch |
| `within_tolerance` | Note was close enough to a target to leave untouched |
| `out_of_range` | Note was farther than `max_correction_cents` from any allowed target |

### Hand-Editing a Curve

Edit the JSON between `plan` and `apply` to override planner choices:

- **Change a target** — update `target_pitch` to a different MIDI note.
- **Keep a note untouched** — set `target_pitch` to `null` and `correction_cents` to `0.0`.
- **Drop a note** — remove its entry entirely. `apply` reconstructs per-frame shifts from whatever notes remain.

The `frames` block is derived from `notes` + the observed f0, so it is safe to leave untouched when editing notes. If you remove `frames`, `apply` falls back to a step curve derived from the notes alone (coarser than the smoothed curve but still works).

## Output Format

### `plan`

```python
{
  "curve":  { ... },   # See "Correction Curve Format" above
  "report": {
    "notes_total":              34,
    "notes_corrected":          28,
    "notes_within_tolerance":    4,
    "notes_out_of_range":        2,
    "voiced_ratio":             0.78,
    "mean_abs_correction_cents": 18.4,
    "max_correction_cents":     72.1,
    "warnings":                 [],
  },
}
```

### `apply`

```python
{
  "audio":  <AudioStreamResource>,   # 1-second chunk stream
  "report": {
    "notes_total":     34,
    "notes_corrected": 28,
    "warnings":        [],
  },
}
```

### `correct`

```python
{
  "audio":  <AudioStreamResource>,
  "report": { ... },     # Merged plan + apply report
  "curve":  { ... },     # Only when `return_curve: true`
}
```

## Full Workflow Example

```yaml
workflow:
  jobs:
    - id: pitch
      component: pitch-estimator        # model / music-pitch-estimation / pesto
      input:
        audio: ${input.vocal as audio}
        pitch_unit: semitone

    - id: key
      component: analyzer               # music-analyzer
      action: key
      input:
        audio: ${input.accompaniment as audio}

    - id: tune
      component: tuner
      action: correct
      depends_on: [ pitch, key ]
      input:
        audio: ${input.vocal as audio}
        pitch: ${jobs.pitch.output.frames}
        key: ${jobs.key.output.key}
        scale: ${jobs.key.output.mode}
        params:
          strength: 0.8
          retune_speed: 40ms

    - id: mix
      component: mixer                  # audio-mixer
      action: mix                       # method: overlay
      depends_on: [ tune ]
      input:
        audio: ${jobs.tune.output.audio}
        overlay: ${input.accompaniment as audio}
        placement:
          gain: 0.7
      output: ${output as file}

components:
  - id: pitch-estimator
    type: model
    task: music-pitch-estimation
    driver: custom
    family: pesto
    model: mir-1k_g7

  - id: analyzer
    type: music-analyzer
    actions:
      - id: key
        metric: key
        audio: ${input.audio as file}

  - id: tuner
    type: music-pitch-corrector
    driver: world
    frame_period: 5ms
    f0_estimator: dio
    actions:
      - id: correct
        method: correct

  - id: mixer
    type: audio-mixer
    driver: ffmpeg
    actions:
      - id: mix
        method: overlay
```

## Related Components

- [`music-pitch-estimation`](model.md) — Produces the `pitch.frames` input (PESTO, pYIN, etc.)
- [`music-analyzer`](music-analyzer.md) — Detects key/mode to feed `plan.key` + `plan.scale`
- [`music-score-loader`](music-score-loader.md) — Loads a reference melody from MIDI/MusicXML and feeds it to `plan.melody`
- [`audio-processor`](audio-processor.md) — For fixed-semitone pitch shifts (no note-aware correction), use the `pitch-shift` method
- [`audio-mixer`](audio-mixer.md) — Mix the corrected vocal back with the accompaniment

## Known Limitations

- **Monophonic input only.** Chord vocals (two singers on one mic) collapse to the dominant pitch — the segmentation step assumes a single melodic line.
- **Reference melody loading** supports MIDI and MusicXML via [`music-score-loader`](music-score-loader.md). ABC/MEI/Guido are not implemented.
- **DTW alignment is defined in the schema but not yet implemented.** Setting `align: dtw` currently has no effect — the planner uses the raw time axis.
- **Resynthesized breaths and consonants** can sound slightly smoother than the original. If texture matters, mix the dry take back in under the corrected regions with [`audio-mixer`](audio-mixer.md).
