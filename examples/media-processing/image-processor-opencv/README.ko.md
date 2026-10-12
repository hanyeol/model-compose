# Image Processor (OpenCV) 예제

이 예제는 model-compose `image-processor` 컴포넌트의 OpenCV driver를 보여줍니다. PIL 바깥에 있는 고전 컴퓨터 비전 알고리즘을 사용하며, ControlNet의 흔한 조건 입력인 Canny edge detection으로 시작합니다.

## 개요

`opencv` driver는 기본 `native` (PIL) driver를 OpenCV 전용 알고리즘으로 보완합니다:

1. **Canny edge detection**: 입력 이미지로부터 단일 채널 edge map 생성
2. **Headless**: 순수 알고리즘, 다운로드할 모델 가중치 없음
3. **ControlNet 호환**: grayscale 출력을 ControlNet canny에 바로 투입

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- `opencv-python`과 `numpy`가 포함된 Python 환경 (자동 관리)

### 환경 설정

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/media-processing/image-processor-opencv
   ```

2. 추가 설정 불필요.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/input-image.jpg" \
     -F "low_threshold=100" \
     -F "high_threshold=200"
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 이미지 업로드 후 threshold 조정
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run image-processor-opencv --input '{"image": "/path/to/your/input-image.jpg", "low_threshold": 100, "high_threshold": 200}'
   ```

## 워크플로우 상세

### "Detect Image Edges (Canny)" 워크플로우

**설명**: 입력 이미지로부터 Canny edge map을 생성합니다.

#### 입력 파라미터

| 파라미터          | 타입     | 필수 | 기본값 | 설명                                       |
|-------------------|----------|------|--------|--------------------------------------------|
| `image`           | image    | 예   | -      | 입력 이미지 파일 (JPEG, PNG 등)            |
| `low_threshold`   | integer  | 아니오 | 100   | gradient magnitude의 하위 히스테리시스 임계값 |
| `high_threshold`  | integer  | 아니오 | 200   | gradient magnitude의 상위 히스테리시스 임계값 |

#### 출력 형식

| 필드 | 타입   | 설명                                              |
|------|--------|---------------------------------------------------|
| -    | image  | 단일 채널 grayscale edge map (L 모드), 0 또는 255 |

## 커스터마이징

### Threshold 튜닝

Canny의 두 threshold가 민감도를 제어합니다:

- 둘 다 낮추면 더 많은 edge (노이즈가 많지만 약한 gradient도 포착)
- 둘 다 높이면 더 적고 깨끗한 edge
- ControlNet 관례는 2:1 비율 (예: 100/200, 50/100)

### ControlNet 워크플로우에 연결

이 컴포넌트를 ControlNet 기반 이미지 또는 비디오 생성기 앞에 체인하여 출력을 ControlNet의 조건 입력으로 전달하세요:

```yaml
workflow:
  jobs:
    - id: edges
      component: image-processor
      action: canny
      input:
        image: ${input.image}
    - id: generate
      component: controlnet-generator
      input:
        prompt: ${input.prompt}
        control_image: ${edges.output}
```

### 배치 및 스트리밍

이미지 리스트 또는 상위 프레임 추출 스트림을 전달하여 비디오 파이프라인용 프레임별 edge map을 생성하세요:

```yaml
component:
  type: image-processor
  driver: opencv
  action:
    method: canny
    image: ${input.frames}
    batch_size: 8
```

## 설계 원칙: 모델 없음

OpenCV driver는 학습된 가중치가 필요 없는 알고리즘만 담습니다. 모델 기반 edge/line 전처리기(HED, PiDiNet, lineart)는 대신 model 컴포넌트 패밀리에 속합니다.
