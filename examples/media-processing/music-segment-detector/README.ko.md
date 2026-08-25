# 음악 구간 감지 예제

이 예제는 model-compose의 `music-segment-detector` 컴포넌트를 사용하여 비트 동기화된 크로마 특성과 클러스터링으로 음악의 구조적 구간 경계(인트로, 벌스, 코러스 등)를 찾는 방법을 보여줍니다.

## 개요

이 예제는 2가지 음악 구간 감지 워크플로우를 제공합니다:

1. **라플라시안 세그멘테이션** (기본): 비트 동기화된 크로마 + MFCC 스펙트럴(라플라시안) 클러스터링으로 구간 경계 감지. 반복되는 섹션(벌스, 코러스 등)이 같은 구조적 레이블을 받는 경향이 있어, 반복 구조가 명확한 음악에 적합
2. **응집형(Agglomerative) 세그멘테이션**: 데이터 기반의 구간 개수로 응집형 클러스터링을 통해 경계 감지. 짧은 클립이나 특이한 소재에서 라플라시안 결과가 불안정할 때 사용

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- Python 의존성은 첫 실행 시 자동 설치:
  - `librosa`, `numpy`, `scipy`, `scikit-learn` (`native` 드라이버용)

### 설정

이 예제 디렉토리로 이동:
```bash
cd examples/media-processing/music-segment-detector
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
   # 라플라시안 세그멘테이션 (기본)
   model-compose run detect-segments --input '{"audio": "/path/to/track.mp3"}'

   # 샘플레이트 지정
   model-compose run detect-segments --input '{
     "audio": "/path/to/track.mp3",
     "sample_rate": 44100
   }'

   # 응집형 세그멘테이션
   model-compose run detect-segments-agglomerative --input '{"audio": "/path/to/track.mp3"}'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-segments" \
     -F "audio=@/path/to/track.mp3"
   ```

## 컴포넌트 세부사항

### 음악 구간 감지 컴포넌트

- **유형**: `music-segment-detector`
- **목적**: 음악의 구조적 구간 경계를 감지하고 각 구간에 구조 레이블을 부여하여 반복되는 섹션을 식별할 수 있게 함
- **드라이버**:
  - `native` - librosa 기반 분석, 세그멘테이션 전략 설정 가능 (기본값)

## 워크플로우 세부사항

### 1. 음악 구간 감지 (라플라시안)

**ID**: `detect-segments`
**설명**: 비트 동기화된 크로마 + MFCC 스펙트럴 클러스터링으로 구간 경계 감지. 반복되는 섹션이 같은 구조적 레이블을 받음.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `sample_rate` | integer | 아니오 | `22050` | 분석에 사용할 모노 PCM 목표 샘플레이트 |

---

### 2. 음악 구간 감지 (응집형)

**ID**: `detect-segments-agglomerative`
**설명**: 데이터 기반의 구간 개수로 응집형 클러스터링을 통해 경계 감지. 짧거나 비표준적인 트랙에서 라플라시안 결과가 불안정할 때 권장.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `audio` | file | 예 | - | 분석할 오디오 파일 |
| `sample_rate` | integer | 아니오 | `22050` | 분석에 사용할 모노 PCM 목표 샘플레이트 |

---

### 출력 형식

각 워크플로우는 전체 오디오 타임라인을 커버하는 연속된 구간들의 평평한 리스트를 반환합니다. 같은 레이블을 갖는 인접 구간은 자동으로 병합됩니다.

| 필드 | 유형 | 설명 |
|-----|------|------|
| `start_time` | number | 구간 시작 시간 (초) |
| `end_time` | number | 구간 종료 시간 (초) |
| `label` | string | 구조 레이블 (`A`, `B`, `C`, ...); 같은 레이블이 반복되면 구조적으로 유사한 섹션임을 의미 |

#### 출력 예시

```json
[
  { "start_time": 0.0,    "end_time": 12.345, "label": "A" },
  { "start_time": 12.345, "end_time": 45.678, "label": "B" },
  { "start_time": 45.678, "end_time": 78.900, "label": "C" },
  { "start_time": 78.900, "end_time": 112.234, "label": "B" }
]
```

위 예시에서 두 개의 `B` 구간은 구조적으로 유사한 섹션(예: 두 번의 코러스)으로 취급됩니다.

## 맞춤화

### 전략 가이드

- **`laplacian`** — 벌스/코러스/브릿지처럼 인식 가능한 반복 구조가 있는 일반적인 곡에 가장 적합한 기본값. 경계와 구조 레이블을 한 번에 산출하므로 반복 섹션이 자연스럽게 정렬됨
- **`agglomerative`** — 반복 모델 없이 데이터 기반으로 구간 개수를 결정. 매우 짧은 클립, 앰비언트/실험적 소재, 또는 `laplacian`이 불안정한 경계를 낼 때 권장

### 샘플레이트

기본값 `22050` Hz는 분석 품질과 속도의 균형을 잘 맞추며, 음악 정보 검색(MIR) 작업의 표준값입니다. 미세한 음색 디테일이 중요한 소재에서는 `44100`으로 올릴 수 있으나, 분석은 느려지고 경계 정밀도의 향상은 미미합니다.

### 최소 구간 지속 시간

컴포넌트의 기본 `min_segment_duration`은 `2s`입니다(이보다 짧은 구간은 이웃 구간에 병합됨). 훨씬 세밀한 전환을 노출하거나, 반대로 더 큰 구조만 남기려면 액션에서 `min_segment_duration`을 지정하세요:

```yaml
actions:
  - id: laplacian
    audio: ${input.audio as file}
    strategy: laplacian
    min_segment_duration: 5s   # 더 큰 구조적 관점
```
