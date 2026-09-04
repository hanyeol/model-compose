# 음악 분석기 예제

이 예제는 model-compose의 `music-analyzer` 컴포넌트를 사용하여 오디오 파일에서 음악 도메인 속성 — 리듬, 조성, 스펙트럴 특성, 하모닉/퍼커시브 비율 — 을 추출하는 방법을 보여줍니다.

## 개요

이 예제는 각 metric마다 하나씩, 총 10개의 워크플로우를 제공합니다:

1. **비트와 BPM 감지** (기본) — 템포 추정 + 비트 시각 + 주기성 기반 신뢰도 점수
2. **노트 온셋 감지** — 어택 타임스탬프 + 정규화된 강도
3. **로컬 템포 분포 계산** — 프레임별 tempogram; BPM이 곡 내에서 변화할 때 유용
4. **활성 구간 감지** — 곡 자체의 다이내믹 레인지 기반 라우드 구간 (silence 감지의 의미적 반대)
5. **음악 조성 감지** — Krumhansl 프로파일 상관관계 기반 tonic + mode
6. **크로마 추출** — 시간에 따른 12차원 pitch-class 에너지
7. **Tonnetz 추출** — 6차원 Harte tonal centroid 특성
8. **스펙트럴 밝기 측정** — Hz 단위 spectral centroid
9. **스펙트럴 평탄도 측정** — [0, 1] 범위의 tonal vs noise 비율
10. **하모닉/퍼커시브 비율 측정** — HPSS 기반 에너지 분리

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- Python 의존성은 첫 실행 시 자동 설치:
  - `librosa`, `numpy`, `soundfile` (`native` 드라이버용)

### 설정

이 예제 디렉토리로 이동:
```bash
cd examples/media-processing/music-analyzer
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
   # 비트와 BPM (기본)
   model-compose run detect-beats --input '{"audio": "/path/to/track.mp3"}'

   # BPM 검색 범위 지정
   model-compose run detect-beats --input '{
     "audio": "/path/to/track.mp3",
     "min_bpm": 80,
     "max_bpm": 160
   }'

   # 온셋 감지 - 최소 간격 지정
   model-compose run detect-onsets --input '{
     "audio": "/path/to/track.mp3",
     "min_gap": "50ms"
   }'

   # 조성 감지
   model-compose run detect-key --input '{"audio": "/path/to/track.mp3"}'

   # 활성 구간 - 엄격한 임계값
   model-compose run detect-activity --input '{
     "audio": "/path/to/track.mp3",
     "level": 0.5,
     "min_duration": "1s"
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-beats" \
     -F "audio=@/path/to/track.mp3"
   ```

## 컴포넌트 상세

### Music Analyzer 컴포넌트

- **타입**: `music-analyzer`
- **목적**: 오디오에서 음악 도메인 속성 — 리듬, 조성, 스펙트럴 특성, 소스 분리 비율 — 을 추출
- **드라이버**:
  - `native` — librosa 기반 분석 (기본)

신호 레벨 측정(라우드니스/피크/게인/클리핑/무음)이 필요하면 [`audio-analyzer`](../audio-analyzer/)를 사용하세요. 원시 특징 행렬(스펙트로그램, 파형)이 필요하면 [`audio-feature-extractor`](../audio-feature-extractor/)를 사용하세요.

## 워크플로우 상세

### 1. 비트와 BPM 감지

**ID**: `detect-beats`
**Metric**: `beats`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `min_bpm` | number | 아니요 | `60.0` | 비트 추적 시 고려할 최저 BPM |
| `max_bpm` | number | 아니요 | `200.0` | 비트 추적 시 고려할 최고 BPM |

#### 출력 예시

```json
{
  "bpm": 137.2,
  "confidence": 8.94,
  "beats": [
    { "time": 0.44 },
    { "time": 0.88 }
  ]
}
```

`confidence`가 1.0에 가까우면 입력에 지배적인 주기성이 없다는 뜻이며, 일반적인 음악은 3 이상입니다.

---

### 2. 노트 온셋 감지

**ID**: `detect-onsets`
**Metric**: `onsets`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `min_gap` | duration | 아니요 | `30ms` | 인접 온셋 간 최소 시간 |

#### 출력 예시

```json
{
  "onsets": [
    { "time": 0.44, "strength": 0.82 },
    { "time": 1.17, "strength": 0.65 }
  ]
}
```

---

### 3. 로컬 템포 분포 계산

**ID**: `compute-tempogram`
**Metric**: `tempogram`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `min_bpm` | number | 아니요 | `60.0` | tempogram 축의 최저 BPM |
| `max_bpm` | number | 아니요 | `200.0` | tempogram 축의 최고 BPM |

#### 출력 예시

```json
{
  "frames": [[0.12, 0.08, "..."], "..."],
  "bpm_axis": [60.0, 62.4, "...", 200.0],
  "fps": 86.13,
  "sample_rate": 44100
}
```

---

### 4. 활성 구간 감지

**ID**: `detect-activity`
**Metric**: `activity`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `min_duration` | duration | 아니요 | `0.3s` | 활성 구간의 최소 지속시간 |
| `level` | number | 아니요 | `0.35` | 곡의 조용함-큰 소리 범위 내 임계값 (0.0 = quiet floor, 1.0 = loud ceiling) |

#### 출력 예시

```json
{
  "activity": [
    { "start_time": 3.0,  "end_time": 7.04 },
    { "start_time": 12.5, "end_time": 44.8 }
  ]
}
```

빈 리스트는 곡에 임계값을 세울 다이내믹 레인지가 없다는 뜻입니다.

---

### 5. 음악 조성 감지

**ID**: `detect-key`
**Metric**: `key`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |

#### 출력 예시

```json
{
  "key": "C",
  "mode": "major",
  "confidence": 0.10
}
```

`confidence`는 우승한 key/mode와 2위 사이의 상관관계 격차입니다.

---

### 6. 크로마 추출

**ID**: `extract-chroma`
**Metric**: `chroma`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |

#### 출력 예시

```json
{
  "frames": [[0.1, 0.05, "...", 0.3], "..."],
  "fps": 86.13,
  "sample_rate": 44100
}
```

각 프레임은 `C, C#, D, D#, E, F, F#, G, G#, A, A#, B` 순의 12개 pitch-class 에너지입니다.

---

### 7. Tonnetz 추출

**ID**: `extract-tonnetz`
**Metric**: `tonnetz`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |

#### 출력 예시

```json
{
  "frames": [[0.1, -0.05, "...", 0.2], "..."],
  "fps": 86.30,
  "sample_rate": 44100
}
```

각 프레임은 Harte tonnetz 상의 6개 tonal-centroid 좌표입니다.

---

### 8. 스펙트럴 밝기 측정

**ID**: `measure-brightness`
**Metric**: `brightness`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |

#### 출력 예시

```json
{
  "brightness_hz": 2140.5,
  "frames": [2130.1, 2145.3, "..."],
  "fps": 86.13,
  "sample_rate": 44100
}
```

---

### 9. 스펙트럴 평탄도 측정

**ID**: `measure-flatness`
**Metric**: `flatness`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |

#### 출력 예시

```json
{
  "flatness": 0.12,
  "frames": [0.10, 0.13, "..."],
  "fps": 86.13,
  "sample_rate": 44100
}
```

---

### 10. 하모닉/퍼커시브 비율 측정

**ID**: `measure-harmonicity`
**Metric**: `harmonicity`

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |

#### 출력 예시

```json
{
  "harmonicity": 0.72,
  "percussivity": 0.28
}
```

## 커스터마이징

### 여러 리듬 metric에서 스펙트럼 재사용

`beats`, `onsets`, `tempogram`, `activity`는 내부적으로 같은 onset envelope를 소비합니다. 같은 트랙에서 여러 metric을 실행할 때는 `audio-feature-extractor` 컴포넌트로 스펙트럼을 미리 계산해 각 metric에 넘기면 중복 FFT를 피할 수 있습니다:

```yaml
components:
  - id: extractor
    type: audio-feature-extractor
    driver: native
    action:
      feature: spectrum
      audio: ${input.audio as file}
      fps: 100
      band_count: 128

  - id: analyzer
    type: music-analyzer
    driver: native
    actions:
      - id: beats
        metric: beats
        spectrum: ${extractor.result}

      - id: onsets
        metric: onsets
        spectrum: ${extractor.result}
```

조성 및 스펙트럴 특성 metric(`key`, `chroma`, `tonnetz`, `brightness`, `flatness`, `harmonicity`)은 raw 오디오가 필요하므로 `audio: ...`를 직접 넘기세요.

### 샘플레이트

기본적으로 파일의 원본 샘플레이트가 유지됩니다. 리샘플을 강제하려면 (긴 트랙에서 속도를 위해 정확도를 트레이드오프할 때) 액션에 `sample_rate`를 지정하세요:

```yaml
actions:
  - id: beats
    metric: beats
    audio: ${input.audio as file}
    sample_rate: 22050
```

### BPM 검색 범위

`beats`와 `tempogram`은 `min_bpm` / `max_bpm`을 받습니다. 장르의 템포 대역이 명확할 때 (예: 하우스/테크노 `100`–`140`, lo-fi `60`–`90`) 범위를 좁히면 도움이 됩니다:

```yaml
actions:
  - id: beats
    metric: beats
    audio: ${input.audio as file}
    min_bpm: 100
    max_bpm: 140
```

### Activity 레벨 임계값

`activity`의 `level`은 곡 자체의 조용함-큰 소리 백분위를 `[0, 1]`로 매핑합니다. 가장 큰 섹션만 (드롭, 코러스 등) 분리하려면 올리고, 조용한 부분도 잡으려면 낮추세요:

```yaml
actions:
  - id: activity
    metric: activity
    audio: ${input.audio as file}
    level: 0.6
    min_duration: 2s
```

상대 임계값이 아닌 절대 dBFS 기준이 필요하면 [`audio-silence-detector`](../audio-silence-detector/)를 사용하세요.
