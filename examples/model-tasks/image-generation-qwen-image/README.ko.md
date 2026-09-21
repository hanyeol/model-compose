# 이미지 생성 모델 태스크 예제 (Qwen-Image 2.1)

이 예제는 model-compose의 기본 image-generation 태스크를 통해 알리바바의 Qwen-Image-2.1로 텍스트 프롬프트에서 고품질 이미지를 생성하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 텍스트-투-이미지 생성을 제공합니다:

1. **로컬 Qwen-Image 2.1 파이프라인**: 7B 규모의 diffusion transformer를 처음부터 끝까지 로컬에서 실행합니다 — 외부 API 호출이 없습니다.
2. **Qwen3-VL 텍스트 인코더**: 파이프라인이 Qwen3-VL을 텍스트 조건자로 사용하므로 중국어, 한국어, 영어 프롬프트 모두 일급 시민으로 처리됩니다.
3. **True-CFG 가이던스**: `true_cfg_scale > 1.0`일 때만 `negative_prompt`와 함께 classifier-free guidance가 활성화됩니다. 기본값 `1.0`을 유지하면 추가 forward pass를 건너뛰어 추론 시간이 절반이 됩니다.
4. **다양한 종횡비 지원**: 1:1 (2048×2048), 4:3, 3:2, 16:9와 그 세로 버전까지 모두 네이티브로 지원합니다.
5. **자동 모델 관리**: 가중치는 첫 실행 시 HuggingFace Hub에서 다운로드되어 로컬에 캐시됩니다.

## 준비 사항

### 사전 요구사항

- model-compose가 설치되어 PATH에서 실행 가능해야 합니다.
- CUDA를 지원하는 GPU. 이 예제는 `cpu_offload: [text_encoder]` 옵션으로 Qwen-Image-2.1을 2048×2048 bfloat16 기준 단일 **24 GB** GPU 한 장에 맞춥니다. VRAM 여유가 더 많으면 해당 옵션을 제거하고, 더 작은 카드에서는 `cpu_offload: model`로 전환하세요.
- `torch`, `diffusers` (main), `transformers>=5.17`을 설치할 수 있는 Python 환경 — 첫 실행 시 격리된 virtualenv에 자동으로 설치됩니다.
- `Qwen/Qwen-Image-2.1`에 대한 라이선스를 수락한 HuggingFace 액세스 토큰. model-compose를 시작하기 전에 `HF_TOKEN` 환경 변수로 설정하세요.

### 격리된 런타임을 사용하는 이유

`QwenImage21Pipeline`은 `diffusers` main 브랜치에 병합되었지만 **아직 정식 릴리스에 포함되지 않았습니다** (2026-09 기준 최신은 v0.40.0). image-generation 드라이버가 이 컴포넌트의 setup requirements에 `diffusers @ git+https://github.com/huggingface/diffusers.git`을 추가하므로, 모델 워커는 전용 `virtualenv` (`.venv/qwen-image`)에서 실행되어 이 미공개 빌드가 컨트롤러 자신의 `diffusers` 설치나 동일 compose 파일 안의 다른 diffusion 컴포넌트와 충돌하지 않도록 합니다.

### 환경 구성

1. 예제 디렉토리로 이동합니다:
   ```bash
   cd examples/model-tasks/image-generation-qwen-image
   ```

2. https://huggingface.co/Qwen/Qwen-Image-2.1 에서 Qwen Research License를 수락한 뒤, `.env`를 샘플에서 복사하고 접근 권한이 있는 HuggingFace 액세스 토큰을 붙여넣습니다:
   ```bash
   cp .env.sample .env
   # .env 파일을 열어 HF_TOKEN=hf_xxx 를 설정합니다
   ```

3. VRAM을 절약하려면 `width` / `height`를 낮추거나(예: 1536×1536, 1024×1024), 기본값 40인 `inference_steps`를 줄이세요.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행은 `.venv/qwen-image`를 만들고, GitHub main에서 `diffusers`를 설치하고, 약 20 GB의 가중치를 다운로드한 뒤 파이프라인을 VRAM에 로드합니다. 컨트롤러가 ready 상태가 되기까지 수 분이 걸립니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 기본 2048×2048 해상도로 텍스트-투-이미지
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "A neon shop sign that reads \"QWEN IMAGE 2.1\", rainy night, reflections on wet pavement"}}' \
     -o output.png

   # 고정 시드로 재현 가능한 샘플링
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "이끼로 덮인 바위 위에서 쉬고 있는 눈표범, 시네마틱 조명", "seed": 42}}' \
     -o output.png

   # 와이드 화면 렌더링 + negative prompt + true-CFG
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"input": {"prompt": "석양의 광활한 사막 협곡, 초정밀 디테일", "negative_prompt": "blurry, low quality, watermark", "true_cfg_scale": 4.0, "width": 2752, "height": 1536}}' \
     -o output.png

   # 이미지 조건 생성 — 편집 지시(instruction) 대상이 될 입력 이미지를 한 장 또는 여러 장 전달
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/input.png" \
     -F 'input={"prompt": "같은 피사체를 눈 덮인 숲 황혼에 배치, 시네마틱 조명", "image": "@ref"}' \
     -o output.png
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 생성할 이미지를 설명하는 `prompt` 입력
   - 재현성을 위해 `seed`를 지정하거나, 가이드가 필요하면 `negative_prompt` + `true_cfg_scale > 1.0`을 설정하거나, 비정사각형 `width`/`height`도 지정 가능
   - "Run Workflow"를 클릭하면 `.png` 파일이 반환됩니다

## 구성 참조

### Component 필드

| 필드            | 설명                                                                   | 기본값  |
|-----------------|------------------------------------------------------------------------|---------|
| `task`          | 반드시 `image-generation`.                                             | —       |
| `driver`        | 반드시 `huggingface`.                                                  | —       |
| `architecture`  | 반드시 `qwen-image`.                                                   | —       |
| `model`         | Qwen-Image 리포지토리 (`Qwen/Qwen-Image-2.1` 또는 로컬 경로).          | —       |
| `device`        | 연산 디바이스. `cuda`를 강력히 권장합니다.                             | `auto`  |

### Action 필드

| 필드                     | 설명                                                                                        | 기본값  |
|--------------------------|---------------------------------------------------------------------------------------------|---------|
| `prompt`                 | 텍스트 프롬프트 (또는 리스트/스트림).                                                        | —       |
| `negative_prompt`        | 피할 내용에 대한 설명. `true_cfg_scale > 1.0`일 때만 적용됩니다.                             | (없음)  |
| `image`                  | 지시(instruction) 기반 편집을 위한 입력 이미지 한 장 또는 리스트. 배치 내 모든 프롬프트에 브로드캐스트됩니다. | (없음)  |
| `width`                  | 출력 이미지 너비 (픽셀).                                                                     | `1024`  |
| `height`                 | 출력 이미지 높이 (픽셀).                                                                     | `1024`  |
| `num_return_images`      | 프롬프트당 반환되는 이미지 수.                                                                | `1`     |
| `seed`                   | 재현성을 위한 랜덤 시드. 설정하지 않으면 매 호출마다 새 샘플이 생성됩니다.                    | (없음)  |
| `batch_size`             | 입력이 리스트 또는 스트림일 때 배치당 처리되는 프롬프트 수.                                   | `1`     |
| `params.inference_steps` | 디노이징 스텝 수.                                                                             | `40`    |
| `params.true_cfg_scale`  | True classifier-free guidance 스케일. `1.0`이면 negative-prompt 가이던스가 비활성화됩니다.   | `1.0`   |

## 참고 사항

- **첫 실행은 느립니다**: 컨트롤러가 `.venv/qwen-image` 환경을 만들고, GitHub main에서 `diffusers`를 설치하고, 약 20 GB의 가중치를 첫 시작 시 다운로드합니다. ready 상태까지 10-15분이 걸립니다. 이후 실행은 캐시된 venv와 가중치를 재사용합니다.
- **Diffusers는 main 고정**: Qwen-Image-2.1은 `diffusers` main에만 있는 클래스(`QwenImage21Pipeline`, `QwenImage21Transformer2DModel`, `AutoencoderKLQwenImage21`)에 의존합니다. 다음 정식 릴리스에 포함되면 이 예제의 setup을 git URL 대신 `diffusers>=<릴리스>`로 고정할 수 있으며, model-compose를 업데이트하면 compose 변경이 필요 없습니다.
- **Qwen Research License**: `Qwen/Qwen-Image-2.1`은 Qwen Research License Agreement (비상업적)로 배포됩니다. 프로덕션 사용 전에 https://huggingface.co/Qwen/Qwen-Image-2.1 에서 조건을 검토하세요.
- **VRAM 계획**: 7B transformer와 Qwen3-VL 텍스트 인코더를 모두 GPU에 상주시키면 2048×2048 bfloat16에서 피크 VRAM이 약 24 GB에 달합니다. 이 예제는 `cpu_offload: [text_encoder]`로 텍스트 인코더를 CPU에 두고 인코딩 순간에만 GPU로 이동시켜, transformer와 VAE는 GPU에 상주한 채 24 GB 한 장에서 최대 속도로 동작합니다. 피크 VRAM을 더 낮추고 싶다면 (속도 손실 감수) `cpu_offload: model` (파이프라인 전체 모듈 단위 offload) 또는 `cpu_offload: sequential` (레이어 단위, ~90% 절감이지만 2–5배 느림)로 전환하세요. 여기에 `quantization` 설정을 더하면 가중치 자체도 줄일 수 있으며, 드라이버는 `transformer`와 `text_encoder`를 양자화 대상으로 표시하므로 4비트/8비트가 가장 큰 절감을 제공합니다.
- **`true_cfg_scale` vs 속도**: `true_cfg_scale > 1.0`이면 파이프라인이 스텝마다 negative prompt에 대한 추가 forward pass를 실행해 추론 시간이 약 두 배가 됩니다. 가장 빠른 경로를 원하면 `1.0`으로 두고, negative prompt가 정말 필요할 때만 올리세요.
- **다국어 프롬프트**: Qwen-Image-2.1의 Qwen3-VL 텍스트 인코더는 중국어, 한국어, 일본어, 영어 프롬프트를 네이티브로 처리하며, 혼합 언어 프롬프트도 동작합니다.
- **출력**: 결과는 diffusion VAE로 디코딩된 입력당 하나의 `.png` (배치 입력의 경우 리스트)입니다.
