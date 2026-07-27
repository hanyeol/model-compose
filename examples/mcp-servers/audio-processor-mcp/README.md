# Audio Processor MCP Server Example

This example demonstrates how to expose a local audio-processing pipeline as an MCP server over **stdio** transport. Each workflow is registered as an MCP tool that accepts a base64-encoded audio clip, applies a DSP effect, and returns the processed audio as a WAV byte stream.

## Overview

This MCP server provides 20 audio processing workflows built on the `audio-processor` component, covering format conversion, filtering, EQ, dynamics, tone shaping, spatial effects, loudness control, and edge shaping:

**Format & Filters**
1. **Resample**: Convert to a different sample rate (e.g. align 32 kHz model output to 44.1 kHz)
2. **Highpass Filter**: Remove low-frequency content below a cutoff (rumble, hum, subsonic noise)
3. **Lowpass Filter**: Remove high-frequency content above a cutoff (hiss, sibilance)

**Parametric EQ**
4. **Bell EQ**: Boost or cut a bell-shaped band around a centre frequency (surgical tone shaping)
5. **Low-Shelf EQ**: Boost or cut everything below a corner frequency (low-end warmth or thinning)
6. **High-Shelf EQ**: Boost or cut everything above a corner frequency (air, sparkle, hiss taming)

**Pitch**
7. **Pitch Shift**: Shift pitch by semitones without changing duration

**Dynamics**
8. **Dynamic Range Compressor**: Attenuate loud parts and keep quiet parts audible
9. **Noise Gate**: Attenuate signal below a threshold to clean up quiet sections

**Tone / Colour**
10. **Distortion**: Aggressive harmonic distortion as a creative effect
11. **Saturation**: Subtle harmonic colour and warmth without audible distortion

**Space**
12. **Reverb**: Add reverberation for a sense of space (room, hall)

**Loudness (Normalize)**
13. **Normalize (RMS)**: Bring audio to a target RMS level with a peak cap
14. **Normalize (Peak)**: Scale audio so its highest peak sits at a target dBFS
15. **Normalize (LUFS)**: Match audio to a target integrated loudness (ITU-R BS.1770) with true-peak protection

**Loudness (Peak Limiting)**
16. **Peak Limit (Hard)**: Brick-wall clip for headroom safety
17. **Peak Limit (Smooth)**: Lookahead limiter for transparent mastering-grade peak control

**Edges**
18. **Trim Silence**: Trim silent tails and cut overlong internal silence gaps
19. **Fade-In**: Cosine fade-in at the start of the audio
20. **Fade-Out**: Cosine fade-out at the end of the audio

Because the server runs over **stdio**, it is designed to be launched directly by an MCP client (e.g. Claude Desktop) rather than a long-running HTTP server.

## Preparation

### Prerequisites

- Python 3.10+
- model-compose installed and available in your PATH
- The `audio-processor` component's driver dependencies installed (installed with model-compose)

### Environment Configuration

No environment variables or API keys are required — this example runs entirely locally.

## How to Run

### Run as a stdio MCP server (typical usage)

Configure your MCP client to launch the server with:

```json
{
  "mcpServers": {
    "audio-processor": {
      "command": "model-compose",
      "args": ["up"],
      "cwd": "/absolute/path/to/examples/mcp-servers/audio-processor-mcp"
    }
  }
}
```

The client will spawn `model-compose up` in this directory, and the process will speak MCP over stdin/stdout. All 20 workflows will appear as tools.

### Run a single workflow from the CLI

You can also invoke a workflow directly without launching the MCP server. Audio inputs should be passed as base64-encoded strings:

```bash
# Highpass filter at 200 Hz
model-compose run highpass --input '{
  "audio": "<base64-encoded-wav>",
  "cutoff": 200
}'

# Pitch shift up 2 semitones
model-compose run pitch-shift --input '{
  "audio": "<base64-encoded-wav>",
  "semitones": 2
}'

# LUFS normalization to -14 LUFS (streaming target)
model-compose run normalize-lufs --input '{
  "audio": "<base64-encoded-wav>",
  "level": -14
}'
```

### Run the smoke test

A self-contained smoke test that spawns the stdio server, lists tools, and calls each workflow with a synthetic 1-second sine wave is included:

```bash
python smoke.py
```

## Component Details

### Audio Processor Component
- **ID**: `audio`
- **Type**: `audio-processor`
- **Purpose**: Local DSP pipeline covering format conversion, filtering, parametric EQ, dynamics, tone shaping, spatial effects, loudness normalization, peak limiting, and edge shaping
- **Actions**: `resample`, `highpass`, `lowpass`, `bell`, `low-shelf`, `high-shelf`, `pitch-shift`, `compressor`, `noise-gate`, `distortion`, `saturation`, `reverb`, `normalize-rms`, `normalize-peak`, `normalize-lufs`, `peak-limit-hard`, `peak-limit-smooth`, `trim-silence`, `fade-in`, `fade-out`

## Workflow Details

### "Resample Audio" Workflow

**Description**: Convert the audio to a different sample rate.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `sample_rate` | number | No | `44100` | Target sample rate in Hz |

### "Apply Highpass Filter" Workflow

**Description**: Remove low-frequency content below a cutoff.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `cutoff` | number | No | `80` | Cutoff frequency in Hz |

### "Apply Lowpass Filter" Workflow

**Description**: Remove high-frequency content above a cutoff.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `cutoff` | number | No | `8000` | Cutoff frequency in Hz |

### "Apply Bell EQ" Workflow

**Description**: Boost or cut a bell-shaped band around a centre frequency.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `frequency` | number | No | `3000` | Centre frequency of the bell in Hz |
| `gain` | number | No | `0` | Gain at the centre frequency in dB (positive boosts, negative cuts) |
| `q` | number | No | `0.707` | Bell width; higher Q means narrower band |

### "Apply Low-Shelf EQ" Workflow

**Description**: Boost or cut everything below a corner frequency.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `frequency` | number | No | `150` | Shelf corner frequency in Hz |
| `gain` | number | No | `0` | Shelf gain in dB (positive boosts, negative cuts) |
| `q` | number | No | `0.707` | Shelf slope; higher Q means steeper corner |

### "Apply High-Shelf EQ" Workflow

**Description**: Boost or cut everything above a corner frequency.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `frequency` | number | No | `10000` | Shelf corner frequency in Hz |
| `gain` | number | No | `0` | Shelf gain in dB (positive boosts, negative cuts) |
| `q` | number | No | `0.707` | Shelf slope; higher Q means steeper corner |

### "Apply Pitch Shift" Workflow

**Description**: Shift pitch by semitones without changing duration.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `semitones` | number | No | `0` | Semitones to shift; positive raises, negative lowers |

### "Apply Dynamic Range Compressor" Workflow

**Description**: Attenuate loud parts and keep quiet parts audible.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `threshold` | number | No | `-20` | Threshold in dB above which compression applies |
| `ratio` | number | No | `4` | Compression ratio (e.g. 4 for 4:1) |

### "Apply Noise Gate" Workflow

**Description**: Attenuate signal below a threshold so noise floor and codec artifacts in quiet sections are cleaned up.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `threshold` | number | No | `-40` | Threshold in dB below which the gate attenuates |
| `ratio` | number | No | `10` | Downward expansion ratio; higher is more aggressive |

### "Apply Distortion" Workflow

**Description**: Add aggressive harmonic distortion as a creative effect.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `drive` | number | No | `25` | Drive amount in dB; typical range 15 to 40 |

### "Apply Saturation" Workflow

**Description**: Add subtle harmonic colour and warmth without audibly distorting.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `drive` | number | No | `3` | Drive amount in dB; typical range 1 to 8 |

### "Apply Reverb" Workflow

**Description**: Add reverberation for a sense of space.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `room_size` | number | No | `0.5` | Room size (0.0–1.0) |
| `damping` | number | No | `0.5` | High-frequency damping (0.0–1.0) |
| `wet_level` | number | No | `0.33` | Wet signal level (0.0–1.0) |

### "Normalize Loudness (RMS)" Workflow

**Description**: Bring audio to a target RMS level with a peak cap. Suits source-to-source alignment when a full loudness meter is overkill.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `level` | number | No | `-20` | Target RMS level in dBFS |
| `peak_limit` | number | No | `0.85` | Peak amplitude cap after normalization (0.0–1.0) |

### "Normalize Loudness (Peak)" Workflow

**Description**: Scale the audio so its highest peak sits at a target dBFS. Use when headroom control matters more than perceived loudness.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `level` | number | No | `-1` | Target peak level in dBFS |

### "Normalize Loudness (LUFS)" Workflow

**Description**: Match the audio to a target integrated loudness in LUFS (ITU-R BS.1770) with true-peak protection. Use for streaming or broadcast delivery.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `level` | number | No | `-14` | Target integrated loudness in LUFS (-14 for streaming, -9 to -12 for punchier masters) |
| `true_peak_ceiling` | number | No | `-1` | True-peak ceiling in dBTP applied after loudness gain |

### "Apply Peak Limit (Hard)" Workflow

**Description**: Cap peak amplitude with a brick-wall clip. Fast and cheap headroom safety; may introduce audible distortion on transient-heavy material.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `level` | number | No | `0.95` | Peak amplitude cap (0.0–1.0) |

### "Apply Peak Limit (Smooth)" Workflow

**Description**: Cap peaks with a lookahead limiter that releases smoothly. Use for transparent mastering-grade peak control.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `level` | number | No | `-1` | Ceiling in dBFS |
| `release` | duration | No | `100ms` | Release time (e.g. `100ms`) |

### "Trim Trailing Silence" Workflow

**Description**: Trim silent tails and cut overlong internal silence gaps.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `threshold` | number | No | `-40` | Silence threshold in dBFS |
| `min_silence` | duration | No | `200ms` | Minimum trailing silence to keep |

### "Apply Fade-In" Workflow

**Description**: Apply a cosine fade-in at the start of the audio for a smooth entry.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `duration` | duration | No | `20ms` | Fade-in duration (e.g. `20ms`) |

### "Apply Fade-Out" Workflow

**Description**: Apply a cosine fade-out at the end of the audio to avoid abrupt endings.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `audio` | audio (base64) | Yes | - | Input audio as base64-encoded bytes |
| `duration` | duration | No | `20ms` | Fade-out duration (e.g. `20ms`) |

## MCP Server Integration

### Connection Details
- **Transport**: stdio
- **Command**: `model-compose up` (run inside this example directory)
- **Protocol**: Model Context Protocol v1.0

### Available Tools
Every workflow is advertised as an MCP tool with the same name:

- `resample`
- `highpass`
- `lowpass`
- `bell`
- `low-shelf`
- `high-shelf`
- `pitch-shift`
- `compressor`
- `noise-gate`
- `distortion`
- `saturation`
- `reverb`
- `normalize-rms`
- `normalize-peak`
- `normalize-lufs`
- `peak-limit-hard`
- `peak-limit-smooth`
- `trim-silence`
- `fade-in`
- `fade-out`

Each tool returns MCP `AudioContent` with `mimeType: audio/wav`; the client receives the base64-encoded WAV directly, no separate download step.

## Troubleshooting

### Common Issues

1. **Tool call returns `TextContent` instead of audio**: The workflow raised inside `model-compose`. Run `model-compose up` manually (without the stdio client) to see the traceback.
2. **`audio requires raw audio bytes, got str`**: Check that the `audio` variable in `model-compose.yml` is declared with the `;base64` decoder hint (e.g. `as audio;base64`).
3. **MCP client can't find the server**: The `cwd` in your MCP config must be an absolute path to this example directory.
4. **Smoke test hangs**: Ensure `model-compose` is on your `PATH` and that no other process is already holding stdio.
