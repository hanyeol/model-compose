# Depth Estimation Model Task 예제

이 예제는 Depth Anything V2를 사용한 model-compose의 내장 depth-estimation task로 입력 이미지로부터 단안(monocular) depth map을 생성하는 방법을 보여줍니다. ControlNet의 조건 입력으로 사용하거나 다운스트림 장면 이해에 활용하기에 적합합니다.

## 개요

이 워크플로우는 다음과 같은 픽셀 단위 depth map을 생성합니다:

1. **로컬 Depth 모델**: 상대 깊이 추정을 위해 Depth Anything V2를 로컬에서 실행
2. **Grayscale 출력**: 0–255로 정규화된 단일 채널 depth map 반환 (기본값: 가까울수록 밝음)
3. **ControlNet 호환**: grayscale 출력을 ControlNet depth 모델에 직접 투입 가능
4. **자동 모델 관리**: 첫 사용 시 모델 자동 다운로드 및 캐싱
5. **외부 API 불필요**: 완전한 오프라인 depth estimation

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- Depth Anything V2 실행을 위한 충분한 리소스 (권장: 8GB+ RAM, GPU 선호)
- torch와 transformers가 포함된 Python 환경 (자동 관리)

### 환경 설정

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/depth-estimation
   ```

2. 추가 설정 불필요 — 모델과 의존성은 자동으로 관리됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "image=@/path/to/your/input-image.jpg"
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 입력 이미지 선택
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run depth-estimation --input '{"image": "/path/to/your/input-image.jpg"}'
   ```

## 컴포넌트 상세

### Depth Estimation Model Component (기본값)
- **Type**: depth-estimation task를 사용하는 Model 컴포넌트
- **용도**: 단안 상대 깊이 추정
- **모델**: depth-anything/Depth-Anything-V2-Small-hf
- **아키텍처**: Depth Anything V2 (DPT 스타일 ViT)
- **특징**:
  - 다양한 실제 이미지에 대해 강건한 zero-shot 상대 깊이 추정
  - ControlNet depth 조건 입력에 바로 사용 가능한 grayscale 출력
  - GPU 가속 지원

### 모델 정보: Depth Anything V2

- **개발자**: DepthAnything (오픈 소스)
- **아키텍처**: DINOv2 ViT 백본 위의 DPT head
- **학습**: 대규모 합성 + 실제 상대 깊이 데이터
- **강점**: 선명한 경계, 다양한 장면에 대한 강한 일반화 성능
- **입출력**: RGB 이미지 → 단일 채널 상대 depth map

## 워크플로우 상세

### "Estimate Image Depth" 워크플로우 (기본값)

**설명**: 사전 학습된 단안 depth 모델로 입력 이미지로부터 depth map을 생성합니다.

#### 입력 파라미터

| 파라미터  | 타입   | 필수 | 기본값 | 설명                                 |
|-----------|--------|------|--------|--------------------------------------|
| `image`   | image  | 예   | -      | 입력 이미지 파일 (JPEG, PNG 등)      |

#### 출력 형식

| 필드 | 타입   | 설명                                      |
|------|--------|-------------------------------------------|
| -    | image  | 단일 채널 grayscale depth map (L 모드)    |

## 커스터마이징

### Depth 관례 반전

일부 ControlNet depth 모델은 가까울수록이 아니라 멀수록 밝은 depth를 기대합니다. 출력을 뒤집으세요:

```yaml
component:
  type: model
  task: depth-estimation
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Small-hf
  action:
    image: ${input.image as image}
    invert: true
```

### 입력 해상도 override

기본 입력 크기는 모델의 자체 image processor를 따릅니다. 세밀한 디테일이나 빠른 추론이 필요할 때 override 하세요:

```yaml
component:
  type: model
  task: depth-estimation
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Small-hf
  action:
    image: ${input.image as image}
    params:
      image_size: 518    # Depth Anything V2 native 크기
```

### 다른 모델 사용

`AutoModelForDepthEstimation`을 노출하는 모든 HuggingFace 모델이 작동합니다. DPT와 Depth Anything 변종은 `architecture` 필드로 1급 지원됩니다:

```yaml
# Depth Anything V2 Base (더 높은 품질, 느림)
component:
  type: model
  task: depth-estimation
  architecture: depth-anything
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Base-hf
  action:
    image: ${input.image as image}

# Intel DPT Large (고전 DPT 기준 모델)
component:
  type: model
  task: depth-estimation
  architecture: dpt
  model:
    provider: huggingface
    repository: Intel/dpt-large
  action:
    image: ${input.image as image}
```

### 배치 및 비디오 처리

이미지 리스트나 상위 프레임 추출 스트림을 전달하세요:

```yaml
component:
  type: model
  task: depth-estimation
  model:
    provider: huggingface
    repository: depth-anything/Depth-Anything-V2-Small-hf
  action:
    image: ${input.frames}
    batch_size: 4
```

이 설정으로 `conditioning_frames`를 받는 ControlNet 기반 video-to-video 파이프라인의 상위 전처리기로 활용할 수 있습니다.

## 문제 해결

### 자주 발생하는 문제

1. **메모리 부족**: `params.image_size` 또는 `batch_size`를 줄이거나 Small 변종으로 전환
2. **모델 다운로드 실패**: 인터넷 연결과 디스크 공간 확인
3. **느린 처리**: GPU 가속이 활성화되었는지 확인
4. **평평하거나 노이즈가 많은 Depth**: 더 큰 변종(Base/Large) 사용 또는 `params.image_size` 증가

## 모델 변종

- **depth-anything/Depth-Anything-V2-Small-hf**: 기본값. 빠름, ~100MB
- **depth-anything/Depth-Anything-V2-Base-hf**: 더 나은 품질, 느림
- **depth-anything/Depth-Anything-V2-Large-hf**: 최고 품질, 가장 느림
- **Intel/dpt-large**: 고전 DPT 기준 모델
- **Intel/dpt-hybrid-midas**: DPT 하이브리드 변종
