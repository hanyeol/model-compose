# 텍스트-투-비디오 모델 태스크 예제 (pi-H3)

이 예제는 **pi-H3** — LakonLab이 발표한 MiniMax-H3의 2/4-step distillation — 를 실행합니다. pi-Flow v2 few-step 샘플링과 DWD(Decoding Without a Decoder)를 결합해 마지막 스텝에서 비디오 VAE를 건너뛰고 픽셀을 바로 예측합니다. model-compose의 내장 text-to-video 태스크로 노출됩니다.

## 개요

MiniMax-H3의 공개 가중치는 이미 CFG-distilled이라서 커뮤니티에서 스텝을 줄이는 경로는 보통 distillation 어댑터입니다. LightX2V Turbo LoRA 변형이 베이스를 50 스텝에서 4–8 스텝으로 줄여준다면, pi-H3는 한 단계 더 나아갑니다:

1. **2 또는 4 스케줄러 스텝** (스텝 수가 어댑터에 내장).
2. **DWD**: 마지막 디노이징 스텝이 픽셀을 직접 예측하므로 비디오 VAE 디코더가 파이프라인에서 빠집니다.
3. **Pruned 베이스**: 전체 70 GB 릴리스 대신 `multimodalart/MiniMax-H3-Pruned` 위에서 돌아갑니다.

드라이버는 diffusers의 `ModularPipeline`으로 pruned 베이스를 로드한 뒤 LakonLab 어댑터 로더로 DWD 헤드와 distilled 가중치를 주입합니다. 추론은 `num_inference_steps`를 `step_count`에 고정한 표준 파이프라인 호출을 씁니다.

## 준비

### 필수 요건

- PATH에 `model-compose`
- CUDA 지원 GPU. 컨슈머급(24 GB)은 `cpu_offload: true`를 유지하세요(이미 설정됨). Blackwell급(B200 / H200)은 끄고 `quantization: {type: fp8}`을 켤 수 있습니다.
- Pruned 베이스 체크포인트용 ~45 GB + pi-H3 어댑터용 ~1 GB의 디스크 공간.
- `torch`, `diffusers==0.40.0`, `peft==0.20.0`, `transformers (>= 4.45)`, `mmcv==1.6.1`, `av`를 설치할 수 있는 Python 환경. 드라이버가 최초 실행 시 `.venv/pi-h3`에 이들을 설치하며, LakonLab(`v0.3.0`)은 PyPI에 없어 GitHub에서 직접 받아옵니다.
- `mmcv==1.6.1` 빌드를 위한 C/C++ 툴체인 (Debian/Ubuntu는 `build-essential`, macOS는 Xcode CLT). mmcv 1.x는 PEP 517 이전 패키지라 드라이버가 `--no-build-isolation`으로 venv의 torch를 사용해 빌드합니다.

### 모델 접근

- **베이스 모델**: Hugging Face의 `multimodalart/MiniMax-H3-Pruned`. MiniMax H3 Community License로 게이트됩니다 — 라이선스에 동의하고 서비스 시작 전에 `hf auth login` 또는 `HF_TOKEN` export를 수행하세요.
- **pi-H3 어댑터**: Hugging Face의 `Lakonik/pi-H3`. "Model Derivatives of MiniMax H3"로 동일한 커뮤니티 라이선스를 따릅니다.

## 어댑터 변형

드라이버가 `step_count`와 `dwd`에서 서브폴더를 자동 선택합니다:

| `step_count` | `dwd`   | 로드되는 서브폴더             | 출력 경로                    |
| :----------- | :------ | :--------------------------- | :--------------------------- |
| `2`          | `true`  | `pi_h3_2step_dwd_adapter`    | 마지막 스텝 직접 픽셀 출력     |
| `4`          | `true`  | `pi_h3_4step_dwd_adapter`    | 마지막 스텝 직접 픽셀 출력     |
| `2`          | `false` | `pi_h3_2step_adapter`        | 표준 비디오 VAE 디코딩         |
| `4`          | `false` | `pi_h3_4step_adapter`        | 표준 비디오 VAE 디코딩         |

**4-step DWD** 변형이 권장 기본값입니다 — B200에서 5초 클립을 수 초에 끝내면서도 모션/텍스처 충실도가 50-step 베이스에 가장 가깝습니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 최초 시작 시 pruned 베이스(~45 GB)와 pi-H3 어댑터를 다운로드합니다. 이후 실행은 캐시된 샤드를 재사용합니다.

2. **워크플로 실행:**
   ```bash
   # 최소 호출 — step_count와 DWD는 이미 예제에 결선되어 있습니다.
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

- **`guidance_scale`과 `negative_prompt`가 없습니다.** pi-H3는 few-step distilled 어댑터로, 매 스텝 single forward만 돌며 CFG가 적용되지 않습니다. 스키마에서 의도적으로 두 필드를 제외합니다.
- **`peft_adapter`로 사용자 LoRA를 얹지 마세요.** distilled 어댑터가 LoRA 슬롯을 점유하며, 그 위에 다른 LoRA를 쌓으면 few-step 궤적이 뒤틀립니다. 스키마가 해당 필드를 거부합니다.
- **`quantization: {type: fp8}`는 Blackwell급 하드웨어(B200 / H200)에서만 유효합니다.** SM89 이하에서는 LakonLab FP8 커널이 느린 fallback으로 떨어지거나 로드에 실패합니다 — 호스트를 검증하지 않았다면 `quantization`을 비워 두세요.
- **`num_frames`는 비디오 VAE가 디코딩 가능한 가장 가까운 `17*n + 5` 값(124–345)으로 올림됩니다.** 124 미만 요청은 올림되고 345 초과는 에러가 납니다.

## 종료

```bash
model-compose down
```
