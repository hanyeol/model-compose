# 포즈 스켈레톤 오버레이 예제

비디오 안의 모든 사람을 YOLOv8-pose로 검출·추적하고, 매 프레임의 각 포즈 위에 스켈레톤을 그린 뒤, 오버레이된 프레임들을 원본 오디오 트랙과 함께 mp4로 다시 조립하는 워크플로우 예제입니다. 전체 파이프라인은 엔드투엔드 스트리밍으로 실행되므로 클립 길이와 무관하게 메모리가 경계 내에서 유지됩니다.

> **라이선스 주의**: 이 예제는 Ultralytics의 YOLOv8-pose 가중치를 자동 다운로드하며, 이 가중치는 **AGPL-3.0**으로 배포됩니다. 개인 사용, 연구, 오픈소스 데모는 문제없습니다. 상업 사용의 경우에는 AGPL-3.0을 준수(전체 시스템 소스 공개)하거나 Ultralytics Enterprise License를 취득해야 합니다 — [ultralytics.com/license](https://www.ultralytics.com/license) 참고.

## 개요

입력 비디오를 주면, 워크플로우는 매 프레임의 검출된 각 사람의 포즈 위에 컬러 스켈레톤이 그려진 동일 비디오의 새 버전을 반환합니다.

전략:

1. **업로드 스트림을 `fan-out` 작업으로 두 갈래로 분기** — 오디오 추출기용과 프레임 추출기용, 두 개의 독립 브랜치로 나눠서, 단일 사용 업로드 스트림을 디스크에 떨어뜨리지 않고 병렬로 소진할 수 있게 합니다.
2. **오디오 트랙 분리** — `audio-extractor`로 비디오에서 오디오를 분리(변경 없이 보존).
3. **프레임 스트리밍** — `video-frame-extractor`로 모든 프레임을 스트리밍(`streaming: true` — 전체 비디오 버퍼링 없음).
4. **프레임 스트림에 포즈 추적 실행** — `streaming: true`로 설정, 소스 이미지와 검출된 포즈별 풀 프레임 스켈레톤 PNG를 담은 프레임별 청크 스트림을 방출하도록 구성. 트랙 세그먼트, 트랙 메타데이터 집계, 최종 메타데이터 청크는 모두 억제 — 오버레이 단계는 프레임만 필요로 함.
5. **각 프레임별 청크에 대해** `merge`가 소스 프레임과 각 포즈의 스켈레톤 이미지를 한 번에 합성. `for-each` 작업의 출력도 스트림이므로 오버레이된 프레임이 인코더로 지연 흐름.
6. **오버레이된 프레임 스트림을 mp4로 인코딩** — `video-encoder`가 추출한 오디오를 함께 먹싱. ffmpeg가 준비되는 대로 상류 스트림에서 프레임을 당겨오므로 이 단계에서도 전체 비디오 버퍼링이 발생하지 않음.

### 왜 스트리밍이 중요한가

순진한 설계는 모든 프레임을 메모리에 실체화하고, 전체 리스트에 대해 검출을 돌린 뒤, 오버레이된 리스트를 인코더에 넘깁니다. 짧은 클립에서는 동작하지만 긴 비디오에서는 메모리가 폭발합니다 (1080p 30 fps 10분 클립 = 18,000 프레임 × 디코딩된 ~6 MB = PIL 이미지 ~110 GB).

엔드투엔드 스트리밍이면 오버레이 단계에 인플라이트인 프레임은 한 번에 최대 `batch_size`장이고, 인코더는 오버레이된 프레임이 도착하는 즉시 소비합니다. 클립 길이와 무관하게 메모리가 경계 내에서 유지됩니다.

### 왜 포즈 추적인가 (단순 검출이 아니라)

여기서 포즈 추적은 순전히 프레임별 검출기 겸 렌더러로 사용됩니다 — 오버레이에 트랙 아이덴티티가 필요하지 않고, 해당 청크 타입들은 모두 비활성화되어 있습니다. 그럼에도 추적기를 쓰는 이유는, 프레임별 청크가 이미 소스 이미지(`return_frame_image: true`)와 검출된 포즈별 풀 프레임 스켈레톤 PNG(`return_skeleton_image: true`)를 함께 패키징해 주기 때문입니다. 각 스켈레톤 PNG는 소스 프레임의 원래 해상도로 투명 배경에 렌더링되므로, 병합 단계는 그냥 전체 스택을 알파 합성만 하면 됩니다 — 포즈별 x/y 계산이 필요 없습니다. 단순 검출기라면 키포인트만 방출해서, 워크플로우가 직접 스켈레톤을 그려야 합니다.

## 준비

### 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- FFmpeg가 설치되어 PATH에서 사용 가능
- YOLO 포즈 검출용 Python 의존성:
  ```bash
  pip install ultralytics lap
  ```
- YOLOv8n-pose 가중치는 첫 실행 시 model-compose의 모델 캐시로 자동 다운로드됩니다.

### 설정

1. 예제 디렉터리로 이동:
   ```bash
   cd examples/media-processing/pose-skeleton-overlay
   ```

2. 오버레이할 비디오 파일을 준비합니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 비디오 업로드, 필요 시 `frame_rate` / `min_confidence` / `skeleton_format` 오버라이드
   - "Run Workflow" 클릭

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"frame_rate": 30, "min_confidence": 0.4, "skeleton_format": "natural"};type=application/json' \
     -F 'video=@./video.mp4'
   ```

   **CLI 사용:**
   ```bash
   model-compose run --input '{
     "video": "./video.mp4",
     "frame_rate": 30,
     "min_confidence": 0.4,
     "skeleton_format": "natural"
   }'
   ```

## 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | video (file) | 예 | - | 오버레이할 입력 비디오 |
| `min_confidence` | number | 아니오 | `0.4` | 포즈 검출 최소 신뢰도 (0.0 – 1.0). 특정 사람이 계속 누락되면 낮춰봅니다 (예: `0.25`) |
| `skeleton_format` | string | 아니오 | `natural` | 스켈레톤 레이아웃: `natural` (COCO-17 키포인트, YOLO 네이티브 출력에 대응) 또는 `openpose` (BODY_18) |
| `frame_rate` | number | 아니오 | `30` | 출력 프레임 레이트. 오디오 드리프트를 피하려면 소스의 실제 fps로 설정 |

## 컴포넌트 상세

### 오디오 추출기 (`audio-extractor`)
- **타입**: `audio-extractor`
- **드라이버**: `ffmpeg`
- **기능**: 비디오 스트림을 읽어 오디오 트랙을 mp3로 분리. 상류 `fan-out` 작업의 한 브랜치로부터 공급받아 프레임 추출기와 병렬로 업로드 스트림을 소비. 나중에 인코더가 오디오를 오버레이된 비디오에 다시 먹싱할 때 사용.

### 프레임 추출기 (`frame-extractor`)
- **타입**: `video-frame-extractor`
- **드라이버**: `ffmpeg`
- **기능**: ffmpeg가 디코딩하는 대로 모든 프레임(`frame_interval: 1`)을 스트리밍. `streaming: true`이므로 추출기는 전체 비디오를 절대 버퍼링하지 않음 — 각 프레임이 아래 추적기로 곧바로 흐름.

### 포즈 추적기 (`pose-tracker`)
- **타입**: `model` — `pose-tracking` 태스크
- **드라이버**: `custom` (YOLO 패밀리, `yolov8n-pose.pt` 가중치)
- **기능**: 프레임 스트림을 소비하고 `{type: "detection", number, timestamp, poses: [{track_id, bounding_box, skeleton_image}], image}` 형태의 프레임별 검출 청크 스트림을 방출. `return_frame_image: true`는 소스 이미지를 매 검출 청크에 함께 담고, `return_skeleton_image: true`는 검출된 포즈별로 소스 해상도의 투명 배경 스켈레톤 PNG를 하나씩 렌더링. 추적기의 나머지 청크 타입은 억제: `return_tracks: false`는 세그먼트별·트랙별 청크를 드롭하고, `return_metadata: false`는 최종 `metadata` 청크를 드롭.

### 스켈레톤 병합기 (`skeleton-merger`)
- **타입**: `image-processor` (`merge` 메서드)
- **드라이버**: `native`
- **기능**: 입력 리스트의 모든 이미지를 가장 큰 입력에 맞춘 공유 캔버스에 알파 합성. 스켈레톤 렌더가 소스 프레임과 동일 해상도이므로 모든 것이 1:1로 정렬 — 소스 프레임이 베이스 레이어로 먼저 가고, 각 포즈의 스켈레톤 PNG가 한 번에 위로 쌓임.

### 인코더 (`encoder`)
- **타입**: `video-encoder`
- **드라이버**: `ffmpeg`
- **기능**: 오버레이된 프레임 스트림을 mp4로 인코딩(`libx264 @ 8M`)하고 추출된 오디오를 먹싱(`aac @ 192k`). 스트림 입력을 받으므로 ffmpeg가 준비되는 대로 프레임을 당겨옴.

## 노트와 튜닝

- **비용**: 포즈 검출은 매 프레임 실행되고, 검출된 포즈마다 프레임당 스켈레톤 PNG 하나가 렌더링됩니다. 10초 30 fps 클립 = 300회의 검출기 호출. 벽시계 시간은 프레임 수에 선형 비례. YOLOv8n-pose는 가장 작고 빠른 가중치 — 지연 시간보다 정밀도가 더 중요하다면 `yolov8s/m/l/x-pose.pt`(더 크고 더 정확)로 교체.
- **동시성**: `for-each` 작업의 `batch_size: 8`은 최대 8개의 병합 파이프라인을 동시에 실행. 메모리를 처리량과 맞바꾸려면 올리고, 병합 컴포넌트가 경합 하에 병목이 되면 낮추세요.
- **프레임 레이트**: 소스와 출력의 프레임 레이트가 다르면 오디오와 비디오가 드리프트합니다. 소스의 실제 fps를 `frame_rate`로 전달하세요.
- **누락된 포즈**: 특정 사람이 계속 누락되면 `min_confidence`를 낮춰봅니다 (예: `0.25`). 아주 작거나 멀리 있는 사람은 여전히 하부 검출기에서 드롭될 수 있음 — 리콜을 높이려면 더 큰 YOLO 가중치로 교체.
- **스켈레톤 스타일**: `skeleton_format: natural`은 COCO-17 키포인트를 사용(YOLO의 네이티브 출력과 일치); `openpose`는 ControlNet 같은 하류 포즈 편집 도구에서 흔한 BODY_18 레이아웃으로 변환. 출력을 OpenPose 조건부 디퓨전 파이프라인에 넣을 계획이라면 `openpose`를 선택.
- **보간된 프레임**: 검출기가 특정 프레임에서 포즈를 놓쳤다가 근처 프레임(`merge_gap` 이내)에서 다시 잡으면, 추적기가 그 갭을 보간된 바운딩 박스와 스켈레톤으로 채워서 오버레이가 짧은 검출 드롭 구간에서도 시각적으로 매끄럽게 유지됩니다. 보간된 포즈는 청크에 `interpolated: true`로 태그되지만, 오버레이 파이프라인은 나머지와 동일하게 처리합니다.
