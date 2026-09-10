# Audio Processor Example

This example demonstrates the `audio-processor` component, which applies a chain of DSP transforms (time/rate, EQ, dynamics, spatial, level, edit, effect) to an audio stream using pedalboard, librosa, soxr, and pyloudnorm.

## Overview

This example exposes twenty-seven workflows built on the same `audio-processor` component:

1. **Resample Audio** — change the sample rate
2. **Change Speed** — speed up or slow down, optionally preserving pitch
3. **Highpass Filter** — attenuate frequencies below a cutoff
4. **Lowpass Filter** — attenuate frequencies above a cutoff
5. **Bell EQ** — boost/cut a narrow band
6. **Low Shelf EQ** — boost/cut below a corner
7. **High Shelf EQ** — boost/cut above a corner
8. **Pitch Shift** — semitone-based pitch change
9. **DC Shift** — remove DC bias / apply offset
10. **Compress Dynamics** — downward compression above threshold
11. **Noise Gate** — attenuate signal below threshold
12. **Distortion** — aggressive harmonic distortion
13. **Saturation** — subtle harmonic coloring
14. **Apply Gain** — boost or attenuate by dB
15. **Chorus** — modulated chorus effect
16. **Delay** — echo effect
17. **Add Reverb** — Freeverb-style reverberation
18. **Normalize (RMS)** — target RMS level in dBFS
19. **Normalize (Peak)** — target peak level in dBFS
20. **Normalize (LUFS)** — target integrated loudness with true-peak limiting
21. **Peak Limit (Hard)** — hard clip above a linear cap
22. **Peak Limit (Smooth)** — smooth limiter with release
23. **Trim Edges** — remove leading/trailing silence relative to peak
24. **Trim Silence** — remove leading/trailing plus long internal silence
25. **Fade In** — cosine fade-in at the start
26. **Fade Out** — cosine fade-out at the end
27. **Anonymize Voice** — pitch + formant shift with jitter to disguise a speaker

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python 3.10+ with `pedalboard`, `librosa`, `soxr`, `pyloudnorm`, and `torchaudio` installed (installed automatically the first time the component runs)

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/audio-processor
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
   - Upload an audio file and fill in the parameters
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Resample to 16 kHz
   model-compose run resample --input '{
     "audio": "/path/to/input.wav",
     "sample_rate": 16000
   }'

   # Play at 1.5x speed while preserving pitch
   model-compose run speed --input '{
     "audio": "/path/to/input.wav",
     "speed": 1.5,
     "preserve_pitch": true
   }'

   # Highpass at 120 Hz (roll off low-frequency rumble)
   model-compose run highpass --input '{
     "audio": "/path/to/input.wav",
     "cutoff": 120
   }'

   # Bell EQ: +3 dB narrow boost around 3 kHz
   model-compose run bell --input '{
     "audio": "/path/to/input.wav",
     "frequency": 3000,
     "gain": 3,
     "q": 1.2
   }'

   # Pitch up by 2 semitones (same duration)
   model-compose run pitch-shift --input '{
     "audio": "/path/to/input.wav",
     "semitones": 2
   }'

   # Compress with a 4:1 ratio above -20 dB
   model-compose run compressor --input '{
     "audio": "/path/to/input.wav",
     "threshold": -20,
     "ratio": 4
   }'

   # Normalize to -14 LUFS (streaming target)
   model-compose run normalize-lufs --input '{
     "audio": "/path/to/input.wav",
     "level": -14
   }'

   # Trim silence with a -40 dBFS threshold
   model-compose run trim-silence --input '{
     "audio": "/path/to/input.wav",
     "threshold": -40
   }'

   # Anonymize a voice with mild pitch/formant shift
   model-compose run anonymize --input '{
     "audio": "/path/to/input.wav",
     "pitch_shift": -2,
     "formant_shift": 1.15
   }'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=speed" \
     -F "audio=@/path/to/input.wav" \
     -F "speed=1.5" \
     -F "preserve_pitch=true"
   ```

## Component Details

### Audio Processor Component

- **Type**: `audio-processor`
- **Driver**: `native`
- **Purpose**: Apply DSP transforms to a PCM stream. Streaming methods (gain, EQ filters, compressor, noise-gate, distortion, saturation, chorus, delay, reverb, fade-in, fade-out) run chunk-by-chunk; methods that need global statistics (normalize, peak-limit, trim-edges, trim-silence, speed, pitch-shift, dc-shift, anonymize) collect the buffer first.

#### Common Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `method` | string | Yes | - | One of the supported action methods (see workflows below) |
| `audio` | audio source | Yes | - | Input audio (file path, upload, or upstream audio reference) |
| `batch_size` | integer | No | `1` | Number of input audios processed per batch when the input is a list/stream |

Output is always a PCM stream; the container/codec is decided downstream by whoever writes the result (`${output as audio}` in a workflow output triggers a WAV encode by default).

## Workflow Details

### 1. Resample Audio

**Description**: Streaming resample using soxr. Pitch and duration are preserved; only the sample rate label changes.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `sample_rate` | integer | Yes | - | Target output sample rate in Hz (e.g., `16000`, `44100`, `48000`) |

### 2. Change Speed

**Description**: Speed the audio up or down. With `preserve_pitch: true` the duration changes but the pitch stays the same (phase-vocoder time-stretch). With `preserve_pitch: false` the waveform is resampled, so the pitch scales inversely with the speed — the classic chipmunk / slowed-down effect.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `speed` | number | Yes | - | Playback speed multiplier (e.g., `2.0` for double speed, `0.5` for half) |
| `preserve_pitch` | boolean | No | `true` | Keep the original pitch when changing speed |

### 3. Highpass Filter

**Description**: Attenuate frequencies below a cutoff. Useful for removing low-frequency rumble or DC offset.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `cutoff` | number | Yes | - | Filter cutoff frequency in Hz |

### 4. Lowpass Filter

**Description**: Attenuate frequencies above a cutoff. Useful for softening harsh high-frequency content.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `cutoff` | number | Yes | - | Filter cutoff frequency in Hz |

### 5. Bell EQ

**Description**: Boost or cut a narrow band around a centre frequency. Higher Q produces a narrower band.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `frequency` | number | Yes | - | Centre frequency in Hz |
| `gain` | number | Yes | - | Gain at the centre in dB (positive to boost, negative to cut) |
| `q` | number | No | `0.707` | Bell width; higher Q is narrower |

### 6. Low Shelf EQ

**Description**: Boost or cut everything below the corner frequency by a fixed dB amount.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `frequency` | number | Yes | - | Shelf corner frequency in Hz |
| `gain` | number | Yes | - | Shelf gain in dB |
| `q` | number | No | `0.707` | Shelf slope; higher Q is a steeper corner |

### 7. High Shelf EQ

**Description**: Boost or cut everything above the corner frequency by a fixed dB amount.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `frequency` | number | Yes | - | Shelf corner frequency in Hz |
| `gain` | number | Yes | - | Shelf gain in dB |
| `q` | number | No | `0.707` | Shelf slope; higher Q is a steeper corner |

### 8. Pitch Shift

**Description**: Shift pitch by a number of semitones while keeping the duration unchanged.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `semitones` | number | Yes | - | Amount of pitch shift (positive raises, negative lowers) |

### 9. DC Shift

**Description**: Remove any DC bias (mean offset) from the signal and optionally apply a fixed DC offset.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `offset` | number | No | `0` | Additional DC offset applied after centering, from `-1.0` to `1.0` |

### 10. Compress Dynamics

**Description**: Downward compression above `threshold` with a given `ratio`. Reduces the level of the loud parts, letting you push the whole track louder afterwards.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `threshold` | number | No | `-20` | Threshold in dB above which compression applies |
| `ratio` | number | No | `4` | Compression ratio (e.g. `4` for 4:1) |
| `attack_time` | duration | No | `1ms` | Attack time |
| `release_time` | duration | No | `100ms` | Release time |

### 11. Noise Gate

**Description**: Attenuate signal below `threshold` with the given `ratio`. Removes low-level noise between wanted content.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `threshold` | number | No | `-40` | Threshold in dB below which the gate attenuates |
| `ratio` | number | No | `10` | Downward expansion ratio; higher gates more aggressively |
| `attack_time` | duration | No | `1ms` | Gate attack time |
| `release_time` | duration | No | `100ms` | Gate release time |

### 12. Distortion

**Description**: Aggressive drive-based distortion. Typical drive range for character is `15`–`40` dB.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `drive` | number | Yes | - | Drive amount in dB; higher is more aggressive |

### 13. Saturation

**Description**: Subtle harmonic coloring. Same underlying algorithm as distortion, but tuned for gentle drive values (`1`–`8` dB).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `drive` | number | No | `3` | Drive amount in dB for subtle coloring |

### 14. Apply Gain

**Description**: Multiply the signal by a linear gain derived from the dB level.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `level` | number | Yes | - | Gain in dB (positive boosts, negative attenuates) |

### 15. Chorus

**Description**: Modulated delay effect that thickens a sound by mixing detuned copies of itself.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `rate` | number | No | `1.0` | Chorus LFO rate in Hz |
| `depth` | number | No | `0.25` | Modulation depth (0.0–1.0) |
| `feedback` | number | No | `0` | Feedback amount (0.0–1.0) |
| `delay` | duration | No | `7ms` | Center delay time |
| `mix` | number | No | `0.5` | Dry/wet mix (0.0=dry, 1.0=wet) |

### 16. Delay

**Description**: Simple delay/echo with feedback and wet/dry mix.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `time` | duration | No | `500ms` | Delay time |
| `feedback` | number | No | `0` | Feedback amount (0.0–1.0) |
| `mix` | number | No | `0.5` | Dry/wet mix (0.0=dry, 1.0=wet) |

### 17. Add Reverb

**Description**: Freeverb-style room reverberation with configurable size, damping, and dry/wet mix.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `room_size` | number | No | `0.5` | Simulated room size (0.0–1.0) |
| `damping` | number | No | `0.5` | High-frequency damping (0.0–1.0) |
| `wet_level` | number | No | `0.33` | Reverberated signal level (0.0–1.0) |
| `dry_level` | number | No | `0.4` | Dry signal level (0.0–1.0) |
| `width` | number | No | `1.0` | Stereo width of the reverb (0.0–1.0) |

### 18. Normalize (RMS)

**Description**: Scale the audio so its RMS (average energy) hits the target level in dBFS, with a peak cap applied after gain.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `level` | number | No | `-20` | Target RMS level in dBFS |
| `peak_limit` | number | No | `0.85` | Peak amplitude cap (0.0–1.0) applied after normalization |

### 19. Normalize (Peak)

**Description**: Scale the audio so its highest sample hits the target peak level in dBFS.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `level` | number | No | `-1` | Target peak level in dBFS (e.g., `-1` leaves 1 dB of headroom) |

### 20. Normalize (LUFS)

**Description**: Iteratively measure and scale the integrated loudness toward the target LUFS, then apply a true-peak limiter.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `level` | number | No | `-14` | Target integrated loudness in LUFS |
| `tolerance` | number | No | `0.5` | Acceptable deviation from the target in LU |
| `max_gain` | number | No | `30` | Maximum absolute gain in dB the verify loop may apply |
| `true_peak_ceiling` | number | No | `-1` | True-peak ceiling in dBTP enforced after loudness gain |

### 21. Peak Limit (Hard)

**Description**: Hard clip that only engages when the input peak exceeds the linear amplitude cap. Fast and cheap, but produces clipping artifacts if pushed hard.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `level` | number | No | `0.95` | Peak amplitude cap (0.0–1.0) |

### 22. Peak Limit (Smooth)

**Description**: True-peak limiter with a release time (pedalboard `Limiter`). Cleaner than hard clipping when pushed.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `level` | number | No | `-1` | Ceiling in dBFS (e.g. `-1` leaves 1 dB of headroom) |
| `release_time` | duration | No | `100ms` | Limiter release time |

### 23. Trim Edges

**Description**: Remove leading and trailing silence detected relative to the signal's peak (threshold in dB below peak).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `threshold` | number | No | `40` | Silence threshold in dB below peak |
| `padding` | duration | No | `0ms` | Padding restored at each edge if trimming shortens the audio |

### 24. Trim Silence

**Description**: Detect silent windows and cut leading/trailing silence plus any internal silence longer than `max_internal_silence`. A short cosine fade avoids clicks at the trimmed boundary.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `window` | duration | No | `20ms` | RMS analysis window size |
| `threshold` | number | No | `-40` | Silence threshold in dBFS |
| `min_silence` | duration | No | `200ms` | Minimum trailing silence to keep |
| `max_internal_silence` | duration | No | `1s` | Internal gaps longer than this are cut |
| `fade` | duration | No | `30ms` | Cosine fade-out applied at the trimmed end |

### 25. Fade In

**Description**: Apply a `sin^2` cosine curve at the start of the audio.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `duration` | duration | No | `500ms` | Fade-in length (e.g. `500ms`, `2s`) |

### 26. Fade Out

**Description**: Apply a `cos^2` curve at the end of the audio.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `duration` | duration | No | `500ms` | Fade-out length |

### 27. Anonymize Voice

**Description**: Disguise a speaker with pitch shift, formant scaling, and time-varying jitter, plus an optional lowpass to attenuate high-frequency speaker cues.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | file | Yes | - | Source audio file |
| `pitch_shift` | number | No | `-2` | Pitch shift in semitones |
| `formant_shift` | number | No | `1.15` | Formant scaling ratio (>1 shifts formants up) |
| `pitch_jitter` | number | No | `0.3` | Random pitch modulation depth in semitones |
| `jitter_rate` | number | No | `4` | Jitter modulation rate in Hz |
| `lowpass_cutoff` | number | No | `6000` | Post-lowpass cutoff in Hz (0 or negative to disable) |

## Tips

- **Streaming vs collect**: Streaming methods (`gain`, EQ filters, `compressor`, `noise-gate`, `distortion`, `saturation`, `chorus`, `delay`, `reverb`, `fade-in`, `fade-out`) run chunk-by-chunk without materializing the whole buffer. Methods that need global statistics (`normalize`, `peak-limit`, `trim-edges`, `trim-silence`, `speed`, `pitch-shift`, `dc-shift`, `anonymize`) collect the input before processing.
- **`speed` vs `resample` vs `pitch-shift`**: `speed` changes duration; `resample` only changes the sample-rate label (no time or pitch change); `pitch-shift` changes pitch and keeps duration.
- **`speed` with `preserve_pitch: false`**: Pure resample. Doubling the speed halves the perceived pitch's period (an octave up), which is the classic chipmunk effect.
- **`normalize` vs `peak-limit`**: `normalize` scales the whole signal to hit a target level; `peak-limit` only reduces peaks that exceed a threshold, leaving the rest untouched.
- **LUFS normalize**: Runs an iterative measure → gain → true-peak-limit loop. Use `-14` for streaming targets (Spotify/YouTube), `-9` to `-12` for punchier masters.
- **Trim-silence tuning**: Lower `threshold` (`-50`, `-60`) is stricter about what counts as silence; higher `max_internal_silence` keeps more of the natural pauses.
- **Chain multiple methods**: Wire several actions in sequence via `${jobs.<id>.output}` to compose e.g. `trim-silence → compressor → normalize-lufs → fade-in`.

## Troubleshooting

### Common Issues

1. **Missing dependencies (`pedalboard`, `librosa`, `soxr`, `pyloudnorm`)**: The component declares these as setup requirements and installs them on first run. If auto-install fails (offline, restricted environment), install them into your Python environment manually.
2. **Clicks at the trimmed boundary**: Increase `fade` in `trim-silence` (e.g. `50ms`) or apply an explicit `fade-out` after trimming.
3. **`normalize` did not reach the target LUFS**: The LUFS loop caps at 3 iterations and respects `max_gain`. Very quiet material may hit that cap; raise `max_gain` or normalize in stages.
4. **`speed` with a very large value sounds artifacted**: The phase-vocoder used for `preserve_pitch: true` degrades at extreme speeds. For speeds well outside `0.5..2.0`, either accept the artifacts or switch to `preserve_pitch: false` for a resample-based speed change.
5. **`distortion` or `peak-limit-hard` sounds harsh**: Both introduce non-linear distortion by design. Try `saturation` (subtle drive) or `peak-limit-smooth` (true-peak limiter) if you need gentler behavior.
