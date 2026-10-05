# Video-Text Scoring 모델 태스크 예제

이 예제는 model-compose의 내장 `video-text-scoring` 태스크로 로컬 X-CLIP 모델을 사용해 비디오와 캡션의 의미적 정합도를 점수화하는 방법을 보여줍니다. 두 개의 워크플로우가 핵심 유스케이스를 커버합니다: text-to-video 품질 게이트용 CLIPScore 스타일 스칼라와, 후보 캡션을 랭킹하는 제로샷 비디오 분류기.

## 개요

X-CLIP의 forward는 텍스트 임베딩을 **스코어링 대상 비디오에 조건부로 재조정**하므로, `video-embedding` + `text-embedding`으로 양쪽을 독립 임베딩해서는 점수를 **재현할 수 없습니다**. `video-text-scoring` 태스크는 전체 X-CLIP forward를 직접 호출해 조밀한 점수 — 코사인 유사도, 선택적 pre-softmax 로짓, 선택적 softmax 확률 — 를 반환합니다.

스코어링 모드는 입력 shape으로 자동 결정됩니다:

- `pairwise` — 비디오 N × 캡션 N. 쌍당 코사인 1개.
- `texts_to_video` — 비디오 1 × 캡션 K. 텍스트 축의 코사인 리스트; softmax가 캡션을 랭킹.
- `videos_to_text` — 비디오 N × 캡션 1. 비디오 축의 코사인 리스트; softmax가 비디오를 랭킹.

길이 불일치는 오류입니다.

## 준비

### 사전 요구사항

- model-compose가 설치되어 PATH에 등록
- `ffmpeg`가 PATH에 등록 (프레임 추출기가 사용)
- X-CLIP 실행에 충분한 시스템 리소스 (권장: 12GB+ RAM, 지연 민감 게이트에는 GPU 권장)
- `transformers`와 `torch`가 포함된 Python 환경(자동 관리)

### 임베딩 대신 스코어링을 쓰는 이유

CLIP(이미지-텍스트)의 경우 양쪽을 임베딩해 코사인을 계산하면 CLIPScore와 정확히 일치합니다. 하지만 X-CLIP은 **일치하지 않습니다** — 텍스트 임베딩이 어느 비디오와 비교되는지에 따라 달라지기 때문입니다. 따라서 `video-text-scoring`이 **실제 X-CLIP 점수를 얻는 유일한 경로**입니다:

- **text-to-video 품질 게이트** — 생성된 클립이 프롬프트와 얼마나 맞는지에 따라 수용/거절.
- **제로샷 비디오 분류** — 라벨을 캡션으로 두고 비디오를 모든 라벨에 대해 스코어링, softmax를 클래스 확률로 사용. 학습 불필요.
- **비디오 검색 랭킹** — 하나의 텍스트 쿼리에 대해 N개 후보 클립을 랭킹.

### 환경 설정

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/video-text-scoring
   ```

2. 추가 환경 설정 불필요 — 모델은 최초 실행 시 자동 다운로드되어 캐시됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 1 — 비디오 × 프롬프트 스코어 (pairwise):**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/score-video/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "video": "https://example.com/clip.mp4",
         "text": "a chef chopping vegetables in a kitchen"
       }
     }'
   ```

   **CLI 사용:**
   ```bash
   model-compose run score-video --input '{
     "video": "https://example.com/clip.mp4",
     "text": "a chef chopping vegetables in a kitchen"
   }'
   ```

   `{"cosine": 0.26}` 같은 스칼라 코사인을 반환합니다.

3. **워크플로우 2 — 제로샷 비디오 분류:**

   ```bash
   model-compose run classify-video --input '{
     "video": "https://example.com/clip.mp4",
     "text": [
       "a cooking video",
       "a sports highlight",
       "an animated short",
       "a dance performance"
     ]
   }'
   ```

   캡션별 코사인 리스트와 캡션 축의 softmax 확률을 반환합니다. 가장 높은 softmax 값을 가진 캡션이 모델의 제로샷 라벨입니다.

   **Web UI 사용:** http://localhost:8081에서 워크플로우를 선택하고 입력값을 넣으면 됩니다.

## 컴포넌트 상세

### Video-Text Scoring 모델 컴포넌트

- **타입**: `video-text-scoring` 태스크를 쓰는 Model 컴포넌트
- **드라이버**: `huggingface`
- **아키텍처**: `xclip` (비디오-조건부 텍스트 임베딩)
- **모델**: `microsoft/xclip-base-patch32`
- **공유 모델, 두 액션**:
  - `score` — pairwise shape; 스칼라 `cosine` 반환
  - `rank` — texts_to_video shape; 리스트 `cosine`과 softmax 확률 반환

### Frame Sampler (Video Frame Extractor)

- **타입**: `video-frame-extractor`
- **드라이버**: `ffmpeg`
- 초당 ~2프레임, 클립당 최대 32프레임 추출. X-CLIP가 내부적으로 자체 기대 프레임 수(8개)로 다시 샘플링하므로 과도 샘플링은 안전합니다.

### 모델 정보: X-CLIP ViT-Base/32

- **개발사**: Microsoft
- **백본**: ViT-Base/32 이미지 인코더 + Multiframe Integration Transformer (MIT) + 비디오 조건부 프롬프트가 적용된 CLIP 텍스트 트랜스포머
- **Projection**: 학습된 logit scale을 갖는 공유 비디오/텍스트 임베딩 공간
- **학습 데이터**: Kinetics-400 / 600
- **라이선스**: MIT

## 워크플로우 상세

### 워크플로우 1 — "Score Video × Prompt (pairwise)"

비디오 1 + 캡션 1 → 스칼라 코사인. 전형적인 text-to-video 품질 게이트.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|-----|------|
| `video` | video | 예 | 비디오 1개 (URL, 경로, 또는 data URI) |
| `text` | text | 예 | 캡션 / 프롬프트 1개 |

#### 출력 포맷

| 필드 | 타입 | 설명 |
|-----|------|-----|
| `cosine` | number | 비디오와 캡션의 코사인 유사도. |

### 워크플로우 2 — "제로샷 비디오 분류"

비디오 1 + 후보 캡션 리스트 → 랭킹 분포.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|-----|------|
| `video` | video | 예 | 비디오 1개. |
| `text` | text[] | 예 | 후보 캡션 (클래스 라벨처럼 취급). |

#### 출력 포맷

| 필드 | 타입 | 설명 |
|-----|------|-----|
| `cosine` | number[] | 후보 캡션별 코사인 1개. |
| `softmax` | number[] | 캡션 축 softmax 확률; 최고 확률 인덱스가 1위 라벨. |

#### 스코어링 모드 매트릭스

| `videos` 길이 | `texts` 길이 | 모드 | 점수 shape |
|-------------|------------|------|-----------|
| 1 | 1 | `pairwise` | 스칼라 코사인 |
| N | N | `pairwise` | 쌍당 코사인 1개 |
| 1 | K (>1) | `texts_to_video` | 코사인 리스트 + 캡션 축 softmax |
| N (>1) | 1 | `videos_to_text` | 코사인 리스트 + 비디오 축 softmax |
| N (>1) | M (>1), N ≠ M | 오류 | — |

## 시스템 요구사항

### 최소 요구사항

- **RAM**: 12GB (권장 16GB+)
- **VRAM**: 4GB+ GPU 강력 권장; CPU 추론은 CLIP보다 10–20배 느림 (Multiframe Integration Transformer 때문)
- **디스크 공간**: ViT-B/32 X-CLIP 체크포인트 ~600MB
- **CPU**: 멀티코어 프로세서 (4코어 이상)
- **인터넷**: 최초 모델 다운로드에 필요

### 성능 참고사항

- 최초 실행 시 모델 다운로드 (~600MB)
- 짧은 클립의 CPU 처리에서는 프레임 추출이 지연 시간의 대부분을 차지; `frame_rate`로 상한 설정
- X-CLIP의 MIT가 프레임 간 cross-attention을 수행 — 더 긴 클립은 프레임 수만으로 추정되는 것보다 비용이 큼

## 커스터마이징

### 여러 비디오를 같은 캡션에 대해 스코어링

중첩 프레임 리스트로 여러 비디오를 한 호출에 담으면, 스코어러가 `videos_to_text` cross matrix를 한 번의 forward로 계산합니다:

```yaml
jobs:
  - id: score
    component: scorer
    action: rank
    input:
      frames:
        - ${jobs.extract-a.output}
        - ${jobs.extract-b.output}
        - ${jobs.extract-c.output}
      text: "a cooking video"
```

결과의 `cosine`과 `softmax`는 비디오 축의 리스트 — 최고 softmax 인덱스가 1위 비디오.

### 제로샷 분류 프롬프트 템플릿

CLIP과 마찬가지로 템플릿이 점수 품질을 올립니다:

```json
{
  "video": "https://example.com/clip.mp4",
  "text": [
    "a video of cooking",
    "a video of a sports game",
    "a video of a dance performance"
  ]
}
```

### 원시 로짓 반환

X-CLIP 코사인은 좁은 범위에 있고, pre-softmax 로짓(코사인 × logit_scale)은 임계값 설정이 쉬운 더 넓은 범위로 신호를 확장합니다:

```yaml
params:
  return_logit: true
```

## 트러블슈팅

### 자주 발생하는 문제

1. **길이 불일치 오류** — 비디오와 캡션 둘 다 1개 초과이고 길이가 다름. 길이를 맞추거나(pairwise) 한쪽을 단일 요소로.
2. **모델 다운로드 실패** — 인터넷 연결과 디스크 공간 확인.
3. **Softmax가 평평해 보임** — 캡션이 너무 비슷하거나 클립이 X-CLIP의 Kinetics 사전학습 도메인에서 벗어남. "a video of {label}" 템플릿 사용 또는 더 구별되는 후보 추가.
4. **점수가 항상 0 근처** — 올바른 쌍에서도 raw 코사인은 0 근처입니다. 코사인 단독이 아닌 softmax 확률이나 원시 로짓과 비교.
5. **ffmpeg not found** — `ffmpeg`를 설치하고 PATH에 등록.

### 성능 최적화

- **GPU**: `device: cuda:0`(Apple Silicon이면 `mps`)로 추론 속도 크게 향상
- **프레임 예산**: 짧은 클립에서는 추출기의 `frame_rate`와 `max_frame_count`를 낮게; 모델이 내부적으로 다시 샘플링
- **배치**: 여러 비디오 job(중첩 프레임)을 한 호출에 담아 N번의 별도 워크플로우보다 효율적

## video-embedding + Cosine과의 비교

| 특성 | `video-text-scoring` | `video-embedding` + `text-embedding` |
|------|----------------------|---------------------------------------|
| 반환값 | 코사인 (+ 로짓, softmax) | 비디오와 텍스트 벡터를 별도로 |
| 모델 자체 점수 재현 | 가능 | **불가능** (X-CLIP이 비디오-조건부로 텍스트 임베딩 생성) |
| 벡터 캐시 | 안 함 | 함 (vector store 영속화) |
| 적합한 용도 | 1회성 게이트, 랭킹, 제로샷 분류 | 검색, 중복 제거, 클러스터링 |

X-CLIP 점수 자체가 필요하면 스코어링을 선택하세요. 임베딩은 디스크에 비디오 벡터를 저장해 나중에 검색하는 용도로만 선택 — 저장된 벡터는 X-CLIP가 보고하는 코사인을 다시 재현할 수 없습니다.
