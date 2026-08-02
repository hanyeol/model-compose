# 참조 스크립트 기반 교정이 포함된 음성 인식

로컬 Whisper 모델로 오디오 파일을 전사하고, 알려진 참조 스크립트에 대해 STT 세그먼트를 정렬합니다. 인식 오타는 참조 스크립트의 표현으로 교체되며, STT에서 얻은 타임스탬프는 그대로 보존됩니다 — 결과는 자막으로 사용하기 적합한 교정된 시간 부여 전사입니다.

## 개요

워크플로우는 두 개의 job으로 구성됩니다:

1. **`transcribe`** — 로컬에서 **faster-whisper**로 `large-v3-turbo`를 실행하며
   `return_timestamps: segment`를 사용합니다. `{text, start_time, end_time}` 세그먼트 목록을 생성합니다.
   faster-whisper는 Whisper의 CTranslate2 포트로 — HuggingFace transformers 백엔드보다
   훨씬 빠르고 CPU 또는 CUDA에서 작동합니다.
2. **`correct`** — 이 세그먼트와 참조 스크립트를 `transcript-corrector` 컴포넌트에 전달합니다.
   각 STT 세그먼트는 참조 스크립트의 가장 잘 일치하는 구간에 앵커링됩니다;
   매칭된 세그먼트는 텍스트가 참조 스크립트의 표현으로 교체되고,
   STT의 `start_time` / `end_time`은 그대로 유지됩니다.

일반적인 사용 사례:
- 알려진 스크립트의 녹음(팟캐스트, 오디오북, 스크립트 기반 내레이션) 정리.
- 참조 스크립트가 오디오와 별도로 작성될 때 정확한 자막 생성.
- 타이밍을 잃지 않으면서 STT 출력의 동음이의어/오타 편차를 제거하는 후처리.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 `PATH`에서 사용 가능.
- faster-whisper는 **CPU**(Apple Silicon 포함 macOS) 또는
  **CUDA**에서 실행됩니다. CTranslate2에는 Metal/MPS 백엔드가 없으므로;
  Apple Silicon에서는 CPU로 실행됩니다 (`turbo` 모델에서는 여전히 빠름).
- Python 의존성은 최초 실행 시 자동으로 설치됩니다:
  - `faster-whisper` — CTranslate2 Whisper 런타임.
  - `rapidfuzz`, `regex` — 정렬 점수 계산.

### 설정

이 예제 디렉토리로 이동:

```bash
cd examples/media-processing/speech-to-text-with-correction
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
   - 오디오 파일을 업로드하고, 참조 스크립트를 붙여넣고, (선택적으로)
     언어 코드를 설정.
   - **Run Workflow** 클릭.

   **CLI 사용:**

   ```bash
   model-compose run --input '{
     "audio": "/path/to/reading.wav",
     "reference": "The full text that the speaker was supposed to read...",
     "language": "en"
   }'
   ```

   **API 사용:**

   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "audio=@/path/to/reading.wav" \
     -F 'reference=The full text that the speaker was supposed to read...' \
     -F "language=en"
   ```

## 입력 매개변수

| 매개변수 | 유형 | 필수 | 설명 |
|-----------|------|------|-------------|
| `audio` | file | 예 | 전사할 오디오 (wav, mp3, flac, m4a, ...). |
| `reference` | string | 예 | 오디오의 기반이 되는 정답 스크립트. |
| `language` | string | 아니오 | ISO 코드 (`en`, `ko`, `ja`, ...). 생략 시 자동 감지. |

## 출력 형식

교정된 세그먼트의 평평한 리스트입니다. STT 출력의 추가 키는 각 세그먼트에 보존됩니다.

| 필드 | 유형 | 설명 |
|-------|------|-------------|
| `text` | string | STT 세그먼트와 가장 잘 일치하는 참조 스크립트 표현. |
| `start_time` | number | 세그먼트 시작(초), STT에서 가져옴. |
| `end_time` | number | 세그먼트 종료(초), STT에서 가져옴. |

최적 참조 매칭이 `match_threshold` 미만인 세그먼트는 잘못된 텍스트로 방출하는 대신 건너뜁니다.

### 예제

참조 스크립트:

```
Alice was beginning to get very tired of sitting by her sister on the bank
and of having nothing to do. Once or twice she had peeped into the book her
sister was reading, but it had no pictures or conversations in it.
```

STT (오타 강조):

```
Alis was begining to get very tired of siting by her sister on the bank
and of having nothing to do. Once or twise she had peeped into the book her
sister was reading, but it had no pictures or convertations in it.
```

교정된 출력:

```json
[
  { "text": "Alice was beginning to get very tired of sitting by her sister on the bank and of having nothing to do.", "start_time": 0.0,  "end_time": 6.2 },
  { "text": "Once or twice she had peeped into the book her sister was reading, but it had no pictures or conversations in it.", "start_time": 6.2, "end_time": 12.8 }
]
```

## 컴포넌트 세부사항

### `stt` — Speech-to-Text

- 유형: `model` (`task: speech-to-text`)
- 드라이버: `custom`, family `faster-whisper`
- 모델: `Systran/faster-whisper-base` — HuggingFace의 사전 변환된 CTranslate2 가중치,
  최초 실행 시 자동 다운로드 (~150 MB). 더 크고 정확한 크기로 교체 가능:
  `Systran/faster-whisper-{small,medium,large-v3}`.
- 장치: `cpu` (macOS에서 CTranslate2는 Metal/MPS 백엔드 없음).
  NVIDIA에서는 `cuda`로 전환.
- `compute_type: int8` — CPU에서 약 2배 빠르며 품질 저하는 작음.
  기타 옵션: `int8_float16`, `float16`, `float32`, `default`.
- `return_timestamps: true`와 `timestamp_level: segment`는 필수 —
  교정기는 세그먼트별 `start_time` / `end_time`이 필요합니다.

### `corrector` — Transcript Corrector

- 유형: `transcript-corrector`
- 드라이버: `native` (기본)
- 정렬: 참조의 슬라이딩 윈도우에 대한 세그먼트별 앵커 매칭,
  `rapidfuzz`의 문자 수준 Levenshtein 유사도로 점수 계산.
- 주요 옵션:
  - `granularity: word` — 공백으로 구분된 스크립트용, `character` — 공백이 없는 CJK/스크립트용.
  - `match_threshold: 0.5` — 이 유사도 미만의 세그먼트는 건너뜀.
  - `case_sensitive: false`, `ignore_punctuation: true` — 점수 계산에만 사용되는 정규화 제어;
    가시적 출력은 참조의 원본 대소문자와 구두점을 보존.

## 사용자 정의

### NVIDIA GPU에서 실행

```yaml
components:
  - id: stt
    ...
    device: cuda
    compute_type: float16       # 또는 낮은 VRAM용 'int8_float16'
```

### 더 작고/더 빠른 Whisper

```yaml
    model: Systran/faster-whisper-tiny     # 또는 -base, -small, -medium, -large-v3
```

### CJK 스크립트 (공백이 없는 중국어, 일본어)

```yaml
  - id: corrector
    type: transcript-corrector
    action:
      ...
      granularity: character
      min_window_tokens: 12
```

### 엄격 매칭 (모호한 세그먼트를 더 많이 제거)

```yaml
      match_threshold: 0.7
```
