# 음악 생성 (YuE2) 모델 태스크 예제

이 예제는 YuE2를 사용해 로컬에서 완결된 곡을 생성하는 방법을 보여주며, model-compose의 내장 모델 태스크 기능을 통해 실행됩니다. YuE2는 심볼릭 스코어 계획(ABC)과 음향 합성을 결합하여, 곡을 처음부터 새로 만들거나 편집 가능한 스코어로부터 생성하거나 오디오 없이 계획만 내보낼 수 있습니다.

## 개요

이 예제는 하나의 YuE2 컴포넌트를 대상으로 세 가지 워크플로우를 노출합니다:

1. **generate** — 스타일 설명과 가사로부터 새 곡 작곡
2. **cover** — 제공된 ABC 스코어를 새로운 스타일로 재해석 (제로샷 커버에는 보통 멜로디만 사용)
3. **score** — 오디오 렌더링 없이 편집 가능한 ABC 스코어만 계획

각 워크플로우는 YuE2의 심볼릭 chain-of-thought를 사용합니다: `cot_mode: full`은 멜로디와 코드 심볼을 모두 작성하고, `melody`는 멜로디만 있는 계획을 작성하며(커버에 권장), `off`는 스코어를 건너뛰고 가사와 스타일에서 바로 생성합니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- **BF16을 지원하는 NVIDIA GPU와 24 GB VRAM** (YuE2는 양자화 없이 48 kHz 스테레오 오디오를 렌더링합니다)
- Python 3.12 환경 (`yue2-infer` 휠과 고정된 `torch==2.10.0`은 첫 실행 시 자동 설치됩니다)
- AR 모델과 VAE 디코더용 ~15 GB 디스크 공간 (첫 사용 시 Hugging Face에서 다운로드)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/music-generation-yue2
   ```

2. 추가 환경 구성은 필요하지 않습니다 — 모델과 종속성이 자동으로 관리됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **"generate" 워크플로우 실행 (기본):**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "style": "English, piano-pop, warm lead vocal, tasteful strings",
         "lyrics": "[Verse]\nMorning light on empty streets\n[Chorus]\nWe are the ones who wait"
       }
     }'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - *Generate*, *Cover*, *Score* 탭 사이를 전환
   - 스타일 설명과 가사를 입력한 후 "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   model-compose run generate --input '{"style": "English, piano-pop", "lyrics": "..."}'
   ```

3. **기존 스코어로 커버 생성:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs/cover \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "style": "English, jazz-funk, warm lead vocal, Rhodes, bass and drums",
         "lyrics": "...새 가사...",
         "abc": "X:1\nT:Sample\nM:4/4\nK:C\n..."
       }
     }'
   ```

4. **스코어만 내보내기 (오디오 없음):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs/score \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "style": "Mandarin, city-pop, mid tempo",
         "lyrics": "..."
       }
     }'
   ```
   후속 편집을 위해 `{ "abc": "...", "truncated": false }`를 반환합니다.

## 컴포넌트 상세

### YuE2 음악 생성 컴포넌트
- **타입**: `music-generation` 태스크의 Model 컴포넌트
- **드라이버 / 패밀리**: `custom` / `yue2`
- **모델**: `m-a-p/YuE2-3B` (자기회귀 모델) + `m-a-p/YuE2-Vae` (디코더, 자동 다운로드)
- **디바이스**: `cuda`
- **출력 형식**: 48 kHz 스테레오 오디오 (`generate`, `cover`) 또는 `{ abc, truncated }` (`score`)
- **동시성**: 1 (한 번에 하나의 요청)

### 모델 정보: YuE2
- **개발자**: M·A·P와 협력 기관 (자세한 내용은 [YuE2 프로젝트 페이지](https://map-yue2.github.io/) 참조)
- **타입**: 플로우 매칭 음향 합성과 VAE 디코딩이 결합된 AR–NAR Mixture-of-Transformers
- **Chain-of-thought 모드**: `full` (코드 포함 스코어, 기본), `melody` (커버에 최적), `off` (직접 생성)
- **백엔드**: `torch` (기본), `torch-eager`, `vllm` (모델의 선택적 `[fast]` extras 필요)
- **양자화**: AR 모델용 선택적 `fp8` — 약간의 품질 저하로 AR VRAM 절반 절약

## 워크플로우 상세

### "Generate" 워크플로우 (기본)

**설명**: 스타일 설명과 가사로부터 새 곡을 작곡합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `style` | text | 예 | - | 스타일, 장르, 분위기, 악기 설명 |
| `lyrics` | text | 예 | - | 선택적 구조 태그(예: `[Verse]`, `[Chorus]`)를 포함한 가사 |
| `cot_mode` | text | 아니오 | `full` | `full` (스코어 + 코드), `melody` (멜로디만), `off` (직접) |
| `cfg_scale` | number | 아니오 | 모델 기본값 | `[0, 20]` 범위의 classifier-free guidance 스케일 |
| `seed` | integer | 아니오 | `831001` | 재현성을 위한 랜덤 시드 |

#### 출력 형식

| 필드 | 타입 | 설명 |
|------|------|------|
| - | audio | 생성된 곡 (48 kHz 스테레오 WAV) |

### "Cover" 워크플로우

**설명**: 제공된 ABC 스코어를 새로운 스타일로 재해석합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `style` | text | 예 | - | 목표 커버 스타일 |
| `lyrics` | text | 예 | - | 커버할 스코어 위에 부를 가사 |
| `abc` | text | 예 | - | 커버를 조건화하는 ABC 스코어 (보통 코드 심볼 없는 멜로디 전사) |
| `cot_mode` | text | 아니오 | `melody` | 커버에는 `melody` 사용; ABC에 코드가 포함되어 있으면 `full` |
| `seed` | integer | 아니오 | `831001` | 랜덤 시드 |

#### 출력 형식

| 필드 | 타입 | 설명 |
|------|------|------|
| - | audio | 커버 녹음 (48 kHz 스테레오 WAV) |

### "Score" 워크플로우

**설명**: 오디오 렌더링 없이 편집 가능한 ABC 스코어만 계획합니다.

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `style` | text | 예 | - | 스코어를 계획할 때 사용하는 스타일 설명 |
| `lyrics` | text | 예 | - | 계획을 형성하는 가사 |
| `cot_mode` | text | 아니오 | `full` | `full` (코드 심볼 포함) 또는 `melody` (멜로디만) |
| `seed` | integer | 아니오 | `831001` | 랜덤 시드 |

#### 출력 형식

| 필드 | 타입 | 설명 |
|------|------|------|
| `abc` | text | 계획된 곡의 편집 가능한 ABC 표기 |
| `truncated` | boolean | 계획이 토큰 예산에 도달했는지 여부 |

## 시스템 요구사항

### 최소 요구사항
- **GPU**: **BF16 지원과 24 GB VRAM**을 갖춘 NVIDIA GPU (비양자화 프리셋)
- **RAM**: 32 GB 권장
- **디스크 공간**: AR 모델과 VAE 디코더용 15 GB+
- **인터넷**: 초기 Hugging Face 다운로드에만 필요

### 성능 참고사항
- 첫 실행 시 Hugging Face에서 모델 가중치 다운로드 (~15 GB)
- 비양자화 프리셋은 24 GB VRAM 필요; 더 작은 GPU에는 `quantization.type: fp8`와 `offload_ar: true` 사용
- VRAM 소진 방지를 위해 컴포넌트당 단일 동시 요청

## 커스터마이징

### VRAM 사용량 줄이기
```yaml
component:
  quantization:
    type: fp8       # AR 메모리 절반 절약
  offload_ar: true  # NAR 합성 중 AR 모델을 CPU로 이동
  memory_budget_gib: 16
  vae:
    tile_size: 512
```

### vLLM 백엔드 사용
```yaml
component:
  backend: vllm
  # `pip install "yue2-infer[fast]"` 필요 (vllm/triton 설치)
```

### 샘플링 조정
```yaml
component:
  actions:
    - method: generate
      style: ${input.style as text}
      lyrics: ${input.lyrics as text}
      params:
        cfg_scale: 1.5
        abc_sampling:
          temperature: 0.7
          top_p: 0.9
        semantic_sampling:
          temperature: 1.0
          top_p: 0.95
          repetition_penalty: 1.2
```

## 관련 예제

- **[music-generation](../music-generation/)**: ACE-Step 1.5를 사용한 로컬 음악 생성
- **[music-source-separation](../music-source-separation/)**: 믹싱된 녹음을 스템으로 분리
- **[music-transcription](../music-transcription/)**: 녹음을 악보로 전사
