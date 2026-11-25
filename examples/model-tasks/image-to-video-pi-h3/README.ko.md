# 이미지-투-비디오 모델 태스크 예제 (pi-H3)

이 예제는 **pi-H3** — LakonLab이 발표한 MiniMax-H3의 2/4-step distillation — 를 사용해 정지 이미지를 네이티브 스테레오 오디오와 함께 짧은 영상으로 변환합니다. 첫 프레임 이미지(필수), 선택적으로 마지막 프레임 이미지(fl2va 키프레임 보간용), 그리고 모션을 묘사하는 프롬프트를 제공합니다. model-compose의 내장 image-to-video 태스크로 노출됩니다.

## 개요

pi-H3는 pi-Flow v2 few-step 샘플링과 DWD(Decoding Without a Decoder)를 결합해 마지막 디노이징 스텝에서 픽셀을 직접 예측합니다. image-to-video에서는 드라이버가 파이프라인 워크플로를 `fl2va`로 고정하여 키프레임 트랜스포머 파티션만 가져오며, 두 가지 입력을 받습니다:

- `image` — 첫 프레임 조건 (필수)
- `last_image` — 마지막 키프레임 (선택); 지정 시 두 프레임 사이를 부드럽게 보간

나머지는 text-to-video 예제와 동일합니다: pruned 베이스 + LakonLab 어댑터 + 선택적 FP8, `num_inference_steps`를 `step_count`에 고정, `num_frames`를 가장 가까운 `17*n + 5`로 스냅.

## 준비

### 필수 요건

- PATH에 `model-compose`
- CUDA 지원 GPU. 컨슈머급(24 GB)은 `cpu_offload: true` 유지(이미 설정됨); Blackwell급(B200 / H200)은 끄고 `quantization: {type: fp8}`을 켤 수 있습니다.
- Pruned 베이스 체크포인트용 ~45 GB + pi-H3 어댑터용 ~1 GB 디스크 공간.
- `torch`, `diffusers (>= 0.36)`, `transformers (>= 4.45)`, `lakonlab (>= 0.3)`, `av`를 설치할 수 있는 Python 환경. 드라이버의 setup requirements에 포함되어 최초 실행 시 `.venv/pi-h3`에 설치됩니다.

### 모델 접근

- **베이스 모델**: Hugging Face의 `multimodalart/MiniMax-H3-Pruned`. MiniMax H3 Community License로 게이트됩니다 — 서비스 시작 전에 라이선스에 동의하고 `hf auth login` 또는 `HF_TOKEN` export를 수행하세요.
- **Distillation 어댑터**: Hugging Face의 `Lakonik/pi-H3`. "Model Derivatives of MiniMax H3"로 동일한 커뮤니티 라이선스를 따릅니다. `distillation` 필드에서 revision을 고정하거나 로컬 스냅샷 경로를 지정할 수 있습니다.

## 어댑터 변형

text-to-video 예제와 동일한 매트릭스 — 드라이버가 `step_count`와 `dwd`에서 서브폴더를 자동 선택합니다:

| `step_count` | `dwd`   | 로드되는 서브폴더             | 출력 경로                    |
| :----------- | :------ | :--------------------------- | :--------------------------- |
| `2`          | `true`  | `pi_h3_2step_dwd_adapter`    | 마지막 스텝 직접 픽셀 출력     |
| `4`          | `true`  | `pi_h3_4step_dwd_adapter`    | 마지막 스텝 직접 픽셀 출력     |
| `2`          | `false` | `pi_h3_2step_adapter`        | 표준 비디오 VAE 디코딩         |
| `4`          | `false` | `pi_h3_4step_adapter`        | 표준 비디오 VAE 디코딩         |

**4-step DWD** 변형이 권장 기본값입니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 최초 시작 시 pruned 베이스(~45 GB)와 pi-H3 어댑터를 다운로드합니다. 이후 실행은 캐시된 샤드를 재사용합니다.

2. **워크플로 실행 — 첫 프레임만:**
   ```bash
   # 프롬프트가 모션을 주도하는 애니메이션.
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"image": "https://example.com/first.jpg", "prompt": "camera slowly dollies in, leaves rustle in the wind"}}'
   ```

3. **워크플로 실행 — 첫/마지막 프레임 (키프레임 보간):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"image": "https://example.com/first.jpg", "last_image": "https://example.com/last.jpg", "prompt": "smooth transition, locked-off camera"}}'
   ```

4. **웹 UI 열기:**
   `http://localhost:8081`에서 Gradio 폼으로 동일 워크플로를 실행할 수 있습니다.

## 튜닝 노트

- **`guidance_scale`과 `negative_prompt`가 없습니다.** pi-H3는 few-step distilled로 CFG가 적용되지 않습니다.
- **`peft_adapter`로 사용자 LoRA를 얹지 마세요.** distilled 어댑터가 LoRA 슬롯을 점유하며 스키마가 해당 필드를 거부합니다.
- **`width`/`height`는 액션에서 설정하지 않으면 입력 이미지 치수를 그대로 따릅니다.** 이미지를 다시 저작하지 않고 업/다운스케일만 할 때 명시하세요.
- **`quantization: {type: fp8}`는 Blackwell급 하드웨어(B200 / H200)에서만 유효합니다.** 그 외에는 `quantization`을 비워 두세요.
- **`video_shift` / `audio_shift`를 설정하지 않으면 스케줄러 기본값(12 / 3)이 유지됩니다.** LakonLab이 공개한 특정 레시피를 맞출 때만 덮어쓰세요.
- **`num_frames`는 비디오 VAE가 디코딩 가능한 가장 가까운 `17*n + 5`(124–345)로 올림됩니다.**

## 종료

```bash
model-compose down
```
