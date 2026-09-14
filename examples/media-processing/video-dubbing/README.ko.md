# 비디오 더빙 파이프라인

이 예제는 엔드투엔드 비디오 더빙 워크플로우를 보여줍니다: 원본 영상에서 오디오를 추출하고, Whisper로 전사한 뒤, 대상 언어로 번역하고, Qwen3-TTS로 새 음성을 합성하여, Wav2Lip으로 원본 영상의 입 모양을 새 음성에 맞춥니다.

## 개요

파이프라인은 다섯 개의 컴포넌트를 순서대로 연결합니다:

1. **audio-extractor (ffmpeg)** — 입력 영상에서 오디오 트랙을 16 kHz PCM WAV로 추출합니다.
2. **speech-to-text (Whisper turbo)** — 추출된 오디오를 원어의 전체 문자열로 전사합니다.
3. **text-to-text (SMaLL-100)** — 특수 `forced_bos_token`으로 대상 언어를 선택하여 전사문을 번역합니다.
4. **text-to-speech (Qwen3-TTS)** — 프리셋 보이스(기본 `vivian`)로 대상 언어 음성을 합성합니다.
5. **lip-sync (Wav2Lip)** — 원본 영상과 새 오디오를 받아 프레임 단위로 입 부분을 다시 그려 번역된 음성에 맞춥니다.

각 단계는 독립 컴포넌트이므로 워크플로우 나머지를 건드리지 않고 어떤 단계든 교체할 수 있습니다. 예를 들어 STT를 `crisper-whisper`로 바꿔 문장부호를 얻거나, 보이스 클로닝 TTS로 교체하여 원본 화자의 음색을 유지하거나, Wav2Lip을 `musetalk` / `latentsync`로 바꿔 더 높은 품질의 립싱크를 얻을 수 있습니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 `PATH`에서 사용 가능.
- `ffmpeg`이 시스템 경로에 존재 (오디오 추출 및 Wav2Lip의 오디오 믹싱 단계에서 사용).
- CUDA GPU 강력 권장 — STT + TTS + 립싱크 스택은 CPU에서도 동작하지만 짧은 클립을 제외하면 실용적이지 않을 정도로 느립니다.

### 환경 설정

1. 예제 디렉터리로 이동:
   ```bash
   cd examples/media-processing/video-dubbing
   ```

2. 별도 환경 설정 필요 없음 — 모든 모델은 첫 실행 시 Hugging Face에서 다운로드되거나 래퍼 라이브러리에 번들되어 있습니다. Wav2Lip 단계는 추가로 upstream `justinjohn0306/Wav2Lip` fork를 전용 virtualenv (`.venv/wav2lip`)에 설치하므로, 오래된 `librosa`/`numba` 핀이 컨트롤러의 site-packages와 충돌하지 않습니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행 시 Whisper large-v3-turbo, SMaLL-100, Qwen3-TTS, Wav2Lip 체크포인트를 다운로드하고 Wav2Lip venv를 설치합니다. 컨트롤러가 준비되기까지 수 분과 수 GB의 다운로드가 필요합니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 영어 소스 영상을 한국어로 더빙
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "src=@/path/to/talking-head.mp4" \
     -F 'input={"video": "@src", "source_language": "en", "target_language": "ko"}'

   # 같은 소스, 일본어 대상
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "src=@/path/to/talking-head.mp4" \
     -F 'input={"video": "@src", "source_language": "en", "target_language": "ja"}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 말하는 얼굴이 명확히 보이는 `video` 업로드 (전면 단일 피사체가 최선의 결과)
   - 드롭다운에서 `source_language`와 `target_language` 선택
   - "Run Workflow" 버튼을 눌러 더빙된 MP4 수신

## 설정 참조

### 워크플로우 입력

| 필드                | 설명                                                          | 선택지                  | 기본값  |
|--------------------|--------------------------------------------------------------|------------------------|---------|
| `video`            | 오디오가 포함된 소스 비디오. ffmpeg이 읽을 수 있는 모든 컨테이너. | `video/*`              | —       |
| `source_language`  | 소스 영상 음성의 언어 (ISO-639-1 코드).                          | `en`, `ko`, `ja`, `zh` | `en`    |
| `target_language`  | 더빙할 대상 언어 (ISO-639-1 코드).                              | `en`, `ko`, `ja`, `zh` | `ko`    |

### Job 흐름

| Job              | 컴포넌트           | 입력                                                     | 의존성            |
|------------------|-------------------|---------------------------------------------------------|------------------|
| `extract-audio`  | `audio-extractor` | `source = input.video`                                  | —                |
| `transcribe`     | `stt`             | `audio = extract-audio.output`, `language`              | `extract-audio`  |
| `translate`      | `translator`      | `text = transcribe.output`, `target_language`           | `transcribe`     |
| `synthesize`     | `tts`             | `text = translate.output`                               | `translate`      |
| `lip-sync`       | `lip-syncer`      | `video = input.video`, `audio = synthesize.output`      | `synthesize`     |

### 컴포넌트

| 컴포넌트          | 백엔드                                            | 비고                                                                     |
|------------------|--------------------------------------------------|-------------------------------------------------------------------------|
| `audio-extractor`| `audio-extractor` (ffmpeg driver)                | 트랙 0을 16 kHz PCM WAV로 추출                                            |
| `stt`            | `model / speech-to-text` (Whisper turbo)         | `openai/whisper-large-v3-turbo`; 입력당 단일 문자열 반환                    |
| `translator`     | `model / text-to-text` (SMaLL-100)               | `alirezamsh/small100`; `forced_bos_token`으로 대상 언어 선택               |
| `tts`            | `model / text-to-speech` (Qwen3-TTS)             | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`; 프리셋 보이스 `vivian`             |
| `lip-syncer`     | `model / lip-sync` (Wav2Lip)                     | `family: wav2lip`, `preset: wav2lip-gan`; 전용 virtualenv에서 실행         |

## 주의사항

- **보이스 일관성**: 기본 `tts` 컴포넌트는 프리셋 보이스를 사용하므로 더빙된 음성은 원본 화자와 일치하지 않습니다. 음색을 보존하려면 TTS 컴포넌트를 보이스 클로닝 예제(예: `text-to-speech-clone-cosyvoice`)로 교체하고 원본 화자의 짧은 참조 클립을 추가 입력으로 넘기세요.
- **세그먼트 단위 더빙**: 이 파이프라인은 영상을 하나의 발화로 전사·번역하므로 짧은 클립(30초 미만)에 가장 적합합니다. 더 긴 소재는 `voice-activity-detection` 컴포넌트를 추가해 오디오를 음성 구간으로 분할하고 `for-each` job으로 각 세그먼트를 독립적으로 번역하세요 — 스트리밍/VAD/`for-each` 패턴은 `examples/media-processing/speech-to-text-with-correction` 참고.
- **언어 코드**: SMaLL-100은 100+ 대상 언어를 지원합니다. 여기 드롭다운은 소규모 기본 세트로 제한되어 있으니 — `model-compose.yml`의 `select/...` 리스트를 편집해 더 많이 노출할 수 있습니다. 다른 다국어 모델로 교체 시 (`NLLB`, `mBART`, `M2M100`) 각 모델의 특수 언어 토큰 형식에 맞춰 `forced_bos_token` 문자열을 조정해야 합니다.
- **립싱크 품질**: Wav2Lip은 빠르지만 diffusion 기반 대안보다 화질이 낮습니다. 더 선명한 결과를 원하면 `lip-syncer` 컴포넌트의 `family: wav2lip`을 `family: musetalk` (v1.5) 또는 `family: latentsync` (1.6)로 교체하세요 — 해당 파라미터 표면은 `examples/model-tasks/lip-sync-musetalk` 및 `lip-sync-latentsync` 참고.
- **오디오 길이 불일치**: 생성된 TTS 클립의 재생 시간은 소스 영상과 다릅니다. Wav2Lip은 오디오가 남을 때 소스 프레임을 앞으로 반복해 채웁니다; 최종 영상 길이는 소스 영상이 아니라 TTS 오디오 길이와 일치합니다.
- **얼굴 검출 실패**: Wav2Lip이 프레임에서 얼굴을 찾지 못하면 `"Face not detected in one of the frames"` 오류가 발생합니다. `lip-syncer` 컴포넌트에 `params.face_bounding_box`를 제공해 검출을 우회하거나, 얼굴이 더 크고 명확히 정면인 소재를 사용하세요.
