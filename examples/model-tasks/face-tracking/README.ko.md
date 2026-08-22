# Face Tracking Model Task 예제

이 예제는 model-compose의 내장 `face-tracking` 작업과 InsightFace를 사용하여 비디오 프레임 전반에서 얼굴을 추적하는 방법을 보여줍니다. 업로드한 비디오에서 일정한 간격으로 프레임을 샘플링하고, 검출과 임베딩을 거친 뒤 코사인 유사도로 클러스터링하여 동일 인물이 프레임 사이에서 하나의 트랙으로 묶이도록 합니다. 결과는 인물별 세그먼트이 타임코드로 정리된 리포트입니다.

## 개요

이 워크플로우는 다음과 같은 로컬 얼굴 추적을 제공합니다:

1. **로컬 얼굴 추적 모델**: 외부 API 없이 InsightFace의 `antelopev2` 모델 팩을 로컬에서 실행
2. **프레임 샘플링**: ffmpeg으로 사용자가 지정한 간격으로 입력 비디오에서 프레임 추출
3. **아이덴티티 클러스터링**: 프레임별 얼굴 임베딩을 코사인 유사도로 클러스터링하여 각 고유 얼굴을 하나의 트랙으로 묶음
4. **세그먼트 집계**: 프레임별 타임스탬프를 인물별 `start_time / end_time / duration` 구간으로 병합
5. **자동 모델 관리**: 첫 실행 시 InsightFace GitHub 릴리스에서 `antelopev2` 팩을 다운로드하여 `./.models/antelopev2`에 압축 해제, 이후 재사용

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- ffmpeg가 설치되어 PATH에서 사용 가능 (프레임 추출용)
- onnxruntime 실행을 위한 충분한 시스템 리소스 (권장: 4GB+ RAM)
- `insightface`, `opencv-python`, `onnxruntime`이 있는 Python 환경 (첫 실행 시 자동 설치)
- 인터넷 연결 (첫 실행 시 antelopev2 팩 다운로드에 필요)

### antelopev2 모델 팩

수동 준비가 필요 없습니다. 첫 실행 시 [model-compose.yml](model-compose.yml)의 `url` + `bundled: true` 설정에 따라 아카이브가 자동으로 다운로드되어 `./.models/antelopev2`에 압축 해제됩니다. 이후 실행은 이 경로를 재사용합니다.

추출되는 구조:

```
.models/
└── antelopev2/
    ├── 1k3d68.onnx
    ├── 2d106det.onnx
    ├── genderage.onnx
    ├── glintr100.onnx
    └── scrfd_10g_bnkps.onnx
```

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/face-tracking
   ```

2. 별도의 환경 설정은 필요하지 않습니다. 첫 실행이 모델 팩을 자동으로 준비합니다.

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
     -F 'input={"video": "@clip", "frame_interval": 15, "sampled_frame_rate": 2.0}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `video` 파일 업로드
   - 필요 시 `frame_interval` / `sampled_frame_rate` / `similarity_threshold` 조정
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 15, "sampled_frame_rate": 2.0}'
   ```

## 컴포넌트 상세

### Frame Extractor 컴포넌트
- **Type**: `video-frame-extractor`
- **Driver**: `ffmpeg`
- **목적**: 입력 비디오에서 일정한 간격으로 프레임을 샘플링하여 tracker에 이미지 스트림으로 흘려보냄
- **핵심 노브**: `frame_interval` (1 = 모든 프레임, 15 = 15프레임마다 하나 등)
- **스트리밍**: 활성화. extractor의 원본 청크 형태는 `{image, timestamp, number, ...}`이며, `output: ${result[].image}`가 각 청크를 `image`로 투영하여 다운스트림 소비자가 단순 이미지 스트림을 받게 합니다. ffmpeg가 프레임을 생산하는 대로 face-tracking으로 흘러가므로 긴 영상도 전체를 버퍼링하지 않습니다.

### Face Tracking Model 컴포넌트
- **Type**: `face-tracking` 작업의 Model 컴포넌트
- **Family**: `insightface`
- **Model**: 로컬 `./.models/antelopev2` 팩
- **기능**:
  - 프레임별로 얼굴을 검출하고 512차원 아이덴티티 임베딩을 추출
  - 임베딩을 코사인 유사도로 온라인 클러스터링하여 각 아이덴티티가 하나의 트랙으로 묶임
  - 트랙별 세그먼트(start/end/duration)을 H:MM:SS.mmm 타임코드 형태로 생성
  - GPU 메모리를 제한하기 위한 직렬 실행 (`max_concurrent_count: 1`)

### 모델 정보: antelopev2 (InsightFace)
- **제공자**: InsightFace
- **백본**: ResNet-100 (`glintr100.onnx`)
- **임베딩 차원**: 512
- **검출기**: SCRFD-10G (`scrfd_10g_bnkps.onnx`)
- **정규화**: L2 정규화된 임베딩 — 코사인 유사도가 내적과 동일
- **라이선스**: 비상업적 연구 용도

## 워크플로우 상세

### 기본 워크플로우

**설명**: 업로드한 비디오에서 프레임을 샘플링하고, 얼굴 추적을 실행하며, 인물별 세그먼트을 반환합니다.

#### Job 흐름

```mermaid
graph TD
    Input((Input<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>job)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[{image, timestamp, ...}]| J1

    J1 --> J2((track<br/>job))
    J2 -.-> C2[Face Tracker<br/>insightface]
    C2 -.-> |{tracks, frame_count}| J2

    J2 --> Output((Output<br/>report))
```

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | video (file) | Yes | - | 입력 비디오 파일 |
| `frame_interval` | number | No | 15 | 추출 시 N번째 프레임마다 하나씩 샘플링 |
| `sampled_frame_rate` | number | No | 2.0 | *샘플링된* 시퀀스의 초당 프레임 수. 프레임별 타임스탬프 산출에 사용되며 `source_fps / frame_interval` 값으로 설정 |
| `similarity_threshold` | number | No | 0.4 | 두 얼굴을 같은 트랙으로 묶기 위한 코사인 유사도 임계값 |
| `min_frame_count` | number | No | 2 | 이 값보다 적은 프레임에만 등장하는 트랙은 폐기 |
| `merge_gap` | number | No | 1.0 | 이 값(초)보다 짧은 간격의 인접 세그먼트는 병합 |
| `return_track_image` | boolean | No | true | 세그먼트마다 얼굴 크롭을 하나씩 첨부. 원본 프레임의 해상도에서 검출된 bounding box 그대로 잘라내며, UI 표시·리사이즈·다른 임베딩 백본으로의 재임베딩에 적합 (아래 [다른 모델로 재임베딩](#다른-모델로-재임베딩) 참조). 타임코드만 필요하면 `false`로 두어 페이로드를 줄일 수 있음 |
| `return_gender_age` | boolean | No | false | 트랙마다 `gender` (`"male"` / `"female"`)와 `age`(정수)를 첨부. 트랙의 최고 스코어 프레임 기준값. 모델 팩이 gender/age 서브모델을 포함해야 함 (`antelopev2`, `buffalo_l`) |
| `bounding_box_padding` | number | No | 0.2 | 얼굴 크롭의 bounding box를 각 변에서 이 비율만큼 확장 (예: `0.2` = 상하좌우 +20%). 반환되는 크롭 이미지에만 적용되며, 임베딩과 클러스터링은 원본 박스를 그대로 사용. 검출 박스가 너무 타이트해서 머리·턱·귀가 잘리는 경우, 또는 얼굴이 프레임에서 작아 크롭이 흐리게 보이는 경우에 유용 |

#### 출력 형식

`report`는 다음 필드를 갖는 JSON 객체입니다:

| 필드 | 타입 | 설명 |
|------|------|------|
| `tracks` | array | 검출된 아이덴티티당 하나의 항목. 아래 참조. |
| `frame_count` | integer | 분석된 샘플 프레임의 총 개수 |

각 `tracks[i]` 항목:

| 필드 | 타입 | 설명 |
|------|------|------|
| `embedding` | number[] | L2 정규화된 아이덴티티 centroid (antelopev2는 512차원). 아이덴티티 DB와 코사인 매칭하거나 같은 인물로 판명된 트랙을 병합하는 데 사용 가능. `return_embedding`이 활성화된 경우에만 존재 |
| `segments` | array | `{start_time, end_time, duration, score}` 리스트 (`return_track_image` 활성화 시 `image` 포함). 아래 참조 |
| `frame_count` | integer | 이 트랙이 등장한 샘플 프레임 수 |
| `score` | number | 이 트랙에 속한 모든 프레임 중 최고 검출 신뢰도. 트랙 정렬/필터링에 유용 |
| `gender` | string | `"male"` 또는 `"female"`. 트랙의 최고 스코어 프레임 기준. `return_gender_age`가 활성화되고 모델 팩이 gender 서브모델을 포함할 때만 존재 |
| `age` | integer | 나이 추정값. 트랙의 최고 스코어 프레임 기준. `return_gender_age`가 활성화되고 모델 팩이 age 서브모델을 포함할 때만 존재 |

각 `segments[j]` 항목:

| 필드 | 타입 | 설명 |
|------|------|------|
| `start_time` | string | 세그먼트 시작 (`H:MM:SS.mmm` 타임코드) |
| `end_time` | string | 세그먼트 종료 (`H:MM:SS.mmm` 타임코드) |
| `duration` | string | `end_time - start_time` (`H:MM:SS.mmm` 타임코드) |
| `score` | number | 이 세그먼트의 대표 프레임(세그먼트 내 최고 스코어 프레임, `image`가 잘려 나오는 그 프레임)의 검출 신뢰도 |
| `image` | image | 이 세그먼트에서 최고 스코어를 얻은 프레임의 얼굴 크롭. 원본 프레임의 해상도에서 검출된 bounding box 크기 그대로 잘라내므로 얼굴마다 크기가 다름. `return_track_image`가 활성화된 경우에만 존재 |

예시 (`return_track_image: false`, `return_embedding: false`):

```json
{
  "report": {
    "tracks": [
      {
        "segments": [
          { "start_time": "0:00:02.000", "end_time": "0:00:08.500", "duration": "0:00:06.500", "score": 0.94 },
          { "start_time": "0:00:14.000", "end_time": "0:00:17.000", "duration": "0:00:03.000", "score": 0.88 }
        ],
        "frame_count": 21,
        "score": 0.94
      }
    ],
    "frame_count": 40
  }
}
```

### 다른 모델로 재임베딩

`return_track_image`를 켜면 세그먼트마다 얼굴 크롭이 하나씩 붙어 나옵니다. 해당 세그먼트에서 가장 스코어가 높은 프레임을, 원본 해상도에서 검출된 bounding box 그대로 잘라낸 이미지입니다. 이 크롭을 별도의 `face-embedding` 컴포넌트(또는 자체 비전 모델)로 흘려 넣으면, 이 태스크의 검출과 클러스터링 결과는 재사용하면서 다른 백본으로 임베딩을 뽑을 수 있습니다. 다운스트림 컴포넌트가 크롭 위에서 검출/정렬을 다시 수행하므로 두 임베딩 모델의 결합이 느슨하게 유지됩니다:

```yaml
- id: track
  component: face-tracker
  input:
    frames: ${jobs.frames.output}
    frame_rate: ${input.sampled_frame_rate}
    return_track_image: true

- id: reembed
  component: alt-face-embedder
  # 각 트랙의 각 세그먼트 대표 크롭을 재임베딩합니다.
  input:
    face_image: ${jobs.track.output.tracks[*].segments[*].image}
```

각 트랙의 `embedding` 필드는 insightface 자체 임베딩들의 running centroid이며 항상 포함되어 있으므로, 다운스트림 코드가 트랙을 직접 비교(예: 조명이 달라 두 트랙으로 갈라진 같은 인물을 병합)하는 데에도 사용할 수 있습니다.

## 시스템 요구사항

### 최소 요구사항
- **RAM**: 4GB (권장 8GB+)
- **디스크 공간**: `antelopev2` 팩용 ~1GB
- **CPU**: 현대적인 x86_64 또는 ARM64 프로세서
- **인터넷**: 1회성 모델 팩 다운로드에 필요

### 성능 참고
- 검출 비용은 샘플 프레임 수에 비례합니다. 잡고자 하는 최소 세그먼트을 커버할 수 있도록 `frame_interval`을 정하세요 (예: 1초 이상 등장을 잡으려면 2 fps로 샘플링)
- onnxruntime 기반의 GPU(CUDA / CoreML / DirectML)를 사용하면 처리량이 크게 향상됩니다
- 첫 실행은 onnxruntime과 검출기 초기화 때문에 느립니다. 이후 실행은 빠릅니다

## 사용자 정의

### 더 조밀하게 샘플링

`frame_interval`을 낮추고 그에 맞춰 `sampled_frame_rate`를 올리세요. 30 fps 소스에서 5프레임마다 샘플링하면 6 fps가 됩니다:

```bash
model-compose run --input '{"video": "clip.mp4", "frame_interval": 5, "sampled_frame_rate": 6.0}'
```

### 아이덴티티 그룹핑 강화

`similarity_threshold`를 높이면 클러스터러가 더 보수적으로 동작합니다(병합이 줄고 트랙이 더 세분화됨). 일반적인 범위:

- `0.30 – 0.40`: 공격적 그룹핑. 비슷하게 생긴 인물이 병합될 수 있음
- `0.40 – 0.55`: 균형
- `> 0.55`: 엄격. 조명/각도 변화가 큰 같은 인물이 분리될 수 있음

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

`face-tracking`은 물리화된 리스트와 async iterator 모두를 투명하게 처리합니다.

## 문제 해결

### 자주 발생하는 문제

1. **`frame_rate` 불일치**: 타임코드가 어긋나 보이면 `sampled_frame_rate`가 `source_fps / frame_interval`과 일치하는지 확인하세요. 값이 잘못되어도 클러스터링이 깨지지는 않지만 보고되는 모든 타임스탬프가 비례해서 어긋납니다.
2. **트랙이 반환되지 않음**: 샘플링 속도를 높이거나(`frame_interval` 낮춤) `min_frame_count`를 낮추세요. 인물이 한 프레임에만 등장했을 수 있습니다.
3. **같은 인물이 여러 트랙으로 분리됨**: `similarity_threshold`를 낮추거나(예: 0.35), 분리가 단순히 인접 갭 때문이라면 `merge_gap`을 높이세요.
4. **다른 인물들이 하나의 트랙으로 병합됨**: `similarity_threshold`를 높이세요(예: 0.5). 기본값은 정밀도보다 재현율에 맞춰져 있습니다.
5. **모델 파일을 찾을 수 없음**: `./.models/antelopev2` 디렉토리에 위에 나열된 `.onnx` 파일들이 모두 있는지 확인하세요.

### 성능 최적화

- **GPU**: 더 빠른 추론을 위해 `onnxruntime-gpu`(CUDA) 또는 `onnxruntime-silicon`(Apple) 설치
- **검출 크기**: 검출 입력이 클수록 작은 얼굴의 재현율이 좋아지지만 추론이 느려집니다. InsightFace family 설정의 `detection_size` 참조
- **샘플 레이트**: 가장 큰 지렛대 — 샘플 fps를 절반으로 줄이면 실행 시간이 대략 절반이 됩니다

## 관련 예제

- `face-embedding`: 정지 이미지에서 단일 아이덴티티 임베딩 추출
- `face-swap`: 소스 이미지의 얼굴 아이덴티티를 타깃 이미지로 전이
- `find-person-scenes` (showcase): 대상 얼굴이 주어졌을 때 비디오에서 그 인물이 등장하는 장면을 찾음 — 내장 tracker 대신 `face-embedding` + `vector-processor`를 사용
