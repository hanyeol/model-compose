# 이미지 분할 모델 태스크 예제

이 예제는 model-compose의 내장 image-segmentation 태스크를 사용하여 Meta의 Segment Anything Model (SAM)로 이미지에서 분할 마스크를 생성하는 방법을 보여줍니다.

## 개요

이 워크플로우는 로컬에서 프롬프트 기반 분할을 제공합니다:

1. **로컬 SAM 모델**: 외부 API 없이 Meta의 Segment Anything Model을 로컬에서 실행
2. **자동 모드**: 프롬프트 없이 이미지의 모든 개별 영역에 대한 마스크 생성
3. **박스 프롬프트 모드**: 사용자가 제공한 바운딩 박스(예: 객체 검출 컴포넌트 결과) 주변으로 마스크를 정교화
4. **SAM 1 및 SAM 2 지원**: 모든 Ultralytics SAM 체크포인트 사용 가능 (`sam_b.pt`, `sam2_b.pt`, `sam2.1_l.pt`, `mobile_sam.pt` 등)
5. **자동 모델 관리**: 최초 사용 시 기본 모델을 다운로드하고 캐시

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- SAM 실행을 위한 충분한 시스템 리소스 (권장: 8GB+ RAM; 자동 모드에서는 GPU 강력 권장)
- `ultralytics`가 포함된 Python 환경 (최초 실행 시 자동 설치)

### 로컬 분할을 사용하는 이유

클라우드 기반 비전 API와 달리 SAM을 로컬에서 실행하면 다음과 같은 장점이 있습니다:

**로컬 처리의 이점:**
- **개인정보 보호**: 모든 이미지가 로컬에서 처리되며 외부 서비스로 전송되지 않음
- **비용**: 이미지당 요금이나 API 사용료 없음
- **오프라인**: 최초 모델 다운로드 이후 인터넷 연결 없이 작동
- **지연 시간**: 추론 시마다 네트워크 왕복이 없음
- **사용자 정의 모델**: 모든 Ultralytics SAM 체크포인트를 연결 가능

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용 — 자동 모드:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image"}'
   ```

   **API 사용 — 박스 프롬프트 모드:**
   ```bash
   # 단일 박스
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image", "box_prompt": [100, 100, 300, 400]}'

   # 여러 박스
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/image.jpg" \
     -F 'input={"image": "@image", "box_prompt": [[100, 100, 300, 400], [500, 200, 250, 250]]}'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 이미지 파일 업로드
   - 선택적으로 `box_prompt`, `min_confidence`, `min_area`, `max_segment_count`, `return_mask` 제공
   - "Run Workflow" 버튼 클릭

## 결과 형식

**자동 모드:**
```json
{
  "segments": [
    {
      "score": 0.92,
      "bounding_box": [x, y, width, height],
      "area": 12345,
      "mask": "<PNG>"
    }
  ],
  "width": 1920,
  "height": 1080
}
```

**박스 프롬프트 모드**는 세그먼트마다 `prompt_index` 필드를 추가합니다:
```json
{
  "segments": [
    {
      "score": 0.87,
      "bounding_box": [x, y, width, height],
      "area": 12345,
      "mask": "<PNG>",
      "prompt_index": 0
    }
  ],
  "width": 1920,
  "height": 1080
}
```

- `score` — 세그먼트 신뢰도 (SAM의 안정성 추정값).
- `bounding_box` — 마스크에서 파생된 `[x, y, width, height]`, 좌상단 원점.
- `area` — 픽셀 단위 마스크 면적.
- `mask` — PNG 형식의 이진 마스크 (`return_mask: false`일 때는 생략).
- `prompt_index` — 이 세그먼트가 대응하는 입력 `box_prompt`의 인덱스 (박스 프롬프트 모드에서만).

세그먼트는 `score` 내림차순으로 정렬되며 `max_segment_count`까지 잘립니다.

## 객체 검출과 결합

[object-detection](../object-detection/README.md) 컴포넌트의 출력을 SAM의 박스 프롬프트로 바로 전달할 수 있습니다:

```yaml
jobs:
  - id: detect
    component: yolo-detector
    action:
      image: ${input.image as image}
  - id: segment
    component: sam-segmenter
    action:
      image: ${input.image as image}
      box_prompt: ${detect.output.objects[*].bounding_box}
```

## 사용자 정의 모델 사용

`model-compose.yml`의 `model` 블록을 원하는 Ultralytics SAM 체크포인트로 교체하세요. 예:

```yaml
model:
  provider: local
  path: /path/to/your/mobile_sam.pt
```

사용 가능한 Ultralytics SAM 체크포인트: `sam_b.pt`, `sam_l.pt`, `sam2_t.pt`, `sam2_b.pt`, `sam2_l.pt`, `sam2.1_t.pt`, `sam2.1_b.pt`, `sam2.1_l.pt`, `mobile_sam.pt`.

## 액션 매개변수

| 매개변수 | 유형 | 기본값 | 설명 |
|---|---|---|---|
| `image` | image | (필수) | 입력 이미지 |
| `box_prompt` | `[x, y, w, h]` 또는 `[[x, y, w, h], ...]` | `null` | 박스 프롬프트. 생략하면 자동 모드로 실행 |
| `max_segment_count` | int | `100` | 이미지당 최대 세그먼트 수 |
| `return_mask` | bool | `true` | 세그먼트별 이진 마스크를 PNG로 반환 |
| `params.min_confidence` | float | `0.5` | 세그먼트 최소 신뢰도 |
| `params.min_area` | int | `null` | 픽셀 단위 최소 마스크 면적 (노이즈 필터) |
