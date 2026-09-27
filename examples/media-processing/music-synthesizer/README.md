# Music Synthesizer Example

This example demonstrates the `music-synthesizer` component — a beat-timeline sequencer that renders a stereo WAV from a score. There is no audio input; the whole piece is described in a JSON score of tracks, beat-anchored events, master shaping, and sidechain ducking.

## Overview

This example exposes a single workflow, **Bake Soundtrack From Score**, wired as a two-job pipe:

1. **Load Score** — a `file-store` job reads the score JSON next to the compose file and parses it into fields.
2. **Bake** — the `music-synthesizer` job feeds every field straight through to the `sequence` action and returns a WAV stream.

Every parameter the synth understands (bpm, beats, seed, tracks, master, sidechain) lives in the score JSON, so swapping `score.json` for a different score is enough to bake a different track without touching the compose file.

The bundled `score.json` is a 32-beat, 128 BPM demo: a four-beat count-in, a kick/hat/snare groove, an 8-beat snare build, a whoosh transition, a two-bar drop, kick-driven sidechain ducking on pad/hats/fx, and a final fade.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python dependencies are automatically installed on first run:
  - `numpy`, `scipy` (used by the `native` driver)

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/music-synthesizer
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
   - Leave `score_path` blank to use the bundled `score.json`, or point it at a different score file
   - Click "Run Workflow" and preview the WAV inline

   **Using CLI:**
   ```bash
   # Bake the bundled demo score
   model-compose run bake-soundtrack --input '{}'

   # Bake a different score sitting next to the compose file
   model-compose run bake-soundtrack --input '{
     "score_path": "my-score.json"
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=bake-soundtrack"
   ```

## Component Details

### Music Synthesizer Component

- **Type**: `music-synthesizer`
- **Driver**: `native` (numpy + scipy)
- **Purpose**: Render a stereo WAV from a beat-anchored score of tracks and events, then apply sidechain ducking and a master chain (soft-clip → normalize → silences → fades).

The action always returns a WAV `audio`. For post-processing an existing audio use [`audio-processor`](../audio-processor/); to combine several audios use [`audio-mixer`](../audio-mixer/).

### File Store Component

- **Type**: `file-store`
- **Driver**: `local`
- **Purpose**: Read the score JSON from the example directory. `${output.content as json}` parses the raw bytes into a dict that the second job can index by field name.

## Score Format

The score JSON is a direct 1:1 mirror of the `sequence` action's fields. It is passed field-by-field into the synth by the compose file; nothing is renamed on the way.

### Top-level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bpm` | number | Yes | Tempo in beats per minute; drives every beat-to-time conversion |
| `beats` | number | Yes | Total length of the piece in beats |
| `seed` | integer | No | Random seed for reproducible noise-based instruments; omit for non-deterministic output |
| `tracks` | array | Yes | Tracks whose events make up the mix |
| `master` | object | No | Master-bus shaping — soft-clip, normalization, silences, fades |
| `sidechain` | object | No | Kick-driven ducking applied before summing |

### Track Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | required | Track identifier; referenced by `sidechain.trigger` and `sidechain.targets` |
| `gain` | number | `1.0` | Linear gain multiplier for the whole track |
| `pan` | number -1..1 | `0.0` | Stereo pan for the whole track |
| `events` | array | `[]` | Events rendered onto this track |

### Event Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `beat` | number \| array \| `{start, end, step, phase}` | required | Beat position(s) this event fires at |
| `instrument` | string | required | Instrument voice — `kick`, `snare`, `hat`, `tick`, `tom`, `pop`, `whoosh`, `chord`, `sub-bass`, `sine`, `noise-burst` |
| `length` | number | `null` | Beat length for sustained instruments (`chord`, `sine`, `sub-bass`, `whoosh`, `noise-burst`); ignored by transient hits |
| `gain` | number | `1.0` | Linear gain multiplier for this event |
| `pan` | number -1..1 | `0.0` | Stereo pan for this event; combined with the track pan |
| `params` | object | `{}` | Instrument-specific parameters |

`beat` accepts three shapes:
- A single number — the event fires once at that beat
- A list of numbers — the event fires at each listed beat
- A `{start, end, step, phase}` object — the event fires at `start + n*step + phase` for every `n` such that the position is `< end`

### Master Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `soft_clip` | number | `1.2` | Pre-tanh drive amount for the soft-clip stage; `0` disables clipping |
| `normalize_level` | number \| null | `-1.0` | Target peak in dBFS after normalization; `null` disables it |
| `silences` | array | `[]` | Hard-silence windows applied after mastering |
| `fades` | array | `[]` | Fade windows applied after mastering |

### Sidechain Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `trigger` | string | required | Track id whose events open the ducking envelope |
| `targets` | array of strings | required | Track ids attenuated on each trigger hit |
| `depth` | number 0..1 | `0.78` | Peak gain reduction per hit (`0` = no ducking, `1` = full mute) |
| `attack_time` | duration | `2ms` | Time to reach peak reduction |
| `release_time` | duration | `70ms` | Time to recover to unity |

## Workflow Details

### Bake Soundtrack From Score

**ID**: `bake-soundtrack`

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `score_path` | string | No | `score.json` | Path to a score JSON, relative to the example directory |

#### Output

| Field | Type | Description |
|-------|------|-------------|
| `audio` | audio | Rendered stereo WAV of the whole piece |

## Customization

### Baking a Different Score

Drop a new JSON file next to the compose file and point `score_path` at it. The compose file is a pure pipe — every top-level field of the score is threaded into `sequence` verbatim, so no compose changes are needed to switch scores.

```bash
model-compose run bake-soundtrack --input '{"score_path": "my-score.json"}'
```

### Instrument Reference

Every event names an `instrument`. The synth ships with 11 built-in voices:

- **Transient hits** (`length` ignored): `kick`, `snare`, `hat`, `tick`, `tom`, `pop`
- **Sustained voices** (`length` in beats): `chord`, `sub-bass`, `sine`, `whoosh`, `noise-burst`

See the [`music-synthesizer` component reference](../../../docs/reference/compose/components/music-synthesizer.md) for each voice's `params`.

### Sidechain Ducking

The bundled score ducks `pad`, `hats`, and `fx` on every kick. Remove the `sidechain` block to keep everything at full level, or point `trigger` at a different track (e.g. the `snares` track) to hear the effect from the snare instead.

### Master Chain

`master.soft_clip` drives a tanh clipper; higher values glue the mix but crush transients. `master.normalize_level` sets the final peak in dBFS — set it to `null` to keep the raw sum. Use `silences` and `fades` for hard cuts and tail fades on the master bus after mixing.

## Tips

- **Score is the whole thing**: everything that shapes the output — tempo, length, tracks, master, sidechain — lives in the score JSON. The compose file itself never needs to change to bake a different track.
- **Reproducible noise**: set `seed` when you want deterministic snares/hats/whoosh output between runs.
- **Beat patterns beat lists**: `{ start, end, step }` is easier to edit than long beat lists for repeating rhythms, and easier to phase-shift with `phase`.
- **Sustained vs transient**: `length` is only read by sustained voices. Setting it on a `kick` is harmless but has no effect.
- **Sidechain routing needs valid ids**: `trigger` and every `targets` entry must match an existing `id` on `tracks`, otherwise the score fails validation.

## Troubleshooting

### Common Issues

1. **`bpm must be positive`** / **`beats must be positive`**: A non-positive tempo or length isn't a valid score. Set both to a positive number.
2. **`channels must be 1 or 2`**: The synth writes mono or stereo WAV only. Anything else is rejected.
3. **`Duplicate track ids`**: Every entry in `tracks[].id` must be unique — sidechain routing and diagnostics rely on it.
4. **`Sidechain trigger '...' does not match any track id`** / **`Sidechain targets not found among tracks`**: Fix the id typos in the `sidechain` block or add the missing track.
5. **`Beat-pattern step must be positive`**: A `{ start, end, step }` beat pattern needs `step > 0`. Use `phase` to offset without a negative step.
6. **Silent output at the end**: Check `master.silences` — a hard-silence window past the last event will look like the render "cut off".
7. **Score file not found**: `score_path` is resolved relative to the example directory (via the `file-store`'s `base_path: .`). Pass a filename that sits next to `model-compose.yml`, not an absolute path unless you widen `base_path`.
