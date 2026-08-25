# 오디오 분석 예제

이 예제는 model-compose의 `audio-analyzer` 컴포넌트를 사용하여 오디오 파일의 신호 수준 속성(라우드니스, 피크, 게인, 클리핑, 무음, 에너지)을 오디오 자체를 변형하지 않고 검사하는 방법을 보여줍니다.

## 개요

이 예제는 지원되는 모든 metric을 커버하는 7가지 분석 워크플로우를 제공합니다:

1. **라우드니스 측정**: EBU R128 통합 라우드니스, 라우드니스 범위(LRA), 트루 피크
2. **피크 레벨 측정**: 샘플 피크와 인터샘플 트루 피크(dBTP)
3. **게인/헤드룸 측정**: RMS, 피크, 헤드룸, 크레스트/플랫 팩터 — 정규화 판단에 필요한 입력
4. **클리핑 감지**: 디지털 클리핑 카운트와 비율
5. **무음 감지**: 무음 구간과 전체 무음 비율
6. **에너지 프로파일 측정**: 활성 비율, 피크, 평균 라우드니스, 그리고 버킷 단위 에너지 프로파일 전체
7. **최적 BGM 세그먼트 찾기**: 에너지 프로파일을 스캔하여 요청된 길이의 가장 강한 세그먼트를 반환 — 고정 길이 영상에 붙일 음악 트랙의 최적 구간 선택에 유용

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- FFmpeg 설치 (`ffmpeg` 드라이버에 필요)

### 설정

이 예제 디렉토리로 이동:
```bash
cd examples/media-processing/audio-analyzer
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
   - 오디오 파일 업로드 및 매개변수 조정 후 "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   # EBU R128 라우드니스 (윈도우별 타임라인 포함)
   model-compose run measure-loudness --input '{
     "audio": "/path/to/track.wav",
     "target_loudness": -23.0,
     "include_timeline": true
   }'

   # 샘플 및 트루 피크
   model-compose run measure-peak --input '{"audio": "/path/to/track.wav"}'

   # RMS / 헤드룸 / 크레스트 팩터
   model-compose run measure-gain --input '{"audio": "/path/to/track.wav"}'

   # 클리핑 카운트 (임계값은 dBFS)
   model-compose run detect-clipping --input '{
     "audio": "/path/to/track.wav",
     "threshold": -0.1
   }'

   # 무음 구간
   model-compose run detect-silence --input '{
     "audio": "/path/to/track.wav",
     "threshold": -60.0,
     "min_duration": "500ms"
   }'

   # 전체 에너지 분석 (프로파일 + 활성 비율 + 피크 + 최적 세그먼트)
   model-compose run measure-energy --input '{
     "audio": "/path/to/music.mp3",
     "threshold": -40.0,
     "segment_duration": 30.0,
     "resolution": "1s"
   }'

   # 동일한 분석이지만 선택된 세그먼트만 반환
   model-compose run find-best-bgm-segment --input '{
     "audio": "/path/to/music.mp3",
     "threshold": -40.0,
     "segment_duration": 30.0
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=measure-loudness" \
     -F "audio=@/path/to/track.wav"
   ```

## 컴포넌트 세부사항

### 오디오 분석 컴포넌트

- **유형**: `audio-analyzer`
- **목적**: 오디오 파일의 신호 수준 속성을 측정하고 간결한 요약을 반환. 마스터링 QA, 레벨 정규화 판단, 무음 트리밍, 오디오를 변형하지 않고 *검사*가 필요한 모든 파이프라인에 사용
- **드라이버**:
  - `ffmpeg` - `ebur128`, `astats`, `silencedetect`를 사용하는 FFmpeg 기반 분석 (기본값)

## 워크플로우 세부사항

### 1. 라우드니스 측정

**ID**: `measure-loudness`
**설명**: EBU R128 기반 통합 라우드니스, 라우드니스 범위, 트루 피크

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `target_loudness` | number | 아니오 | `-23.0` | 기준 타깃 라우드니스 (LUFS) |
| `include_timeline` | boolean | 아니오 | `false` | 윈도우별 momentary/short-term/integrated 타임라인 포함 여부 |

#### 출력 예시

```json
{
  "integrated_loudness": -18.4,
  "loudness_range": 6.1,
  "loudness_range_low": -25.7,
  "loudness_range_high": -19.6,
  "sample_peak_dbfs": -1.2,
  "true_peak_dbtp": -0.8,
  "target_loudness": -23.0
}
```

---

### 2. 피크 레벨 측정

**ID**: `measure-peak`
**설명**: 샘플 피크와 인터샘플 트루 피크(dBTP)

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `true_peak` | boolean | 아니오 | `true` | 인터샘플 트루 피크(dBTP) 계산 여부 |

#### 출력 예시

```json
{
  "sample_peak_dbfs": -0.9,
  "max_sample": 0.902,
  "min_sample": -0.898,
  "true_peak_dbtp": -0.4
}
```

---

### 3. 게인/헤드룸 측정

**ID**: `measure-gain`
**설명**: RMS, 피크, 헤드룸, DC 오프셋, 크레스트/플랫 팩터 — 정규화/컴프레션 판단의 입력값

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |

#### 출력 예시

```json
{
  "rms_dbfs": -18.7,
  "rms_peak_dbfs": -6.2,
  "rms_trough_dbfs": -42.1,
  "peak_dbfs": -0.9,
  "headroom_db": 0.9,
  "dc_offset": 0.00012,
  "crest_factor": 8.4,
  "flat_factor": 0.02
}
```

---

### 4. 클리핑 감지

**ID**: `detect-clipping`
**설명**: `astats` 기반 디지털 클리핑 카운트와 비율. 세밀한 구간 감지는 아직 미구현 (`regions`는 빈 배열로 반환)

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `threshold` | number | 아니오 | `-0.1` | 클리핑으로 간주되는 진폭 임계값 (dBFS) |
| `min_consecutive_length` | integer | 아니오 | `3` | 클리핑 구간으로 인정되기 위한 최소 연속 초과 샘플 수 |

#### 출력 예시

```json
{
  "threshold_dbfs": -0.1,
  "min_consecutive_length": 3,
  "sample_count": 8820000,
  "clipped_sample_count": 342,
  "clipped_ratio": 0.0000387,
  "peak_dbfs": -0.02,
  "regions": []
}
```

---

### 5. 무음 감지

**ID**: `detect-silence`
**설명**: FFmpeg `silencedetect` 필터를 통한 무음 구간 감지

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `threshold` | number | 아니오 | `-60.0` | 무음으로 간주되는 진폭 임계값 (dBFS) |
| `min_duration` | string | 아니오 | `500ms` | 무음으로 인정되기 위한 최소 지속 시간 (예: `500ms`, `1s`, `2.5s`) |

#### 출력 예시

```json
{
  "threshold_dbfs": -60.0,
  "min_duration": 0.5,
  "duration": 180.5,
  "total_silent": 12.3,
  "silent_ratio": 0.068,
  "regions": [
    { "start": 0.0, "end": 3.4, "duration": 3.4 },
    { "start": 175.6, "end": 180.5, "duration": 4.9 }
  ]
}
```

---

### 6. 에너지 프로파일 측정

**ID**: `measure-energy`
**설명**: momentary 라우드니스를 거친 에너지 프로파일로 집계한 뒤 전체 분석 결과를 반환 — 활성 비율, 최초 활성 시각, 피크, 평균 라우드니스, 버킷별 프로파일, 그리고 (`segment_duration` 지정 시) 최적 세그먼트

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `threshold` | number | 아니오 | `-40.0` | 활성으로 간주되는 momentary 라우드니스 임계값 (LUFS) |
| `segment_duration` | number | 아니오 | `30.0` | 탐색할 세그먼트 길이(초). 생략 시 세그먼트 탐색을 건너뛰고 프로파일만 반환 |
| `resolution` | string | 아니오 | `1s` | 프로파일 집계에 사용할 다운샘플링 간격 |

#### 출력 예시

```json
{
  "threshold": -40.0,
  "duration": 180.5,
  "resolution": 1.0,
  "active_duration": 142.0,
  "active_ratio": 0.787,
  "first_active_time": 12.0,
  "peak_time": 45.0,
  "peak_loudness": -8.3,
  "average_loudness": -22.5,
  "best_segment": {
    "start": 45.0,
    "duration": 30.0,
    "average_loudness": -18.7
  },
  "profile": [
    { "time": 0.0, "loudness": null,  "active": false },
    { "time": 1.0, "loudness": -55.2, "active": false },
    { "time": 2.0, "loudness": -38.1, "active": true }
  ]
}
```

---

### 7. 최적 BGM 세그먼트 찾기

**ID**: `find-best-bgm-segment`
**설명**: `measure-energy`와 동일한 에너지 분석을 수행하지만, 워크플로우 출력은 선택된 세그먼트만으로 축약 — 다운스트림의 오디오 클리퍼가 바로 소비할 수 있는 필드

#### 입력 매개변수

`measure-energy`와 동일

#### 출력 예시

```json
{
  "start": 45.0,
  "duration": 30.0,
  "average_loudness": -18.7
}
```

## 맞춤화

### metric 선택 가이드

- **`loudness`** — 마스터링 QA, 지각적 레벨 체크, 방송 규격 준수
- **`peak`** — 인코딩 전 클립 안전성 체크. 특히 인터샘플 피크가 중요한 손실 압축 포맷
- **`gain`** — 정규화 이전 검사: 트랙의 평균 라우드니스와 남은 헤드룸
- **`clipping`** — 원본에 이미 존재하는 디지털 오버 감지
- **`silence`** — 시작/끝 데드 에어 정리, 긴 녹음을 구조적 정지 기준으로 분할
- **`energy`** — 긴 트랙에서 임팩트 있는 발췌 구간 선택 (BGM 선택, 썸네일, 프리뷰)

### 임계값 및 지속 시간 가이드

- **Loudness `target_loudness`**: `-23.0` LUFS는 EBU R128 방송 기준, `-14.0`은 스트리밍 플랫폼에서 흔히 사용
- **Silence `threshold` / `min_duration`**: 낮은 임계값과 긴 지속 시간을 조합하면 구조적 무음(테이크/곡 사이) 분리에 적합, 높은 임계값과 짧은 지속 시간은 세밀한 정지 감지에 적합
- **Energy `threshold`**: `-40.0` LUFS가 균형 잡힌 기본값. `-50`은 조용한 앰비언트 구간까지 포함, `-30`은 명확히 에너지 있는 구간만 고려
- **Energy `segment_duration`**: 음악이 붙을 영상 길이에 맞춰 지정. 세그먼트 스코어링 없이 에너지 프로파일만 원하면 생략

### metric 조합

여러 워크플로우를 조합해 상위 수준 도구를 구성할 수 있습니다:
- 라우드니스 + 피크 → 마스터링 프리플라이트
- 무음 + 에너지 → 조용한 인트로/아웃트로 자동 제거 후 가장 강한 세그먼트 선택
- 게인 + 클리핑 → 추가 처리 전 정규화(다운) 필요 여부 판단
