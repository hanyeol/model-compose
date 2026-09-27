# 이미지 생성 모델 태스크 예제 (Qwen-Image 2.1 + Pruna LoRA)

이 예제는 알리바바의 Qwen-Image-2.1을 [PrunaAI의 distilled LoRA](https://huggingface.co/PrunaAI/Pruna-Qwen-Image-2.1)로 가속하여, 베이스 파이프라인이 40스텝을 쓰는 데 반해 5스텝 또는 8스텝만으로 텍스트-투-이미지 생성을 수행하는 방법을 보여줍니다.

## 개요

이 워크플로우는 베이스 Qwen-Image-2.1 파이프라인에 PEFT LoRA 어댑터를 부착하고 감소된 스텝 수로 실행합니다:

1. **베이스 Qwen-Image 2.1 파이프라인**: [image-generation-qwen-image](../image-generation-qwen-image) 예제와 동일한 로컬 파이프라인 — 7B diffusion transformer, Qwen3-VL 텍스트 인코더, 다국어 프롬프트 지원.
2. **Pruna Distilled LoRA**: Pruna가 베이스 모델에서 distill한 공개 LoRA 어댑터로, 파이프라인이 훨씬 적은 스텝만으로 수렴하도록 합니다.
3. **선언적 어댑터 조합**: 어댑터는 모델 컴포넌트의 표준 `peft_adapters` 필드로 부착됩니다 — 코드 없이 YAML만으로 처리.
4. **격리된 런타임**: 베이스 Qwen-Image 예제와 동일한 virtualenv 전략을 사용하여, `QwenImage21Pipeline`을 포함한 미공개 `diffusers` 빌드를 컨트롤러 환경 밖으로 격리합니다.

## 준비 사항

### 사전 요구사항

- model-compose가 설치되어 PATH에서 실행 가능해야 합니다.
- CUDA를 지원하는 GPU. 이 예제는 `cpu_offload: model`로 파이프라인을 24 GB 카드 한 장에 맞춥니다. VRAM 여유가 더 많으면 옵션을 제거하거나 낮추세요.
- `torch`, `diffusers` (main), `transformers>=5.17`, `peft`를 설치할 수 있는 Python 환경 — 첫 실행 시 격리된 virtualenv에 자동 설치됩니다.
- `Qwen/Qwen-Image-2.1`에 대한 라이선스를 수락한 HuggingFace 액세스 토큰. model-compose를 시작하기 전에 `HF_TOKEN` 환경 변수로 설정하세요.

### 어댑터에 관하여

`PrunaAI/Pruna-Qwen-Image-2.1`은 동일한 리포지토리에 두 가지 `.safetensors` 변형을 제공합니다:

| 변형                                            | 디노이징 스텝 | 참고                                          |
|-------------------------------------------------|---------------|-----------------------------------------------|
| `p_qwen_image_2.1_8step_v0.1.safetensors`       | 8             | 이 예제의 기본값. 품질과 속도의 균형이 좋습니다. |
| `p_qwen_image_2.1_5step_v0.1.safetensors`       | 5             | 최대 속도; 품질 저하가 더 눈에 띕니다.           |

변형을 전환하려면 세 필드를 함께 편집합니다:

- `peft_adapters[0].model.filename`
- `action.params.inference_steps`
- `action.params.sigmas` (LoRA는 변형마다 특정 sigma 스케줄로 학습됨)

5스텝 변형의 경우 `sigmas: [1.0, 0.94, 0.857142857, 0.666666667, 0.4]`와 `inference_steps: 5`를 사용하세요.

Pruna 모델 카드에서는 v0.1의 품질이 40스텝 기준 베이스 모델에는 아직 미치지 못한다고 명시합니다 — drop-in 대체가 아니라 속도/품질 트레이드오프로 다뤄야 합니다.

### 환경 구성

1. 예제 디렉토리로 이동합니다:
   ```bash
   cd examples/model-tasks/image-generation-qwen-image-pruna
   ```

2. https://huggingface.co/Qwen/Qwen-Image-2.1 에서 Qwen Research License를 수락한 뒤, `.env`를 샘플에서 복사하고 접근 권한이 있는 액세스 토큰을 붙여넣습니다:
   ```bash
   cp .env.sample .env
   # .env 파일을 열어 HF_TOKEN=hf_xxx 를 설정합니다
   ```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행은 `.venv/qwen-image-pruna`를 만들고, GitHub main에서 `diffusers`와 `peft`를 설치하고, 약 20 GB의 베이스 가중치와 LoRA 파일을 다운로드한 뒤 파이프라인을 VRAM에 로드합니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 기본 1024×1024 해상도로 8스텝 텍스트-투-이미지
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A neon shop sign that reads \"QWEN IMAGE 2.1\", rainy night, reflections on wet pavement"}}' \
     -o output.png

   # 고정 시드로 재현 가능한 샘플링
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "이끼로 덮인 바위 위에서 쉬고 있는 눈표범, 시네마틱 조명", "seed": 42}}' \
     -o output.png

   # 이미지 조건 생성 — 편집 지시 대상이 될 입력 이미지를 한 장 또는 여러 장 전달
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/input.png" \
     -F 'input={"prompt": "같은 피사체를 눈 덮인 숲 황혼에 배치, 시네마틱 조명", "image": "@ref"}' \
     -o output.png
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 생성할 이미지를 설명하는 `prompt` 입력
   - 재현성을 위해 `seed`를 지정하거나 비정사각형 `width`/`height`도 지정 가능
   - "Run Workflow"를 클릭하면 `.png` 파일이 반환됩니다

## 구성 참조

### PEFT Adapter 필드

| 필드                        | 설명                                                                                     | 기본값  |
|-----------------------------|------------------------------------------------------------------------------------------|---------|
| `type`                      | 어댑터 유형. Diffusion 파이프라인은 현재 `lora`만 지원합니다.                              | —       |
| `name`                      | 여러 어댑터를 조합할 때 참조에 쓰는 식별자 (`set_adapters([...])`).                        | (없음)  |
| `model.repository`          | 어댑터 가중치가 있는 HuggingFace 리포지토리.                                              | —       |
| `model.filename`            | 리포지토리 내에서 로드할 파일. 리포지토리가 여러 변형을 함께 배포할 때 필수입니다.         | (없음)  |
| `weight`                    | LoRA 활성 시 적용되는 어댑터 강도.                                                        | `1.0`   |

### Action 필드

베이스 [image-generation-qwen-image](../image-generation-qwen-image) 예제와 동일합니다. 이 변형에서 조정이 필요한 두 노브:

| 필드                     | 설명                                                                                       | 기본값  |
|--------------------------|--------------------------------------------------------------------------------------------|---------|
| `params.inference_steps` | LoRA 변형과 일치시켜야 합니다: 8스텝 파일이면 `8`, 5스텝 파일이면 `5`.                     | `8`     |
| `params.true_cfg_scale`  | Pruna의 distillation은 `1.0`을 목표로 학습됨. 올리면 가속 효과가 사라집니다.               | `1.0`   |

## 참고 사항

- **작업 중인 어댑터**: Pruna 모델 카드는 v0.1을 명시적으로 work in progress로 표시하며, 40스텝 베이스 파이프라인의 품질에는 아직 미치지 못합니다. 최고 화질보다 지연시간이 더 중요할 때 이 예제를 사용하세요.
- **`true_cfg_scale`는 고정값**: distilled 어댑터는 classifier-free guidance 없이 학습되었습니다. `true_cfg_scale`을 `1.0`보다 올리면 추가 forward pass 비용만 늘고 품질 이득이 없으며, `negative_prompt`는 베이스 예제와의 대칭을 위해 받지만 이 스케일에서는 효과가 없습니다.
- **VRAM 계획**: LoRA를 부착해도 VRAM 사용량은 베이스 파이프라인과 크게 다르지 않습니다. 속도를 낮춰 피크 메모리를 줄이는 방법은 베이스 예제의 VRAM 참고 사항을 확인하세요.
- **스텝 수 전환**: `filename`만 편집하는 것으로는 충분하지 않습니다 — 세 필드(`filename`, `inference_steps`, `sigmas`)를 함께 바꿔야 합니다. 파이프라인은 8스텝 LoRA를 5스텝으로 돌려도 실행은 되지만, 결과물은 눈에 띄게 under-denoise됩니다.
- **라이선스**: `Qwen/Qwen-Image-2.1`과 Pruna LoRA 모두 각자의 HuggingFace 라이선스를 따릅니다. 프로덕션 사용 전에 각 리포지토리의 조건을 검토하세요.
