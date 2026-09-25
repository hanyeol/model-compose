# 10장: 로컬 AI 모델 사용

이 장에서는 model-compose와 함께 로컬 AI 모델을 사용하는 방법을 다룹니다.

---

## 10.1 로컬 모델 개요

### 로컬 모델이란?

로컬 모델은 외부 API 없이 시스템에서 직접 실행되는 AI 모델입니다. model-compose는 다양한 드라이버와 모델 포맷을 지원하여 유연한 모델 실행 환경을 제공합니다.

### 지원 모델 드라이버

model-compose는 다음 모델 드라이버를 지원합니다:

| 드라이버 | 설명 | 주요 사용 사례 |
|---------|------|---------------|
| `huggingface` | HuggingFace transformers | 범용 모델 추론, 가장 광범위한 모델 지원 |
| `unsloth` | Unsloth 최적화 모델 | 빠른 파인튜닝, 메모리 효율적 학습 |
| `vllm` | vLLM 추론 엔진 | 고성능 LLM 서빙, 프로덕션 배포 |
| `llamacpp` | llama.cpp 엔진 | CPU 추론, GGUF 포맷, 저사양 환경 |
| `custom` | 커스텀 구현 | 특수 모델, 사용자 정의 로직 |

### 지원 모델 포맷

다양한 모델 포맷을 지원합니다:

| 포맷 | 설명 | 호환 드라이버 |
|------|------|--------------|
| `pytorch` | PyTorch 기본 포맷 (.bin, .pt) | huggingface, unsloth |
| `safetensors` | 안전한 텐서 저장 포맷 | huggingface, unsloth |
| `onnx` | 최적화된 크로스 플랫폼 포맷 | custom |
| `gguf` | llama.cpp 양자화 포맷 | llamacpp |
| `tensorrt` | NVIDIA TensorRT 최적화 | custom |

### 로컬 모델의 장단점

**장점:**
- **비용 절감**: API 호출 비용 없음
- **프라이버시**: 데이터가 외부로 전송되지 않음
- **오프라인 실행**: 인터넷 연결 불필요
- **커스터마이징**: 파인튜닝, LoRA 어댑터 적용 가능
- **낮은 레이턴시**: 네트워크 지연 없음 (로컬 하드웨어 성능에 따라)

**단점:**
- **하드웨어 요구사항**: GPU 메모리, 연산 성능 필요
- **모델 크기**: 대용량 모델 파일 다운로드 및 저장 필요
- **설정 복잡도**: 환경 설정, 의존성 관리 필요
- **성능 제약**: 대형 모델은 고사양 GPU 필요

### 기본 사용법

**간단한 모델 로드 (HuggingFace)**
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  # 기본 드라이버는 huggingface
```

**드라이버 명시**
```yaml
component:
  type: model
  task: text-generation
  driver: unsloth  # Unsloth 드라이버 사용
  model: unsloth/llama-2-7b-bnb-4bit
```

**로컬 파일 로드**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: local
    path: /path/to/model
    format: pytorch
```

**GGUF 포맷**
```yaml
component:
  type: model
  task: text-generation
  driver: llamacpp
  model:
    provider: local
    path: /models/llama-2-7b-chat.Q4_K_M.gguf
    format: gguf
```

---

## 10.2 모델 설치 및 준비

### 모델 소스 지정 방법

model-compose는 두 가지 provider를 통해 모델을 로드할 수 있습니다:

#### 1. HuggingFace Hub (provider: huggingface)

**간단한 방법 (문자열)**
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  # 자동으로 HuggingFace Hub에서 로드
```

**상세 설정**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    revision: main                  # 브랜치 또는 커밋 해시
    filename: pytorch_model.bin     # 특정 파일 지정
    cache_dir: /custom/cache        # 캐시 디렉토리
    local_files_only: false         # 로컬 캐시만 사용 여부
    token: ${env.HUGGINGFACE_TOKEN} # 프라이빗 모델 토큰
```

**HuggingFace 설정 필드:**
- `repository`: HuggingFace 모델 리포지토리 (필수)
- `revision`: 모델 버전 또는 브랜치 (기본값: `main`)
- `filename`: 리포지토리 내 특정 파일 지정 (선택)
- `cache_dir`: 모델 파일 캐시 디렉토리 (기본값: `~/.cache/huggingface/`)
- `local_files_only`: 로컬 캐시만 사용 (기본값: `false`)
- `token`: 프라이빗 모델 접근 토큰 (선택)

#### 2. 로컬 파일 (provider: local)

**간단한 방법 (경로 문자열)**
```yaml
component:
  type: model
  task: text-generation
  model: /path/to/model
  # 로컬 경로로 자동 인식
```

**상세 설정**
```yaml
component:
  type: model
  task: text-generation
  model:
    provider: local
    path: /path/to/model
    format: pytorch  # pytorch, safetensors, onnx, gguf, tensorrt
```

**Local 설정 필드:**
- `path`: 모델 파일 또는 디렉토리 경로 (필수)
- `format`: 모델 파일 포맷 (기본값: `pytorch`)

**로컬 경로 인식 규칙:**

다음 패턴으로 시작하는 문자열은 자동으로 로컬 경로로 인식됩니다:
- 절대 경로: `/path/to/model`
- 상대 경로: `./model`, `../model`
- 홈 디렉토리: `~/models/model`
- Windows 드라이브: `C:\models\model`

그 외는 HuggingFace Hub 리포지토리로 인식됩니다:
- `meta-llama/Llama-2-7b-hf`
- `gpt2`
- `username/custom-model`

### HuggingFace 모델 다운로드

모델은 처음 실행 시 자동으로 다운로드되며, 필요한 패키지도 자동으로 설치됩니다:

```yaml
component:
  type: model
  task: chat-completion
  model: meta-llama/Llama-2-7b-chat-hf
  # 첫 실행 시 자동으로 ~/.cache/huggingface/ 에 다운로드됨
```

수동 다운로드:
```bash
# HuggingFace CLI로 사전 다운로드
pip install huggingface-hub
huggingface-cli download meta-llama/Llama-2-7b-chat-hf
```

### 프라이빗 모델 접근

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    token: ${env.HUGGINGFACE_TOKEN}
```

환경 변수 설정:
```bash
export HUGGINGFACE_TOKEN=hf_your_token_here
model-compose up
```

### 특정 모델 버전 사용

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    revision: v1.0  # 특정 태그
    # 또는 커밋 해시: revision: a1b2c3d4
```

### 오프라인 모드

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: gpt2
    local_files_only: true  # 로컬 캐시에서만 로드
```

---

## 10.3 지원 태스크 유형

model-compose는 다음 태스크 타입을 지원합니다:

| 태스크 | 설명 | 주요 사용 사례 |
|--------|------|---------------|
| `text-generation` | 텍스트 생성 | 스토리 작성, 코드 생성 |
| `chat-completion` | 대화형 완성 | 챗봇, 어시스턴트 |
| `text-to-text` | Seq2seq 텍스트 변환 | 번역, 요약, 재작성 |
| `text-classification` | 텍스트 분류 | 감정 분석, 주제 분류 |
| `text-embedding` | 텍스트 임베딩 | 시맨틱 검색, RAG |
| `text-reranking` | 쿼리-문서 스코어링 | RAG 파이프라인에서 검색 결과 재정렬 |
| `typed-decision` | 후보별 확률을 함께 반환하는 타입드 분류 | 라우팅, 정책 판단, 구조화된 트리아지 |
| `image-to-text` | 이미지 캡셔닝 | 이미지 설명 생성, VQA |
| `image-text-to-text` | 멀티모달 이미지 + 텍스트 생성 | 시각 추론, 멀티모달 대화 |
| `image-embedding` | 이미지 임베딩 | 시각 검색, 이미지 중복 제거, 클러스터링 |
| `video-embedding` | 비디오 임베딩 | 시맨틱 비디오 검색, 중복 제거, 클러스터링 |
| `image-generation` | 이미지 생성 | 텍스트→이미지 변환 |
| `image-upscale` | 이미지 업스케일 | 해상도 향상 |
| `text-to-speech` | 텍스트 음성 합성 | 음성 생성, 복제, 디자인 |
| `speech-to-text` | 음성 인식 | 자막 생성, 받아쓰기 |
| `speaker-diarization` | 화자별 발화 구간 분할 | 회의·인터뷰의 화자별 턴 분할 |
| `voice-activity-detection` | 오디오의 음성 구간 감지 | ASR 전 침묵 필터링, 자막 분할 |
| `face-detection` | 얼굴 검출 | 이미지에서 얼굴 위치 검출 |
| `pose-detection` | 자세 검출 | 인체 키포인트 추정 |
| `object-detection` | 객체 검출 | 클래스 라벨과 바운딩 박스로 객체 검출 |
| `image-segmentation` | 이미지 세그멘테이션 | 영역별 이진 마스크 생성 (자동 또는 박스 프롬프트) |
| `text-to-video` | 텍스트→비디오 생성 | 프롬프트 기반 짧은 비디오 클립 |
| `image-to-video` | 이미지→비디오 생성 | 정지 이미지를 애니메이션화, 선택적으로 프롬프트로 유도 |
| `video-to-video` | 소스 클립→비디오 변환 | 프롬프트로 클립 리스타일(AnimateDiff), 또는 입력의 포즈/표정으로 참조 캐릭터 구동(Wan-Animate) |
| `image-to-3d` | 단일 이미지 3D 메시 생성 | 참조 이미지에서 텍스처가 입혀진 GLB 자산 생성 |
| `face-embedding` | 얼굴 임베딩 | 얼굴 인식, 비교 |
| `face-tracking` | 얼굴 추적 | 비디오 프레임 전반에서 아이덴티티를 추적하고 타임코드 세그먼트로 정리 |
| `pose-tracking` | 자세 추적 | 비디오 프레임 전반에서 사람(자세)을 트랙별 타임코드 세그먼트로 추적 |
| `object-tracking` | 객체 추적 | 비디오 프레임 전반에서 객체를 트랙별 타임코드 세그먼트로 추적 |
| `shot-boundary-detection` | 샷 경계 검출 | 비디오에서 하드 컷을 검출하고 샷별 시작/종료 타임코드 반환 |
| `music-generation` | 음악 생성 | 오디오/음악 합성 |
| `music-source-separation` | 음악 소스 분리 | 믹스를 보컬 / 드럼 / 베이스 / 기타 스템으로 분리 |
| `music-transcription` | 음악 전사 | 오디오 녹음을 MIDI와 노트 이벤트로 변환 |
| `music-beat-tracking` | 음악 비트 트래킹 | 음악 녹음의 비트와 다운비트 위치를 검출 |
| `talking-head` | 초상화→비디오 립싱크 | 정지 초상화를 구동 오디오에 맞춰 움직임 (아이덴티티 합성) |
| `lip-sync` | 비디오→비디오 립싱크 | 얼굴 비디오의 입 움직임을 새 오디오에 맞춰 재싱크 |

### 10.3.1 text-generation

프롬프트를 기반으로 텍스트를 생성합니다.

```yaml
component:
  type: model
  task: text-generation
  model: HuggingFaceTB/SmolLM3-3B
  action:
    prompt: ${input.prompt as text}
    params:
      max_output_length: 32768
      temperature: 0.7
      top_p: 0.9
```

**주요 파라미터:**
- `max_output_length`: 최대 생성 토큰 수
- `temperature`: 생성 랜덤성 (0.0~2.0, 낮을수록 결정적)
- `top_p`: Nucleus sampling threshold
- `top_k`: Top-K sampling
- `repetition_penalty`: 반복 방지 (1.0~2.0)

### 10.3.2 chat-completion

대화 형식의 메시지를 처리합니다.

```yaml
component:
  type: model
  task: chat-completion
  model: HuggingFaceTB/SmolLM3-3B
  action:
    messages:
      - role: system
        content: ${input.system_prompt}
      - role: user
        content: ${input.user_prompt}
    params:
      max_output_length: 2048
      temperature: 0.7
```

**메시지 형식:**
- `role`: `system`, `user`, `assistant`
- `content`: 메시지 내용

**채팅 템플릿 재정의:**

컴포넌트에 `chat_template`을 지정하면 토크나이저 기본 Jinja 템플릿을 재정의합니다 (`huggingface`, `vllm`, `llamacpp` 드라이버에 적용됩니다):

```yaml
component:
  type: model
  task: chat-completion
  model: HuggingFaceTB/SmolLM3-3B
  chat_template: |
    {%- for message in messages %}
    <|{{ message.role }}|>
    {{ message.content }}</s>
    {%- endfor %}
```

### 10.3.3 text-to-text

번역, 요약, 재작성 같은 seq2seq(인코더-디코더) 변환을 수행합니다.

```yaml
# 번역 (Helsinki-NLP)
component:
  type: model
  task: text-to-text
  driver: huggingface
  model: Helsinki-NLP/opus-mt-en-fr
  action:
    text: ${input.text as text}
```

```yaml
# 요약 (BART)
component:
  type: model
  task: text-to-text
  driver: huggingface
  architecture: bart
  model: facebook/bart-large-cnn
  action:
    text: ${input.document as text}
    params:
      max_output_length: 150
```

```yaml
# T5 계열 (입력 텍스트에 태스크 접두사 필요)
component:
  type: model
  task: text-to-text
  driver: huggingface
  architecture: t5
  model: t5-base
  action:
    text: "summarize: ${input.document}"
```

**지원 아키텍처:**
- `auto` (기본값): 모델로부터 자동 추론
- `bart`: BART 계열 인코더-디코더 모델
- `t5`: T5 계열 모델 (입력 텍스트에 태스크 접두사 필요)

### 10.3.4 text-classification

텍스트를 카테고리로 분류합니다.

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased-finetuned-sst-2-english
  action:
    text: ${input.text as text}
    output:
      label: ${result.label}
      score: ${result.score}
```

### 10.3.5 text-embedding

텍스트를 고차원 벡터로 변환합니다.

```yaml
component:
  type: model
  task: text-embedding
  model: sentence-transformers/all-MiniLM-L6-v2
  action:
    text: ${input.text as text}
    output:
      embedding: ${result.embedding}
```

사용 예제 (RAG 시스템):
```yaml
workflow:
  title: Document Search
  jobs:
    - id: embed-query
      component: embedder
      input:
        text: ${input.query}
      output:
        query_vector: ${result.embedding}

    - id: search
      component: vector-store
      action: search
      input:
        vector: ${jobs.embed-query.output.query_vector}
        top_k: 5
```

### 10.3.6 text-reranking

(query, document) 쌍마다 cross-encoder로 점수를 매기고 관련도순으로 정렬된 문서를 반환합니다. 일반적인 검색 파이프라인의 두 번째 단계입니다: 벡터 스토어가 넓은 후보 집합을 가져오고, 리랭커가 상위 결과를 정제합니다.

```yaml
component:
  type: model
  task: text-reranking
  model: BAAI/bge-reranker-v2-m3
  action:
    query: ${input.query}
    documents: ${input.candidates}
    top_k: 5
```

**주요 파라미터:**
- `query`: 쿼리 문자열. 리스트를 넘기면 여러 개의 독립적인 리랭킹 작업을 한 번에 실행합니다.
- `documents`: 후보 문서. 문자열이거나, `document_field: <field>`와 함께 페어링된 객체입니다.
- `top_k`: 쿼리별 상위 K개 결과만 유지합니다.
- `score_threshold`: 이 점수 미만의 결과를 버립니다.
- `return_documents`: `false`이면 결과에 `index`와 `score`만 포함됩니다.

사용 예제 (RAG 리랭크 단계):
```yaml
workflow:
  title: Reranked Document Search
  jobs:
    - id: embed-query
      component: embedder
      input:
        text: ${input.query}

    - id: retrieve
      component: vector-store
      action: search
      input:
        vector: ${jobs.embed-query.output}
        top_k: 50

    - id: rerank
      component: reranker
      input:
        query: ${input.query}
        candidates: ${jobs.retrieve.output}
        document_field: text
        top_k: 5
```

### 10.3.7 typed-decision

호출자가 제공한 스키마의 각 질문에 대해 타입드 응답과 후보별 확률을 반환합니다. 스코어러가 응답 토큰의 로짓을 직접 읽으므로, 출력은 반드시 허용된 값 중 하나가 되도록 보장되며 자유 형식 생성이나 JSON 파싱이 없습니다.

**질문 타입** (`schema` 항목별):
- `noul` — 예/아니오. 선택적 `criteria: {true?: ..., false?: ...}`로 두 옵션 텍스트를 다듬을 수 있습니다.
- `choice` — N개의 명명된 옵션 중 하나 선택. `criteria`는 `{이름: 설명}` 맵입니다.
- `score` — 순서형 스케일로 평점. `criteria`는 인덱스 0부터 시작하는 레벨 설명 리스트입니다. 결과는 레벨에 대한 softmax의 평균으로 계산된 **기대 레벨**(float)입니다.

세 가지 패밀리가 지원됩니다 (모두 `driver: custom`). 컴포넌트당 하나를 선택하며, 여러 패밀리를 결합하려면 여러 컴포넌트를 실행하세요.

```yaml
component:
  type: model
  task: typed-decision
  driver: custom
  family: laya                          # 'laya' | 'kev' | 'nimble'
  preset: multilingual                  # laya 전용: 'english' | 'multilingual' (기본값) | 'typed-decisions'
  action:
    text: ${input.text}
    schema: ${input.schema}
    return_probabilities: true
```

**주요 파라미터:**
- `text`: 스코어러가 판단할 비정형 텍스트. 리스트를 넘기면 여러 입력을 한 호출에서 스코어링합니다.
- `schema`: 질문 ID → 질문 스펙 맵. 각 스펙은 `type: noul | choice | score`, `instructions`, 그리고 (`noul`을 제외한 경우) `criteria`를 가집니다.
- `return_probabilities`: 질문별 후보 점수를 `fields[qid].scores`에 포함합니다.
- `return_logits`: 질문별 softmax 이전 원시 로짓 포함 (`nimble`은 API 레벨에서만 로짓을 노출).

**결과 형태**: `{ decision: { qid: value }, fields?: { qid: { scores: {...} } } }`. `noul`은 boolean으로, `choice`는 승리한 옵션 이름으로, `score`는 기대 레벨로 해석됩니다.

**패밀리:**

- `laya` (Convai Innovations, [예제](../../examples/model-tasks/typed-decision-laya)) — ModernBERT/mmBERT 기반의 비자기회귀 스코어러로 RLCD로 학습된 디시전 헤드를 가집니다. `preset`으로 선택되는 세 개의 체크포인트를 제공합니다: `english` (ModernBERT-large, 512 토큰 컨텍스트), `multilingual` (mmBERT-base, 100+ 언어, 최대 1024 토큰 — `max_seq_length`으로 8192까지 확장 가능), `typed-decisions` (4개의 typed-decisions 워크플로우에 파인튜닝). CUDA, MPS (Apple Silicon), CPU에서 실행됩니다. Linux+x86_64에서는 `fast: true`로 TileLang 융합 CUDA 커널을 활성화할 수 있습니다.
- `kev` (Jared Palmer, [예제](../../examples/model-tasks/typed-decision-kev)) — 고정된 Qwen3.5 베이스 위에 얹은 LoRA 어댑터, 포인터 스코어링 헤드, 메타데이터의 번들입니다 (베이스 모델 ID는 체크포인트의 `head.pt`에서 읽어오므로 수동 오버라이드가 필요 없습니다). 사이즈: 0.8B / 4B / 9B. 백엔드는 Apple Silicon에서 MLX, CUDA/CPU에서 Torch를 자동 선택하며, `max_state_length`와 `max_branch_length`가 공유 상태와 질문별 브랜치를 각각 독립적으로 제한합니다.
- `nimble` (Bespoke Labs, [예제](../../examples/model-tasks/typed-decision-nimble)) — 첫 실행 시 베이스 모델(기본값 Qwen/Qwen3.5-9B)에 LoRA 어댑터를 병합한 스냅샷을 캐싱합니다. Apple Silicon에서는 MLX, Linux에서는 BF16을 지원하는 NVIDIA GPU가 필요하며, 드라이버가 백엔드를 자동 선택합니다.

### 10.3.8 image-to-text

이미지를 분석하여 텍스트를 생성합니다.

```yaml
component:
  type: model
  task: image-to-text
  model: Salesforce/blip-image-captioning-large
  architecture: blip
  action:
    image: ${input.image as image}
    prompt: ${input.prompt as text}
```

**지원 아키텍처:**
- `blip`: 이미지 캡셔닝
- `git`: Generative Image-to-Text
- `vit-gpt2`: Vision Transformer + GPT-2

### 10.3.9 image-embedding

이미지를 고정 크기 벡터로 인코딩합니다. 시각적 유사도, 중복 제거, 검색 인덱스 구축에 사용됩니다.

```yaml
component:
  type: model
  task: image-embedding
  driver: huggingface
  architecture: clip
  model: openai/clip-vit-base-patch32
  action:
    image: ${input.image as image}
    batch_size: 16
    params:
      normalize: true
```

**지원 아키텍처:**
- `clip`: OpenAI CLIP — `get_image_features`로 이미지 인코딩
- `siglip`: Google SigLIP — `get_image_features`로 이미지 인코딩
- `dinov2`: Meta DINOv2 — 자기지도 학습 인코더, `params.pooling`으로 풀링
- `auto`: `AutoModel` 자동 판별 — 로드된 모델이 `get_image_features`를 노출하면 그 경로를 사용하고, 아니면 `last_hidden_state`를 풀링

CLIP과 SigLIP은 내장 풀링을 사용하므로 `params.pooling`이 무시됩니다. DINOv2(그리고 `auto`가 projection head 없는 모델을 로드한 경우)에서는 `params.pooling`으로 `cls`(기본값), `mean`, `max` 중 선택합니다.

결과: 이미지당 벡터 하나(`List[float]`). 리스트 입력이면 벡터 리스트, 비동기 스트림 입력이면 벡터를 순차 방출하는 async iterator.

### 10.3.10 video-embedding

비디오 프레임 시퀀스를 하나의 고정 크기 벡터로 인코딩합니다. 시맨틱 비디오 검색, 중복 제거, 클러스터링에 적합합니다. 소스 비디오에서 프레임을 먼저 샘플링하려면 `video-frame-extractor`와 함께 사용하세요.

```yaml
component:
  id: video-embed
  type: model
  task: video-embedding
  driver: huggingface
  architecture: xclip
  model: microsoft/xclip-base-patch32
  action:
    frames: ${input.frames}
    params:
      normalize: true
    output: ${result}
```

| 필드 | 타입 | 기본값 | 설명 |
|-------|------|---------|-------------|
| `frames` | image / list | **필수** | 한 비디오의 프레임, 프레임 리스트, 비디오별 프레임 배치 리스트, 또는 배치 스트림 |
| `batch_size` | int | `1` | 한 번에 처리할 비디오 수 |
| `params.normalize` | bool | `true` | 출력 벡터를 L2 정규화 |

**지원 아키텍처:**
- `xclip`: Microsoft X-CLIP (비디오-텍스트 대조 학습; 예: `microsoft/xclip-base-patch32`).
- `videomae`: VideoMAE masked autoencoder (예: `MCG-NJU/videomae-base`).
- `auto`: 로드된 모델 구성에서 자동 추론.

결과 형태:

```json
[0.021, -0.114, 0.087, ...]
```

일반적인 파이프라인: `video-frame-extractor` → `video-embedding` → `vector-store` (검색용).

### 10.3.11 image-generation

텍스트 프롬프트에서 이미지를 생성합니다.

```yaml
component:
  type: model
  task: image-generation
  architecture: flux
  model: black-forest-labs/FLUX.1-dev
  action:
    prompt: ${input.prompt as text}
    width: 1024
    height: 1024
    params:
      inference_steps: 50
```

**지원 아키텍처:**
- `flux`: FLUX 모델
- `sdxl`: Stable Diffusion XL
- `hunyuan`: HunyuanDiT

### 10.3.12 image-upscale

이미지 해상도를 향상시킵니다.

```yaml
component:
  type: model
  task: image-upscale
  architecture: real-esrgan
  model: RealESRGAN_x4plus
  action:
    image: ${input.image as image}
    params:
      scale: 4
```

**지원 아키텍처:**
- `real-esrgan`: Real-ESRGAN
- `esrgan`: ESRGAN
- `swinir`: SwinIR
- `ldsr`: Latent Diffusion Super Resolution

### 10.3.13 text-to-speech

텍스트에서 음성 오디오를 합성합니다. 이 태스크는 `driver: custom`과 `family` 필드로 모델 패밀리를 선택하고, 액션의 `method` 필드로 생성 방식을 선택합니다. 일곱 개의 패밀리가 지원됩니다: `qwen`, `kokoro`, `chatterbox`, `luxtts`, `tada`, `cosyvoice`, `fireredtts3`.

**사용 가능한 메서드:**

| 메서드 | 설명 |
|--------|------|
| `generate` | 프리셋 음성으로 합성, 선택적으로 스타일 제어 |
| `clone` | 참조 오디오 클립에서 음성 복제 |
| `design` | 자연어 설명으로 새로운 음성 생성 |
| `edit` | 기존 오디오 편집 (내용, 속도, 피치, 볼륨) |

모든 패밀리가 모든 메서드를 구현하지는 않습니다 — 아래 패밀리 섹션과 [레퍼런스 매트릭스](../reference/compose/components/model.md#text-to-speech)를 참고하세요.

**공통 액션 필드 (모든 패밀리):**

| 필드 | 타입 | 기본값 | 설명 |
|-------|------|---------|-------------|
| `method` | string | **필수** | 생성 방식: `generate`, `clone`, `design`, `edit` |
| `text` | string/array | **필수** | 합성할 텍스트 (또는 텍스트 리스트); `edit`에서는 무시됨 |
| `language` | string | `null` | 텍스트 언어; 언어 조건부 패밀리에서 사용 |
| `batch_size` | int | `1` | 배치당 처리할 입력 텍스트 수 |

#### 패밀리: `qwen`

Alibaba Qwen3-TTS. 세 가지 메서드 모두 사용 가능하며, 메서드에 맞는 체크포인트를 선택하세요.

권장 체크포인트:

| 모델 | 메서드 | 설명 |
|-------|--------|-------------|
| `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | `generate` | 스타일 제어가 가능한 내장 음성 |
| `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | `clone` | 참조 오디오에서 음성 복제 |
| `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | `design` | 텍스트 설명으로 음성 디자인 |

`generate` — 내장 음성을 선택하고 선택적으로 스타일 지시를 추가:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice | vivian}
    instructions: ${input.instructions | ""}
```

`clone` — 짧은 참조 클립에서 대상 음성을 재현:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-Base
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text as text}
```

`design` — 원하는 음성을 자연어로 설명:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: qwen
  model: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign
  device: cuda:0
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
```

지원 언어: 영어, 중국어, 일본어, 한국어, 독일어, 프랑스어, 러시아어, 포르투갈어, 스페인어, 이탈리아어 — `language`의 ISO 639-1 접두사(예: `ko`, `zh-CN`)로 결정됩니다.

#### 패밀리: `kokoro`

Kokoro TTS. 경량 프리셋 음성 합성; `generate` 전용.

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: kokoro
  model: hexgrad/Kokoro-82M
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice | af_heart}
    speed: ${input.speed | 1.0}
```

음성 ID는 Kokoro의 `<language><gender>_<name>` 규칙을 따릅니다 (예: `af_heart`, `af_bella`, `am_michael`, `bf_emma`). 지원 언어: 미국 영어, 영국 영어, 일본어, 표준 중국어, 스페인어, 프랑스어, 힌디어, 이탈리아어, 브라질 포르투갈어. 출력 샘플레이트: 24 kHz.

#### 패밀리: `chatterbox`

Resemble AI Chatterbox. 프리셋 합성과 zero-shot 클로닝, 표현력 제어 (`exaggeration`, `cfg_weight`, `temperature`) 지원.

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: chatterbox
  model: ResembleAI/chatterbox
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    exaggeration: 0.6
    cfg_weight: 0.5
    temperature: 0.8
```

프리셋 합성을 사용하려면 `method`를 `generate`로 바꾸고 `reference_audio`를 제거하세요. 권장 참조 길이: 5초 이상.

#### 패밀리: `luxtts`

LuxTTS. flow-matching 세밀 제어가 가능한 zero-shot 클로닝; `clone` 전용.

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: luxtts
  model: BeaverAI/luxtts-v1
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    num_steps: 4
    guidance_scale: 3.0
    speed: 1.0
```

`num_steps` (기본값 `4`)와 `guidance_scale` (기본값 `3.0`)로 품질과 속도를 조절하세요. 출력 샘플레이트: 48 kHz. CPU에서는 스레드 수가 자동으로 제한됩니다.

#### 패밀리: `tada`

Hume TADA. Zero-shot 클로닝; `clone` 전용. `reference_text`를 생략하면 TADA가 내장 ASR로 참조 클립을 전사합니다 — 영어 전용.

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: tada
  model:
    repository: HumeAI/tada-v0.1
    allow_patterns: ["*.safetensors", "*.json", "*.txt", "*.bin", "*.model"]
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text | ""}
```

토크나이저는 기본적으로 게이팅되지 않은 `unsloth/Llama-3.2-1B` 미러를 사용하며, 필요 시 컴포넌트 레벨의 `tokenizer` 필드로 오버라이드할 수 있습니다. 출력 샘플레이트: 24 kHz. Apple Silicon에서는 flow-matching 불안정성 때문에 MPS가 CPU로 폴백됩니다.

#### 패밀리: `cosyvoice`

FunAudioLLM CosyVoice / CosyVoice2 / CosyVoice3. AutoModel 팩토리가 모델 디렉토리 내 `cosyvoice{,2,3}.yaml`을 검사해 알맞은 버전을 선택합니다.

런타임이 첫 실행 시 상위 `cosyvoice`와 `matcha` 패키지를 GitHub에서 다운로드하여 설치합니다(고정 커밋). `git` CLI는 필요하지 않지만 첫 실행에는 시간이 걸릴 수 있습니다.

`generate` — `CosyVoice-300M-SFT`의 내장 스피커, 또는 v2/v3의 사전 등록된 zero-shot 스피커 사용:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/CosyVoice-300M-SFT
  device: cuda:0
  action:
    method: generate
    text: ${input.text as text}
    voice: ${input.voice}
```

`clone` — 전사가 있으면 zero-shot, 없으면 cross-lingual (어떤 언어의 참조라도 가능):

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/CosyVoice2-0.5B
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text | ""}
```

`design` — 지시문 기반 음성 디자인 (CosyVoice2/3 전용):

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: cosyvoice
  model: FunAudioLLM/CosyVoice2-0.5B
  device: cuda:0
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
    reference_audio: ${input.reference_audio as audio}
```

CUDA 전용 가속 플래그: `load_jit`, `load_trt`, `load_vllm`, `fp16`. CPU에서는 모두 조용히 무시됩니다.

#### 패밀리: `fireredtts3`

FireRedTeam FireRedTTS3. 두 개의 프리셋이 이 패밀리를 공유합니다:

- `preset: base` — 언어 조건 클로닝만 지원.
- `preset: instruct` — 클로닝, 음성 디자인, 오디오 편집 지원.

런타임이 첫 실행 시 상위 `fireredtts3` 패키지를 GitHub에서 다운로드하여 설치합니다 (고정 커밋).

`base` 프리셋에서 `clone`:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: fireredtts3
  preset: base
  model: FireRedTeam/FireRedTTS3
  device: cuda:0
  action:
    method: clone
    text: ${input.text as text}
    reference_audio: ${input.reference_audio as audio}
    reference_text: ${input.reference_text | ""}
    language: ${input.language | en}
```

`instruct` 프리셋에서 `design` — 대상 음성을 설명:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: fireredtts3
  preset: instruct
  model: FireRedTeam/FireRedTTS3-Instruct
  device: cuda:0
  action:
    method: design
    text: ${input.text as text}
    instructions: ${input.instructions as text}
```

`instruct` 프리셋에서 `edit` — `text` 필드는 무시되고 지시문만으로 오디오를 재작성:

```yaml
component:
  type: model
  task: text-to-speech
  driver: custom
  family: fireredtts3
  preset: instruct
  model: FireRedTeam/FireRedTTS3-Instruct
  device: cuda:0
  action:
    method: edit
    reference_audio: ${input.reference_audio as audio}
    instructions: ${input.instructions as text}
    mode: ${input.mode | semantic}
```

편집 모드: 자유 형식 내용 편집은 `semantic`, `adjust the speed to 1.2`같은 템플릿 지시는 `acoustic`. 출력 샘플레이트: 두 프리셋 모두 24 kHz. `base` 프리셋에서 `design`/`edit`을 호출하면 런타임 오류가 발생합니다.

### 10.3.14 speech-to-text

오디오를 텍스트로 전사하며, 선택적으로 세그먼트별 또는 단어별 타임스탬프를 함께 반환합니다. HuggingFace transformers 백엔드 (Whisper 계열)와 여러 `custom` 패밀리 (faster-whisper, crisper-whisper, fun-asr, vibevoice)를 지원합니다.

```yaml
component:
  id: transcriber
  type: model
  task: speech-to-text
  driver: custom
  family: faster-whisper
  model:
    provider: huggingface
    repository: Systran/faster-whisper-large-v3
  compute_type: float16
  action:
    audio: ${input.audio as audio}
    language: en
    return_timestamps: true
    timestamp_level: word
    output: ${result as json}
```

**공통 액션 필드:**

| 필드 | 타입 | 기본값 | 설명 |
|-------|------|---------|-------------|
| `audio` | audio | **필수** | 입력 오디오 파일, 오디오 리스트, 또는 async 스트림 |
| `language` | string | `null` | 언어 코드 (`en`, `ko`, ...); 지정하지 않으면 지원되는 경우 자동 감지 |
| `return_timestamps` | bool | `false` | 결과에 세그먼트별 타임스탬프 포함 |
| `timestamp_level` | string | `segment` | `segment` 또는 `word`; word 레벨은 백엔드 지원 필요 |
| `time_offset` | time / list | `null` | 각 세그먼트 타임스탬프에 더할 오프셋; 스칼라는 브로드캐스트, 리스트는 오디오별로 페어링 |
| `batch_size` | int | `1` | 배치당 처리할 오디오 수 |
| `streaming` | bool | `false` | 전사된 청크를 점진적으로 방출 |

패밀리별 액션 필드로는 `faster-whisper`와 HuggingFace `whisper` 드라이버의 Whisper 스타일 디코딩 파라미터 (`num_beams`, `temperature`, `no_speech_threshold`, ...), `crisper-whisper`의 스타일/핫워드 제어 (`mode`, `hotwords`, `longform_strategy`, ...), `vibevoice`의 샘플링/빔/컨텍스트 노브 (`temperature`, `top_p`, `num_beams`, `context_info`) 등이 있습니다. Fun-ASR은 컴포넌트에서 VAD와 문장부호를 구성합니다 (`voice_activity_detection`, `punctuation`).

플레인 텍스트 모드(기본값)는 입력당 문자열을 반환하고, 타임스탬프 모드는 `{ text, start_time, end_time }` 세그먼트 리스트를 반환합니다. `timestamp_level: word`이면 `words` 배열이 추가됩니다.

```json
[
  {
    "text": "Hello world",
    "start_time": 0.12,
    "end_time": 1.03,
    "words": [
      { "text": "Hello", "start_time": 0.12, "end_time": 0.44 },
      { "text": "world", "start_time": 0.46, "end_time": 1.03 }
    ]
  }
]
```

`streaming: true`이면 Whisper 계열 백엔드는 디코딩이 진행됨에 따라 토큰 레벨 청크를 스트리밍합니다 — `return_timestamps: false`이면 플레인 텍스트 청크, 타임스탬프가 켜져 있으면 `"type": "segment"`를 포함하는 세그먼트 딕셔너리를 방출합니다. VibeVoice 스트리밍 체크포인트는 청크별 전사 텍스트를 스트리밍하고, 오프라인 체크포인트는 수집된 세그먼트를 하나씩 재방출하거나 (각각 `"type": "segment"` 포함), 타임스탬프가 꺼져 있으면 전체 전사를 하나의 문자열 청크로 반환합니다.

#### 지원 패밀리

| 패밀리 | 백엔드 | 비고 |
|--------|---------|-------|
| `faster-whisper` | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | CTranslate2 Whisper 런타임; 빔 서치, VAD, 청크 롱폼 |
| `crisper-whisper` | [nyralabs/crisperwhisper](https://pypi.org/project/crisperwhisper/) | 단어 정밀 Whisper 변형. `ct2` 포크가 있으면 사용하고 없으면 `transformers`. 사이즈 축약어 (`large`, `turbo`, `medium`, `small`, `*_pro`)는 `nyralabs/CrisperWhisper2.0_<size>`로 해석됨 |
| `fun-asr` | [FunAudioLLM/FunASR](https://github.com/modelscope/FunASR) | 중국어 중심의 다국어 ASR. VAD와 문장부호 단계를 선택적으로 사용. 기본 모델: `FunAudioLLM/Fun-ASR-MLT-Nano-2512` |
| `vibevoice` | [microsoft/VibeVoice](https://github.com/microsoft/VibeVoice) | 스트리밍 및 오프라인 ASR 체크포인트. 기본값: `microsoft/VibeVoice-ASR-Streaming-1.5B`. 언어는 10개 언어에서 자동 감지 |

HuggingFace `whisper` 드라이버는 stock Whisper 체크포인트를 `transformers`로 실행합니다. transformers 생태계(LoRA 어댑터, 양자화)가 필요할 때 CT2 기반 `faster-whisper` 고속 경로 대신 사용하세요.

### 10.3.15 speaker-diarization

오디오 파일을 화자별로 세그먼트하고, 시작/종료 시각과 화자 라벨을 포함한 화자별 턴을 반환합니다. `pyannote.audio` 화자 다이어라이제이션 파이프라인을 실행합니다.

```yaml
component:
  id: diarizer
  type: model
  task: speaker-diarization
  driver: custom
  family: pyannote
  model:
    provider: huggingface
    repository: pyannote/speaker-diarization-3.1
    token: ${env.HUGGINGFACE_TOKEN}
  action:
    audio: ${input.audio as audio}
    min_speaker_count: 2
    max_speaker_count: 4
    params:
      min_segment_duration: 250ms
      merge_gap: 500ms
    output: ${result as json}
```

| 필드 | 타입 | 기본값 | 설명 |
|-------|------|---------|-------------|
| `audio` | audio | **필수** | 입력 오디오 파일, 오디오 리스트, 또는 async 스트림 |
| `speaker_count` | int | `null` | 정확한 화자 수를 알고 있을 때 지정 |
| `min_speaker_count` | int | `null` | 고려할 화자 수 하한 |
| `max_speaker_count` | int | `null` | 고려할 화자 수 상한 |
| `batch_size` | int | `1` | 배치당 처리할 오디오 수 |
| `streaming` | bool | `false` | 턴을 async iterator로 방출 (가짜 스트림: 파이프라인은 전체 오디오가 먼저 필요) |
| `params.min_segment_duration` | duration | `"0s"` | 이보다 짧은 턴은 제거 |
| `params.merge_gap` | duration | `"0s"` | 이 간격 이내의 인접 동일 화자 턴을 병합 |

Duration 필드는 `"250ms"`, `"0.5s"`, 또는 순수 숫자(초) 형식을 허용합니다.

결과 형태 (`start_time` 순으로 정렬된 `segments` 배열을 담은 오디오별 dict):

```json
{
  "segments": [
    { "speaker": "SPEAKER_00", "start_time": 0.48,  "end_time": 3.72,  "confidence": 1.0 },
    { "speaker": "SPEAKER_01", "start_time": 3.90,  "end_time": 7.16,  "confidence": 1.0 },
    { "speaker": "SPEAKER_00", "start_time": 7.44,  "end_time": 12.02, "confidence": 1.0 }
  ]
}
```

`confidence`는 `1.0`으로 보고됩니다 — pyannote는 턴별 신뢰도를 노출하지 않습니다. Pyannote 다이어라이제이션은 실제로 스트리밍이 불가능합니다: `streaming: true`이면 `AsyncIterator` 계약을 유지하기 위해 동일한 턴을 하나씩 재방출하며, 각 청크는 세그먼트 필드와 함께 `"type": "segment"`를 포함합니다.

기본 `pyannote/speaker-diarization-3.1` 체크포인트는 HuggingFace에서 게이팅되어 있습니다. 라이선스를 수락하고 `model.token`(또는 `${env.HUGGINGFACE_TOKEN}`)으로 액세스 토큰을 전달하세요.

#### 지원 패밀리

| 패밀리 | 백엔드 | 비고 |
|--------|---------|-------|
| `pyannote` | [pyannote/pyannote-audio](https://github.com/pyannote/pyannote-audio) | `pyannote.audio` 다이어라이제이션 파이프라인을 실행; HuggingFace 라이선스 수락 필요 |

### 10.3.16 voice-activity-detection

오디오 파일에서 음성 구간을 감지하고, 각 구간의 시작/종료 시각과 신뢰도를 반환합니다. 침묵 구간은 결과에서 제외됩니다. 주로 speech-to-text 전처리 단계로 사용되어 침묵 구간을 건너뛰고 환각을 줄이는 데 활용됩니다.

```yaml
component:
  type: model
  task: voice-activity-detection
  driver: custom
  family: silero
  device: cpu
  action:
    audio: ${input.audio as audio}
    sample_rate: 16000
    params:
      threshold: 0.5
      min_speech_duration: 250ms
      min_silence_duration: 500ms
      speech_padding_time: 100ms
```

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `sample_rate` | int | `16000` | 대상 샘플레이트 (16000 또는 8000); 필요 시 자동 리샘플링 |
| `threshold` | float | `0.5` | 음성 확률 임계값 (0.0 - 1.0); 높을수록 엄격 |
| `min_speech_duration` | duration | `250ms` | 이보다 짧은 음성 구간은 제거 |
| `min_silence_duration` | duration | `500ms` | 인접 구간을 분리하는 데 필요한 침묵 |
| `speech_padding_time` | duration | `100ms` | 감지된 각 구간 양쪽에 추가되는 패딩 |

Duration 필드는 `"250ms"`, `"0.5s"`, 또는 순수 숫자(초) 형식을 허용합니다.

결과 형식 (감지된 음성 구간 배열 `segments`를 담은 dict; 침묵 구간은 생략):

```json
{
  "segments": [
    { "start_time": 0.124, "end_time": 44.58,  "confidence": 0.916 },
    { "start_time": 47.07, "end_time": 150.02, "confidence": 0.937 }
  ]
}
```

`streaming: true`이면 입력별 결과가 async iterator로 반환되며, 음성 구간이 확정될 때마다 청크가 하나씩 방출됩니다. 각 청크는 segment 필드와 함께 `"type": "segment"`를 포함합니다.

#### 지원 패밀리

| 패밀리 | 백엔드 | 비고 |
|--------|---------|------|
| `silero` | [snakers4/silero-vad](https://github.com/snakers4/silero-vad) (pip) | 경량 CNN (~1MB); 모델이 pip 패키지에 번들됨 |

### 10.3.17 face-embedding

얼굴 이미지에서 특징 벡터를 추출합니다.

```yaml
component:
  type: model
  task: face-embedding
  model: buffalo_l
  action:
    image: ${input.image as image}
```

### 10.3.18 face-tracking

비디오 프레임 시퀀스에서 얼굴을 추적합니다. 프레임별 검출 결과를 얼굴 임베딩의 코사인 유사도로 아이덴티티 트랙에 그룹핑하고, 같은 아이덴티티의 연속 히트를 타임코드 세그먼트로 병합합니다. InsightFace를 사용합니다.

```yaml
component:
  type: model
  task: face-tracking
  driver: custom
  family: insightface
  model:
    provider: local
    path: ./.models/antelopev2
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    return_track_image: true
    params:
      similarity_threshold: 0.4
      min_frame_count: 2
      merge_gap: 1.0
```

단일 프레임 시퀀스, 시퀀스 리스트, 프레임 배치의 async 스트림을 모두 받으며 스트리밍 입력은 전체 비디오를 버퍼링하지 않고 지연 실행됩니다. 전체 옵션과 결과 스키마는 [Model Component 레퍼런스](../reference/compose/components/model.md#face-tracking)를 참고하세요.

### 10.3.19 pose-tracking

비디오 프레임 시퀀스에서 사람(자세)을 추적합니다. 프레임별 자세 검출을 트래커의 지속 `track_id`로 그룹핑하고, 연속된 히트를 타임코드 세그먼트로 병합합니다. Ultralytics YOLO-pose를 사용합니다.

```yaml
component:
  type: model
  task: pose-tracking
  driver: custom
  family: yolo
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    skeleton_format: openpose
    return_track_image: true
    params:
      min_confidence: 0.5
      min_frame_count: 3
      merge_gap: 0.5
```

face-tracking과 동일한 입력 형태를 받습니다. 전체 옵션, 스트리밍 청크 스키마, 결과 스키마는 [Model Component 레퍼런스](../reference/compose/components/model.md#pose-tracking)를 참고하세요.

### 10.3.20 object-tracking

비디오 프레임 시퀀스에서 객체를 추적합니다. 프레임별 검출을 트래커의 지속 `track_id`로 그룹핑하고, 연속된 히트를 타임코드 세그먼트로 병합하며 짧은 갭은 선택적으로 보간합니다. Ultralytics YOLO를 사용합니다.

```yaml
component:
  type: model
  task: object-tracking
  driver: custom
  family: yolo
  action:
    frames: ${input.frames}
    frame_rate: ${input.frame_rate}
    labels: [ person, car ]
    return_track_image: true
    params:
      min_confidence: 0.3
      min_frame_count: 3
      merge_gap: 0.5
      tracker: bytetrack
```

face-tracking과 동일한 입력 형태를 받습니다. 전체 옵션, 스트리밍 청크 스키마, 결과 스키마는 [Model Component 레퍼런스](../reference/compose/components/model.md#object-tracking)를 참고하세요.

### 10.3.21 object-detection

이미지에서 객체를 검출하고, 객체별로 바운딩 박스, 클래스 라벨, 신뢰도 점수를 반환합니다. Ultralytics YOLO를 사용합니다.

```yaml
component:
  type: model
  task: object-detection
  driver: custom
  family: yolo
  action:
    image: ${input.image as image}
    labels: [ person, dog ]      # 선택: 클래스 필터
    bounding_box_padding: 0.05   # 후속 크롭이나 SAM 프롬프트를 위해 박스를 5% 확장
    params:
      min_confidence: 0.4
```

Ultralytics YOLO 검출(또는 세그멘테이션) `.pt` 체크포인트 어느 것이나 사용할 수 있습니다. 전체 옵션과 결과 스키마는 [Model Component 레퍼런스](../reference/compose/components/model.md#object-detection)를 참고하세요.

### 10.3.22 image-segmentation

이미지에서 영역별 이진 세그멘테이션 마스크를 생성합니다. **자동 모드**(모든 뚜렷한 영역을 마스크)와 **박스 프롬프트 모드**(사용자가 제공한 바운딩 박스 주변을 정밀하게 세그멘트, 예: `object-detection` 출력)를 지원합니다. Meta의 Segment Anything Model(SAM)을 Ultralytics를 통해 사용합니다.

```yaml
component:
  type: model
  task: image-segmentation
  driver: custom
  family: sam
  action:
    image: ${input.image as image}
    box_prompt: ${input.box_prompt as json}   # 선택: 생략하면 자동 모드
    max_segment_count: 20
    params:
      min_confidence: 0.6
```

Ultralytics SAM 체크포인트(`sam_b.pt`, `sam2_b.pt`, `mobile_sam.pt` 등) 어느 것이나 사용할 수 있습니다. 전체 옵션과 결과 스키마는 [Model Component 레퍼런스](../reference/compose/components/model.md#image-segmentation)를 참고하세요.

### 10.3.23 text-to-video

텍스트 프롬프트에서 짧은 비디오 클립을 생성합니다. `driver: custom`을 사용하며 `family` 필드로 모델 패밀리를, `preset` 필드로 체크포인트 변형을 선택합니다.

```yaml
component:
  type: model
  task: text-to-video
  driver: custom
  family: wan
  preset: t2v-a14b
  model: Wan-AI/Wan2.2-T2V-A14B
  device: cuda:0
  action:
    prompt: ${input.prompt as text}
    negative_prompt: ${input.negative_prompt | ""}
    params:
      num_frames: 81
      fps: 24
      width: 1280
      height: 720
      inference_steps: 50
      guidance_scale: 5.0
```

**지원되는 패밀리와 프리셋:**
- `wan`
  - `t2v-a14b` — Wan2.2 T2V 27B (14B active); 약 80GB 이상의 VRAM 필요.
  - `ti2v-5b` — Wan2.2 하이브리드 텍스트/이미지→비디오 5B; 단일 24GB GPU (RTX 4090)에서 실행 가능.

결과는 단일 mp4 스트림(배치 프롬프트에는 mp4 스트림 리스트)입니다. 전체 옵션은 [Model Component 레퍼런스](../reference/compose/components/model.md#text-to-video)를 참고하세요.

### 10.3.24 image-to-video

입력 이미지를 애니메이션화한 짧은 비디오 클립을 생성하며, 선택적으로 텍스트 프롬프트로 유도할 수 있습니다.

```yaml
component:
  type: model
  task: image-to-video
  driver: custom
  family: wan
  preset: i2v-a14b
  model: Wan-AI/Wan2.2-I2V-A14B
  device: cuda:0
  action:
    image: ${input.image as image}
    prompt: ${input.prompt | ""}
    params:
      num_frames: 81
      fps: 24
      inference_steps: 40
      guidance_scale: 5.0
```

**지원되는 패밀리와 프리셋:**
- `wan`
  - `i2v-a14b` — Wan2.2 I2V 27B (14B active); 약 80GB 이상의 VRAM 필요.
  - `ti2v-5b` — Wan2.2 하이브리드 텍스트/이미지→비디오 5B; 단일 24GB GPU에서 실행 가능.

`width`/`height`는 선택 사항이며, 생략하면 입력 이미지의 크기를 사용합니다. 결과 형태는 `text-to-video`와 동일합니다 (입력당 mp4 스트림).

### 10.3.25 video-to-video

기존 비디오 클립을 변환합니다. 두 개의 드라이버 패밀리가 지원됩니다:

- **`huggingface` (AnimateDiff)** — 모션은 유지하면서 텍스트 프롬프트로 클립을 리스타일합니다. Stable Diffusion 1.5 체크포인트 위에 얹은 HuggingFace diffusers의 AnimateDiff 파이프라인 기반.
- **`custom` (Wan-Animate)** — 입력 클립의 포즈와 표정으로 참조 캐릭터를 구동합니다.

```yaml
# AnimateDiff — 모션을 유지하며 프롬프트로 리스타일
component:
  type: model
  task: video-to-video
  driver: huggingface
  architecture: animatediff
  model:
    provider: huggingface
    repository: SG161222/Realistic_Vision_V5.1_noVAE
  motion_adapter:
    provider: huggingface
    repository: guoyww/animatediff-motion-adapter-v1-5-3
  # 선택적 IP-Adapter — 액션 레벨의 `reference_image`로 외형을 유도할 수 있음.
  ip_adapter:
    provider: huggingface
    repository: h94/IP-Adapter
    filename: models/ip-adapter_sd15.bin
  device: cuda
  action:
    video: ${input.video as video}
    prompt: ${input.prompt}
    negative_prompt: ${input.negative_prompt | "bad quality, worst quality, low resolution"}
    reference_image: ${input.reference_image as image?}
    seed: ${input.seed as integer}
    params:
      num_frames: ${input.num_frames as integer}
      fps: ${input.fps as integer}
      inference_steps: ${input.inference_steps as integer | 25}
      guidance_scale: ${input.guidance_scale as number | 7.5}
      denoise_strength: ${input.denoise_strength as number | 0.5}
      ip_adapter_scale: ${input.ip_adapter_scale as number | 0.6}
```

```yaml
# Wan-Animate — 입력 클립의 모션으로 참조 캐릭터를 구동
component:
  type: model
  task: video-to-video
  driver: custom
  family: wan
  preset: animate-14b
  model: Wan-AI/Wan2.2-Animate-14B
  # 전처리 체크포인트 — 포즈 추출과 인물 검출은 항상 필수.
  pose2d_model: Wan-AI/Wan2.2-Animate-14B/process_checkpoint/pose2d/vitpose_h_wholebody.onnx
  det_model: Wan-AI/Wan2.2-Animate-14B/process_checkpoint/det/yolov10m.onnx
  # 선택 — 리플레이스먼트 모드와 이미지 편집 기반 포즈 리타게팅에만 필요.
  sam2_model: Wan-AI/Wan2.2-Animate-14B/process_checkpoint/sam2/sam2_hiera_large.pt
  flux_kontext_model: black-forest-labs/FLUX.1-Kontext-dev
  cpu_offload: false
  device: cuda:0
  action:
    video: ${input.driving_video as video}
    reference_image: ${input.reference_image as image}
    prompt: ${input.prompt | ""}
    params:
      clip_len: 77
      inference_steps: 20
      guidance_scale: 1.0
      resolution_width: 1280
      resolution_height: 720
      preprocess_fps: 30
```

**지원되는 패밀리 / 아키텍처:**

- `huggingface` → `animatediff` — Stable Diffusion 1.5 체크포인트 + AnimateDiff 모션 어댑터. 어떤 SD 1.5 파인튜닝이든 외형 백본으로 동작합니다.
- `custom` → `wan` (`animate-14b`) — Wan2.2 Animate 14B. CUDA가 필요합니다.

**AnimateDiff 참고:** `num_frames`/`fps`는 선택 사항입니다. 생략하면 모든 입력 프레임을 소비하고 출력은 소스 클립의 원본 fps를 상속하므로 입력의 재생 시간을 그대로 유지합니다. AnimateDiff는 약 16 프레임 윈도우로 학습되었기 때문에 매우 긴 클립에서는 품질이 떨어집니다 — 긴 입력은 업스트림에서 짧은 세그먼트로 나누고(예: `video-clipper`) 다운스트림에서 결과를 이어 붙이세요. `reference_image`를 제공하면 IP-Adapter가 색상/텍스처/피사체 단서를 전달합니다. `ip_adapter_scale`은 `0.5-0.7` 정도로 유지하세요.

**Wan-Animate 참고:** `reference_image`는 필수입니다 — 구동 클립에 맞춰 애니메이션되는 대상 캐릭터입니다. 드라이버는 메인 생성 단계 전에 Wan 전처리 파이프라인(포즈 추출, 인물 검출, 그리고 선택적으로 캐릭터 리플레이스먼트를 위한 SAM2와 포즈 리타게팅을 위한 FLUX.1-Kontext)을 실행하므로 해당 체크포인트를 컴포넌트에 선언해야 합니다. 캐릭터 리플레이스먼트에는 `params.replace_flag: true`(`sam2_model` 필요)를, 편집 기반 리타게팅에는 `params.use_flux: true`와 `params.retarget_flag: true`(`flux_kontext_model` 필요)를 설정하세요. `cpu_offload: true`는 처리량 대신 최대 VRAM을 줄입니다.

결과는 입력당 mp4 스트림(배치 입력에는 리스트)입니다. 전체 옵션은 [Model Component 레퍼런스](../reference/compose/components/model.md#video-to-video)를 참고하세요.

### 10.3.26 image-to-3d

단일 이미지에서 3D GLB 자산을 생성합니다. `family: pixal3d`는 sparse-structure / shape / texture flow-matching 단계를 체이닝해 PBR 맵이 구워진 메시를 만들어내고, `family: anigen`은 리그드 메시(뼈 + 스키닝 가중치가 표준 glTF skinned-mesh에 구워짐)와 별도 스켈레톤 시각화를 함께 생성합니다.

```yaml
component:
  type: model
  task: image-to-3d
  driver: custom
  family: pixal3d
  device: cuda
  model:
    provider: huggingface
    repository: TencentARC/Pixal3D
  low_vram: false
  action:
    image: ${input.image as image}
    seed: ${input.seed as integer}
    params:
      texture_size: 4096
      shape_slat_sampling_steps: 12
      tex_slat_sampling_steps: 12
```

AniGen의 경우 컴포넌트에서 SS-Flow / SLAT-Flow 변형을 선택하고 액션에서 어떤 결과를 받을지 토글합니다:

```yaml
component:
  type: model
  task: image-to-3d
  driver: custom
  family: anigen
  device: cuda
  model:
    provider: huggingface
    repository: VAST-AI/AniGen
  ss_variant: solo      # solo(기본, 정확한 지오메트리), epic, duet
  slat_variant: auto    # auto(기본, 네트워크가 관절 수 결정), control
  action:
    image: ${input.image as image}
    seed: ${input.seed as integer}
    return_mesh: true
    return_skeleton: true
    params:
      ss_steps: 25
      slat_steps: 25
      texture_size: 1024
```

**지원 패밀리와 프리셋:**
- `pixal3d` — Pixal3D 단일 이미지→텍스처 GLB. CUDA GPU 필요. 1536 해상도(기본)에서는 약 18 GB VRAM, `low_vram: true`와 1024 해상도에서는 약 10-12 GB.
- `anigen` — AniGen 단일 이미지→리그드 GLB + 스켈레톤 시각화. VRAM 18 GB 이상의 CUDA GPU 필요(Linux 전용, CUDA 11.8 또는 12.x).

Pixal3D의 경우 `low_vram: true`는 스테이지 모델을 CPU에 두고 필요할 때만 GPU로 옮겨 최대 VRAM을 지연 시간과 맞바꾸고, `manual_fov`(라디안)는 MoGe 기반 자동 FOV 추정을 대체합니다. AniGen의 경우 `slat_variant: control`은 `params.joints_density`(0-4)를 따르며, 기본 `auto`는 관절 수를 스스로 결정합니다. 출력 형태는 패밀리마다 다릅니다 — `pixal3d`는 입력당 하나의 `.glb` 스트림(`model/gltf-binary`)을 반환하고, `anigen`은 `mesh`와 `skeleton` GLB 스트림을 담은 dict를 입력당 하나씩 반환합니다(`return_image: true`이면 `image`도 포함). 전체 옵션은 [Model Component 레퍼런스](../reference/compose/components/model.md#image-to-3d)를 참고하세요.

### 10.3.27 shot-boundary-detection

비디오에서 샷 경계(하드 컷과 트랜지션)를 검출하고, 샷별 시작/종료 타임코드와 프레임 인덱스를 반환합니다. 딥러닝 모델을 사용하여 프레임 단위로 정확한 컷 지점을 식별합니다. `driver: custom`을 사용하며 `family` 필드로 모델 패밀리를 선택합니다.

```yaml
component:
  id: shot-detector
  type: model
  task: shot-boundary-detection
  driver: custom
  family: transnetv2
  model:
    provider: local
    path: ./models/transnetv2-weights
  max_concurrent_count: 1
  action:
    video: ${input.video as file}
    params:
      threshold: 0.5
    output: ${result as json}
```

| 필드 | 타입 | 기본값 | 설명 |
|-------|------|---------|-------------|
| `video` | video | **필수** | 입력 비디오 파일, 비디오 리스트, 또는 async 스트림 |
| `start_time` | time | `null` | 검출이 시작되는 소스 내 시각 (예: `00:01:00`, `60s`) |
| `end_time` | time | `null` | 검출이 종료되는 소스 내 시각 |
| `batch_size` | int | `1` | 배치당 처리할 비디오 수 |
| `streaming` | bool | `false` | 확정된 샷을 하나씩 방출 (입력별 스트림) |
| `params.threshold` | float | `0.5` | 프레임을 샷 경계로 간주할 신뢰도 임계값 (0.0 - 1.0); 높을수록 경계 수 감소 |

결과 형태 (`shots` 배열을 담은 비디오별 dict):

```json
{
  "shots": [
    {
      "index": 0,
      "start_time": "00:00:00.000",
      "end_time": "00:00:12.345",
      "start_frame": 0,
      "end_frame": 370,
      "duration": "00:00:12.345"
    },
    {
      "index": 1,
      "start_time": "00:00:12.345",
      "end_time": "00:00:28.678",
      "start_frame": 370,
      "end_frame": 860,
      "duration": "00:00:16.333"
    }
  ]
}
```

`streaming: true`이면 입력별 결과가 async iterator로 반환되며, 경계가 검출될 때마다 샷 청크가 하나씩 방출됩니다. 각 청크는 샷 필드와 함께 `"type": "shot"`을 포함합니다.

#### 지원 패밀리

| 패밀리 | 백엔드 | 비고 |
|--------|---------|-------|
| `transnetv2` | [soCzech/TransNetV2](https://github.com/soCzech/TransNetV2) | 딥러닝 샷 검출기; GPU 가속 (TensorFlow). `model.path`를 `saved_model.pb`와 `variables/`를 포함한 SavedModel 폴더로 지정 |

`video-scene-detector` 컴포넌트(PySceneDetect/FFmpeg의 고전적 CV 휴리스틱을 사용해 시맨틱적으로 유사한 프레임을 그룹핑)와 비교하면, `shot-boundary-detection`은 컷 지점 로컬라이제이션에 특화된 학습을 거친 신경망을 실행하므로 현대 편집 컨텐츠에서 일반적으로 더 정확합니다.

### 10.3.28 music-generation

음악 오디오를 생성하거나 편집합니다. 액션의 `method` 필드로 동작을 선택합니다 — 프롬프트로부터 새로 생성(MIDI 합성도 이 메서드를 사용), 기존 트랙을 새로운 스타일로 커버, 특정 구간 재생성, 뒤에 이어붙이기, 새 악기 레이어 추가, 보컬 전용 소스에 반주 만들기, 편집 가능한 ABC 스코어 계획. `driver: custom`을 사용하며 `family` 필드로 모델 계열을 선택합니다. ACE-Step은 `preset` 필드로 체크포인트 변형을 지정하고, YuE2는 `vae`, `backend`, `quantization`, `memory_budget_gib`, `cpu_offload`를 사용합니다.

```yaml
component:
  type: model
  task: music-generation
  driver: custom
  family: ace-step
  preset: acestep-v15-turbo
  model: /path/to/ace-step-checkpoints
  device: cuda:0
  action:
    method: generate
    prompt: ${input.prompt as text}
    lyrics: ${input.lyrics | ""}
    params:
      duration: 30
      bpm: 120
      key_scale: C
      time_signature: 4/4
      inference_steps: 8
      guidance_scale: 5.0
```

**지원되는 method:**

| Method | 목적 | 필수 필드(공통 필드 외) |
|--------|------|-------------------------|
| `generate` | 프롬프트로부터 새 음악 생성 | `prompt` (선택: `lyrics`, `reference_audio`) |
| `cover` | 기존 트랙을 새 스타일로 커버 | `source`, `prompt` (선택: `lyrics`) |
| `rewrite` | 특정 `[start_time, end_time]` 구간 재생성 | `source`, `start_time`, `end_time`, `prompt` (선택: `lyrics`) |
| `extend` | 소스를 자연스러운 끝 이후로 이어붙이기 | `source`, `prompt` (선택: `lyrics`) |
| `layer` | 소스 위에 새 악기/파트 레이어 추가 | `source`, `track_class` (선택: `prompt`, `lyrics`) |
| `accompany` | 보컬 전용 소스에 대한 반주 생성 (`ace-step` 전용) | `vocal`, `track_classes` (선택: `prompt`) |
| `score` | 오디오 렌더링 없이 편집 가능한 ABC 스코어 계획 (`yue2` 전용) | `style`, `lyrics` |

**지원되는 family와 preset:**
- `ace-step`
  - `acestep-v15-turbo` — 빠른 turbo 변형 (기본 `inference_steps: 8`).
  - `acestep-v15-base` — base 변형 (권장 `inference_steps: 32`).
  - `acestep-v15-sft` — SFT 변형 (권장 `inference_steps: 50`).
- `midi-ddsp`
  - 모노포닉 MIDI 파일을 특정 URMP 악기 음색(violin, viola, cello, double-bass, flute, oboe, clarinet, saxophone, bassoon, trumpet, horn, trombone, tuba)으로 합성합니다. `method: generate`에 `midi`와 `instrument` 필드를 사용합니다. 다성 MIDI는 거부됩니다.
- `yue2`
  - 편집 가능한 ABC 스코어 계획을 갖춘 완전한 곡 생성. `generate`는 `style` + `lyrics`로 작곡하고, `cover`는 제공된 ABC 스코어를 재해석하며, `score`는 계획된 ABC만 반환합니다. `params.cot_mode`가 chain-of-thought 스타일을 선택합니다(`full` — 코드 심볼 포함, `melody` — 커버용, `off` — 직접 생성). 48 kHz 스테레오 오디오를 렌더링합니다.

`ace-step`과 `midi-ddsp`는 HuggingFace Hub 식별자를 지원하지 않으며, `model`은 반드시 로컬 체크포인트 디렉토리여야 합니다. `yue2`는 HuggingFace 저장소 ID(예: `m-a-p/YuE2-3B`)와 로컬 경로 모두 허용합니다.

MIDI-DDSP는 TensorFlow 2.11을 고정 의존하며 호스트 mindor 스택과 함께 실행할 수 없기 때문에, 컴포넌트를 격리된 런타임(`virtualenv`, `docker`, `apple-container`)에서 실행해야 합니다. `native` / `embedded` / `process` 런타임은 로드 시점에 거부됩니다.

YuE2의 비양자화 프리셋은 BF16을 지원하는 CUDA GPU와 24 GB 이상 VRAM이 필요합니다. 더 작은 예산에 맞추려면 `quantization.type: fp8`, `cpu_offload: ar`, 그리고 더 작은 `vae.tile_size`를 지정하세요. macOS 15.1 미만에서는 MPS 백엔드가 VAE의 대형 Conv1d를 실행할 수 없으므로, `cpu_offload: vae`(또는 `cpu_offload: [ar, vae]`)로 디코더를 CPU에서 실행하세요. `backend: vllm`을 선택하면 모델의 `[fast]` 엑스트라(vLLM + Triton)가 자동으로 설치됩니다.

```yaml
component:
  type: model
  task: music-generation
  driver: custom
  family: midi-ddsp
  runtime:
    type: virtualenv
    driver: pyenv
    python: "3.10.14"
  model: /path/to/midi_ddsp_model_weights_urmp_9_10
  action:
    method: generate
    midi: ${input.midi}
    instrument: violin
```

```yaml
component:
  type: model
  task: music-generation
  driver: custom
  family: yue2
  model: m-a-p/YuE2-3B
  device: cuda
  action:
    method: generate
    style: ${input.style as text}
    lyrics: ${input.lyrics as text}
    params:
      cot_mode: full
```

오디오를 생성하는 메서드는 입력당 PCM 오디오 스트림(배치 입력에는 스트림 리스트)을 반환합니다. YuE2의 `score`는 대신 `{ abc, truncated }`를 반환합니다. 메서드별 전체 필드 목록은 [Model Component 레퍼런스](../reference/compose/components/model.md#music-generation)를 참고하세요.

### 10.3.29 music-source-separation

믹스된 녹음을 개별 악기 스템(보컬, 드럼, 베이스, 기타)으로 분리합니다. `driver: custom`을 사용하며 `family` 필드로 모델 백엔드를 선택합니다.

```yaml
component:
  type: model
  task: music-source-separation
  driver: custom
  family: demucs
  model: htdemucs_ft
  device: cpu   # htdemucs_ft는 MPS를 지원하지 않으므로 cpu 또는 cuda를 사용하세요
  action:
    audio: ${input.audio as audio}
    params:
      stems: [ vocals ]   # 생략하면 모델이 제공하는 모든 스템이 반환됩니다
      overlap: 0.25
      shifts: 1
```

**지원되는 family:**

| Family | 범위 | 비고 |
|--------|------|------|
| `demucs` | 4-스템(또는 6-스템) 분리 | Meta AI의 Hybrid Transformer Demucs. `htdemucs_ft`는 파인튜닝된 앙상블이며, `htdemucs_6s`는 `guitar`와 `piano` 스템을 추가로 제공합니다 |
| `mdx-net` | 보컬 분리 | ONNX Runtime 기반 UVR MDX-Net. 인스트루멘털 스템은 믹스에서 보컬을 뺀 결과로 파생됩니다 |
| `bs-roformer` | 구성 가능한 스템 분리 | lucidrains의 Band-Split RoFormer. 아키텍처만 제공하는 패키지이므로 `model`에 사전 학습된 `.ckpt`/`.safetensors` 체크포인트를 지정하고 `params`를 그 체크포인트에 맞춰 설정합니다 |
| `mel-band-roformer` | 구성 가능한 스템 분리 | BS-RoFormer의 mel-band 변형. mel 필터뱅크가 모델 생성 시점에 결정되므로 `params.sample_rate`가 체크포인트와 일치해야 합니다 |

스템 하나만 요청하면 액션이 단일 오디오 스트림을 반환합니다. 여러 스템을 요청하거나(예: `stems: [vocals, drums, bass, other]`), `stems`를 생략해 모델이 제공하는 모든 스템이 반환되는 경우에는 `{ "<stem_name>": <stream>, ... }` 형태의 맵을 반환합니다. `shifts`와 `overlap` 값을 높이면 실행 시간이 길어지는 대신 더 깨끗한 분리 결과를 얻을 수 있습니다.

`music-transcription`과 연결하면 각 스템을 개별 MIDI로 전사할 수 있고, 보컬 스템에 `speech-to-text`를 연결하면 더 깨끗한 가사 전사가 가능합니다. 전체 family별 필드 목록은 [Model Component 레퍼런스](../reference/compose/components/model.md#music-source-separation)를 참고하세요.

### 10.3.30 music-transcription

녹음된 오디오를 MIDI 파일과 노트 이벤트(시작 시간, 종료 시간, 음높이, 벨로시티) JSON 리스트로 전사합니다. `driver: custom`을 사용하며 `family` 필드로 모델 백엔드를 선택합니다.

```yaml
component:
  type: model
  task: music-transcription
  driver: custom
  family: basic-pitch
  device: auto
  action:
    audio: ${input.audio as audio}
    return_pitch_bends: false
    params:
      onset_threshold: 0.5
      frame_threshold: 0.3
      minimum_note_length: 58.0
```

**지원되는 family:**

| Family | 범위 | 비고 |
|--------|------|------|
| `basic-pitch` | 다성음, 악기 무관 | Spotify Basic Pitch (ICASSP-2022); ONNX로 CPU에서 실행; 체크포인트가 wheel에 포함되어 있음 |
| `piano-transcription` | 88건반 피아노 전용 | ByteDance Piano Transcription; 서스테인 페달 이벤트 검출; 최초 사용 시 약 180 MB 체크포인트 자동 다운로드 |

액션은 입력마다 두 개의 필드를 가진 딕셔너리를 반환합니다: `midi` (MIDI 파일)와 `notes` (초 단위 시간과 MIDI 노트 번호로 표현된 음높이를 담은 `{start_time, end_time, pitch, velocity}` 객체의 JSON 리스트). Basic Pitch는 `return_pitch_bends`가 활성화되면 노트별 `pitch_bends` 배열을 추가합니다. Piano Transcription은 페달 이벤트를 MIDI에 직접 기록합니다.

`music-source-separation`과 연결하면 믹스의 각 스템을 독립적으로 전사할 수 있습니다(예: 보컬 라인과 반주를 별도 파트로 전사). 전체 family별 필드 목록은 [Model Component 레퍼런스](../reference/compose/components/model.md#music-transcription)를 참고하세요.

### 10.3.31 music-beat-tracking

음악 녹음에서 비트와 다운비트 위치를 검출합니다. 각 비트는 마디 내에서의 위치를 함께 기록하므로 비트 동기화 편집, 템포/박자 분석, DJ 스타일 워핑, 구조 세그멘테이션 등에 활용할 수 있습니다. `driver: custom`을 사용하며 `family` 필드로 모델 백엔드를 선택합니다.

```yaml
component:
  type: model
  task: music-beat-tracking
  driver: custom
  family: beat-this
  device: auto
  model: final0
  dbn: false
  action:
    audio: ${input.audio as audio}
    return_metadata: true
```

**지원되는 family:**

| Family | 백엔드 | 비고 |
|--------|--------|------|
| `beat-this` | CPJKU Beat This! (ISMIR 2024) | 트랜스포머 기반 비트/다운비트 공동 추정기; 체크포인트는 HuggingFace에서 자동 다운로드; `dbn: true`로 madmom DBN 후처리 선택 가능 |

액션은 입력마다 `beats` 리스트를 담은 딕셔너리를 반환합니다. 각 이벤트는 `time`(초 단위), `is_downbeat`(마디 시작이면 `true`), `beat_number`(마디 내 위치 — 다운비트에서 `1`이 되고 이후 `2, 3, ...`로 이어짐; 첫 다운비트 이전의 pickup 비트는 `null`)를 포함합니다. `return_metadata: true`이면 `duration`도 함께 반환됩니다.

전체 family별 필드 목록은 [Model Component 레퍼런스](../reference/compose/components/model.md#music-beat-tracking)를 참고하세요.

### 10.3.32 talking-head

정지 초상화 이미지를 구동 오디오 클립에 맞춰 립싱크(그리고 머리 움직임)를 시킵니다. 기존 비디오의 입을 편집하는 `lip-sync`와 달리, `talking-head`는 단일 이미지로부터 머리 움직임과 표정을 합성합니다. `driver: custom`을 사용하며 `family` 필드로 모델 백엔드를 선택합니다.

```yaml
component:
  type: model
  task: talking-head
  driver: custom
  family: sadtalker
  preset: v0.0.2-256
  preprocessor: full
  model: vinthony/SadTalker
  device: cuda:0
  action:
    image: ${input.image as image}
    audio: ${input.audio as audio}
    params:
      still: true
      expression_scale: 1.0
      pose_style: 0
```

**지원되는 family:**

| Family | 프리셋 | 비고 |
|--------|---------|-------|
| `sadtalker` | `v0.0.2-256`, `v0.0.2-512` | 고전적 Audio2Coeff + 얼굴 렌더러; 256 프리셋은 약 6 GB VRAM, 512는 약 12 GB 필요. 참조 비디오 모션 전송과 수동 yaw/pitch/roll 키프레임 지원. |
| `hallo2` | (단일 빌드) | 확산 기반 초상화 애니메이터. 장시간 비디오를 위한 청크·블렌드 모드 제공. 신호별 가중치(pose/face/lip)와 선택적 내장 초해상도 지원. |
| `hallo3` | (단일 빌드) | 새로운 DiT 기반 초상화 비디오 생성기; 선택적 텍스트 프롬프트 수용. 추론 시간이 더 길지만 품질이 더 높음. |
| `sonic` | (단일 빌드) | LeonJoe13/Sonic. SVD-XT 백본과 whisper-tiny 오디오 임베딩 사용; 표현력 있는 머리 움직임 생성. |
| `echomimic` | `v1`, `v2` | AntGroup EchoMimic: v1은 초상화 프레이밍, v2는 상반신용이며 선택적 모션 싱크 참조 비디오 지원. |
| `float` | (단일 빌드) | 감정별 조건이 가능한 flow-matching 초상화 애니메이터; 확산 계열 옵션 중 가장 빠름. |

**주요 액션 필드** (패밀리별 상이 — 전체 목록은 레퍼런스 참고):

- `image`, `audio` — 필수 입력; 둘 다 단일 값, 리스트, 또는 스트림 가능.
- `params.fps` — 출력 프레임률 (기본값 25).
- `params.inference_steps` — 디노이징/flow-matching 스텝 수 (지원 패밀리).
- `params.cfg_scale`, `params.guidance_scale` — classifier-free guidance 제어.
- `params.still` (SadTalker), `params.crop` (Float) — 머리/몸을 정지시키고 입만 애니메이션.
- `params.enhancer` — 프레임별로 적용되는 선택적 얼굴 인핸서 (`gfpgan`, `RestoreFormer`) (SadTalker).
- `params.long_video` — 모델의 컨텍스트 윈도우보다 긴 오디오에 대한 윈도우·블렌드 활성화 (Hallo2, Hallo3).

결과는 mp4 스트림(배치 입력에는 스트림 리스트)이며, 각각 `format: "mp4"`와 요청한 프레임률에 맞는 `fps` 속성을 가집니다. 전체 패밀리별 필드 목록은 [Model Component 레퍼런스](../reference/compose/components/model.md#talking-head)를 참고하세요.

### 10.3.33 lip-sync

얼굴 비디오의 입 움직임을 구동 오디오 클립에 맞춰 재싱크합니다. 입 영역만 재생성되고 아이덴티티, 표정, 머리 자세, 배경은 원본 비디오에서 그대로 가져옵니다. `driver: custom`을 사용하며 `family` 필드로 모델 백엔드를 선택합니다.

```yaml
component:
  type: model
  task: lip-sync
  driver: custom
  family: wav2lip
  preset: wav2lip-gan
  device: cuda:0
  action:
    video: ${input.video as video}
    audio: ${input.audio as audio}
    params:
      face_bounding_box_padding: [0, 0, 0, 10]
      resize_factor: 1
      face_smoothing: true
```

**지원되는 family:**

| Family | 프리셋 | 비고 |
|--------|---------|-------|
| `wav2lip` | `wav2lip`, `wav2lip-gan` | 고전적 GAN 기반 립싱크; 최소 VRAM, 최고 속도. Easy-Wav2Lip 릴리스 미러에서 프리셋 체크포인트를 자동 다운로드. |
| `musetalk` | `v1`, `v15` | InsightFace + Whisper 프론트엔드를 갖춘 확산 잠재 VAE+UNet. Wav2Lip보다 높은 품질; v1.5는 파싱 기반 블렌딩 사용. `TMElyralab/MuseTalk` 자동 다운로드. |
| `latentsync` | `1.5`, `1.6` | ByteDance 확산 기반 립싱크; 512×512에서 가장 선명한 출력 (v1.6). v1.6은 약 12GB VRAM, v1.5는 약 6GB 필요. `ByteDance/LatentSync-<preset>` 자동 다운로드. |

**주요 액션 필드** (패밀리별 상이 — 전체 목록은 레퍼런스 테이블 참고):

- `video`, `audio` — 필수 입력; 둘 다 단일 값, 리스트, 또는 스트림 가능.
- `params.fps` — 출력 프레임률; 지정하지 않으면 소스 비디오의 프레임률을 사용.
- `params.face_bounding_box` — 얼굴 검출을 우회하는 LTRB 픽셀 튜플 (Wav2Lip). 소스 비디오의 자동 검출이 실패할 때 제공.
- `params.face_bounding_box_padding` — 검출된 얼굴 주변에 추가되는 LTRB 픽셀 패딩 (Wav2Lip). 클로즈업 샷에서 턱이 잘리는 것을 막으려면 `bottom`을 확장.
- `params.parsing_mode` — 블렌딩에 사용할 얼굴 파싱 영역: `jaw`, `neck`, `raw` (MuseTalk v1.5).
- `params.inference_steps`, `params.guidance_scale` — 확산 샘플링 제어 (LatentSync).
- `params.generator_batch_size` — UNet 추론 배치 (Wav2Lip, MuseTalk).
- `params.use_float16` — 메모리와 지연 시간을 줄이는 fp16 추론 (MuseTalk, LatentSync).

오디오가 비디오보다 길면 Wav2Lip과 MuseTalk는 소스 프레임을 루프하여 타임라인을 채웁니다 (MuseTalk는 ping-pong, Wav2Lip은 순방향 반복). LatentSync는 오디오 길이와 정확히 일치하는 결과를 생성하고 소스 비디오를 맞춰 잘라냅니다.

결과는 mp4 스트림(배치 입력에는 스트림 리스트)이며, 각각 `format: "mp4"`와 출력 프레임률에 맞는 `fps` 속성을 가집니다. 전체 패밀리별 필드 목록은 [Model Component 레퍼런스](../reference/compose/components/model.md#lip-sync)를 참고하세요.

---

## 10.4 모델 설정 (디바이스, 정밀도, 배치 크기)

### 디바이스 설정

```yaml
component:
  type: model
  task: text-generation
  model: gpt2
  device: cuda         # 'cuda', 'cpu', 'mps' (Apple Silicon)
  device_mode: single  # 'single', 'auto' (multi-GPU)
```

**디바이스 옵션:**
- `cuda`: NVIDIA GPU
- `cpu`: CPU만 사용
- `mps`: Apple Silicon GPU (M1/M2/M3)

**디바이스 모드:**
- `single`: 단일 GPU 사용
- `auto`: 여러 GPU에 자동 분산

다중 GPU 예제:
```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  device: cuda
  device_mode: auto  # 자동으로 여러 GPU에 모델 분산
```

### 정밀도 설정

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  precision: float16  # 'auto', 'float32', 'float16', 'bfloat16'
```

**정밀도 옵션:**
- `auto`: 자동 선택 (GPU는 float16, CPU는 float32)
- `float32`: 최고 정확도, 가장 많은 메모리 사용
- `float16`: 절반 메모리, 빠른 추론 (CUDA)
- `bfloat16`: float16 대안, 더 안정적 (최신 GPU)

정밀도 비교:

| 정밀도 | 메모리 | 속도 | 정확도 | 권장 사용 |
|--------|--------|------|--------|-----------|
| float32 | 100% | 기준 | 최고 | CPU, 높은 정확도 필요 시 |
| float16 | 50% | 2배 빠름 | 약간 감소 | CUDA GPU |
| bfloat16 | 50% | 2배 빠름 | float16보다 안정 | 최신 GPU (A100, H100) |

### 양자화

메모리를 더 줄이고 속도를 높이기 위한 양자화:

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  quantization: int8  # 'int8', 'int4', 'fp4', 'nf4' (양자화하지 않으려면 생략)
```

**양자화 옵션:**
- (`quantization:` 생략): 양자화 없음 (기본값)
- `int8`: 8비트 정수 (bitsandbytes 필요)
- `int4`: 4비트 정수 (bitsandbytes 필요)
- `fp4`: 4비트 부동소수점 (bitsandbytes 필요)
- `nf4`: 4비트 NormalFloat (QLoRA용)

`quantization`을 상세 설정으로 확장할 수도 있습니다:

```yaml
quantization:
  type: nf4
  compute_dtype: bfloat16
  double_quant: true
```

### 배치 크기

```yaml
component:
  type: model
  task: text-classification
  model: distilbert-base-uncased
  action:
    batch_size: 32  # 한 번에 처리할 입력 수
```

배치 크기 선택 가이드:
- **작은 배치 (1-8)**: 낮은 레이턴시, 실시간 추론
- **중간 배치 (16-32)**: 균형잡힌 처리량/레이턴시
- **큰 배치 (64+)**: 최대 처리량, 배치 처리

### 저메모리 로딩

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  low_cpu_mem_usage: true  # CPU RAM 사용 최소화
  device: cuda
```

---

## 10.5 LoRA/PEFT 어댑터 사용

LoRA (Low-Rank Adaptation)는 전체 모델을 파인튜닝하지 않고 작은 어댑터 모듈을 추가하여 모델을 특정 태스크에 맞게 조정하는 기법입니다.

### LoRA 어댑터 적용

```yaml
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-7b-hf
  peft_adapters:
    - type: lora
      name: alpaca
      model: tloen/alpaca-lora-7b
      weight: 1.0
  action:
    prompt: ${input.prompt as text}
```

### 다중 LoRA 어댑터

여러 LoRA 어댑터를 동시에 적용할 수 있습니다:

```yaml
component:
  type: model
  task: text-generation
  model:
    provider: huggingface
    repository: meta-llama/Llama-2-7b-hf
    token: ${env.HUGGINGFACE_TOKEN}
  peft_adapters:
    - type: lora
      name: alpaca
      model: tloen/alpaca-lora-7b
      weight: 0.7
    - type: lora
      name: assistant
      model: plncmm/guanaco-lora-7b
      weight: 0.8
  action:
    prompt: ${input.prompt as text}
```

### 어댑터 가중치

`weight` 파라미터로 어댑터의 영향력을 조절합니다:

```yaml
peft_adapters:
  - type: lora
    name: style-adapter
    model: user/style-lora
    weight: 0.5  # 50% 영향력
```

- `weight: 0.0`: 어댑터 비활성화
- `weight: 0.5`: 50% 적용
- `weight: 1.0`: 100% 적용 (기본값)

### 로컬 LoRA 어댑터

로컬 파일 시스템의 어댑터 사용:

```yaml
peft_adapters:
  - type: lora
    name: custom-lora
    model:
      provider: local
      path: /path/to/lora/adapter
    weight: 1.0
```

### LoRA 사용 사례

**1. 도메인 적응**
```yaml
# 의료 도메인에 특화된 모델
peft_adapters:
  - type: lora
    name: medical
    model: medalpaca/medalpaca-lora-7b
    weight: 1.0
```

**2. 스타일 제어**
```yaml
# 여러 작문 스타일 조합
peft_adapters:
  - type: lora
    name: formal
    model: user/formal-writing-lora
    weight: 0.6
  - type: lora
    name: technical
    model: user/technical-lora
    weight: 0.4
```

**3. 다국어 지원**
```yaml
# 한국어 지원 강화
peft_adapters:
  - type: lora
    name: korean
    model: beomi/llama-2-ko-7b-lora
    weight: 1.0
```

---

## 10.6 모델 서빙 프레임워크

대규모 프로덕션 환경이나 고성능 추론이 필요한 경우, 전용 모델 서빙 프레임워크를 사용할 수 있습니다.

> **중요:** vLLM, Ollama 등의 모델 서빙 프레임워크는 로컬 모델을 사용하지만, `model` 컴포넌트가 아닌 `http-server`나 `http-client` 컴포넌트를 통해 HTTP API로 접근합니다. 이는 별도의 서버 프로세스가 모델을 로드하고 서빙하기 때문입니다.

### vLLM

vLLM은 대규모 언어 모델을 위한 고성능 추론 엔진입니다.

#### vLLM 특징

- **PagedAttention**: 메모리 효율적인 어텐션 메커니즘
- **연속 배칭**: 높은 처리량
- **빠른 추론**: 최적화된 CUDA 커널
- **OpenAI 호환 API**: 기존 코드와 쉽게 통합

#### vLLM 설정 예제

```yaml
component:
  type: http-server
  manage:
    install:
      - bash
      - -c
      - |
        eval "$(pyenv init -)" &&
        (pyenv activate vllm 2>/dev/null || pyenv virtualenv $(python --version | cut -d' ' -f2) vllm) &&
        pyenv activate vllm &&
        pip install vllm
    start:
      - bash
      - -c
      - |
        eval "$(pyenv init -)" &&
        pyenv activate vllm &&
        python -m vllm.entrypoints.openai.api_server
          --model Qwen/Qwen2-7B-Instruct
          --port 8000
          --served-model-name qwen2-7b-instruct
          --max-model-len 2048
  port: 8000
  action:
    method: POST
    path: /v1/chat/completions
    headers:
      Content-Type: application/json
    body:
      model: qwen2-7b-instruct
      messages:
        - role: user
          content: ${input.prompt as text}
      max_tokens: 512
      temperature: ${input.temperature as number | 0.7}
      stream: true
    stream_format: json
    output: ${response[].choices[0].delta.content}
```

#### vLLM 파라미터

**서버 파라미터:**
- `--model`: 모델 이름 또는 경로
- `--port`: 서버 포트
- `--host`: 바인드 호스트
- `--served-model-name`: API에서 사용할 모델 이름
- `--max-model-len`: 최대 시퀀스 길이
- `--tensor-parallel-size`: Tensor parallelism (다중 GPU)
- `--dtype`: 데이터 타입 (auto, float16, bfloat16)

**추론 파라미터:**
- `max_tokens`: 최대 생성 토큰 수
- `temperature`: 생성 랜덤성
- `top_p`: Nucleus sampling
- `streaming`: 스트리밍 응답 여부

### Ollama

Ollama는 로컬에서 대형 언어 모델을 실행하기 위한 간단한 도구입니다.

#### Ollama 특징

- **간편한 설치**: 원클릭 설치
- **모델 라이브러리**: 사전 최적화된 모델 제공
- **낮은 진입장벽**: 복잡한 설정 불필요
- **REST API**: 간단한 HTTP 인터페이스

#### Ollama 자동 관리 (http-server 컴포넌트)

model-compose가 Ollama를 자동으로 설치하고 실행하는 경우:

```yaml
component:
  type: http-server
  manage:
    install:
      - bash
      - -c
      - |
        # macOS/Linux
        curl -fsSL https://ollama.ai/install.sh | sh
        # 모델 다운로드
        ollama pull llama2
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/generate
  headers:
    Content-Type: application/json
  body:
    model: llama2
    prompt: ${input.prompt as text}
    stream: false
  output:
    response: ${response.response}
```

**스트리밍 예제:**

```yaml
component:
  type: http-server
  manage:
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/generate
  body:
    model: llama2
    prompt: ${input.prompt as text}
    stream: true
  stream_format: json
  output: ${response[].response}
```

**채팅 API:**

```yaml
component:
  type: http-server
  manage:
    start: [ ollama, serve ]
  port: 11434
  method: POST
  path: /api/chat
  body:
    model: llama2
    messages: ${input.messages}
  output:
    message: ${response.message.content}
```

#### 기존 Ollama 서버 사용 (http-client)

이미 실행 중인 Ollama 서버가 있는 경우:

```yaml
component:
  type: http-client
  endpoint: http://localhost:11434/api/generate
  method: POST
  body:
    model: llama2
    prompt: ${input.prompt as text}
  output:
    response: ${response.response}
```

### TGI (Text Generation Inference)

HuggingFace의 프로덕션 레벨 추론 서버입니다.

```yaml
component:
  type: http-client
  endpoint: http://localhost:8080/generate
  method: POST
  headers:
    Content-Type: application/json
  body:
    inputs: ${input.prompt as text}
    parameters:
      max_new_tokens: 512
      temperature: 0.7
      top_p: 0.9
  output:
    generated_text: ${response.generated_text}
```

### 프레임워크 비교

| 프레임워크 | 장점 | 단점 | 권장 사용 |
|-----------|------|------|-----------|
| **vLLM** | 최고 성능, 높은 처리량 | 설정 복잡도, CUDA 전용 | 프로덕션, 대규모 서비스 |
| **Ollama** | 간편한 설치, 낮은 진입장벽 | 제한적인 모델, 제한적인 제어 | 개발, 프로토타입, 개인 사용 |
| **TGI** | HuggingFace 통합, 안정성 | vLLM보다 느림 | HuggingFace 생태계 사용 시 |
| **transformers** | 최대 호환성, 커스터마이징 | 낮은 성능 | 연구, 실험, 커스텀 모델 |

---

## 10.7 성능 최적화 팁

### 1. 적절한 정밀도 선택

```yaml
# GPU가 있는 경우
component:
  type: model
  model: large-model
  precision: float16  # 또는 bfloat16 (최신 GPU)
  device: cuda

# CPU만 있는 경우
component:
  type: model
  model: small-model
  precision: float32  # CPU는 float32가 더 안정적
  device: cpu
```

### 2. 양자화 활용

```yaml
# 메모리가 제한적인 경우
component:
  type: model
  model: meta-llama/Llama-2-13b-hf
  quantization: int8  # 메모리 사용량 약 50% 감소
  device: cuda
```

### 3. 적절한 배치 크기

```yaml
# 처리량 최적화
component:
  type: model
  task: text-classification
  model: bert-base
  action:
    batch_size: 32  # GPU 메모리에 맞게 조정
```

### 4. 모델 캐싱

```yaml
# 모델 재사용을 위한 캐싱
component:
  type: model
  model:
    provider: huggingface
    repository: gpt2
    cache_dir: /data/model-cache  # 고속 SSD 사용
```

### 5. 다중 GPU 활용

```yaml
# 모델 병렬화
component:
  type: model
  task: text-generation
  model: meta-llama/Llama-2-70b-hf
  device: cuda
  device_mode: auto  # 자동으로 여러 GPU에 분산
```

### 일반적인 성능 문제와 해결책

| 문제 | 원인 | 해결책 |
|------|------|--------|
| 느린 첫 실행 | 모델 다운로드, 컴파일 | 모델 사전 다운로드, 워밍업 |
| OOM (Out of Memory) | 모델이 GPU 메모리보다 큼 | 양자화, 정밀도 낮추기, 작은 배치 |
| 낮은 처리량 | 작은 배치 크기 | 배치 크기 증가 |
| 높은 레이턴시 | 큰 배치 크기 | 배치 크기 감소, 실시간 처리 |
| 불안정한 출력 | float16 정밀도 문제 | bfloat16 또는 float32 사용 |

---

## 다음 단계

실습해보세요:
- HuggingFace Hub에서 다양한 모델 테스트
- 양자화 및 정밀도 설정 실험
- LoRA 어댑터 로드 및 병합
- 배치 처리로 처리량 최적화

---

**다음 장**: [11. 모델 훈련](./11-model-training.md)
