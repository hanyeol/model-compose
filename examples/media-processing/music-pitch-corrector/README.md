# Music Pitch Corrector Example

This example demonstrates how to use model-compose with the `music-pitch-corrector` component to apply offline pitch correction to a recorded vocal — detect its pitch, snap each note to the song's key, and resynthesize while preserving timbre.

## Overview

Correction runs in two stages so you can inspect or edit the result in the middle:

1. **plan** — pick a target pitch for each sung note from a pitch track and build a correction curve (JSON). Takes only `pitch`, not the recording.
2. **apply** — resynthesize the vocal along the curve. Takes the recording (`audio`) and the curve. The curve is the sole handoff from plan; nothing in the audio pipeline is implicit.

The default `correct-pitch` workflow runs both at once (needs both `audio` and `pitch`). The other workflows expose the split path — plan-only variants emit the curve as JSON, and `apply-curve` takes an edited curve back for resynthesis.

`audio` always means "the recording to resynthesize" — never a pitch estimation source. Pitch estimation happens in a separate component (`music-pitch-estimation`), so `plan` is engine-agnostic and never silently falls back to a built-in estimator.

### Workflows

1. **Correct Vocal Pitch** (default) — pitch estimation → key detection → curve planning → WORLD resynthesis → mix with accompaniment. Targets are picked by snapping each sung note to the song's detected key.
2. **Plan a Correction Curve** — same path as `correct-pitch` without resynthesis; emits the curve as JSON so you can hand-edit note targets or bypass specific notes before feeding it to `apply-curve`.
3. **Correct Vocal Pitch to Reference Melody** — upload a melody file (`.mid`, `.midi`, `.xml`, `.musicxml`, or `.mxl`) alongside the vocal; `music-score-loader` extracts the notes, pitch estimation runs on the vocal, each sung note is snapped to its matching reference note, WORLD resynthesizes, and the result is mixed with the accompaniment. Use this when you have the song's intended melody (hand-authored MIDI, exported from a notation editor, etc.) and want each sung note mapped to its specific reference note rather than to the nearest scale tone.
4. **Plan a Correction Curve from a Reference Melody** — same melody-loading path, but emits the curve as JSON without resynthesis for hand editing.
5. **Apply an Edited Curve** — resynthesizes a vocal from an edited `plan-only` or `plan-with-melody` curve, so curve edits actually make it into the output.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python dependencies are automatically installed on first run:
  - `pyworld`, `librosa`, `numpy`, `soundfile` (used by the `world` driver)
- `pyworld` builds from source if no pre-built wheel exists for your platform, so a C compiler must be available.

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/music-pitch-corrector
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   On first start the service installs `pyworld`, `librosa`, and friends, which may take a minute if `pyworld` has to compile from sdist.

2. **Open the Web UI:**
   Visit `http://localhost:8081` and pick a workflow. The default form expects a vocal and an accompaniment file.

3. **Call the API directly:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
        -F vocal=@vocal.wav \
        -F accompaniment=@backing.wav \
        -F strength=0.8
   ```

## Correction Behavior

Algorithm tuning lives under `params:` (default-reasonable, override as needed):

- **params.strength** controls how far each note is pulled toward the target. `1.0` is full correction; `0.6` leaves some character.
- **params.retune_speed** sets how quickly a sung note slides to its target. `0ms` is the robotic Auto-Tune effect; `40ms`–`80ms` sounds natural.
- **params.tolerance_cents** leaves notes within this many cents of a target untouched. Raise it on expressive singing; lower it on tight studio takes.
- **params.preserve_vibrato** keeps intra-note wobble intact by moving only the note's center pitch. Disable to flatten everything to the target.

## Curve Format

The curve emitted by `plan` has two parts: a `notes` array (one entry per detected note) and a `frames` block (dense per-frame arrays). Edit the JSON directly between `plan` and `apply` to override individual notes — change a `target_pitch`, set `target_pitch: null` to leave a note alone, or drop a note entirely to keep its original pitch.

## Known Limitations

- Resynthesized breaths and growls can sound slightly smoother than the original. Mix in the dry take under corrected regions if you need the texture back.
- Chord vocals (two singers on one mic) will be collapsed to the dominant pitch — this component assumes a single melodic line.
- Reference melody loading supports MIDI and MusicXML files; other formats (ABC, MEI, Guido) are not implemented. Pass them through a converter first, or supply a pre-built notes list.
