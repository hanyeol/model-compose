# Video Embedding Model Task 예제

이 예제는 model-compose의 내장 `video-embedding` 작업을 통해 X-CLIP을 사용하여 업로드된 비디오로부터 단일 비디오 수준 임베딩을 생성하는 방법을 보여줍니다. 비디오에서 프레임을 샘플링하고, X-CLIP의 vision encoder + multi-frame integration transformer를 통과시켜 X-CLIP의 텍스트 인코더와 동일한 결합 video-text 공간에 있는 하나의 512차원 벡터로 축약합니다. 이를 통해 쿼리마다 비디오를 다시 인코딩하지 않고도 벡터에 대해 자연어 검색을 수행할 수 있습니다.

## 개요

이 워크플로우는 다음과 같은 로컬 비디오 임베딩을 제공합니다:

1. **로컬 비디오 인코더**: 외부 API 없이 HuggingFace transformers를 통해 X-CLIP을 로컬에서 실행
2. **고정 길이 벡터**: 임의 길이의 비디오를 코사인 유사도 검색에 적합한 하나의 512차원 L2 정규화 임베딩으로 축약
3. **결합된 video-text 공간**: 벡터는 X-CLIP의 텍스트 임베딩과 동일한 공간에 존재하므로 텍스트 쿼리로 비디오를 직접 검색 가능
4. **자동 프레임 처리**: 임베더는 추출된 프레임을 X-CLIP이 학습된 프레임 수(`-patch16`은 32, `-patch32`는 8)로 재샘플링하므로 정확한 추출 stride를 맞출 필요 없음

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- ffmpeg가 설치되어 PATH에서 사용 가능 (프레임 추출용)
- X-CLIP 실행을 위한 충분한 시스템 리소스 (권장: 8GB+ RAM, GPU는 선택 사항이지만 추론을 가속화함)
- `transformers`, `torch`, `accelerate`가 있는 Python 환경 (첫 실행 시 자동 설치)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/video-embedding
   ```

2. 추가 환경 구성 불필요 — X-CLIP 체크포인트는 첫 실행 시 HuggingFace에서 다운로드됩니다.

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
     -F 'input={"video": "@clip", "frame_interval": 15}'
   ```

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - `video` 파일 업로드
   - 필요하면 `frame_interval` / `max_frame_count` 조정
   - "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"video": "/path/to/video.mp4", "frame_interval": 15}'
   ```

## 컴포넌트 세부사항

### Frame Extractor 컴포넌트
- **유형**: `video-frame-extractor`
- **드라이버**: `ffmpeg`
- **목적**: 고정된 간격으로 입력 비디오에서 프레임을 샘플링하고, 구체화된 리스트로 임베더에 전달
- **주요 옵션**: `frame_interval` (stride; 1 = 모든 프레임, 15 = 15번째마다) 및 `max_frame_count` (추출된 리스트의 상한, 긴 비디오에 유용)
- **스트리밍 아님**: X-CLIP은 모든 프레임을 하나의 forward pass에서 함께 인코딩하므로 임베더는 실행 전에 전체 리스트가 필요합니다.

### Video Embedding Model 컴포넌트
- **유형**: `video-embedding` 작업을 사용하는 Model 컴포넌트
- **드라이버**: `huggingface`
- **아키텍처**: `xclip`
- **모델**: `microsoft/xclip-base-patch16-zero-shot`
- **기능**:
  - X-CLIP의 vision encoder + multi-frame integration transformer (MIT)를 로컬에서 실행
  - 추출된 프레임 리스트를 X-CLIP의 기대 프레임 수(`-patch16`은 32, `-patch32`는 8)로 균일하게 재샘플링
  - 512차원 L2 정규화 float 벡터 방출 — X-CLIP 텍스트 임베딩에 대한 코사인 유사도는 내적과 동일
  - GPU 메모리를 제한하기 위한 직렬 실행 (`max_concurrent_count: 1`)

### 모델 정보: X-CLIP base-patch16 (zero-shot)
- **개발자**: Microsoft
- **아키텍처**: CLIP ViT-B/16 vision encoder + multi-frame integration transformer + CLIP text encoder
- **학습 프레임**: 32프레임 @ 224x224
- **임베딩 차원**: 512
- **학습 데이터셋**: Kinetics-400
- **Zero-Shot 정확도**: Kinetics-600에서 65.2%, UCF-101에서 72.0%, HMDB-51에서 44.6%
- **라이센스**: MIT
- **모델 카드**: [microsoft/xclip-base-patch16-zero-shot](https://huggingface.co/microsoft/xclip-base-patch16-zero-shot)

## 워크플로우 세부사항

### 기본 워크플로우

**설명**: 업로드된 비디오에서 프레임을 샘플링하고, X-CLIP을 실행하며, 단일 비디오 임베딩을 반환합니다.

#### 작업 흐름

```mermaid
graph TD
    Input((입력<br/>video)) --> J1

    %% Jobs
    J1((frames<br/>작업)) --> C1[Frame Extractor<br/>ffmpeg]
    C1 -.-> |[image, ...]| J1

    J1 --> J2((embed<br/>작업))
    J2 -.-> C2[Video Embedder<br/>X-CLIP]
    C2 -.-> |[512차원 벡터]| J2

    J2 --> Output((출력<br/>embedding))
```

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `video` | video (파일) | 예 | - | 입력 비디오 파일 |
| `frame_interval` | number | 아니오 | 15 | 추출 시 N번째 프레임마다 샘플링. 낮을수록 소스 커버리지가 조밀하나 추출 비용 증가. |
| `max_frame_count` | number | 아니오 | 64 | 추출된 프레임 리스트의 상한. 임베더가 X-CLIP의 학습 프레임 수(32)로 재샘플링하므로 그 값 이상이면 무엇이든 작동하며, 더 큰 값은 추출 시간만 낭비합니다. |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `embedding` | number[] | 512개의 부동소수점 숫자. L2 정규화되어 `dot(a, b)`가 코사인 유사도와 같습니다. |

예시:

```json
{
  "embedding": [0.023, -0.451, 0.187, ...]
}
```

## 시스템 요구사항

### 최소 요구사항
- **RAM**: 8GB (권장 16GB+)
- **디스크 공간**: X-CLIP 체크포인트를 위한 약 1GB
- **CPU**: 모든 최신 x86_64 또는 ARM64 프로세서
- **GPU**: 선택 사항 (CUDA / MPS) — 추론 속도를 크게 향상시킴
- **인터넷**: 1회 모델 다운로드에만 필요

### 성능 참고사항
- 첫 실행 시 X-CLIP 체크포인트(약 400MB) 다운로드 및 transformers 초기화 — 이후 실행은 훨씬 빠름
- 추론 비용은 32프레임 ViT-B/16 forward pass가 지배 — 중급 GPU에서 수백 밀리초, CPU에서 수 초
- 프레임 추출 비용은 `frame_interval`에 따라 확장 — 값을 낮추는 것(조밀한 샘플링)은 `max_frame_count`까지만 유용

## 사용자 정의

### 더 빠른 모델 (더 적은 프레임)

작은 정확도 손실을 대가로 약 4배 빠른 추론을 위해 8프레임 `-patch32` 변형으로 전환:

```yaml
- id: video-embedder
  type: model
  task: video-embedding
  driver: huggingface
  architecture: xclip
  model: microsoft/xclip-base-patch32
```

임베더는 모델의 config에서 기대 프레임 수를 읽으므로 다른 변경은 필요 없습니다.

### 사용자 정의 X-CLIP 체크포인트

HuggingFace의 모든 X-CLIP 계열 체크포인트가 작동합니다 — `model:` 필드만 교체하세요. `get_video_features`를 노출하는 비-X-CLIP 비디오 인코더를 로드하는 경우 `architecture: auto`로 설정하세요.

### 짧은 비디오를 위한 조밀한 샘플링

비디오가 `frame_interval × 32`보다 짧다면, ffmpeg가 최소 32프레임을 생성하도록 `frame_interval`을 낮추거나(또는 `max_frame_count`를 제거하세요). 그러면 임베더는 마지막 프레임을 복제하는 대신 모든 X-CLIP 입력 슬롯에 실제 프레임을 갖게 됩니다.

## 통합 예제

### 벡터 스토어 (인덱싱)

비디오를 한 번 임베딩하고, 벡터를 저장한 뒤 나중에 검색:

```yaml
workflows:
  - id: index-video
    jobs:
      - id: frames
        component: frame-extractor
        input:
          video: ${input.video as video}

      - id: embed
        component: video-embedder
        depends_on: [ frames ]
        input:
          frames: ${jobs.frames.output}

      - id: store
        component: vector-store
        depends_on: [ embed ]
        input:
          vector: ${jobs.embed.output}
          metadata:
            video_id: ${input.video_id}
            title: ${input.title}
```

### 텍스트 검색 (조회)

자연어로 인덱싱된 비디오를 검색. X-CLIP은 자체 텍스트 인코더와 임베딩 공간을 공유하므로 텍스트 측에서도 동일한 X-CLIP 체크포인트를 사용하세요:

```yaml
workflows:
  - id: search-videos
    jobs:
      - id: embed-query
        component: xclip-text-embedder
        input:
          text: ${input.query}

      - id: search
        component: vector-store
        depends_on: [ embed-query ]
        input:
          action: search
          vector: ${jobs.embed-query.output}
          top_k: 10
```

> **참고**: X-CLIP의 텍스트 분기는 비디오 분기와 함께 학습되므로 텍스트 쿼리는 동일한 X-CLIP 모델로 임베딩되어야 합니다 — 일반적인 sentence-transformers 임베딩은 비디오 벡터 공간과 일치하지 않습니다.

## 문제 해결

### 일반적인 문제

1. **추론 중 메모리 부족**: `-patch32` 변형으로 낮추거나 모델 컴포넌트에 `device: cpu`를 설정하여 CPU로 이동.
2. **매우 짧은 비디오에서 모두 중복된 임베딩**: 소스에 총 32프레임 미만이 있으면 임베더는 입력 텐서를 채우기 위해 마지막 프레임을 복제합니다. `frame_interval`을 낮추거나 저하된 충실도를 수용하세요.
3. **모델 다운로드 실패**: 인터넷 연결 및 HuggingFace 가용성 확인; 첫 실행 시 약 400MB를 가져옵니다.
4. **텍스트 쿼리가 일치하지 않음**: 아마도 비-X-CLIP 텍스트 인코더를 사용 중일 것입니다. 텍스트와 비디오 임베딩은 둘 다 동일한 X-CLIP 체크포인트에서 나올 때만 정렬됩니다.

### 성능 최적화

- **GPU**: 모델 컴포넌트에 `device: cuda` (NVIDIA) 또는 `device: mps` (Apple Silicon)를 설정하여 CPU 대비 자릿수 단위의 속도 향상
- **더 작은 모델**: `-patch32` (8프레임)은 일반적인 액션 인식에서 적당한 정확도 손실로 `-patch16` (32프레임)보다 약 4배 빠름
- **여러 비디오 배치**: `frames:`를 리스트의 리스트로 지정하면 여러 비디오를 한 번의 forward pass에서 임베딩 (`batch_size`가 GPU 스트림을 공유하는 개수를 제어)

## 관련 예제

- `text-embedding`: 텍스트에서 임베딩 생성 (크로스 모달 검색을 위해 일치하는 X-CLIP 체크포인트와 함께 사용)
- `image-embedding`: CLIP / SigLIP / DINOv2를 사용한 단일 이미지 변형
- `face-tracking`: 비디오 내 인물별 시간 구간 — 비디오 임베딩과 함께 인덱싱할 수 있는 직교 신호
