# 샷 경계 감지 예제 (TransNetV2)

이 예제는 model-compose의 `shot-boundary-detection` 모델 태스크와 **TransNetV2** 딥러닝 모델을 사용하여 비디오 파일의 샷 경계를 감지하는 방법을 보여줍니다.

## 개요

TransNetV2는 CNN 기반 샷 경계 감지 모델로, 디졸브·페이드·와이프·빠른 움직임 등 휴리스틱 방식(프레임 차이·히스토그램)이 취약한 케이스에서 뛰어난 성능을 냅니다.

이 예제는 2가지 워크플로우를 제공합니다:

1. **기본 감지**: 전체 비디오에서 샷 경계 감지
2. **시간 범위 감지**: 특정 시간 범위 내에서 샷 경계 감지

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- FFmpeg 설치 (내부적으로 프레임 추출에 사용)
- Python 의존성은 첫 실행 시 자동 설치:
  - `transnetv2` (TransNetV2 패키지 설치)

### 모델 가중치 다운로드

`transnetv2` pip 패키지에는 사전학습 가중치가 **포함되어 있지 않습니다**. [공식 TransNetV2 저장소](https://github.com/soCzech/TransNetV2)에서 SavedModel 가중치를 받아 `./models/transnetv2-weights/` 아래에 배치해야 합니다.

```bash
# 이 예제 디렉토리에서:
mkdir -p ./models

# 옵션 1: 저장소 clone (git-lfs 필요)
git lfs install
git clone https://github.com/soCzech/TransNetV2.git /tmp/TransNetV2
cp -r /tmp/TransNetV2/inference/transnetv2-weights ./models/

# 옵션 2: 이미 가중치가 있다면 심링크 또는 복사
ln -s /path/to/transnetv2-weights ./models/transnetv2-weights
```

이 단계 이후 디렉토리 구조는 다음과 같아야 합니다:
```
./models/transnetv2-weights/
├── saved_model.pb
└── variables/
    ├── variables.data-00000-of-00001
    └── variables.index
```

> 참고: 합리적인 처리량을 위해서는 GPU가 권장되며, CPU 추론도 동작하지만 상당히 느립니다.

### 설정

이 예제 디렉토리로 이동:
```bash
cd examples/model-tasks/shot-boundary-detection
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
   - 비디오 파일 업로드
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   # 기본 감지
   model-compose run detect-shots --input '{"video": "/path/to/video.mp4"}'

   # 임계값 커스텀
   model-compose run detect-shots --input '{"video": "/path/to/video.mp4", "threshold": 0.4}'

   # 시간 범위 감지
   model-compose run detect-shots-range --input '{
     "video": "/path/to/video.mp4",
     "start_time": "00:01:00",
     "end_time": "00:05:00"
   }'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=detect-shots" \
     -F "video=@/path/to/video.mp4"
   ```

## 컴포넌트 세부사항

### 샷 경계 감지 컴포넌트

- **유형**: `model`
- **태스크**: `shot-boundary-detection`
- **드라이버**: `custom`
- **패밀리**: `transnetv2`
- **목적**: 딥러닝 모델을 사용하여 비디오 파일의 샷 경계 및 전환 감지

## 워크플로우 세부사항

### 1. 샷 감지

**ID**: `detect-shots`
**설명**: 전체 비디오에서 샷 경계 감지

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | file | 예 | - | 분석할 비디오 파일 |
| `threshold` | number | 아니오 | `0.5` | 감지 신뢰도 임계값 (0.0 - 1.0) |

---

### 2. 샷 감지 (시간 범위)

**ID**: `detect-shots-range`
**설명**: 특정 시간 범위 내에서 샷 경계 감지

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | file | 예 | - | 분석할 비디오 파일 |
| `threshold` | number | 아니오 | `0.5` | 감지 신뢰도 임계값 (0.0 - 1.0) |
| `start_time` | string | 아니오 | - | 시작 시간 (예: `00:01:00`) |
| `end_time` | string | 아니오 | - | 종료 시간 (예: `00:05:00`) |

---

### 출력 형식

모든 워크플로우는 감지된 샷들의 평평한 리스트를 반환합니다.

| 필드 | 유형 | 설명 |
|-----|------|------|
| `index` | integer | 샷 인덱스 (0부터 시작) |
| `start_time` | string | 샷 시작 타임코드 (HH:MM:SS.mmm) |
| `end_time` | string | 샷 종료 타임코드 (HH:MM:SS.mmm) |
| `start_frame` | integer | 샷 시작 프레임 번호 |
| `end_frame` | integer | 샷 종료 프레임 번호 |
| `duration` | string | 샷 지속 시간 타임코드 |

#### 출력 예시

```json
[
  {
    "index": 0,
    "start_time": "00:00:00.000",
    "end_time": "00:00:12.345",
    "start_frame": 0,
    "end_frame": 370,
    "duration": "00:00:12.345"
  },
  {
    "index": 1,
    "start_time": "00:00:12.345",
    "end_time": "00:00:28.678",
    "start_frame": 370,
    "end_frame": 860,
    "duration": "00:00:16.333"
  }
]
```

## 임계값 가이드

TransNetV2 임계값은 `0.0` ~ `1.0` 범위이며, 모델이 한 프레임을 샷 경계로 판정하기 위해 필요한 신뢰도를 조절합니다:

- `0.3` - 더 민감 (미세한 전환도 감지, 과분할 가능)
- `0.5` - 기본값 (균형)
- `0.7` - 덜 민감 (강한 전환만 감지)

## TransNetV2 사용 시점

TransNetV2는 다양한 전환 효과가 있는 콘텐츠에서 진가를 발휘합니다. 단순한 콘텐츠이거나 GPU 없이 사용하는 환경이라면 `video-scene-detector` 컴포넌트(`pyscenedetect` 또는 `ffmpeg` 드라이버)가 더 나은 선택일 수 있습니다.

| 콘텐츠 유형 | 권장 |
|-------------|------|
| 디졸브·페이드가 있는 영화·드라마·다큐 | `shot-boundary-detection` (이 예제) |
| 다양한 전환 효과가 있는 뮤직비디오·광고 | `shot-boundary-detection` (이 예제) |
| 대부분 하드 컷 위주의 UGC | `video-scene-detector` + `pyscenedetect` 또는 `ffmpeg` |
| 빠른 프로토타이핑 또는 CPU 전용 환경 | `video-scene-detector` + `ffmpeg` |
