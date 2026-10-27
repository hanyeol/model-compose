# Active Speaker Detection Model Task 예제

이 예제는 model-compose의 내장 `active-speaker-detection` 작업과 Light-ASD를 사용해 **화면 속 어떤 인물이 현재 말하고 있는지**를 판별하는 방법을 보여줍니다. 업로드한 비디오에서 일정한 간격으로 프레임을 샘플링하고, InsightFace 얼굴 추적을 거친 뒤, 짝지어진 오디오로 Light-ASD가 각 트랙을 점수화하여 트랙별 발화 구간과 "지금 누가 말하고 있나"를 나타내는 플랫 타임라인을 산출합니다.

## 개요

이 워크플로우는 다음과 같은 로컬 활성 화자 검출을 제공합니다:

1. **로컬 활성 화자 모델**: 외부 API 없이 Light-ASD 모델을 로컬에서 실행
2. **얼굴 트랙 재사용**: 자체 얼굴 검출기를 돌리지 않고 짝지어진 `face-tracking` 컴포넌트가 생산한 검출 결과를 사용하여, 공유 프레임 시퀀스에 대해 바운딩 박스가 프레임 단위로 정확히 정렬되도록 보장
3. **오디오-비주얼 점수화**: 25 fps의 112x112 그레이스케일 얼굴 크롭과 16 kHz 모노 오디오에서 추출한 100 Hz MFCC 특징을 짝지어 평가
4. **발화 구간**: 프레임별 로짓 스트림을 트랙별 `start_time / end_time / duration` 구간으로 병합
5. **자동 소스 설치**: 첫 실행 시 Light-ASD 상위 저장소를 mindor 설치 루트에 `lightasd/`로 클론하고, Light-ASD 체크포인트를 `~/.cache/models/light_asd/`에 다운로드

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- ffmpeg가 설치되어 PATH에서 사용 가능 (프레임과 오디오 추출용)
- `git`이 설치되어 PATH에서 사용 가능 (첫 실행 시 Light-ASD 상위 소스 클론에 사용)
- 소형 torch 모델 실행을 위한 충분한 시스템 리소스 (권장: 4GB+ RAM)
- `torch`, `torchaudio`, `python_speech_features`, `insightface`, `opencv-python`, `onnxruntime`이 있는 Python 환경 (첫 실행 시 자동 설치)
- `./models/antelopev2`에 배치된 `antelopev2` 모델 팩 (face-tracking이 사용하며, 다운로드 레이아웃은 face-tracking 예제를 참고)

### 모델 설정

- Light-ASD 체크포인트는 첫 실행 시 상위 GitHub 저장소에서 자동으로 가져와 `~/.cache/models/light_asd/`에 캐시됩니다.
- Light-ASD 상위 소스는 임시 캐시(git 리비전으로 키됨)에 클론되어 첫 실행 시 실행 중인 `mindor` 패키지 옆에 `lightasd` 패키지로 설치됩니다. 이후 실행은 설치된 사본을 재사용합니다.
- `antelopev2` 얼굴 추적 팩은 **자동 다운로드되지 않습니다** — `./models/antelopev2` 아래에 배치하는 방법은 face-tracking 예제 README를 참고하세요.

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/active-speaker-detection
   ```

2. face-tracking 예제와 동일한 레이아웃으로 `antelopev2` 팩을 `./models/antelopev2` 아래에 배치하세요.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "frame_interval": 2, "sampled_frame_rate": 25.0}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `video` 파일 업로드
   - 필요 시 `frame_interval` / `sampled_frame_rate` 조정
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 2, "sampled_frame_rate": 25.0}'
   ```

## 컴포넌트 상세

### Frame Extractor 컴포넌트
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **역할**: 일정한 간격으로 프레임을 샘플링하고 리스트로 materialize하여 tracker와 speaker detector가 동일한 시퀀스를 소비할 수 있도록 함
- **주요 knob**: `frame_interval` (1 = 모든 프레임, 2 = 매 두 번째 프레임 등). 샘플링 fps가 모델 컴포넌트에 설정된 `sampled_frame_rate`와 일치하도록 값을 고르세요 (예: 50 fps 소스 + `frame_interval: 2` = 25 fps, Light-ASD가 훈련된 값)
- **Streaming**: 꺼짐. detector는 tracker가 본 것과 동일한 materialize된 프레임 리스트가 필요하므로 바운딩 박스가 정렬됩니다 — extractor의 출력을 스트리밍하면 detector가 읽기 전에 tracker에서 소진됩니다.

### Face Tracking 모델 컴포넌트
- **Type**: `face-tracking` 작업을 가진 Model 컴포넌트
- **Family**: `insightface`
- **Model**: 로컬 `./models/antelopev2` 팩
- **이 워크플로우에서의 역할**: speaker detector가 소비할 프레임별 `detections` 리스트 생산. 하위 단계에서는 프레임 레벨 바운딩 박스만 필요하므로 `return_tracks`는 비활성화하고 `return_detections`를 활성화.

### Active-Speaker Detection 모델 컴포넌트
- **Type**: `active-speaker-detection` 작업을 가진 Model 컴포넌트
- **Family**: `light-asd`
- **Preset**: `finetuning-talkset` (기본값) 또는 `pretrain-ava-cvpr`
- **기능**:
  - tracker와 동일한 materialize된 프레임을 받아 각 얼굴 트랙을 112x112 그레이스케일로 재크롭하고, 입력 비디오 오디오에서 추출한 100 Hz MFCC 특징과 짝지음
  - 프레임별 발화 로짓을 설정 가능한 윈도우로 스무딩한 후 임계값을 적용하므로 단일 프레임 깜빡임이 발화 구간을 조각내지 않음
  - 트랙별 발화 구간과 트랙 교차 `active_timeline` 산출
  - GPU 메모리 제한을 위한 직렬 실행 (`max_concurrent_count: 1`)

### 모델 정보: Light-ASD
- **상위 저장소**: [Junhua-Liao/Light-ASD](https://github.com/Junhua-Liao/Light-ASD) (CVPR 2023)
- **아키텍처**: 양방향 GRU 백엔드를 가진 경량 오디오-비주얼 2-stream 인코더 (~1M 파라미터)
- **훈련**: AVA-ActiveSpeaker (pretrain) 및 TalkSet (finetune)
- **입력 요구사항**: 25 fps 그레이스케일 얼굴 크롭 (112x112, 입을 중심에 둠) 및 16 kHz 모노 MFCC (100 Hz, 13 계수)
- **라이선스**: MIT

## 워크플로우 상세

### 기본 워크플로우

**설명**: 업로드한 비디오에서 프레임을 샘플링하고, 얼굴 추적을 실행하고, Light-ASD로 각 트랙을 점수화한 뒤 트랙별 발화 구간을 반환합니다.

#### Job 흐름

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[image, image, ...]| J1

    J1 --> J2((track<br/>job))
    J1 --> J3((detect<br/>job))
    J2 -.-> C2[Face Tracker<br/>insightface]
    C2 -.-> |detections| J2
    J2 --> J3

    Input --> |audio| J3
    J3 -.-> C3[Speaker Detector<br/>light-asd]
    C3 -.-> |speakers, active_timeline| J3

    J3 --> Output((Output<br/>report))
```

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `video` | video (file) | 예 | - | 입력 비디오 파일; Light-ASD에 공급되는 오디오의 소스이기도 함 |
| `frame_interval` | number | 아니오 | 2 | 추출 시 매 N번째 프레임을 샘플링. `source_fps / frame_interval` ≈ 25가 되도록 값을 선택 (Light-ASD는 25 fps로 훈련됨) |
| `sampled_frame_rate` | number | 아니오 | 25.0 | *샘플링된* 시퀀스의 초당 프레임 수. 프레임별 타임스탬프 도출에 사용. `source_fps / frame_interval`로 설정 |

#### 출력 형식

`report`는 다음을 포함하는 JSON 객체입니다:

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `speakers` | array | 발화 프레임을 생산한 얼굴 트랙별 항목 하나. 아래 참고. |
| `active_timeline` | array | 모든 트랙에 걸친 발화 구간의 시간순 플랫 리스트. 서로 다른 트랙의 겹치는 항목은 구분해서 유지. |
| `frame_count` | integer | 분석된 총 샘플 프레임 수 |
| `track_count` | integer | detector가 점수화한 총 얼굴 트랙 수 |

각 `speakers[i]` 항목:

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `track_id` | integer | 얼굴 추적 클러스터 ID; face-tracking 컴포넌트가 반환한 `track_id`와 매칭되므로 두 출력을 조인할 수 있음 |
| `segments` | array | `{start_time, end_time, duration, score}` 리스트. 아래 참고. |

각 `segments[j]` 항목:

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `start_time` | string | `H:MM:SS.mmm` 타임코드 형식의 구간 시작 |
| `end_time` | string | `H:MM:SS.mmm` 타임코드 형식의 구간 끝 |
| `duration` | string | `H:MM:SS.mmm` 타임코드 형식의 `end_time - start_time` |
| `score` | number | 이 구간의 모든 프레임에서 가장 높은 스무딩된 Light-ASD 로짓 |

각 `active_timeline[k]` 항목:

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `start_time` | string | `H:MM:SS.mmm` 타임코드 형식의 구간 시작 |
| `end_time` | string | `H:MM:SS.mmm` 타임코드 형식의 구간 끝 |
| `track_id` | integer | 이 항목 동안 어느 얼굴 트랙이 말하고 있는지 |
| `score` | number | 이 구간의 스무딩된 로짓 |

예시:

```json
{
  "report": {
    "speakers": [
      {
        "track_id": 1,
        "segments": [
          { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "duration": "0:00:06.500", "score": 1.42 }
        ]
      },
      {
        "track_id": 2,
        "segments": [
          { "start_time": "0:00:09.200", "end_time": "0:00:12.800", "duration": "0:00:03.600", "score": 1.08 }
        ]
      }
    ],
    "active_timeline": [
      { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "track_id": 1, "score": 1.42 },
      { "start_time": "0:00:09.200", "end_time": "0:00:12.800", "track_id": 2, "score": 1.08 }
    ],
    "frame_count": 450,
    "track_count": 2
  }
}
```

## 시스템 요구사항

### 최소 요구사항
- **RAM**: 4GB (권장 8GB+)
- **디스크 공간**: `antelopev2` 팩과 Light-ASD 소스 합계 ~1GB
- **CPU**: 최신 x86_64 또는 ARM64 프로세서
- **인터넷**: 일회성 상위 소스 클론과 Light-ASD 체크포인트 다운로드에 필요

### 성능 참고사항
- Light-ASD는 소형 모델(~1M 파라미터)로 짧은 클립에서는 CPU로도 충분한 경우가 많습니다. 긴 입력에서는 GPU(CUDA / MPS)가 더 빠릅니다.
- 긴 비디오에서 지배적인 비용은 Light-ASD 점수화가 아닌 얼굴 추적입니다.

## 커스터마이징

### AVA 체크포인트로 전환

기본 preset은 `finetuning-talkset` 가중치(일반 환경 발화에 더 적합)를 사용합니다. 영상의 훈련 분포에 맞추려면 active-speaker-detector 컴포넌트의 `preset`을 `pretrain-ava-cvpr`로 설정하세요:

```yaml
- id: active-speaker-detector
  type: model
  task: active-speaker-detection
  driver: custom
  family: light-asd
  preset: pretrain-ava-cvpr
```

### 발화 구간 다듬기 또는 패딩

컴포넌트의 `params` 블록은 구간 shaping knob을 노출합니다:

```yaml
params:
  smoothing_window: 0.4s       # 윈도우가 길수록 깜빡임을 더 억제
  threshold: 0.0               # 올리면 더 엄격; 내리면 작은 소리의 발화까지 포착
  min_segment_duration: 0.3s   # 병합 후 이 길이보다 짧은 구간은 삭제
  merge_gap: 0.2s              # 같은 트랙에서 최대 이 간격만큼 떨어진 구간은 병합
```

### 트랙별 분석 없이 타임라인만

트랙별 분석을 제거하고 시간순 플랫 리스트만 반환하려면 `return_speakers: false`와 `return_timeline: true`로 설정하세요. detector는 내부적으로 여전히 트랙별 점수화를 수행하며, 이는 단순히 분석을 숨길 뿐입니다.

## 문제 해결

### 자주 발생하는 문제

1. **발화 구간이 반환되지 않음**: `audio` 입력에 실제로 발화가 담겨 있는지 확인하세요 — Light-ASD는 얼굴 움직임과 무관하게 무음을 비발화로 점수화합니다. 또한 `sampled_frame_rate` ≈ 25인지 확인하세요. 편차가 크면 얼굴 크롭이 MFCC 윈도우와 맞지 않는 프레임으로 밀려 로짓이 평평해집니다.
2. **화자가 하나의 트랙으로 합쳐짐**: 조인은 face-tracking의 `track_id`를 기준으로 합니다 — 서로 다른 두 사람이 하나의 트랙을 공유하면 speaker detector는 둘의 발화를 모두 그 단일 트랙에 귀속시킵니다. 이 경우 face-tracker의 `similarity_threshold`를 조정하세요.
3. **모델 파일을 찾을 수 없음**: Light-ASD 체크포인트와 상위 소스는 자동으로 provisioning됩니다. 첫 실행이 실패하면 `git`이 `PATH`에 있는지, 그리고 `github.com` / `raw.githubusercontent.com`에 접근할 수 있는지 확인하세요.
4. **`frame_rate` 불일치 경고**: `sampled_frame_rate`가 `source_fps / frame_interval`과 일치하는지 확인하세요.

### 성능 최적화

- **GPU**: 더 빠른 추론을 위해 CUDA가 활성화된 `torch`(및 얼굴 추적용 `onnxruntime-gpu`)를 설치하세요.
- **짧은 프레임**: `sampled_frame_rate`와 `frame_interval`을 비례해서 낮추세요 — Light-ASD는 25 fps로 훈련되었으므로 점수 품질을 위해 그 근처를 유지하는 것이 중요합니다.
