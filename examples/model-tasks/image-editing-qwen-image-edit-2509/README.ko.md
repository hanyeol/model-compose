# 이미지 편집 모델 태스크 예제 (Qwen-Image-Edit-2509)

이 예제는 model-compose의 기본 image-generation 태스크를 통해 알리바바의 Qwen-Image-Edit-2509로 자연어 지시문을 사용해 하나 이상의 레퍼런스 이미지를 편집하는 방법을 보여줍니다.

## 개요

이 워크플로우는 다음과 같은 로컬 지시문 기반 이미지 편집을 제공합니다:

1. **로컬 Qwen-Image-Edit-2509 파이프라인**: 20B 규모의 diffusion transformer를 처음부터 끝까지 로컬에서 실행합니다 — 외부 API 호출이 없습니다.
2. **Qwen2.5-VL 텍스트 인코더**: 파이프라인이 Qwen2.5-VL을 비전-언어 조건자로 사용하므로 이미지 내용을 직접 참조하는 지시문("재킷을 빨간색으로", "피사체를 눈 덮인 숲에 배치")이 가능합니다.
3. **멀티 레퍼런스 편집**: 레퍼런스 이미지 1장 또는 최대 3장의 리스트를 전달할 수 있습니다. 모델이 이들을 융합해 정체성 보존 편집, 상품 합성, 포즈 전이를 수행합니다.
4. **True-CFG 가이던스**: `true_cfg_scale` 기본값이 `4.0`이므로 `negative_prompt`가 실제로 샘플링을 유도합니다. 추가 forward pass를 건너뛰고 추론 시간을 절반으로 줄이고 싶다면 `1.0`으로 낮추세요 (대신 네거티브 프롬프트 가이던스는 사라집니다).
5. **자동 모델 관리**: 가중치는 첫 실행 시 HuggingFace Hub에서 다운로드되어 로컬에 캐시됩니다.

## 준비 사항

### 사전 요구사항

- model-compose가 설치되어 PATH에서 실행 가능해야 합니다.
- CUDA를 지원하는 GPU. 이 예제는 `cpu_offload: model` 옵션으로 Qwen-Image-Edit-2509를 1024×1024 bfloat16 기준 단일 **24 GB** GPU 한 장에 맞춥니다. 더 작은 카드에서는 `cpu_offload: sequential`로 레이어 단위 오프로드로 전환하거나, 48 GB 이상 카드에서는 해당 옵션을 제거해 최고 속도를 뽑으세요.
- `torch`, `diffusers>=0.41.0`, `transformers>=4.51.3`을 설치할 수 있는 Python 환경 — 첫 실행 시 격리된 virtualenv에 자동으로 설치됩니다.
- `Qwen/Qwen-Image-Edit-2509`에 대한 라이선스를 수락한 HuggingFace 액세스 토큰. model-compose를 시작하기 전에 `HF_TOKEN` 환경 변수로 설정하세요.

### 격리된 런타임을 사용하는 이유

`QwenImageEditPlusPipeline`은 `diffusers >= 0.41.0`에서 사용 가능하지만, 컨트롤러의 공유 환경이 다른 컴포넌트가 쓰는 더 낮은 릴리스에 pin되어 있을 수 있습니다. 모델 워커는 전용 `virtualenv` (`.venv/qwen-image-edit`)에서 실행되므로, 이 컴포넌트의 `diffusers` 업그레이드가 컨트롤러의 자체 설치를 덮어쓰거나 동일 compose 파일 안의 다른 diffusion 컴포넌트와 충돌하지 않습니다.

### 환경 구성

1. 예제 디렉토리로 이동합니다:
   ```bash
   cd examples/model-tasks/image-editing-qwen-image-edit-2509
   ```

2. https://huggingface.co/Qwen/Qwen-Image-Edit-2509 에서 Qwen Research License를 수락한 뒤, 셸이나 이 README 옆의 `.env` 파일에 `HF_TOKEN`을 설정합니다:
   ```bash
   export HF_TOKEN=hf_xxx
   ```

3. 최대 VRAM을 줄이려면 `width` / `height`를 낮추거나 (예: 768×768) `inference_steps`를 기본값 40보다 낮추세요.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 시작 시 `.venv/qwen-image-edit` 환경을 생성하고 `diffusers`와 `transformers`를 설치한 뒤 약 40 GB의 가중치를 다운로드해 파이프라인을 VRAM에 로드합니다. 컨트롤러가 ready 상태를 보고하기까지 10-20분 정도 걸립니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 단일 레퍼런스 편집 — 이미지 1장을 첨부하고 편집 지시
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/subject.png" \
     -F 'input={"prompt": "피사체를 황혼의 눈 덮인 소나무 숲에 배치, 영화적 조명", "image": "@ref"}' \
     -o output.png

   # 고정 시드 + 네거티브 프롬프트
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "ref=@/path/to/subject.png" \
     -F 'input={"prompt": "재킷을 빨간 가죽 봄버로 변경", "negative_prompt": "흐릿함, 추가 팔다리, 워터마크", "image": "@ref", "seed": 42}' \
     -o output.png

   # 멀티 레퍼런스 편집 — 두 이미지를 하나의 지시문으로 합성
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "a=@/path/to/person.png" \
     -F "b=@/path/to/outfit.png" \
     -F 'input={"prompt": "첫 번째 이미지의 사람에게 두 번째 이미지의 의상을 입히기", "image": ["@a", "@b"]}' \
     -o output.png
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `image`에 레퍼런스 이미지 1장 이상 업로드
   - `prompt`에 편집 지시문 입력
   - 필요시 `seed`, `negative_prompt`, 또는 정사각이 아닌 `width`/`height` 설정
   - "Run Workflow"를 눌러 `.png` 파일을 받으세요

## 설정 레퍼런스

### 컴포넌트 필드

| 필드           | 설명                                                              | 기본값 |
|---------------|------------------------------------------------------------------|--------|
| `task`        | `image-generation`이어야 합니다.                                  | —      |
| `driver`      | `huggingface`여야 합니다.                                         | —      |
| `architecture`| `qwen-image-edit`이어야 합니다.                                    | —      |
| `model`       | Qwen-Image-Edit 저장소 (`Qwen/Qwen-Image-Edit-2509` 또는 로컬 경로). | —   |
| `device`      | 연산 디바이스. `cuda`를 강력히 권장합니다.                           | `auto` |
| `cpu_offload` | VRAM 감소 전략. `model`은 단일 24 GB GPU에 맞춥니다.                 | (없음) |

### 액션 필드

| 필드                          | 설명                                                                                    | 기본값 |
|-------------------------------|----------------------------------------------------------------------------------------|--------|
| `prompt`                      | 자연어 편집 지시문 (또는 지시문의 리스트/스트림).                                        | —      |
| `negative_prompt`             | 피하고 싶은 내용을 설명하는 텍스트. `true_cfg_scale > 1.0`일 때만 효과가 있습니다.         | (없음) |
| `image`                       | **필수.** 레퍼런스 이미지 1장 또는 최대 3장의 리스트.                                      | —      |
| `width`                       | 출력 이미지 너비(픽셀).                                                                   | `1024` |
| `height`                      | 출력 이미지 높이(픽셀).                                                                   | `1024` |
| `num_return_images`           | 프롬프트당 반환할 이미지 수.                                                               | `1`    |
| `seed`                        | 재현성을 위한 랜덤 시드. 호출마다 새로운 샘플을 원하면 설정하지 마세요.                      | (없음) |
| `batch_size`                  | 입력이 리스트/스트림일 때 배치당 처리할 프롬프트 수.                                        | `1`    |
| `params.inference_steps`      | 디노이징 스텝 수.                                                                         | `40`   |
| `params.true_cfg_scale`       | True classifier-free guidance 스케일. 1.0을 초과하면 네거티브 프롬프트 가이던스가 활성화됩니다. | `4.0`  |
| `params.max_sequence_length`  | Qwen2.5-VL 텍스트 인코더의 최대 토큰 길이.                                                 | `512`  |

## 참고 사항

- **첫 실행은 느림**: 컨트롤러가 `.venv/qwen-image-edit` 환경을 생성하고 `diffusers`와 `transformers`를 설치한 뒤 첫 시작 시 약 40 GB의 가중치를 다운로드합니다. 이후 실행에서는 캐시된 venv와 가중치를 재사용합니다.
- **Qwen Research License**: `Qwen/Qwen-Image-Edit-2509`은 Qwen Research License Agreement(비상업용)로 공개되었습니다. 상업적 사용 전에 https://huggingface.co/Qwen/Qwen-Image-Edit-2509 의 조건을 확인하세요.
- **VRAM 계획**: 20B 트랜스포머와 Qwen2.5-VL 텍스트 인코더(~7B)를 둘 다 GPU에 상주시키면 24 GB를 초과합니다. 이 예제는 `cpu_offload: model`(파이프라인 전체 모듈 단위 오프로드)로 1024×1024 기준 peak VRAM을 24 GB 이하로 유지합니다. 더 낮은 peak VRAM이 필요하면 `cpu_offload: sequential`(레이어 단위 오프로드, 약 90% VRAM 절감이지만 2–5배 느림)로 전환하세요. `quantization` 설정을 추가하면 가중치가 추가로 줄어들며, 드라이버가 `transformer`와 `text_encoder`를 양자화 가능으로 표시하므로 4비트/8비트에서 가장 큰 이득을 얻습니다.
- **`true_cfg_scale` vs 속도**: `true_cfg_scale > 1.0`에서는 네거티브 프롬프트를 위한 추가 forward pass가 스텝마다 돌아가 추론 시간이 약 두 배가 됩니다. Edit-2509는 네거티브 프롬프트 가이던스에 맞춰 튜닝되어 기본값이 `4.0`입니다. `negative_prompt`가 필요 없을 때만 `1.0`으로 낮추세요.
- **멀티 레퍼런스 입력**: 정체성 보존 합성, 상품 배치, 의상 전이용으로 `image`를 JSON 배열로 전달하세요. Edit-2509는 레퍼런스 이미지 1-3장에 대해 검증되어 있으며, 더 긴 리스트도 허용되지만 품질이 떨어집니다.
- **다국어 지시문**: Qwen2.5-VL은 중국어, 한국어, 일본어, 영어 프롬프트를 네이티브로 처리하며 혼합 언어 프롬프트도 작동합니다.
- **출력**: 결과는 입력당 하나의 `.png`(배치 입력의 경우 리스트)이며 diffusion VAE에서 디코딩됩니다.
