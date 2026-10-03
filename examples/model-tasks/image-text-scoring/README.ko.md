# Image-Text Scoring 모델 태스크 예제

이 예제는 model-compose의 내장 `image-text-scoring` 태스크로 로컬 CLIP 모델을 사용해 이미지와 캡션의 의미적 정합도를 점수화하는 방법을 보여줍니다. 두 개의 워크플로우가 전체 모드를 커버합니다: 단일 쌍의 CLIPScore와, 제로샷 분류로도 쓰이는 브로드캐스트 랭킹.

## 개요

`image-text-scoring` 태스크는 CLIP(혹은 SigLIP) 모델의 forward를 실행하고, 임베딩이 아닌 조밀한 점수 — 코사인 유사도, 선택적 pre-softmax 로짓, 선택적 softmax 확률 — 를 반환합니다. 스코어링 모드는 입력 shape으로 자동 결정됩니다:

- `pairwise` — 이미지 1개 × 캡션 1개 (혹은 N × N). 쌍당 코사인 1개.
- `texts_to_image` — 이미지 1개 × 캡션 N개. 캡션당 코사인 1개; softmax가 캡션을 랭킹.
- `images_to_text` — 이미지 N개 × 캡션 1개. 이미지당 코사인 1개; softmax가 이미지를 랭킹.

길이 불일치(예: 이미지 2개 × 캡션 3개)는 오류가 발생합니다.

## 준비

### 사전 요구사항

- model-compose가 설치되어 PATH에 등록
- CLIP 실행에 충분한 시스템 리소스 (권장: 8GB+ RAM, GPU 선택)
- `transformers`와 `torch`가 포함된 Python 환경(자동 관리)

### 임베딩 대신 스코어링을 쓰는 이유

바이-인코더 임베딩 태스크(`image-embedding`, `text-embedding`)는 원본 벡터를 돌려주고, 유사도 선택·임계값 설정·양쪽 결합은 다운스트림에서 직접 처리해야 합니다. `image-text-scoring`은 이 과정을 한 번의 호출로 압축해, 실제로 필요한 수치를 바로 반환합니다:

- **CLIPScore 품질 게이트** — 생성 이미지가 프롬프트와 얼마나 맞는지에 따라 수용/거절.
- **캡션 랭킹** — 한 이미지에 대해 후보 캡션 중 최적 선택.
- **제로샷 분류** — 라벨을 캡션으로 두고 이미지를 모든 라벨에 대해 스코어링하면 softmax가 클래스 확률. 학습 불필요.

지속 저장이 필요한 검색용 벡터를 대체하지는 않습니다. 최종 결과가 "점수"일 때 "접착 코드"를 대체합니다.

### 환경 설정

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/image-text-scoring
   ```

2. 추가 환경 설정 불필요 — 모델은 최초 실행 시 자동 다운로드되어 캐시됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 1 — CLIPScore (pairwise):**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/clip-score/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "image": "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
         "text": "a photo of a cat"
       }
     }'
   ```

   **CLI 사용:**
   ```bash
   model-compose run clip-score --input '{
     "image": "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
     "text": "a photo of a cat"
   }'
   ```

   `{"cosine": 0.28}` 같은 스칼라 코사인을 반환합니다.

3. **워크플로우 2 — 후보 랭킹 (broadcast):**

   이미지 1개 × 캡션 여러 개 (캡션 랭킹):
   ```bash
   model-compose run rank-candidates --input '{
     "image": "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
     "text": [
       "a photo of a cat",
       "a photo of a dog",
       "a photo of a car",
       "a photo of a bowl of fruit"
     ]
   }'
   ```

   캡션별 코사인 리스트와 캡션 축의 softmax 확률을 반환합니다. 가장 높은 softmax 값을 가진 캡션이 모델의 제로샷 라벨입니다.

   이미지 여러 개 × 캡션 1개 (이미지 랭킹) — 같은 워크플로우에서 shape만 뒤집으면 됩니다:
   ```bash
   model-compose run rank-candidates --input '{
     "image": [
       "https://images.unsplash.com/photo-1543852786-1cf6624b9987",
       "https://images.unsplash.com/photo-1518717758536-85ae29035b6d",
       "https://images.unsplash.com/photo-1552053831-71594a27632d"
     ],
     "text": "a photo of a cat"
   }'
   ```

   이미지당 코사인 1개와 이미지 축 softmax를 반환합니다.

   **Web UI 사용:** http://localhost:8081에서 워크플로우를 선택하고 입력값을 넣으면 됩니다.

## 컴포넌트 상세

### Image-Text Scoring 모델 컴포넌트

- **타입**: `image-text-scoring` 태스크를 쓰는 Model 컴포넌트
- **드라이버**: `huggingface`
- **아키텍처**: `clip` (CLIP의 공동 이미지/텍스트 projection과 logit-scale softmax)
- **모델**: `openai/clip-vit-base-patch32`
- **공유 모델, 두 액션**:
  - `score` — pairwise shape; 스칼라 `cosine` 반환
  - `rank` — broadcast shape; 리스트 `cosine`과 softmax 확률 반환

### 모델 정보: CLIP ViT-Base/32

- **개발사**: OpenAI
- **백본**: ViT-Base/32 이미지 인코더 + 12-layer 텍스트 트랜스포머
- **Projection**: 학습된 logit scale을 갖는 공유 이미지/텍스트 임베딩 공간
- **라이선스**: MIT

## 워크플로우 상세

### 워크플로우 1 — "CLIPScore (pairwise)"

이미지 1개 + 캡션 1개 → 스칼라 코사인. 전형적인 CLIPScore 신호.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|-----|------|
| `image` | image | 예 | 이미지 1개 (URL, 경로, 또는 base64) |
| `text` | text | 예 | 캡션 1개 |

#### 출력 포맷

| 필드 | 타입 | 설명 |
|-----|------|-----|
| `cosine` | number | 이미지와 캡션의 코사인 유사도 (−1 ~ 1). |

### 워크플로우 2 — "후보 랭킹 (broadcast)"

한쪽이 다수인 스코어링. 입력 길이로부터 `texts_to_image` 또는 `images_to_text`가 자동 선택됩니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|-----|------|
| `image` | image \| image[] | 예 | 이미지 1개 또는 이미지 리스트. |
| `text` | text \| text[] | 예 | 캡션 1개 또는 캡션 리스트. 한쪽이 반드시 길이 1이어야 broadcast; 같은 길이이면 pairwise. |

#### 출력 포맷

| 필드 | 타입 | 설명 |
|-----|------|-----|
| `cosine` | number[] | "다수" 축의 후보당 코사인 1개. |
| `softmax` | number[] | "다수" 축에 대한 softmax 확률; 최고 확률 인덱스가 1위. |

#### 스코어링 모드 매트릭스

| `image` 길이 | `text` 길이 | 모드 | 점수 shape |
|-------------|------------|------|-----------|
| 1 | 1 | `pairwise` | 스칼라 코사인 |
| N | N | `pairwise` | 쌍당 코사인 1개 |
| 1 | N (>1) | `texts_to_image` | 코사인 리스트 + 캡션 축 softmax |
| N (>1) | 1 | `images_to_text` | 코사인 리스트 + 이미지 축 softmax |
| N (>1) | M (>1), N ≠ M | 오류 | — |

## 시스템 요구사항

### 최소 요구사항

- **RAM**: 8GB (권장 16GB+)
- **VRAM**: 선택; 4GB+ GPU 사용 시 배치 스코어링 속도 크게 향상
- **디스크 공간**: ViT-B/32 체크포인트 ~600MB
- **CPU**: 멀티코어 프로세서 (4코어 이상 권장)
- **인터넷**: 최초 모델 다운로드에 필요

### 성능 참고사항

- 최초 실행 시 모델 다운로드 (~600MB)
- pairwise 워크플로우는 CPU 추론으로 충분; 배치 랭킹은 GPU에서 큰 이득
- 작은 이미지의 CPU 처리에서는 이미지 전처리(224×224 리사이즈)가 지연 시간의 대부분을 차지

## 커스터마이징

### 다른 CLIP / SigLIP 체크포인트 사용

더 큰 CLIP 또는 SigLIP 체크포인트로 교체:

```yaml
components:
  - id: scorer
    type: model
    task: image-text-scoring
    driver: huggingface
    architecture: clip
    model: openai/clip-vit-large-patch14   # 정확도 향상, 속도 저하
```

```yaml
components:
  - id: scorer
    type: model
    task: image-text-scoring
    driver: huggingface
    architecture: siglip
    model: google/siglip-base-patch16-224  # SigLIP (sigmoid loss 변형)
```

### 제로샷 분류 프롬프트 템플릿

캡션을 "a photo of a {label}" 템플릿으로 작성하면 점수 품질이 크게 향상됩니다:

```json
{
  "image": "https://example.com/animal.jpg",
  "text": [
    "a photo of a cat",
    "a photo of a dog",
    "a photo of a horse"
  ]
}
```

짧은 라벨(`"cat"`, `"dog"`)만 써도 동작하지만 softmax 분포 대비가 낮아지는 경향이 있습니다.

### 원시 로짓 반환

CLIP의 코사인은 좁은 범위(자연 이미지에서 대략 −0.1 ~ 0.4)에 있고, pre-softmax 로짓(코사인 × logit_scale)은 대략 [−3, 30]으로 신호를 확장해 임계값 설정이 쉬워집니다:

```yaml
params:
  return_logit: true
```

## 트러블슈팅

### 자주 발생하는 문제

1. **길이 불일치 오류** — 두 입력 리스트의 길이가 다르고 어느 쪽도 1이 아님. 길이를 맞추거나(pairwise) 한쪽을 단일 요소로 설정하세요.
2. **모델 다운로드 실패** — 인터넷 연결과 디스크 공간을 확인.
3. **코사인 값이 전반적으로 낮음** — CLIP 코사인은 올바른 쌍에서도 0 근처입니다. 임계값은 코사인 단독이 아닌 softmax 확률이나 원시 로짓과 비교.
4. **Softmax가 평평해 보임** — 짧은 라벨이나 비슷한 캡션은 분포를 압축합니다. "a photo of a {label}" 템플릿을 쓰거나 더 큰 체크포인트로 전환.

### 성능 최적화

- **GPU**: `device: cuda:0`(Apple Silicon이면 `mps`)로 추론 속도 크게 향상
- **배치 크기**: huggingface 드라이버가 스코어링 job을 자동 배치; 호출을 N번 쪼개지 말고 후보를 한 번에 전달
- **모델 크기**: 지연시간 민감 게이트에는 ViT-B/32, 최고 정확도에는 ViT-L/14

## Image Embedding + Cosine과의 비교

| 특성 | `image-text-scoring` | `image-embedding` + `text-embedding` |
|------|----------------------|---------------------------------------|
| 반환값 | 코사인 (+ 로짓, softmax) | 이미지와 텍스트 벡터를 별도로 |
| 다운스트림 접착 코드 | 없음 | 수동 코사인 / softmax |
| 벡터 캐시 | 안 함 | 함 (vector store 영속화) |
| 적합한 용도 | 1회성 게이트, 랭킹, 분류 | 검색, 중복 제거, 클러스터링 |

지금 판단이 필요하면 스코어링, 나중에 검색할 벡터가 필요하면 임베딩을 선택하세요.
