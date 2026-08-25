# 오디오 무음 감지 예제

이 예제는 model-compose의 `audio-silence-detector` 컴포넌트를 사용하여 FFmpeg의 `silencedetect` 필터로 오디오 파일 내 무음 구간을 찾는 방법을 보여줍니다.

## 개요

이 예제는 2가지 무음 감지 워크플로우를 제공합니다:

1. **기본 감지**: 사용자가 임계값과 최소 지속 시간을 지정하는 일반적인 무음 감지 (트리밍/구간 분할 등에 적합)
2. **엄격 감지**: 더 길고 더 조용한 무음만 감지 — 녹음 앞뒤의 데드 에어(dead air) 정리에 적합

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- FFmpeg 설치 (`ffmpeg` 드라이버에 필요)

### 설정

이 예제 디렉토리로 이동:
```bash
cd examples/media-processing/audio-silence-detector
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   서비스 시작 후:
   - API 엔드포인트: http://localhost:8080/api
   - 웹 UI: http://localhost:8081

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 드롭다운에서 워크플로우 선택
   - 오디오 파일 업로드
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   # 기본 감지 (임계값 및 최소 지속 시간 지정)
   model-compose run detect-silences --input '{
     "audio": "/path/to/audio.wav",
     "silence_threshold": -30.0,
     "min_silence_duration": "500ms"
   }'

   # 엄격 감지 (-40 dBFS / 2초 고정)
   model-compose run detect-silences-strict --input '{"audio": "/path/to/audio.wav"}'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-silences" \
     -F "audio=@/path/to/audio.wav"
   ```

## 컴포넌트 세부사항

### 오디오 무음 감지 컴포넌트

- **유형**: `audio-silence-detector`
- **목적**: 오디오 트랙 내 무음(조용한) 구간을 찾아 소리 구간과 무음 구간이 교차하는 타임라인을 생성
- **드라이버**:
  - `ffmpeg` - FFmpeg `silencedetect` 오디오 필터 (기본값)

## 워크플로우 세부사항

### 1. 무음 감지 (기본)

**ID**: `detect-silences`
**설명**: FFmpeg의 `silencedetect` 필터를 사용해 임계값과 최소 지속 시간을 커스터마이즈하여 무음 감지

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `silence_threshold` | number | 아니오 | `-30.0` | 무음 감지 임계값 (dBFS, 값이 낮을수록 더 조용해야 무음으로 인식) |
| `min_silence_duration` | string | 아니오 | `500ms` | 무음으로 인정되기 위한 최소 지속 시간 (예: `500ms`, `1s`, `2.5s`) |

---

### 2. 무음 감지 (엄격)

**ID**: `detect-silences-strict`
**설명**: 길고 깊은 무음만 감지 (`-40.0` dBFS 임계값, `2s` 최소 지속 시간 고정). 시작/끝부분 무음 트리밍에 유용

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |

---

### 출력 형식

각 워크플로우는 전체 오디오 타임라인을 커버하는 세그먼트들의 평평한 리스트를 반환합니다. 세그먼트는 `audible`(소리 있음)과 `silence`(임계값 이하가 `min_silence_duration` 이상 지속) 사이를 교차합니다.

| 필드 | 유형 | 설명 |
|-----|------|------|
| `start_time` | number | 세그먼트 시작 시간 (초) |
| `end_time` | number | 세그먼트 종료 시간 (초) |
| `type` | string | 세그먼트 분류: `audible` 또는 `silence` |

#### 출력 예시

```json
[
  { "start_time": 0.0,   "end_time": 12.345, "type": "audible" },
  { "start_time": 12.345, "end_time": 15.678, "type": "silence" },
  { "start_time": 15.678, "end_time": 42.100, "type": "audible" },
  { "start_time": 42.100, "end_time": 45.000, "type": "silence" }
]
```

## 맞춤화

### 임계값 및 지속 시간 가이드

- **`silence_threshold`** (dBFS): 무음으로 인정되기 위해 얼마나 조용해야 하는지
  - `-20.0` — 매우 관대함, 작은 볼륨 저하도 무음으로 인식
  - `-30.0` — 일반적인 음성/음악에 적합한 균형 잡힌 기본값
  - `-40.0` — 엄격, 거의 완전한 무음만 인정
- **`min_silence_duration`**: 무음 구간이 얼마나 길게 지속되어야 하는지
  - `200ms` — 단어 사이의 짧은 정지도 감지
  - `500ms` — 문장 사이의 자연스러운 간격 (기본값)
  - `2s` 이상 — 시작/끝의 데드 에어만

낮은 임계값과 긴 지속 시간을 조합하면 구조적 무음(테이크 사이, 곡 사이, 챕터 사이 등)을 분리할 수 있고, 높은 임계값과 짧은 지속 시간을 조합하면 세밀한 정지도 감지할 수 있습니다.
