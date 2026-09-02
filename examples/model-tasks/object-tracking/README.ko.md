# Object Tracking Model Task 예제

이 예제는 model-compose의 내장 `object-tracking` 작업과 Ultralytics YOLO를 사용하여 비디오 프레임 전반에서 객체를 추적하는 방법을 보여줍니다. 업로드한 비디오에서 일정한 간격으로 프레임을 샘플링하고, YOLO 검출과 내장 트래커(ByteTrack / BoT-SORT)를 거쳐 동일 객체가 프레임 사이에서 안정적인 아이덴티티를 유지하도록 합니다. 결과는 객체별 세그먼트 리포트로, 각 세그먼트마다 타임코드·레이블·베스트 프레임 bounding box가 포함됩니다.

## 개요

이 워크플로우는 다음과 같은 로컬 객체 추적을 제공합니다:

1. **로컬 YOLO 모델**: 외부 API 없이 Ultralytics YOLO 검출 체크포인트를 로컬에서 실행
2. **프레임 샘플링**: ffmpeg으로 사용자가 지정한 간격으로 입력 비디오에서 프레임 추출
3. **아이덴티티 추적**: 프레임을 YOLO 내장 트래커(ByteTrack 또는 BoT-SORT)에 입력하여 각 객체가 프레임 사이에서 안정적인 `track_id`를 유지
4. **세그먼트 집계**: 프레임별 타임스탬프를 객체별 `start_time / end_time / duration` 구간으로 병합
5. **스트리밍 처리**: extractor가 ffmpeg의 생성 속도에 맞춰 프레임을 트래커에 흘려보내므로 긴 영상도 전체를 버퍼링하지 않음
6. **자동 모델 관리**: 첫 실행 시 `yolov8n.pt` 기본 체크포인트를 자동으로 다운로드 및 캐시

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- ffmpeg가 설치되어 PATH에서 사용 가능 (프레임 추출용)
- YOLO 실행을 위한 충분한 시스템 리소스 (권장: 4GB+ RAM)
- `ultralytics`와 `lap`이 있는 Python 환경 (첫 실행 시 자동 설치)

### YOLO 모델 가중치

수동 준비가 필요 없습니다. [model-compose.yml](model-compose.yml)의 `model.path`는 `./models/yolov8n.pt`를 가리키며, 첫 실행 시 파일명에 대응하는 Ultralytics 릴리스에서 자동으로 다운로드되어 `./models/`에 캐시됩니다. 이후 실행은 이 파일을 재사용합니다.

다른 체크포인트를 사용하려면(더 큰 모델이나 파인튜닝한 모델 등), `.pt` 파일을 `./models/`에 넣고 `model.path`가 그것을 가리키게 하거나, `model.path`에 Ultralytics 프리셋 이름(`yolov8n.pt`, `yolo11n.pt`, `yolo11s.pt`, …)을 지정하면 됩니다.

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/object-tracking
   ```

2. 별도의 환경 설정은 필요하지 않습니다. 첫 실행이 체크포인트를 자동으로 다운로드합니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 기본 yolov8n.pt로 COCO의 모든 클래스 추적
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "frame_interval": 5, "sampled_frame_rate": 6.0}'

   # 특정 레이블만 추적
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "clip=@/path/to/video.mp4" \
     -F 'input={"video": "@clip", "labels": ["person", "car"], "min_confidence": 0.35}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `video` 파일 업로드
   - 필요 시 `frame_interval` / `sampled_frame_rate` / `labels` / `tracker` 조정
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 5, "sampled_frame_rate": 6.0}'
   ```

## 컴포넌트 상세

### Frame Extractor 컴포넌트
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **목적**: 입력 비디오에서 일정한 간격으로 프레임을 샘플링하여 트래커에 이미지 스트림으로 흘려보냄
- **핵심 노브**: `frame_interval` (1 = 모든 프레임, 5 = 5프레임마다 하나 등)
- **스트리밍**: 활성화. extractor의 원본 청크 형태는 `{image, timestamp, number, ...}`이며, `output: ${result[].image}`가 각 청크를 `image`로 투영하여 다운스트림 소비자가 단순 이미지 스트림을 받게 합니다. ffmpeg가 프레임을 생산하는 대로 object-tracking으로 흘러가므로 긴 영상도 전체를 버퍼링하지 않습니다.

### Object Tracking Model 컴포넌트
- **Type**: `object-tracking` 작업의 Model 컴포넌트
- **Family**: `yolo`
- **Model**: 로컬 `./models/yolov8n.pt` (첫 실행 시 자동 다운로드)
- **기능**:
  - 프레임별로 YOLO 검출을 수행한 뒤 결과를 ByteTrack 또는 BoT-SORT로 넘겨 프레임 사이에서 `track_id`가 안정적으로 유지되도록 함
  - 프레임 스트림을 지연 소비 — 전체 비디오를 버퍼링하지 않음
  - 프레임별 검출을 트랙별 세그먼트(`start_time / end_time / duration`)로 집계하여 H:MM:SS.mmm 타임코드 형태로 생성. 각 세그먼트는 베스트 프레임의 레이블과 bounding box를 함께 포함
  - GPU 메모리를 제한하기 위한 직렬 실행 (`max_concurrent_count: 1`)

### 모델 정보: yolov8n (Ultralytics)
- **제공자**: Ultralytics
- **작업**: 객체 검출 (기본 80-class COCO)
- **크기**: Nano — YOLOv8의 가장 작고 빠른 변종
- **사용 가능한 트래커**: ByteTrack (기본), BoT-SORT
- **라이선스**: AGPL-3.0 (Ultralytics)

## 워크플로우 상세

### 기본 워크플로우

**설명**: 업로드한 비디오에서 프레임을 샘플링하고, 객체 추적을 실행하며, 객체별 세그먼트를 반환합니다.

#### Job 흐름

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[{image, timestamp, ...}]| J1

    J1 --> J2((track<br/>job))
    J2 -.-> C2[Object Tracker<br/>yolo]
    C2 -.-> |{tracks, detections}| J2

    J2 --> Output((Output<br/>report))
```

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | video (file) | Yes | - | 입력 비디오 파일 |
| `frame_interval` | number | No | 5 | 추출 시 N번째 프레임마다 하나씩 샘플링 |
| `sampled_frame_rate` | number | No | 6.0 | *샘플링된* 시퀀스의 초당 프레임 수. 프레임별 타임스탬프 산출에 사용되며 `source_fps / frame_interval` 값으로 설정 |
| `labels` | list[string] | No | - | 이 클래스 레이블(예: `["person", "car"]`)로 검출을 제한. 알 수 없는 레이블은 즉시 실패. 지정하지 않으면 모델이 아는 모든 클래스 반환 |
| `min_confidence` | number | No | 0.25 | 검출 최소 신뢰도 `[0, 1]` |
| `min_frame_count` | number | No | 3 | 이 값보다 적은 프레임에만 등장하는 트랙은 폐기 |
| `merge_gap` | number | No | 0.5 | 객체가 검출되지 않아도 세그먼트가 분리되지 않도록 허용하는 추가 초. 연속된 프레임은 항상 병합 |
| `tracker` | string | No | `bytetrack` | 사용할 Ultralytics 트래커 — `bytetrack` 또는 `botsort` |
| `return_detections` | boolean | No | true | 프레임 중심 뷰(각 샘플 프레임 하나당 하나의 항목, `track_id`로 태깅)를 `tracks`와 함께 포함할지 여부 |
| `return_frame_image` | boolean | No | false | 각 detection 항목에 전체 소스 프레임을 첨부. `return_detections: true` 필요 |

#### 출력 형식

`report`는 다음 필드를 갖는 JSON 객체입니다:

| 필드 | 타입 | 설명 |
|------|------|------|
| `tracks` | array | 검출된 객체 아이덴티티당 하나의 항목 (아래 참조) |
| `detections` | array | 프레임 중심 detection 뷰 — 각 샘플 프레임당 하나의 항목, `track_id`로 태깅된 검출 객체 포함. `return_detections`가 활성화된 경우에만 존재 |

각 `tracks[i]` 항목:

| 필드 | 타입 | 설명 |
|------|------|------|
| `track_id` | integer | 트래커가 부여한 아이덴티티. 비디오 전체에서 안정적으로 유지됨 |
| `label` | string | 베스트 스코어 프레임의 클래스 레이블 (예: `"person"`, `"car"`) |
| `label_id` | integer | 모델이 보고한 정수 클래스 인덱스 |
| `segments` | array | 이 트랙이 등장한 세그먼트 리스트. 아래 참조 |
| `frame_count` | integer | 이 트랙이 등장한 샘플 프레임 총 개수 |
| `score` | number | 이 트랙에 속한 모든 프레임 중 최고 검출 신뢰도 |

각 `segments[j]` 항목:

| 필드 | 타입 | 설명 |
|------|------|------|
| `start_time` | string | 세그먼트 시작 (`H:MM:SS.mmm` 타임코드) |
| `end_time` | string | 세그먼트 종료 (`H:MM:SS.mmm` 타임코드) |
| `duration` | string | `end_time - start_time` (`H:MM:SS.mmm` 타임코드) |
| `label` | string | 세그먼트의 베스트 스코어 프레임의 클래스 레이블 |
| `label_id` | integer | 세그먼트의 베스트 스코어 프레임의 정수 클래스 인덱스 |
| `score` | number | 세그먼트의 베스트 스코어 프레임의 검출 신뢰도 |
| `bounding_box` | object | 세그먼트의 베스트 스코어 프레임의 `{x, y, width, height}` (픽셀, top-left 원점) |

각 `detections[k]` 항목 (`return_detections` 활성화 시):

| 필드 | 타입 | 설명 |
|------|------|------|
| `number` | integer | 이 샘플 프레임의 1부터 시작하는 인덱스 |
| `timestamp` | string | 프레임 타임스탬프 (`H:MM:SS.mmm` 타임코드) |
| `objects` | array | 이 프레임의 검출 객체들. 각 객체는 `track_id`, `label`, `label_id`, `bounding_box`, `score`를 포함하며, 검출이 누락된 구간에서 선형 보간된 box인 경우 `interpolated: true`가 추가됨 |
| `image` | image | 전체 샘플 프레임. `return_frame_image`가 활성화된 경우에만 존재 |

예시 (`return_detections: false`):

```json
{
  "report": {
    "tracks": [
      {
        "track_id": 1,
        "label": "person",
        "label_id": 0,
        "segments": [
          {
            "start_time": "0:00:00.500", "end_time": "0:00:04.833", "duration": "0:00:04.333",
            "label": "person", "label_id": 0, "score": 0.91,
            "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 460 }
          }
        ],
        "frame_count": 26,
        "score": 0.91
      }
    ]
  }
}
```

## 시스템 요구사항

### 최소 요구사항
- **RAM**: 4GB (권장 8GB+)
- **디스크 공간**: `yolov8n.pt`용 ~10MB (더 큰 변종: `yolov8s.pt` ~22MB, `yolov8m.pt` ~52MB, `yolov8l.pt` ~87MB, `yolov8x.pt` ~136MB)
- **CPU**: 현대적인 x86_64 또는 ARM64 프로세서
- **인터넷**: 1회성 가중치 다운로드에 필요

### 성능 참고
- 검출 비용은 샘플 프레임 수에 비례합니다. 잡고자 하는 최소 세그먼트를 커버할 수 있도록 `frame_interval`을 정하세요 (예: 6 fps로 샘플링하면 연속 등장 ≥ ~0.5초를 잡을 수 있음)
- GPU(CUDA)를 사용하면 처리량이 크게 향상됩니다. Apple Silicon에서는 사용 가능한 경우 MPS 백엔드가 자동으로 사용됩니다
- 첫 실행은 YOLO와 트래커 초기화 때문에 느립니다. 이후 실행은 빠릅니다
- 트래커가 extractor의 스트림에서 프레임을 지연 소비하므로 피크 메모리가 비디오 길이에 비례해 증가하지 않습니다

## 사용자 정의

### 더 조밀하게 샘플링

`frame_interval`을 낮추고 그에 맞춰 `sampled_frame_rate`를 올리세요. 30 fps 소스에서 2프레임마다 샘플링하면 15 fps가 됩니다:

```bash
model-compose run --input '{"video": "clip.mp4", "frame_interval": 2, "sampled_frame_rate": 15.0}'
```

### 트래커 전환

`bytetrack`은 더 빠르고 대부분의 장면에서 잘 동작합니다. `botsort`는 외관 특징(ReID)을 추가하여 짧은 가림(occlusion)에 더 강한 편입니다:

```bash
model-compose run --input '{"video": "clip.mp4", "tracker": "botsort"}'
```

### 특정 클래스로 제한

관심 있는 클래스만 남기려면 `labels` 리스트를 전달하세요. 리스트에 없는 검출은 추적 이전에 제거되므로 처리 속도도 빨라집니다:

```bash
model-compose run --input '{"video": "clip.mp4", "labels": ["person"], "min_confidence": 0.4}'
```

### 사용자 정의 모델 사용

`model-compose.yml`의 `model` 블록을 임의의 Ultralytics YOLO 체크포인트를 가리키도록 교체하세요. 예를 들어 자체 데이터셋으로 파인튜닝한 검출기:

```yaml
- id: object-tracker
  type: model
  task: object-tracking
  driver: custom
  family: yolo
  model:
    provider: local
    path: /path/to/your/model.pt
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    labels: [ your_class_a, your_class_b ]
    params:
      tracker: bytetrack
      min_confidence: 0.3
```

Segmentation 체크포인트(`yolo11*-seg.pt` 등)도 지원됩니다 — bounding box만 사용됩니다.

### 물리화된 프레임 리스트 (non-streaming)

이 예제는 extractor를 스트리밍 모드로 실행합니다. 전체 프레임 리스트를 먼저 물리화하고 싶다면(예: `for-each` job에서 확인하거나 디스크에 저장) `streaming`을 끄고 투영을 `[*]`로 바꾸세요:

```yaml
- id: frame-extractor
  type: video-frame-extractor
  driver: ffmpeg
  action:
    video: ${input.video}
    frame_interval: ${input.frame_interval}
    streaming: false
    output: ${result[*].image}
```

`object-tracking`은 물리화된 리스트와 async iterator 모두를 투명하게 처리합니다.

## 문제 해결

### 자주 발생하는 문제

1. **`frame_rate` 불일치**: 타임코드가 어긋나 보이면 `sampled_frame_rate`가 `source_fps / frame_interval`과 일치하는지 확인하세요. 값이 잘못되어도 추적이 깨지지는 않지만 보고되는 모든 타임스탬프가 비례해서 어긋납니다.
2. **트랙이 반환되지 않음**: 샘플링 속도를 높이거나(`frame_interval` 낮춤) `min_frame_count`를 낮추세요. 객체가 두어 프레임에만 등장했을 수 있습니다.
3. **같은 객체가 여러 트랙으로 분리됨**: 짧은 가림 때문이라면 `merge_gap`을 높이거나, 외관 기반 재식별을 사용하는 `tracker: botsort`를 시도해 보세요.
4. **다른 객체들이 하나의 트랙으로 병합됨**: `merge_gap`을 낮추거나 `min_confidence`를 높이거나 `labels`를 좁히세요. 같은 클래스의 매우 가까운 bounding box가 ID 할당을 혼란시킬 수 있습니다.
5. **모델 파일을 찾을 수 없음**: `./models/yolov8n.pt`가 존재하는지(또는 `model.path`가 첫 실행 다운로드로 해결 가능한 유효한 Ultralytics 프리셋 이름을 가리키는지) 확인하세요.

### 성능 최적화

- **GPU**: 큰 속도 향상을 위해 CUDA 지원 PyTorch 설치. Apple Silicon은 MPS가 자동으로 사용됩니다
- **샘플 레이트**: 가장 큰 지렛대 — 샘플 fps를 절반으로 줄이면 실행 시간이 대략 절반이 됩니다
- **레이블 필터**: `labels`를 전달하면 관심 밖 클래스가 추적 이전에 제거되어 associator가 관리해야 하는 트랙 수가 줄어듭니다
- **모델 크기**: `yolov8n.pt`가 가장 빠릅니다. 재현율이 더 필요하면 `yolov8s/m/l/x`로 올리되 처리량은 감소합니다

## 관련 예제

- `object-detection`: 같은 YOLO family로 단일 이미지에서 객체 검출 (추적 없음)
- `pose-tracking`: 사람의 포즈(키포인트)를 비디오에서 추적. 동일한 스트리밍/세그먼트 형태
- `face-tracking`: InsightFace로 비디오에서 얼굴을 추적. 임베딩 기반 아이덴티티 클러스터링
