# Music Synthesizer Component

The music synthesizer component builds a stereo mix from scratch on a beat-timeline sequencer — no audio input, only a score. Each track owns a list of beat-anchored events, every event names an **instrument voice** (kick, snare, hat, chord, whoosh, ...) plus per-event gain/pan/length/params. The engine renders each track, applies kick-driven sidechain ducking, and runs a master chain (soft-clip → normalize → silences → fades) before emitting a WAV stream.

Use it to lay a rhythm track under an AI-generated video, produce click-tracks and stingers for demos, or bake procedural drops next to model-generated music. For post-processing an existing audio, use [`audio-processor`](audio-processor.md); to combine several audios, use [`audio-mixer`](audio-mixer.md).

## Basic Configuration

```yaml
component:
  type: music-synthesizer
  driver: native
  action:
    method: sequence
    bpm: 128
    beats: 32
    tracks:
      - id: kicks
        events:
          - beat: { start: 0, end: 16, step: 1 }
            instrument: kick
      - id: pad
        events:
          - beat: 0
            instrument: chord
            length: 4
            params: { notes: [A3, C4, E4, A4], cutoff: 900 }
            gain: 0.3
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `music-synthesizer` |
| `driver` | string | `native` | Synthesis backend (currently only `native`) |
| `actions` | array | `[]` | List of synthesis actions |

### Common Action Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Synthesis operation; currently only `sequence` |
| `streaming` | boolean \| string | `false` | If true, the synthesized output is emitted as a byte stream instead of a temporary file |

The action always returns a raw PCM stream (16-bit signed little-endian, at the configured `sample_rate` and `channels`). Consume it as an `audio` value directly, or pipe it into `audio-converter` if you need `mp3`/`flac`/etc.

## Sequence Method

Renders a piece from a beat-anchored score.

```yaml
action:
  method: sequence
  bpm: 128
  beats: 32
  seed: 128
  tracks: [ ... ]
  master: { ... }
  sidechain: { ... }
```

### Sequence Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bpm` | float \| string | **required** | Tempo in beats per minute. Drives every beat-to-time conversion in the piece |
| `beats` | float \| string | **required** | Total length of the piece in beats |
| `sample_rate` | integer \| string | `48000` | Output sample rate in Hz (e.g., `44100`, `48000`) |
| `channels` | integer \| string | `2` | Output channel count — `1` (mono) or `2` (stereo) |
| `seed` | integer \| string | `null` | Random seed for reproducible noise-based instruments. Omit for non-deterministic output |
| `tracks` | array | **required** | Tracks whose events make up the mix. See [Tracks & Events](#tracks--events) |
| `master` | object | one default | Master-bus soft-clip, normalization, silence and fade shaping. See [Master](#master) |
| `sidechain` | object | `null` | Kick-driven ducking applied to selected tracks before summing. See [Sidechain](#sidechain) |

## Tracks & Events

Each **track** is an independent bus that renders its events onto a private buffer; buses are summed after optional sidechaining. Track ids must be unique — validation fails otherwise.

### Track Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | string | **required** | Track identifier used by sidechain routing and diagnostics |
| `gain` | number \| string | `1.0` | Linear gain multiplier applied to the whole track |
| `pan` | number \| string | `0.0` | Stereo pan applied to the whole track, from `-1.0` (full left) to `1.0` (full right) |
| `events` | array | `[]` | Events rendered onto this track |

### Event Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `beat` | number \| array \| pattern | **required** | Beat position(s) this event fires at. See [Beat Positions](#beat-positions) |
| `instrument` | string | **required** | Instrument voice — see [Instruments](#instruments) |
| `length` | number \| string | `null` | Beat length used by sustained instruments (`chord`, `sine`, `sub-bass`, `whoosh`, `noise-burst`). Ignored by transient hits (`kick`, `snare`, `hat`, ...) |
| `gain` | number \| string | `1.0` | Linear gain multiplier for this event |
| `pan` | number \| string | `0.0` | Stereo pan for this event, from `-1.0` to `1.0`. Combined with the track pan |
| `params` | object | `{}` | Instrument-specific parameters — see [Instruments](#instruments) |

### Beat Positions

`beat` accepts three shapes:

**Single beat**

```yaml
beat: 4
```

**Explicit list**

```yaml
beat: [4, 5, 6, 7]
```

**Pattern object** — expands to `[start, start+step, ...]` while below `end`:

```yaml
beat: { start: 4, end: 20, step: 2 }        # 4, 6, 8, 10, 12, 14, 16, 18
beat: { start: 4, end: 20, step: 0.5 }      # 8th-note grid
beat: { start: 4, end: 20, step: 1, phase: 0.5 }  # 4.5, 5.5, 6.5, ...
```

| Pattern Field | Type | Default | Description |
|-------|------|---------|-------------|
| `start` | float \| string | **required** | First beat position emitted (inclusive) |
| `end` | float \| string | **required** | Beat position the pattern stops before (exclusive) |
| `step` | float \| string | `1.0` | Beat interval between successive events (must be positive) |
| `phase` | float \| string | `0.0` | Beat offset added to every emitted position |

## Instruments

Every event names one of the following instruments. Extra tuning is passed through `params`. Instruments that draw noise from the RNG are reproducible when `seed` is set on the sequence.

### `kick`

Sine-body kick with a rapidly falling pitch and a short click transient.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `big` | bool | `false` | Longer decay and deeper pitch drop — use on the "downbeat" of drops |

### `snare`

Sine tone + band-passed noise burst.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `velocity` | float | `1.0` | Amplitude multiplier for the snare hit |

### `hat`

High-passed noise burst.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `open` | bool | `false` | Longer decay for an open-hat sound; closed hat otherwise |

### `tick`

Short high-frequency sine — count-in ticks and click tracks.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `frequency` | float | `1760.0` | Sine frequency in Hz |

### `tom`

Descending sine tom.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `frequency` | float | `140.0` | Base frequency in Hz; pitch sweeps up ~60% above this at the transient |

### `pop`

Rising-pitch pop for stingers and shape hits.

No configurable params.

### `whoosh`

Swept band-pass noise with an envelope that peaks at a configurable point in the event window. `length` controls the total whoosh length; defaults to `1.0` beat if omitted.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `f0` | float | `200.0` | Start frequency of the sweep in Hz |
| `f1` | float | `6000.0` | End frequency of the sweep in Hz |
| `peak` | float | `0.7` | Fractional position (0.0–1.0) of the envelope peak inside the whoosh |

### `chord`

Sum of detuned super-saw voices at each named note, cosine-enveloped and low-pass filtered (or swept band-pass). `length` controls the chord length; defaults to `4.0` beats.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `notes` | string[] | `[A3, C4, E4, A4]` | Note names to stack. Each is `<letter><octave>` — `A0`–`G8`. Sharps/flats are not supported |
| `cutoff` | float | `2000.0` | Low-pass cutoff in Hz (when `sweep_from`/`sweep_to` are not set) |
| `sweep_from` | float | `null` | If both `sweep_from` and `sweep_to` are set, apply a swept band-pass filter instead of the low-pass |
| `sweep_to` | float | `null` | End frequency of the sweep in Hz |

### `sub-bass`

Sine-wave sub-bass with a fast attack and exponential decay. `length` defaults to `0.45` beat.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `frequency` | float | `55.0` | Sub frequency in Hz |

### `sine`

Pure sine with exponential decay. `length` defaults to `0.5` beat.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `frequency` | float | `440.0` | Sine frequency in Hz |
| `decay` | float | `4.0` | Exponential decay rate (higher = faster fade-out) |

### `noise-burst`

Filtered noise burst. `length` defaults to `0.25` beat.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `kind` | string | `highpass` | Filter type: `highpass`, `lowpass`, or `bandpass` |
| `frequency` | float \| [float, float] | `3000.0` | Filter cutoff in Hz. For `bandpass` pass `[low, high]` |
| `decay` | float | `20.0` | Exponential decay rate |
| `order` | int | `2` | Butterworth filter order |

## Master

Applied after summing all buses, in fixed order: **soft-clip → normalize → fades → silences**.

```yaml
master:
  soft_clip: 1.2
  normalize_level: -1.0
  fades:
    - { start_beat: 31.5, end_beat: 32, curve: quadratic }
  silences:
    - { start_beat: 27.9, end_beat: 28, pre_fade_duration: 3ms }
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `soft_clip` | float \| string | `1.2` | Pre-tanh drive amount for the soft-clip stage. `0` disables clipping |
| `normalize_level` | float \| string \| null | `-1.0` | Target peak level in dBFS after normalization. `null` disables normalization |
| `fades` | array | `[]` | Fade-out windows applied to the mix. See [Fade Fields](#fade-fields) |
| `silences` | array | `[]` | Hard-silence windows applied to the mix. See [Silence Fields](#silence-fields) |

### Fade Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `start_beat` | float \| string | **required** | Beat position where the fade begins |
| `end_beat` | float \| string | **required** | Beat position where the fade ends (mix stays silent past this point) |
| `curve` | `linear` \| `quadratic` | `quadratic` | Fade curve shape |

### Silence Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `start_beat` | float \| string | **required** | Beat position where the silence begins (inclusive) |
| `end_beat` | float \| string | **required** | Beat position where the silence ends (exclusive) |
| `pre_fade_duration` | duration \| string | `3ms` | Fade-out duration applied just before the silence to avoid click artifacts |

## Sidechain

Detects onsets on a trigger track and dips a duck envelope over selected target tracks — the classic kick-under-pad "pumping" sound.

```yaml
sidechain:
  trigger: kicks
  targets: [pad, bass]
  depth: 0.78
  attack_time: 2ms
  release_time: 70ms
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `trigger` | string | **required** | Track id whose events open the ducking envelope. Validated against the track list |
| `targets` | string[] | **required** | Track ids attenuated on each trigger hit. Validated against the track list |
| `depth` | float \| string | `0.78` | Peak gain reduction on each hit, `0.0` (no ducking) to `1.0` (full mute) |
| `attack_time` | duration \| string | `2ms` | Time to reach peak reduction after each hit |
| `release_time` | duration \| string | `70ms` | Time to recover to unity gain after each hit |

Trigger hits are picked from the trigger track's rendered signal (any sample above half its own peak). If the trigger track is silent, ducking is a no-op.

## Examples

### Four-on-the-floor with a chord pad and pre-drop silence

```yaml
components:
  - id: synth
    type: music-synthesizer
    actions:
      - id: bake
        method: sequence
        bpm: 128
        beats: 32
        seed: 128
        tracks:
          - id: kicks
            events:
              - beat: { start: 4, end: 20, step: 1 }
                instrument: kick
              - beat: { start: 28, end: 32, step: 1 }
                instrument: kick
                params: { big: true }
          - id: hats
            events:
              - beat: { start: 4, end: 20, step: 0.5, phase: 0.5 }
                instrument: hat
                params: { open: true }
                gain: 0.28
                pan: 0.25
          - id: pad
            events:
              - beat: 0
                instrument: chord
                length: 4
                params: { notes: [A3, C4, E4, A4], cutoff: 900 }
                gain: 0.22
              - beat: 4
                instrument: chord
                length: 4
                params: { notes: [F3, A3, C4, F4], cutoff: 2400 }
                gain: 0.22
        master:
          soft_clip: 1.2
          normalize_level: -1
          silences:
            - { start_beat: 27.9, end_beat: 28, pre_fade_duration: 3ms }
          fades:
            - { start_beat: 31.5, end_beat: 32, curve: quadratic }
        sidechain:
          trigger: kicks
          targets: [pad, hats]
```

### Click track from a variable BPM

```yaml
components:
  - id: click
    type: music-synthesizer
    actions:
      - method: sequence
        bpm: ${input.bpm}
        beats: ${input.beats}
        tracks:
          - id: metronome
            events:
              - beat: { start: 0, end: ${input.beats}, step: 1 }
                instrument: tick
                params: { frequency: 1760 }
```

## See Also

- [`audio-mixer`](audio-mixer.md) — layer the synthesized bed with narration or SFX
- [`audio-converter`](audio-converter.md) — transcode the WAV output to `mp3`/`flac`/etc.
- [`audio-processor`](audio-processor.md) — apply DSP (EQ, compressor, reverb) to the mix
- [`music-analyzer`](music-analyzer.md) — the reverse direction: extract musical features from audio
