# Audio Processor Component

The audio processor component applies DSP transforms (rate/time, EQ, dynamics, spatial, level, edit, effect) to a PCM audio stream. It runs on the `native` driver, backed by `pedalboard`, `librosa`, `soxr`, and `pyloudnorm`.

## Basic Configuration

```yaml
component:
  type: audio-processor
  action:
    method: speed
    audio: ${input.audio as audio}
    speed: 1.5
    preserve_pitch: true
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `audio-processor` |
| `driver` | string | `native` | Processing backend. Currently only `native` is supported. |
| `actions` | array | `[]` | List of audio processing actions |

### Common Action Configuration

All audio processor actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Processing method (see below). One of: `resample`, `speed`, `highpass`, `lowpass`, `bell`, `low-shelf`, `high-shelf`, `pitch-shift`, `dc-shift`, `compressor`, `noise-gate`, `distortion`, `saturation`, `gain`, `chorus`, `delay`, `reverb`, `normalize`, `peak-limit`, `trim-edges`, `trim-silence`, `fade-in`, `fade-out`, `anonymize` |
| `audio` | string / array | **required** | Input audio (a file path, upload, or upstream audio reference — single or list) |
| `batch_size` | integer / string | `null` | Number of input audios processed per batch |
| `output` | any | `null` | Output variable mapping |

### Streaming vs Collect

Methods split into two execution modes:

- **Streaming** (chunk-by-chunk, no full buffer materialized): `highpass`, `lowpass`, `bell`, `low-shelf`, `high-shelf`, `compressor`, `noise-gate`, `distortion`, `saturation`, `gain`, `chorus`, `delay`, `reverb`, `fade-in`, `fade-out`, `resample`
- **Collect** (requires global statistics or offline analysis): `normalize`, `peak-limit`, `trim-edges`, `trim-silence`, `speed`, `pitch-shift`, `dc-shift`, `anonymize`

Collect methods materialize the full input buffer before processing.

## Audio Processing Methods

### Resample

Change the sample rate of an audio using soxr. Pitch and duration are preserved; only the sample rate label changes.

```yaml
component:
  type: audio-processor
  action:
    method: resample
    audio: ${input.audio as audio}
    sample_rate: 16000
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sample_rate` | integer | **required** | Target output sample rate in Hz (e.g., `16000`, `44100`, `48000`) |

### Speed

Speed audio up or down. With `preserve_pitch: true` the duration changes but pitch stays the same (phase-vocoder time-stretch via librosa). With `preserve_pitch: false` the waveform is resampled, so pitch scales inversely with the speed — the classic chipmunk / slowed-down effect.

```yaml
component:
  type: audio-processor
  action:
    method: speed
    audio: ${input.audio as audio}
    speed: 1.5
    preserve_pitch: true
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `speed` | number | **required** | Playback speed multiplier (e.g., `2.0` for double speed, `0.5` for half) |
| `preserve_pitch` | boolean | `true` | Keep the original pitch when changing speed |

`speed` vs `resample` vs `pitch-shift`:

- `speed` changes duration (and, with `preserve_pitch: false`, pitch too)
- `resample` only changes the sample-rate label (no time or pitch change)
- `pitch-shift` changes pitch while keeping duration unchanged

### Highpass

Attenuate frequencies below the cutoff. Useful for removing low-frequency rumble or DC offset.

```yaml
component:
  type: audio-processor
  action:
    method: highpass
    audio: ${input.audio as audio}
    cutoff: 120
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cutoff` | number | **required** | Filter cutoff frequency in Hz |

### Lowpass

Attenuate frequencies above the cutoff. Useful for softening harsh highs.

```yaml
component:
  type: audio-processor
  action:
    method: lowpass
    audio: ${input.audio as audio}
    cutoff: 8000
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cutoff` | number | **required** | Filter cutoff frequency in Hz |

### Bell EQ

Boost or cut a narrow band around a centre frequency (parametric peaking EQ).

```yaml
component:
  type: audio-processor
  action:
    method: bell
    audio: ${input.audio as audio}
    frequency: 3000
    gain: 3
    q: 1.2
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frequency` | number | **required** | Centre frequency in Hz |
| `gain` | number | **required** | Gain at the centre in dB (positive to boost, negative to cut) |
| `q` | number | `0.707` | Bell width; higher Q produces a narrower band |

### Low Shelf EQ

Boost or cut everything below the corner frequency by a fixed dB amount.

```yaml
component:
  type: audio-processor
  action:
    method: low-shelf
    audio: ${input.audio as audio}
    frequency: 200
    gain: -3
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frequency` | number | **required** | Shelf corner frequency in Hz |
| `gain` | number | **required** | Shelf gain in dB |
| `q` | number | `0.707` | Shelf slope; higher Q is a steeper corner |

### High Shelf EQ

Boost or cut everything above the corner frequency by a fixed dB amount.

```yaml
component:
  type: audio-processor
  action:
    method: high-shelf
    audio: ${input.audio as audio}
    frequency: 8000
    gain: 2
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `frequency` | number | **required** | Shelf corner frequency in Hz |
| `gain` | number | **required** | Shelf gain in dB |
| `q` | number | `0.707` | Shelf slope; higher Q is a steeper corner |

### Pitch Shift

Shift the pitch of an audio by a number of semitones while keeping the duration unchanged.

```yaml
component:
  type: audio-processor
  action:
    method: pitch-shift
    audio: ${input.audio as audio}
    semitones: 2
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `semitones` | number | **required** | Amount of pitch shift (positive raises, negative lowers) |

### DC Shift

Remove any DC bias (mean offset) from the signal and optionally apply a fixed DC offset afterwards.

```yaml
component:
  type: audio-processor
  action:
    method: dc-shift
    audio: ${input.audio as audio}
    offset: 0
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `offset` | number | `0` | Additional DC offset applied after centering, from `-1.0` to `1.0` |

### Compressor

Downward compression above `threshold` at the given `ratio`. Reduces the level of the loud parts.

```yaml
component:
  type: audio-processor
  action:
    method: compressor
    audio: ${input.audio as audio}
    threshold: -20
    ratio: 4
    attack_time: 1ms
    release_time: 100ms
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold` | number | `-20` | Threshold in dB above which compression applies |
| `ratio` | number | `4` | Compression ratio (e.g., `4` for 4:1) |
| `attack_time` | duration / number | `1ms` | Attack time |
| `release_time` | duration / number | `100ms` | Release time |

### Noise Gate

Attenuate signal below `threshold` with a downward-expansion ratio.

```yaml
component:
  type: audio-processor
  action:
    method: noise-gate
    audio: ${input.audio as audio}
    threshold: -40
    ratio: 10
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold` | number | `-40` | Threshold in dB below which the gate attenuates |
| `ratio` | number | `10` | Downward expansion ratio; higher gates more aggressively |
| `attack_time` | duration / number | `1ms` | Gate attack time |
| `release_time` | duration / number | `100ms` | Gate release time |

### Distortion

Aggressive drive-based harmonic distortion. Typical drive range for character is `15`–`40` dB.

```yaml
component:
  type: audio-processor
  action:
    method: distortion
    audio: ${input.audio as audio}
    drive: 20
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `drive` | number | **required** | Drive amount in dB; higher values produce more aggressive distortion |

### Saturation

Subtle harmonic coloring. Same underlying algorithm as `distortion`, but tuned for gentle drive values (`1`–`8` dB).

```yaml
component:
  type: audio-processor
  action:
    method: saturation
    audio: ${input.audio as audio}
    drive: 3
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `drive` | number | `3` | Drive amount in dB for subtle coloring |

### Gain

Multiply the signal by a linear gain derived from the dB level.

```yaml
component:
  type: audio-processor
  action:
    method: gain
    audio: ${input.audio as audio}
    level: 6
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | number | **required** | Gain in dB (positive boosts, negative attenuates) |

### Chorus

Modulated delay effect that thickens a sound by mixing detuned copies of itself.

```yaml
component:
  type: audio-processor
  action:
    method: chorus
    audio: ${input.audio as audio}
    rate: 1.0
    depth: 0.25
    feedback: 0.0
    delay: 7ms
    mix: 0.5
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rate` | number | `1.0` | Chorus LFO rate in Hz |
| `depth` | number | `0.25` | Modulation depth (0.0–1.0) |
| `feedback` | number | `0` | Feedback amount (0.0–1.0) |
| `delay` | duration / number | `7ms` | Centre delay time |
| `mix` | number | `0.5` | Dry/wet mix (0.0=dry, 1.0=wet) |

### Delay

Simple delay/echo with feedback and wet/dry mix.

```yaml
component:
  type: audio-processor
  action:
    method: delay
    audio: ${input.audio as audio}
    time: 500ms
    feedback: 0.3
    mix: 0.4
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `time` | duration / number | `500ms` | Delay time |
| `feedback` | number | `0` | Feedback amount (0.0–1.0) |
| `mix` | number | `0.5` | Dry/wet mix (0.0=dry, 1.0=wet) |

### Reverb

Freeverb-style room reverberation.

```yaml
component:
  type: audio-processor
  action:
    method: reverb
    audio: ${input.audio as audio}
    room_size: 0.5
    damping: 0.5
    wet_level: 0.33
    dry_level: 0.4
    width: 1.0
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `room_size` | number | `0.5` | Simulated room size (0.0–1.0) |
| `damping` | number | `0.5` | High-frequency damping (0.0–1.0) |
| `wet_level` | number | `0.33` | Reverberated signal level (0.0–1.0) |
| `dry_level` | number | `0.4` | Dry signal level (0.0–1.0) |
| `width` | number | `1.0` | Stereo width of the reverb (0.0–1.0) |

### Normalize

Normalize the audio to a target loudness. `mode` selects the strategy: RMS (average energy), peak (highest sample), or LUFS (integrated loudness with true-peak limiting).

```yaml
component:
  type: audio-processor
  action:
    method: normalize
    mode: lufs
    audio: ${input.audio as audio}
    level: -14
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | **required** | `rms`, `peak`, or `lufs` |

Mode-specific fields:

**`mode: rms`**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | number | `-20` | Target RMS level in dBFS |
| `peak_limit` | number | `0.85` | Peak amplitude cap (0.0–1.0) applied after normalization |

**`mode: peak`**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | number | `-1` | Target peak level in dBFS (e.g., `-1` leaves 1 dB of headroom) |

**`mode: lufs`**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | number | `-14` | Target integrated loudness in LUFS |
| `tolerance` | number | `0.5` | Acceptable deviation from the target in LU |
| `max_gain` | number | `30` | Maximum absolute gain in dB the verify loop may apply |
| `true_peak_ceiling` | number | `-1` | True-peak ceiling in dBTP enforced after loudness gain |

The `mode` value must be a literal string at load time (discriminator). Use `${input.level ...}` for numeric parameters, but not for `mode` — define one action per mode instead.

### Peak Limit

Cap peaks that exceed a threshold. `mode: hard` clips above a linear cap; `mode: smooth` uses a true-peak limiter with release time.

```yaml
component:
  type: audio-processor
  action:
    method: peak-limit
    mode: smooth
    audio: ${input.audio as audio}
    level: -1
    release_time: 100ms
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | string | **required** | `hard` or `smooth` |

Mode-specific fields:

**`mode: hard`**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | number | `0.95` | Peak amplitude cap (0.0–1.0) |

**`mode: smooth`**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | number | `-1` | Ceiling in dBFS (e.g., `-1` leaves 1 dB of headroom) |
| `release_time` | duration / number | `100ms` | Limiter release time |

As with `normalize`, `mode` must be a literal at load time.

### Trim Edges

Remove leading and trailing silence detected relative to the signal's peak.

```yaml
component:
  type: audio-processor
  action:
    method: trim-edges
    audio: ${input.audio as audio}
    threshold: 40
    padding: 100ms
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold` | number | `40` | Silence threshold in dB below peak |
| `padding` | duration / number | `null` | Padding restored at each edge when trimming shortens the audio |

### Trim Silence

Detect silent windows and cut leading/trailing silence plus any internal silence longer than `max_internal_silence`. A short cosine fade avoids clicks at the trimmed boundary.

```yaml
component:
  type: audio-processor
  action:
    method: trim-silence
    audio: ${input.audio as audio}
    threshold: -40
    max_internal_silence: 1s
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `window` | duration / number | `20ms` | RMS analysis window size |
| `threshold` | number | `-40` | Silence threshold in dBFS |
| `min_silence` | duration / number | `200ms` | Minimum trailing silence to keep |
| `max_internal_silence` | duration / number | `1s` | Internal gaps longer than this are cut |
| `fade` | duration / number | `30ms` | Cosine fade-out applied at the trimmed end |

### Fade In

Apply a `sin^2` cosine curve at the start of the audio.

```yaml
component:
  type: audio-processor
  action:
    method: fade-in
    audio: ${input.audio as audio}
    duration: 500ms
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `duration` | duration / number | `20ms` | Fade-in length (e.g., `500ms`, `2s`) |

### Fade Out

Apply a `cos^2` cosine curve at the end of the audio.

```yaml
component:
  type: audio-processor
  action:
    method: fade-out
    audio: ${input.audio as audio}
    duration: 500ms
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `duration` | duration / number | `20ms` | Fade-out length |

### Anonymize

Disguise a speaker with pitch shift, formant scaling, and time-varying jitter, plus an optional lowpass to attenuate high-frequency speaker cues.

```yaml
component:
  type: audio-processor
  action:
    method: anonymize
    audio: ${input.audio as audio}
    pitch_shift: -2
    formant_shift: 1.15
    pitch_jitter: 0.3
    jitter_rate: 4
    lowpass_cutoff: 6000
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pitch_shift` | number | `-2` | Pitch shift in semitones |
| `formant_shift` | number | `1.15` | Formant scaling ratio (>1 shifts formants up) |
| `pitch_jitter` | number | `0.3` | Random pitch modulation depth in semitones |
| `jitter_rate` | number | `4` | Jitter modulation rate in Hz |
| `lowpass_cutoff` | number | `6000` | Post-lowpass cutoff in Hz (`null` or `0` to disable) |
| `seed` | integer | `null` | Random seed for reproducible jitter (`null` for non-deterministic output) |

## Multiple Actions Configuration

Define multiple audio processing actions on the same component:

```yaml
component:
  type: audio-processor
  actions:
    - id: trim
      method: trim-silence
      audio: ${input.audio as audio}
      threshold: -45
      output: ${output}

    - id: master
      method: normalize
      mode: lufs
      audio: ${input.audio as audio}
      level: -14
      output: ${output}

    - id: warm-up
      method: fade-in
      audio: ${input.audio as audio}
      duration: 800ms
      output: ${output}
```

## Usage Examples

### Prepare Speech for Transcription

Trim edges, compress dynamics, and resample to a model's expected sample rate:

```yaml
workflows:
  - id: prepare-speech
    jobs:
      - id: trim
        component: audio
        action: trim
        input:
          audio: ${input.audio as audio}
        output:
          trimmed: ${output}

      - id: compress
        component: audio
        action: compress
        input:
          audio: ${jobs.trim.output.trimmed}
        output:
          compressed: ${output}
        depends_on: [ trim ]

      - id: resample
        component: audio
        action: resample-16k
        input:
          audio: ${jobs.compress.output.compressed}
        depends_on: [ compress ]

components:
  - id: audio
    type: audio-processor
    actions:
      - id: trim
        method: trim-silence
        audio: ${input.audio}
        threshold: -45
        output: ${output}

      - id: compress
        method: compressor
        audio: ${input.audio}
        threshold: -20
        ratio: 3
        output: ${output}

      - id: resample-16k
        method: resample
        audio: ${input.audio}
        sample_rate: 16000
        output: ${output}
```

### Mastering Chain

RMS-normalize, boost highs, and true-peak limit for a streaming target:

```yaml
components:
  - id: audio
    type: audio-processor
    actions:
      - id: level
        method: normalize
        mode: lufs
        audio: ${input.audio}
        level: -14
        output: ${output}

      - id: air
        method: high-shelf
        audio: ${input.audio}
        frequency: 8000
        gain: 2
        output: ${output}

      - id: ceiling
        method: peak-limit
        mode: smooth
        audio: ${input.audio}
        level: -1
        release_time: 120ms
        output: ${output}
```

### Half-Speed with Chipmunk Fallback

Two workflows sharing a single component — one preserves pitch, the other doesn't:

```yaml
components:
  - id: audio
    type: audio-processor
    actions:
      - id: slow-natural
        method: speed
        audio: ${input.audio}
        speed: 0.5
        preserve_pitch: true
        output: ${output}

      - id: slow-chipmunk
        method: speed
        audio: ${input.audio}
        speed: 0.5
        preserve_pitch: false
        output: ${output}
```

### Voice Anonymization

Disguise a speaker before publishing an interview clip:

```yaml
component:
  type: audio-processor
  action:
    method: anonymize
    audio: ${input.interview as audio}
    pitch_shift: -3
    formant_shift: 1.2
    pitch_jitter: 0.4
    jitter_rate: 5
    lowpass_cutoff: 5500
    seed: 42
```

## Variable Interpolation

Numeric and duration parameters accept `${input....}` expressions. **Discriminator fields (`mode` on `normalize` and `peak-limit`) must be literal strings** at load time; parametrize them by defining one action per mode:

```yaml
component:
  type: audio-processor
  actions:
    - id: level-rms
      method: normalize
      mode: rms
      audio: ${input.audio}
      level: ${input.level as number | -20}
      output: ${output}

    - id: level-lufs
      method: normalize
      mode: lufs
      audio: ${input.audio}
      level: ${input.level as number | -14}
      output: ${output}
```

## Best Practices

1. **Streaming methods first**: When possible, chain streaming methods before collect methods so the collect step operates on the shortest buffer.
2. **`speed` vs `resample` vs `pitch-shift`**: `speed` changes duration, `resample` only relabels the sample rate, `pitch-shift` changes pitch and keeps duration.
3. **LUFS for streaming targets**: Use `-14` LUFS for Spotify/YouTube; use `-9` to `-12` for punchier masters.
4. **Trim tuning**: Lower `threshold` (`-50`, `-60`) is stricter about what counts as silence; higher `max_internal_silence` keeps more of the natural pauses.
5. **Chain via workflow jobs**: Wire actions with `${jobs.<id>.output}` to compose e.g. `trim-silence → compressor → normalize-lufs → fade-in`.
6. **Anonymize with a seed for reproducibility**: Set `seed` on `anonymize` if you need deterministic output between runs (e.g., for tests).
7. **Prefer `saturation` over `distortion` for gentle warmth**: Same algorithm; the schema difference just documents intended drive range.

## Troubleshooting

1. **Missing dependencies (`pedalboard`, `librosa`, `soxr`, `pyloudnorm`)**: The component declares these as setup requirements and installs them on first run. If auto-install fails, install them manually.
2. **`Input tag '${input.mode ...}' does not match any expected tags`**: `mode` fields on `normalize` and `peak-limit` are pydantic discriminators and must be literal strings — see [Variable Interpolation](#variable-interpolation) for the split-action pattern.
3. **Clicks at trimmed boundaries**: Increase `trim-silence.fade` (e.g., `50ms`) or apply an explicit `fade-out` after trimming.
4. **`normalize` did not reach the target LUFS**: The LUFS loop caps at 3 iterations and respects `max_gain`. Raise `max_gain` or normalize in stages for very quiet material.
5. **`speed` with a very large value sounds artifacted**: The phase-vocoder used for `preserve_pitch: true` degrades at extreme speeds. For speeds well outside `0.5..2.0`, either accept the artifacts or switch to `preserve_pitch: false`.
