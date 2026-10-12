# Image Edge Detection Model Task 예제

이 예제는 model-compose의 모델 기반 edge detector들을 보여줍니다: HED, PiDiNet, Lineart. 세 모델 모두 이미지 또는 비디오 생성용 ControlNet 조건 입력에 적합한 단일 채널 edge map을 생성합니다.

## 개요

세 개의 모델이 각각 별도 워크플로우로 노출됩니다:

1. **HED** (Holistically-Nested Edge Detection) — 고전적인 soft edge, ControlNet HED/softedge에 널리 사용
2. **PiDiNet** (Pixel Difference Network) — 컴팩트한 soft edge, HED보다 가벼운 가중치
3. **Lineart** — 애니메이션 스타일 line 추출, 두 variant (realistic / coarse)

모든 가중치는 공개된 `lllyasviel/Annotators` HuggingFace repo에 있으며 첫 사용 시 자동 다운로드됩니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- torch, numpy, PIL이 포함된 Python 환경 (자동 관리)
- 첫 실행 시 인터넷 접근 (모델 다운로드)

### 모델 가중치

| Family              | 가중치 파일            | 크기    |
|---------------------|------------------------|---------|
| HED                 | `ControlNetHED.pth`    | ~56 MB  |
| PiDiNet             | `table5_pidinet.pth`   | ~2 MB   |
| Lineart (realistic) | `sk_model.pth`         | ~17 MB  |
| Lineart (coarse)    | `sk_model2.pth`        | ~17 MB  |

모든 체크포인트는 `lllyasviel/Annotators`에서 가져오며 표준 HuggingFace 캐시 디렉토리에 저장됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/hed/runs \
     -F "image=@/path/to/your/input-image.jpg"
   ```

   `hed`를 `pidinet` 또는 `lineart`로 바꿔 다른 전처리기를 호출하세요.

   **Web UI 사용:**
   - http://localhost:8081 열기
   - 워크플로우 선택 후 이미지 업로드
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   model-compose run hed --input '{"image": "/path/to/your/input-image.jpg"}'
   ```

## 컴포넌트 상세

### HED 컴포넌트
- **아키텍처**: VGG16 스타일 5단계 인코더에 side-output score layer (Xie & Tu, 2015), 단일 edge map으로 fusion
- **입력 전처리**: BGR, ImageNet 평균 subtraction, [0, 255]
- **출력**: Grayscale edge map, 밝은 픽셀 = edge

### PiDiNet 컴포넌트
- **아키텍처**: Pixel-difference convolution network (Su et al., ICCV 2021), `lllyasviel/Annotators`가 사용하는 Table 5 variant
- **입력 전처리**: RGB, [0, 1]로 정규화
- **출력**: Grayscale edge map

### Lineart 컴포넌트
- **아키텍처**: ResNet-9 U-Net generator (Anime2Sketch / Mukosame), ControlNet 1.1 lineart에서 사용
- **Variants**:
  - `realistic` — `sk_model.pth`, 상세한 line 추출
  - `coarse` — `sk_model2.pth`, 단순화된 line
- **입력 전처리**: RGB in `[-1, 1]`
- **출력**: Grayscale line map (어두운 배경 위 밝은 edge가 되도록 미리 반전되어 ControlNet 관례와 일치)

## 커스터마이징

### 출력 반전

ControlNet lineart variant은 기본값(어두운 배경 위 밝은 line) 대신 밝은 배경 위 어두운 line을 기대하는 경우가 있습니다. 출력을 뒤집으세요:

```yaml
action:
  image: ${input.image as image}
  invert: true
```

### 입력 해상도 변경

기본 입력 크기는 512 (모델 native)입니다. 더 선명한 디테일을 위해 올리거나 속도를 위해 낮추세요:

```yaml
action:
  image: ${input.image as image}
  params:
    image_size: 768
```

### Safe Mode (HED / PiDiNet)

ControlNet에서 흔히 가짜 배경 텍스처가 되는 약한 edge를 억제합니다:

```yaml
action:
  image: ${input.image as image}
  params:
    use_safe_mode: true
```

### ControlNet 워크플로우에 연결

edge 전처리기를 ControlNet 기반 이미지 또는 비디오 생성기 앞에 체인합니다:

```yaml
workflow:
  jobs:
    - id: edges
      component: hed
      input:
        image: ${input.image}
    - id: generate
      component: controlnet-generator
      input:
        prompt: ${input.prompt}
        control_image: ${edges.output}
```

### 배치 및 스트리밍

비디오 파이프라인용 프레임별 edge map을 생성하기 위해 이미지 리스트 또는 프레임 추출 스트림을 전달하세요:

```yaml
action:
  image: ${input.frames}
  batch_size: 4
```

## 문제 해결

### 자주 발생하는 문제

1. **메모리 부족**: `params.image_size` 또는 `batch_size`를 줄이거나 PiDiNet(가장 가벼움)으로 전환
2. **모델 다운로드 실패**: 인터넷 연결과 HuggingFace 캐시 디렉토리 권한 확인
3. **평평하거나 노이즈 많은 출력**: `use_safe_mode: true` (HED/PiDiNet) 시도 또는 `image_size` 증가
4. **잘못된 관례**: ControlNet이 밝은 배경 위 어두운 edge를 기대하면 `invert: true` 추가

## 모델 기반 vs 알고리즘 Edge Detection

모델 가중치 없이 순수 알고리즘 edge detection을 원한다면 `image-processor` 컴포넌트의 OpenCV driver와 `canny` method를 참고하세요. 두 접근은 상호 보완적입니다:

- **Canny** — 빠르고, 가중치 없음, 결정적. 명확한 경계가 있는 조명이 좋은 피사체에 최적.
- **HED / PiDiNet / Lineart** — 모델 기반, 고전 알고리즘이 놓치는 의미적 edge(머리카락, 부드러운 그라디언트, 옷 주름)에 더 강함. 대부분의 ControlNet 1.1 edge/line 조건에 필수.
