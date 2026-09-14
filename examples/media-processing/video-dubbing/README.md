# Video Dubbing Pipeline

This example demonstrates an end-to-end video dubbing workflow: it extracts the source audio from a video, transcribes it with Whisper, translates the transcript into the target language, synthesises a new voice-over with Qwen3-TTS, and re-syncs the original video's mouth movements to the generated voice using Wav2Lip.

## Overview

The pipeline chains five components in sequence:

1. **audio-extractor (ffmpeg)** — pulls the source audio track out of the input video as a 16 kHz PCM WAV.
2. **speech-to-text (Whisper turbo)** — transcribes the extracted audio into a full-length string in the source language.
3. **text-to-text (SMaLL-100)** — translates the transcript into the target language via a special `forced_bos_token` selecting the language code.
4. **text-to-speech (Qwen3-TTS)** — synthesises a new voice track in the target language using a preset voice (`vivian` by default).
5. **lip-sync (Wav2Lip)** — takes the original video plus the newly-generated audio and rewrites the mouth region frame by frame so the lips match the translated speech.

Each stage is a separate component, so any step can be swapped without touching the rest of the workflow — for example switch the STT to `crisper-whisper` for punctuation, plug in a voice-cloning TTS to preserve the source speaker's timbre, or replace Wav2Lip with `musetalk` / `latentsync` for higher-quality lip sync.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- `ffmpeg` on the system path (used by the audio extractor and by Wav2Lip's audio mux step)
- A CUDA-capable GPU is strongly recommended; the STT + TTS + lip-sync stack runs on CPU but is impractically slow for anything but very short clips

### Environment Configuration

1. Navigate to this example directory:
   ```bash
   cd examples/media-processing/video-dubbing
   ```

2. No additional environment configuration required — every model is either downloaded from Hugging Face on first run or bundled by its wrapper library. The Wav2Lip stage additionally installs the upstream `justinjohn0306/Wav2Lip` fork into a dedicated virtualenv (`.venv/wav2lip`) so its old `librosa`/`numba` pins don't collide with the controller's site-packages.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First-time startup downloads Whisper large-v3-turbo, SMaLL-100, Qwen3-TTS, and Wav2Lip checkpoints, and installs the Wav2Lip venv. Expect several minutes and multi-GB downloads before the controller reports ready.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Dub an English source video into Korean
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "src=@/path/to/talking-head.mp4" \
     -F 'input={"video": "@src", "source_language": "en", "target_language": "ko"}'

   # Same source, Japanese target
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "src=@/path/to/talking-head.mp4" \
     -F 'input={"video": "@src", "source_language": "en", "target_language": "ja"}'
   ```

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Upload a `video` with a clearly-visible speaking face (best results with a front-facing single subject)
   - Pick a `source_language` and a `target_language` from the dropdown
   - Click the "Run Workflow" button to receive a dubbed MP4 back

## Configuration Reference

### Workflow Inputs

| Field              | Description                                                     | Choices                | Default |
|--------------------|-----------------------------------------------------------------|------------------------|---------|
| `video`            | Source video with an audible speaker. Any container ffmpeg can read. | `video/*`          | —       |
| `source_language`  | Language of the speech in the source video (ISO-639-1 code).    | `en`, `ko`, `ja`, `zh` | `en`    |
| `target_language`  | Language to dub the video into (ISO-639-1 code).                | `en`, `ko`, `ja`, `zh` | `ko`    |

### Job Flow

| Job              | Component        | Input                                                | Depends on       |
|------------------|------------------|------------------------------------------------------|------------------|
| `extract-audio`  | `audio-extractor`| `source = input.video`                               | —                |
| `transcribe`     | `stt`            | `audio = extract-audio.output`, `language`           | `extract-audio`  |
| `translate`      | `translator`     | `text = transcribe.output`, `target_language`        | `transcribe`     |
| `synthesize`     | `tts`            | `text = translate.output`                            | `translate`      |
| `lip-sync`       | `lip-syncer`     | `video = input.video`, `audio = synthesize.output`   | `synthesize`     |

### Components

| Component        | Backend                                        | Notes                                                                       |
|------------------|------------------------------------------------|-----------------------------------------------------------------------------|
| `audio-extractor`| `audio-extractor` (ffmpeg driver)              | Extracts track 0 as 16 kHz PCM WAV                                          |
| `stt`            | `model / speech-to-text` (Whisper turbo)       | `openai/whisper-large-v3-turbo`; returns a single string per input          |
| `translator`     | `model / text-to-text` (SMaLL-100)             | `alirezamsh/small100`; target selected via `forced_bos_token`               |
| `tts`            | `model / text-to-speech` (Qwen3-TTS)           | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`; preset voice `vivian`               |
| `lip-syncer`     | `model / lip-sync` (Wav2Lip)                   | `family: wav2lip`, `preset: wav2lip-gan`; runs in a dedicated virtualenv    |

## Notes

- **Voice consistency**: the default `tts` component uses a preset voice, so the dubbed voice will not match the source speaker. To preserve timbre, swap the TTS component for a voice-cloning example (e.g. `text-to-speech-clone-cosyvoice`) and feed a short reference clip of the source speaker as an additional input.
- **Segmented dubbing**: this pipeline transcribes and translates the video as a single utterance, which works best for short clips (< 30 s). For longer material, add a `voice-activity-detection` component to split the audio into speech regions and use a `for-each` job to translate each segment independently — see `examples/media-processing/speech-to-text-with-correction` for the streaming/VAD/`for-each` pattern.
- **Language codes**: SMaLL-100 accepts 100+ target languages. The dropdown here is limited to a small default set — edit the `select/...` list in `model-compose.yml` to expose more.
- **Lip-sync quality**: Wav2Lip is fast but lower-fidelity than diffusion-based alternatives. For sharper results swap `family: wav2lip` with `family: musetalk` (v1.5) or `family: latentsync` (1.6) in the `lip-syncer` component — see `examples/model-tasks/lip-sync-musetalk` and `lip-sync-latentsync` for the corresponding param surface.
- **Audio length mismatch**: the generated TTS clip's duration will differ from the source video. Wav2Lip loops the source frames forward to fill any audio overhang; the resulting video's length matches the TTS audio, not the source video.
- **Face detection failures**: if Wav2Lip can't find a face in a frame, the workflow raises `"Face not detected in one of the frames"`. Provide a `params.face_bounding_box` on the `lip-syncer` component to bypass detection, or use footage with a clearer, larger, front-facing face.
