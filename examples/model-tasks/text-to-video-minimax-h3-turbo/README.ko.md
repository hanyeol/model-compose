# 텍스트-투-비디오 모델 태스크 예제 (MiniMax-H3 + LightX2V Turbo LoRA)

이 예제는 text-to-video-minimax-h3와 동일한 워크플로이지만, MiniMax-H3 Omni-Transformer 위에 LightX2V/ModelTC Turbo LoRA를 얹어 적은 스텝으로 생성이 끝나도록 합니다. model-compose의 내장 text-to-video 태스크로 노출됩니다.

## 개요

MiniMax-H3는 few-step 체크포인트를 공개하지 않으며, 공개된 가중치는 이미 CFG-distilled이므로 `guidance_scale`은 실질적으로 영향이 없습니다. LightX2V Turbo LoRA는 커뮤니티에서 가장 널리 쓰이는 step-distilled 옵션으로, 베이스를 재학습하지 않고 기본 50 스케줄러 스텝을 4 또는 8 모델 평가로 줄여줍니다. 이 예제는 그 설정을 선언형으로 구성합니다:

1. **베이스 파이프라인 재사용**: 기본 예제와 동일한 `MiniMaxH3ModularPipeline`을 로드하며, LoRA와 스텝/shift 설정만 다릅니다.
2. **Turbo LoRA 부착**: 예제가 `peft_adapter`로 LoRA를 선언하면, 드라이버가 Hugging Face에서 다운로드해 로드 시점에 베이스 트랜스포머 위에 부착합니다 — 별도 변환 과정은 필요하지 않습니다.
3. **LoRA에 맞춘 Scheduler Shift**: 768p Turbo 파일은 **video shift 6**로 학습되었으며, 이는 스케줄러 기본값 12가 아닙니다. 예제는 `video_shift: 6`을 설정해 LoRA가 기대하는 시그마에 스케줄을 맞춥니다.

## 준비

### 필수 요건

베이스 MiniMax-H3 예제와 동일합니다: PATH에 model-compose, CUDA 지원 GPU(컨슈머급은 `cpu_offload: true` 필요, 이미 설정됨), 베이스 체크포인트용 ~70 GB + LoRA용 수백 MB의 디스크 공간, 그리고 `torch`, `diffusers (>= 0.36)`, `transformers (>= 4.45)`, `av`를 설치할 수 있는 Python 환경.

### 모델 접근

- **베이스 모델**: Hugging Face의 `MiniMaxAI/MiniMax-H3`는 MiniMax H3 Community License로 게이트됩니다. 라이선스에 동의하고 서비스 시작 전에 `hf auth login`을 실행하거나 `HF_TOKEN`을 export하세요.
- **Turbo LoRA**: Hugging Face의 `lightx2v/Minimax-h3-Turbo`. 저장소는 여러 변형을 한곳에 묶어 제공합니다 — 아래 표를 참고하세요.

## LoRA 변형

업스트림 저장소에는 다섯 개의 LoRA 파일이 포함됩니다. 파일을 올바른 `video_shift`와 `inference_steps`에 맞추는 것이 중요합니다: 768p 파일을 기본 스케줄러 shift와 짝지으면 스케줄이 어긋나 모션 품질이 눈에 띄게 저하됩니다. [ModelTC/Minimax-H3-Turbo 모델 스펙](https://github.com/ModelTC/Minimax-H3-Turbo#1-model-specs) 기준:

| 파일명                                                   | 태스크      | 학습 video_shift | NFE | `inference_steps` |
| ------------------------------------------------------- | ---------- | ---------------: | --: | ----------------: |
| `minimax_h3_fl2v_turbo_4step_v0.1.safetensors`          | T2VA/FL2VA |               12 |   4 |                 5 |
| `minimax_h3_fl2v_turbo_8step_v1.0_bf16.safetensors`     | T2VA/FL2VA |               12 |   8 |                 9 |
| `minimax_h3_fl2v_turbo_4step_v1.0_768p_bf16.safetensors`| T2VA/FL2VA |                6 |   4 |                 5 |
| `minimax_h3_fl2v_turbo_8step_v1.0_768p_bf16.safetensors`| T2VA/FL2VA |                6 |   8 |                 9 |
| `minimax_h3_ref2v_turbo_4step_v0.1_bf16.safetensors`    | Ref2VA     |               12 |   4 |                 5 |

노트:

- 예제는 균형 잡힌 기본값으로 **8-step 768p** 파일(`minimax_h3_fl2v_turbo_8step_v1.0_768p_bf16.safetensors`)을 선택합니다. 변경하려면 `peft_adapter[0].model.filename`, `inference_steps`, `video_shift`를 함께 바꾸세요 — 위 표의 각 행은 한 패키지입니다.
- **`inference_steps`는 NFE + 1 입니다.** MiniMax-H3 스케줄러가 종단 0을 포함한 시그마 그리드 포인트 수를 세기 때문입니다. "8-step" 파일을 `inference_steps: 8`로 넘기면 8번이 아닌 7번 평가됩니다.
- `audio_shift: 3`은 위 모든 행에 공통입니다 — 오디오 스케줄러는 모든 Turbo 변형에서 shift 3으로 학습되었습니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 최초 시작 시 베이스 체크포인트(~70 GB)와 LoRA(수백 MB)를 다운로드합니다. 이후 실행은 캐시된 샤드를 재사용합니다.

2. **워크플로 실행:**
   ```bash
   # 최소 호출 — Turbo LoRA + shift는 이미 예제에 결선되어 있습니다.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "a quiet alleyway at dusk, warm neon reflections on wet pavement, slow dolly in"}}'

   # 시드 고정 및 더 긴 클립 요청.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "waves crashing on a rocky coast, overcast sky, slow-motion spray", "num_frames": 192, "seed": 42}}'
   ```

3. **웹 UI 열기:**
   `http://localhost:8081`에서 Gradio 폼으로 동일 워크플로를 실행할 수 있습니다.

## 튜닝 노트

- **`guidance_scale`을 1.0 이상으로 올리지 마세요.** MiniMax-H3 가중치는 CFG-distilled이므로 값을 높여도 프롬프트 반영이 개선되지 않으며, Turbo LoRA가 기대하는 single-forward 스케줄이 깨집니다.
- **`inference_steps`를 파일에 맞추세요.** 4-step 파일은 `inference_steps: 5`, 8-step 파일은 `inference_steps: 9`. 학습된 예산을 넘겨 스텝을 늘려도 품질은 개선되지 않습니다 — LoRA는 고정 NFE로 distill되었기 때문입니다.
- **`video_shift` / `audio_shift`를 설정하지 않으면 스케줄러 기본값(12 / 3)이 유지됩니다.** Turbo LoRA 없이 베이스 모델을 실행할 때는 키를 생략하거나 `null`로 두세요; 기본값은 distill되지 않은 50-step 레시피 기준입니다.

## 종료

```bash
model-compose down
```
