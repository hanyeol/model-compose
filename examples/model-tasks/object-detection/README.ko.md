# 객체 감지 모델 태스크 예제

이 예제는 model-compose의 내장 object-detection 태스크를 사용하여 Ultralytics YOLO로 이미지에서 객체를 감지하는 방법을 보여주며, 오프라인 감지 기능을 제공합니다.

## 개요

이 워크플로우는 다음과 같은 로컬 객체 감지를 제공합니다:

1. **로컬 YOLO 모델**: 외부 API 없이 Ultralytics YOLO 감지 모델을 로컬에서 실행
2. **경계 상자**: 클래스 레이블과 신뢰도 점수를 포함한 축 정렬 경계 상자를 객체별로 반환
3. **사용자 정의 가중치**: 모든 Ultralytics YOLO 감지 또는 세그멘테이션 체크포인트(`.pt`) 지원
4. **레이블 필터**: `labels` 액션 매개변수를 통해 감지를 특정 클래스 레이블로 선택적 제한
5. **자동 모델 관리**: 첫 사용 시 기본 모델을 자동으로 다운로드 및 캐시

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- YOLO 실행에 충분한 시스템 리소스 (권장: 4GB+ RAM)
- `ultralytics`가 포함된 Python 환경 (첫 실행 시 자동 설치)

### 로컬 객체 감지의 장점

클라우드 기반 비전 API와 달리, 로컬에서 YOLO를 실행하면 다음과 같은 이점이 있습니다:

**로컬 처리의 이점:**
- **개인정보 보호**: 모든 이미지가 로컬에서 처리되며, 외부 서비스로 데이터 전송 없음
- **비용**: 이미지 단위나 API 사용 요금 없음
- **오프라인**: 초기 모델 다운로드 후 인터넷 연결 없이 작동
- **지연 시간**: 추론 시마다 네트워크 왕복 시간 없음
- **사용자 정의 모델**: 도메인 특화 모델을 포함한 모든 Ultralytics YOLO 체크포인트(`.pt`) 플러그인 가능

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 모든 객체 감지 (기본 yolo11n.pt로 COCO 80 클래스)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image"}'

   # 특정 레이블만 감지
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image", "labels": ["person", "dog"], "min_confidence": 0.5}'
   ```

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 이미지 파일 업로드
   - `labels`, `min_confidence`, `max_object_count`, `iou_threshold`, `agnostic_nms`, `bounding_box_padding` 선택적 조정
   - "Run Workflow" 버튼 클릭

## 결과 형식

```json
{
  "objects": [
    {
      "label": "person",
      "label_id": 0,
      "score": 0.87,
      "bounding_box": { "x": 320, "y": 180, "width": 220, "height": 460 }
    }
  ],
  "width": 1920,
  "height": 1080
}
```

- `label` — `model.names`의 사람이 읽을 수 있는 클래스 이름.
- `label_id` — 모델이 보고하는 정수 클래스 인덱스.
- `score` — `[0, 1]` 범위의 감지 신뢰도.
- `bounding_box` — 좌측 상단 원점 기준의 픽셀 단위 `{x, y, width, height}`.

## 사용자 정의 모델 사용

`model-compose.yml`의 `model` 블록을 교체하여 모든 Ultralytics YOLO 체크포인트를 가리키도록 합니다. 예를 들어, 자체 데이터셋으로 학습된 사용자 정의 감지기를 사용하려면:

```yaml
component:
  type: model
  task: object-detection
  driver: custom
  family: yolo
  model:
    provider: local
    path: /path/to/your/model.pt
  action:
    image: ${input.image as image}
    labels: [ your_class_a, your_class_b ]
    params:
      min_confidence: 0.3
```

세그멘테이션 체크포인트(`yolo11*-seg.pt` 등)도 지원됩니다 - 경계 상자만 읽고 마스크는 무시됩니다.

## 액션 매개변수

| 매개변수 | 유형 | 기본값 | 설명 |
|---|---|---|---|
| `image` | image | (필수) | 입력 이미지 |
| `labels` | list[str] | `null` | 이 클래스 레이블로 감지 제한. 알 수 없는 레이블은 즉시 실패 |
| `max_object_count` | int | `300` | 이미지당 최대 감지 수 |
| `bounding_box_padding` | float | `0.0` | 각 경계 상자를 모든 방향으로 너비/높이 비율만큼 확장 (예: `0.1` = 10%). 이미지 경계로 제한됨. 상자를 크롭이나 SAM 박스 프롬프트에 전달할 때 유용 |
| `params.min_confidence` | float | `0.25` | 최소 감지 신뢰도 |
| `params.iou_threshold` | float | `0.7` | 비최대 억제를 위한 IoU 임계값 |
| `params.agnostic_nms` | bool | `false` | 모든 레이블에 대해 클래스 불가지론적 NMS 수행 |
