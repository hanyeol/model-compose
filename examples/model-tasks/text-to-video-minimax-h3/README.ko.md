# 텍스트-투-비디오 모델 태스크 예제 (MiniMax-H3)

이 예제는 MiniMax-H3 Omni-Transformer를 사용해 텍스트 프롬프트에서 네이티브 스테레오 오디오가 포함된 짧은 클립을 생성하는 방법을 보여줍니다. model-compose의 내장 text-to-video 태스크로 노출됩니다.

## 개요

MiniMax-H3는 텍스트 조건, 오디오 트랙, 타겟 비디오 프레임을 하나의 시퀀스로 패킹하고 그 시퀀스 위에서 full self-attention을 돌려 **비디오 + 오디오**를 한 번의 파이프라인 호출로 생성합니다. 이 예제는 이를 로컬 선언형 워크플로로 구성합니다:

1. **로컬 디퓨전 파이프라인**: HuggingFace diffusers `MiniMaxH3ModularPipeline`을 end-to-end 실행 — 외부 API 없음.
2. **비디오 + 오디오 공동 생성**: 매 생성은 24 fps 비디오와 32 kHz 스테레오 오디오를 반환하며, 두 트랙은 하나의 mp4로 먹싱됩니다.
3. **선택적 Sol-Attn 가속**: NVIDIA Blackwell 컨슈머 GPU(SM120)에서 `sol_attn`을 활성화하면 메인 트랜스포머 블록이 Sol-Attn의 컴파일된 `flex_attention` 커널로 라우팅되어 긴 패킹된 시퀀스에서 SDPA보다 빠르면서 품질을 위해 마지막 디노이징 스텝은 dense로 유지합니다.

## 준비

### 필수 요건

- model-compose가 설치되고 PATH에서 사용 가능할 것.
- CUDA 지원 GPU. Omni-Transformer는 ~33B 파라미터이므로 단일 컨슈머 GPU에서는 예제에 설정된 `cpu_offload: true`가 필요합니다. H100 급은 offload 없이 실행 가능.
- 체크포인트용 디스크 공간 (베이스 트랜스포머, Qwen3-VL 텍스트 인코더, VAE, 오디오 VAE 합쳐 ~70 GB).
- `torch`, `diffusers (>= 0.36)`, `transformers (>= 4.45)`, `av`를 설치할 수 있는 Python 환경 — 첫 실행 시 자동 설치됩니다.
- (선택) Sol-Attn 사용 시 compute capability 12.0을 보고하는 NVIDIA Blackwell 컨슈머 GPU (RTX 5090 / RTX PRO 6000). `sol_attn`이 활성화되면 예제가 자동으로 `mindor-sol-attn-blackwell` 커널 패키지를 설치하며, 다른 GPU는 투명하게 dense attention으로 라우팅됩니다.

### 모델 접근

MiniMax-H3 가중치는 Hugging Face의 `MiniMaxAI/MiniMax-H3`에 있으며 MiniMax H3 Community License로 게이트됩니다. 모델의 Hugging Face 페이지에서 라이선스에 동의하고 서비스 시작 전에 `hf auth login`을 실행하거나 `HF_TOKEN`을 export하세요.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 최초 시작 시 Hugging Face에서 체크포인트를 다운로드합니다 (~70 GB). 초기 설정은 오래 걸리며, 이후 실행에서는 캐시된 샤드를 재사용합니다.

2. **워크플로 실행:**
   ```bash
   # 최소 호출 — 기본값으로 짧은 영화적 클립 생성.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "a quiet alleyway at dusk, warm neon reflections on wet pavement, slow dolly in"}}'

   # 시드 고정 및 더 긴 클립 요청.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "waves crashing on a rocky coast, overcast sky, slow-motion spray", "num_frames": 240, "seed": 42}}'
   ```

3. **웹 UI 열기:**
   `http://localhost:8081`에서 Gradio 폼으로 동일 워크플로를 실행할 수 있습니다.

## Attention 백엔드 전환

예제는 component의 `backend: torch`가 기본이며, 이는 attention을 diffusers의 표준 SDPA / FlashAttention 디스패치로 라우팅합니다. 지원되는 Blackwell 호스트에서 Sol-Attn을 사용하려면 component에 백엔드를 지정하세요:

```yaml
component:
  # ...
  family: minimax-h3
  backend: sol
```

Sol-Attn 선택적 튜닝은 `action.params.sol_attn`에 둡니다:

```yaml
params:
  sol_attn:
    tau: 1.0
    thresh_type: diag
    dense_steps: 1
```

동작 노트:

- `tau`는 라우팅 임계값 스케일. 높으면 더 많은 KV 블록을 건너뜀 (빠르지만 정확도 저하); 낮으면 dense attention에 가까워짐.
- `thresh_type: diag`은 더 빠른 추정자; `exact`는 작은 비용으로 더 정확.
- `dense_steps`는 마지막 N 디노이징 스텝을 full dense attention으로 실행. 마지막 스텝에서 sparse 근사가 가장 눈에 띄므로 1 스텝을 dense로 두는 것이 저렴한 품질 가드.
- SM120이 아닌 하드웨어에서는 processor가 경고를 로그하고 각 attention 호출마다 dense로 폴백합니다 — 코드 변경 없이 portable하게 실행 가능.
- `backend: sol` 상태에서 `sol_attn` 블록을 생략해도 유효합니다; 위 기본값이 그대로 적용됩니다.

## 종료

```bash
model-compose down
```
