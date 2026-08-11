# VAD 사전 분할이 포함된 음성 인식

로컬 Silero VAD 모델로 긴 오디오 파일을 발화 구간으로 나누고, 각 구간을 클리핑한 뒤 Whisper로 전사합니다 — 이 모든 것을 하나의 스트리밍 파이프라인으로 처리합니다. 각 세그먼트는 원본 오디오의 절대 타임스탬프와 함께 방출되므로 결과를 자막이나 시간 부여 전사로 바로 사용할 수 있습니다.

## 개요

워크플로우는 두 개의 스트리밍 오퍼레이터(clipper의 `return_timestamp`, transcribe job의 `+`)로 이어진 세 개의 job으로 구성됩니다:

1. **`detect`** — Silero VAD를 스트리밍 모드로 실행. 발화 구간이 확정되는 대로 `{start_time, end_time, confidence}` 스트림을 방출합니다.
2. **`clip`** — `audio-clipper` (ffmpeg 드라이버)가 VAD 스트림을 소비합니다. `return_timestamp: true`가 설정되어 있어 각 출력 clip은 `{audio, start_time, end_time}` 형태로 감싸져 원본 span 정보가 downstream으로 전달됩니다.
3. **`transcribe`** — `for-each` job이 clip 스트림을 순회합니다. 각 clip마다 clip의 VAD `start_time`을 STT의 `time_offset`으로 넘겨 Whisper를 실행하므로, 반환되는 세그먼트가 이미 원본 오디오의 절대 타임스탬프를 갖습니다. job의 `+` 오퍼레이터가 Whisper의 clip별 세그먼트 스트림들을 하나의 연속된 세그먼트 스트림으로 flatten합니다.

워크플로우 출력은 이 flatten된 스트림을 JSON으로 직렬화한 것으로, 호출자는 오디오 전체를 기다리지 않고 `{text, start_time, end_time}` dict가 하나씩 도착하는 것을 볼 수 있습니다.

일반적인 사용 사례:
- 긴 녹음(팟캐스트, 강의, 인터뷰)에서 정확한 세그먼트 타이밍을 가진 자막 파일 생성.
- 긴 오디오에서 VAD로 사전 분할하여 Whisper의 30초 chunking 한계 회피.
- 긴 무음 구간을 건너뛰어 Whisper 시간을 실제 발화에만 사용.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 `PATH`에서 사용 가능.
- `ffmpeg`가 `PATH`에 있어야 함 (clipper용).
- Whisper는 **CPU**, **CUDA**, 또는 **MPS**(Apple Silicon)에서 실행됩니다. 기본 설정은 `device: mps`이며 필요에 따라 `cpu`나 `cuda`로 전환.
- Python 의존성은 최초 실행 시 자동으로 설치됩니다:
  - `silero-vad`, `torch`, `torchaudio`, `soxr` — VAD.
  - `transformers`, `torch` — Whisper.

### 설정

이 예제 디렉토리로 이동:

```bash
cd examples/media-processing/speech-to-text-with-vad
```

## 실행 방법

1. **서비스 시작:**

   ```bash
   model-compose up
   ```

   - API 엔드포인트: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - http://localhost:8081 열기.
   - 오디오 파일을 업로드하고 언어 선택.
   - **Run Workflow** 클릭. Whisper가 각 clip을 완료하는 대로 세그먼트가 스트리밍됩니다.

   **CLI 사용:**

   ```bash
   model-compose run --input '{
     "audio": "/path/to/lecture.mp3",
     "language": "en"
   }'
   ```

   **API 사용 (SSE 스트림):**

   ```bash
   curl -N -X POST http://localhost:8080/api/workflows/runs \
     -F "audio=@/path/to/lecture.mp3" \
     -F "language=en"
   ```

## 입력 매개변수

| 매개변수 | 유형 | 필수 | 설명 |
|-----------|------|------|-------------|
| `audio` | file | 예 | 전사할 오디오 (wav, mp3, flac, m4a, ...). |
| `language` | string | 아니오 | ISO 코드 (`en`, `ko`, `ja`, `zh`). 기본값은 `en`. |

## 출력 형식

각 라인이 하나의 세그먼트인 JSON 스트림. 타임스탬프는 원본 오디오의 절대 위치(VAD clip 시작 + Whisper의 clip-relative 시간)입니다.

| 필드 | 유형 | 설명 |
|-------|------|-------------|
| `text` | string | 이 세그먼트에 대한 인식 텍스트. |
| `start_time` | number | 세그먼트 시작(초), 절대값. |
| `end_time` | number | 세그먼트 종료(초), 절대값. |

### 예제

```json
{"text": "Welcome back to the show.",        "start_time":   0.42, "end_time":   2.15}
{"text": "Today we're talking about VAD.",   "start_time":   2.60, "end_time":   5.30}
{"text": "It splits audio into speech runs.","start_time": 224.44, "end_time": 226.76}
```

## 컴포넌트 세부사항

### `vad` — Voice Activity Detection

- 유형: `model` (`task: voice-activity-detection`)
- 드라이버: `custom`, family `silero`
- 장치: `cpu` (Silero는 크기가 작아 CPU로 충분; MPS는 미지원).
- `sample_rate: 16000` — Whisper의 native 샘플레이트와 일치시켜 clip → STT 경로에서 추가 리샘플링을 피함. Silero는 8000 Hz도 지원.
- `streaming: true` — 확정되는 대로 세그먼트가 방출되어 downstream clipper와 STT가 즉시 작업을 시작할 수 있음.
- 주요 `params`:
  - `threshold: 0.5` — 세그먼트 진입에 필요한 발화 확률.
  - `min_speech_duration: 250ms`, `min_silence_duration: 500ms` — hysteresis 경계.
  - `max_speech_duration: 30s` — 하나의 발화가 Whisper의 30초 window에 맞도록 캡.
  - `speech_padding_time: 100ms` — 감지된 구간 주변의 추가 오디오로 단어 경계 잘림 방지.

### `clipper` — Audio Clipper

- 유형: `audio-clipper`
- 드라이버: `ffmpeg`
- `return_timestamp: true` — 각 clip을 `{audio, start_time, end_time}` 형태로 방출하여 downstream for-each가 audio와 span을 함께 STT에 전달할 수 있게 함.

### `stt` — Speech to Text

- 유형: `model` (`task: speech-to-text`)
- 드라이버: `huggingface`, architecture `whisper`
- 모델: `openai/whisper-large-v3-turbo` — 빠르고 정확; 다른 크기/속도 트레이드오프를 원하면 `openai/whisper-{tiny,base,small,medium,large-v3}`로 교체.
- 장치: `mps` — Apple Silicon GPU. NVIDIA에서는 `cuda`, 그 외에는 `cpu`.
- `return_timestamps: true` — 세그먼트별 `start_time` / `end_time`을 방출.
- `streaming: true` — Whisper가 세그먼트를 생성하는 대로 스트리밍. `+` 오퍼레이터와 결합되어 워크플로우가 flat한 세그먼트 스트림을 출력.
- `time_offset: ${input.time_offset}` — for-each가 각 clip의 VAD 시작 시간을 이 offset으로 전달하고, STT가 반환하는 모든 세그먼트의 `start_time` / `end_time`에 이 값을 더해 결과가 원본 오디오의 절대 위치를 갖도록 함.

## 사용자 정의

### CPU 또는 CUDA에서 실행

```yaml
components:
  - id: stt
    ...
    device: cpu   # 또는 NVIDIA에서 'cuda'
```

### 더 작고/더 빠른 Whisper

```yaml
    model: openai/whisper-small       # 또는 -base, -medium, -large-v3 등
```

### VAD 감도 조정

```yaml
  - id: vad
    ...
    action:
      params:
        threshold: 0.3               # 더 관대; 조용한 발화도 포착
        min_speech_duration: 100ms   # 더 짧은 발화 유지
        min_silence_duration: 300ms  # 더 짧은 pause에서 분할
```

### 타임스탬프를 clip 상대 시간으로 유지

STT input에서 `time_offset`을 제거하면 각 세그먼트가 자신의 clip 내에서 0부터 시작합니다:

```yaml
    - id: transcribe
      type: for-each
      input: ${jobs.clip.output}
      do:
        component: stt
        input:
          audio: ${item.audio}
          language: ${input.language}
      output:
        "+": ${output}
```
