# Text to Speech (Voice Cloning with LuxTTS) Model Task Example

This example demonstrates how to perform zero-shot voice cloning using LuxTTS (ZipVoice) at 48 kHz, running locally via model-compose's built-in model task functionality.

## Overview

This workflow provides local voice cloning and speech synthesis that:

1. **Local Model Execution**: Runs LuxTTS locally without external APIs
2. **Zero-Shot Voice Cloning**: Reproduces a speaker's voice from a short reference audio sample
3. **Transcript-Free**: No reference transcript required — cloning is driven by the reference audio alone
4. **48 kHz Output**: Emits synthesized speech at the model's native 48 kHz sample rate for higher fidelity

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Sufficient system resources (recommended: 8GB+ VRAM if using a GPU)
- Python environment with LuxTTS dependencies (automatically managed)
- A reference audio file for voice cloning

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/model-tasks/text-to-speech-clone-luxtts
   ```

2. No additional environment configuration required - model and dependencies are managed automatically.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using Web UI (Recommended):**
   - Open the Web UI: http://localhost:8084
   - Enter the text to synthesize
   - Upload a reference audio file
   - Click the "Run Workflow" button

   **Using API:**
   ```bash
   curl -X POST http://localhost:8083/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "text": "This is synthesized speech using a cloned voice.",
         "reference_audio": "<base64-encoded-audio>"
       }
     }'
   ```

   **Using CLI:**
   ```bash
   model-compose run --input '{
     "text": "This is synthesized speech using a cloned voice.",
     "reference_audio": "<base64-encoded-audio>"
   }'
   ```

## Component Details

### Text-to-Speech Model Component (Default)
- **Type**: Model component with `text-to-speech` task
- **Purpose**: Zero-shot voice cloning and speech synthesis from reference audio
- **Model**: `YatharthS/LuxTTS`
- **Driver**: `custom`
- **Family**: `luxtts`
- **Device**: `auto`
- **Method**: `clone` - clones a voice from reference audio and generates speech
- **Concurrency**: 1 (single request at a time)

### Model Information: LuxTTS
- **Base**: ZipVoice
- **Type**: Zero-shot voice cloning TTS model
- **Sample Rate**: 48 kHz output
- **Output Format**: Audio (WAV)

## Workflow Details

### "Text to Speech with Voice Cloning (LuxTTS)" Workflow (Default)

**Description**: Zero-shot voice cloning using LuxTTS (ZipVoice) at 48 kHz.

#### Job Flow

```mermaid
graph TD
    J1((Default<br/>job))
    C1[TTS Model<br/>component]
    J1 -.-> C1
    C1 -.-> |audio| J1
    Input((Input)) --> J1
    J1 --> Output((Output))
```

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | text | Yes | - | The text to synthesize with the cloned voice |
| `reference_audio` | audio | Yes | - | Reference audio sample to clone the voice from |

#### Output Format

| Field | Type | Description |
|-------|------|-------------|
| - | audio | Generated speech audio in the cloned voice (WAV, 48 kHz) |

## Example Output

The workflow returns a WAV audio stream containing speech synthesized in the cloned voice at 48 kHz.

## Customization

### Using a Different Device

Force CPU or a specific GPU by adjusting `device`:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: luxtts
  model: YatharthS/LuxTTS
  device: cuda:0   # or cpu, mps, auto
```

### Reference Audio Tips

- Use clean audio without background noise
- 3-10 seconds of natural speech works best
- Ensure the audio is in a common format (WAV, MP3, FLAC)

## Related Examples

- **[text-to-speech-clone](../text-to-speech-clone/)**: Voice cloning with Qwen3-TTS
- **[text-to-speech-clone-cosyvoice](../text-to-speech-clone-cosyvoice/)**: Voice cloning with CosyVoice2 at 24 kHz
- **[text-to-speech-clone-tada](../text-to-speech-clone-tada/)**: Voice cloning with HumeAI TADA
