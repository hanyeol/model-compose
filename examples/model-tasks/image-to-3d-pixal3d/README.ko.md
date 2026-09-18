# 이미지-3D 모델 태스크 예제

이 예제는 model-compose의 내장 image-to-3d 태스크를 통해 Pixal3D로 단일 이미지에서 텍스처가 입혀진 GLB 메시를 생성하는 방법을 보여줍니다.

## 개요

이 워크플로우는 로컬 단일 이미지 3D 자산 생성을 제공합니다:

1. **로컬 Pixal3D 파이프라인**: Pixal3D의 sparse-structure / shape / texture flow-matching 단계를 외부 API 없이 end-to-end로 실행합니다.
2. **자동 카메라 추정**: MoGe-2 depth 모델이 입력 이미지의 카메라 FOV를 자동으로 추정합니다. 자동 추정 결과가 어색해 보이면 `manual_fov`(라디안)로 직접 지정하세요.
3. **PBR 텍스처**: 생성된 GLB에는 base colour, metallic, roughness 맵이 함께 구워져 있어 glTF 뷰어, Blender, Unreal 등 PBR을 지원하는 어느 렌더러에서도 곧바로 사용할 수 있습니다.
4. **디테일 조절**: `resolution`(1024 또는 1536), `max_num_tokens`, 각 단계별 샘플링 스텝으로 메시 디테일 / 텍스처 품질 / VRAM·시간을 조율할 수 있습니다.
5. **자동 모델 관리**: Pixal3D 가중치, MoGe-2 depth 모델, DINOv3 conditioning 가중치가 첫 실행 시 HuggingFace Hub에서 자동으로 내려받아 로컬에 캐시됩니다.

## 사전 준비

### 요구 사항

- model-compose가 PATH에서 실행 가능해야 합니다.
- CUDA GPU가 필요합니다. 최대 VRAM은 1536 해상도에서 약 **18 GB**, `low_vram: true` + 1024 해상도에서 약 **10-12 GB** 입니다. Apple Silicon(MPS)과 CPU는 지원하지 않습니다 — Pixal3D의 커널은 CUDA 전용입니다.
- CUDA 툴킷이 설치된 Linux 호스트가 필요합니다. 첫 실행 시 neighborhood attention 커널(natten)을 nvcc로 컴파일하므로 런타임만으로는 부족합니다.
- `torch`, `natten`, Pixal3D의 부수 패키지를 설치할 수 있는 파이썬 환경이 필요합니다 — 첫 실행 시 자동으로 설치됩니다.

### 로컬 이미지-3D의 장점

클라우드 3D 생성 서비스와 비교했을 때:

**로컬 처리의 장점:**
- **프라이버시**: 참조 이미지와 생성된 자산이 로컬을 벗어나지 않습니다.
- **비용**: 생성 건당 API 요금이 없습니다.
- **반복 실험**: 샘플러 스텝, 텍스처 크기, 카메라 FOV를 호출마다 자유롭게 조정할 수 있습니다.
- **파이프라인 결합**: image-background-removal, file-store 같은 다른 model-compose 태스크와 연결해 end-to-end 3D 자산 파이프라인을 구성할 수 있습니다.

**단점:**
- **하드웨어 요구**: CUDA GPU가 필수. `low_vram: true` 기준 최소 10 GB, 풀 디테일 모드는 18 GB 이상 VRAM이 필요합니다.
- **초기 실행 비용**: 파이프라인은 약 15 GB의 가중치를 다운로드하고 CUDA 커널을 컴파일합니다 — 최초 실행 시 컨트롤러가 준비를 마치기까지 수 분이 걸립니다.
- **라이선스**: Pixal3D와 사용된 하위 모델 각각의 라이선스를 상업적 사용 전에 반드시 확인하세요.

### 환경 설정

1. 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/image-to-3d-pixal3d
   ```

2. 추가 환경 설정이 필요하지 않습니다 — Pixal3D 체크포인트(`TencentARC/Pixal3D`), MoGe-2 depth 모델(`Ruicheng/moge-2-vitl`), DINOv3 conditioning 가중치(`camenduru/dinov3-vitl16-pretrain-lvd1689m`)는 첫 실행 시 HuggingFace Hub에서 다운로드되어 `~/.cache/huggingface/`에 캐시됩니다.

3. 추론 속도를 희생하고 VRAM을 줄이려면 `model-compose.yml`에서 `low_vram: true`로 설정하세요. 텍스처 품질을 낮추고 속도를 얻으려면 `resolution: 1024`로 설정합니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행 시 약 15 GB의 가중치를 내려받고 CUDA 커널을 컴파일합니다. 컨트롤러 준비 완료까지 수 분이 걸립니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 이미지에서 기본 설정으로 GLB 생성
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img"}' \
     -o output.glb

   # 시드 고정으로 재현 가능한 샘플링
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "seed": 42}' \
     -o output.glb

   # MoGe가 잘못 추정하는 경우 카메라 FOV 수동 지정 (0.2 rad ≈ 11.5°, 좁은 렌즈)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "manual_fov": 0.2}' \
     -o output.glb

   # 고품질 텍스처 (8K 베이크) + 스테이지별 샘플 스텝 확대
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "texture_size": 8192, "shape_slat_sampling_steps": 24, "tex_slat_sampling_steps": 24}' \
     -o output.glb
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `image`를 업로드 (깨끗한 배경의 피사체가 가장 잘 나옵니다 — Pixal3D가 배경을 자동으로 제거하지만 배경이 복잡하면 포즈 추정에 영향을 줍니다)
   - 필요하면 `seed`로 재현성을 확보하거나 자동 카메라가 어색해 보일 때 `manual_fov`를 지정
   - "Run Workflow" 클릭 → `.glb` 파일 수신

## 구성 참조

### 컴포넌트 필드

| 필드         | 설명                                                                                                       | 기본값             |
|--------------|------------------------------------------------------------------------------------------------------------|--------------------|
| `task`       | `image-to-3d`이어야 합니다.                                                                                | —                  |
| `driver`     | `custom`이어야 합니다.                                                                                     | —                  |
| `family`     | `pixal3d`이어야 합니다.                                                                                    | —                  |
| `model`      | Pixal3D 모델 저장소 (HuggingFace repo 또는 로컬 경로).                                                     | —                  |
| `device`     | 컴퓨트 디바이스. `cuda`로 해석되어야 합니다 — Pixal3D는 CPU / MPS 미지원.                                  | `auto`             |
| `low_vram`   | 스테이지별 모델을 CPU에 두고 필요할 때만 GPU로 옮김. 최대 VRAM을 약 10-12 GB로 낮춥니다.                    | `false`            |
| `resolution` | 파이프라인 그리드 해상도 (`1024` 또는 `1536`). 미설정 시 low-VRAM 모드는 `1024`, 아니면 `1536`이 기본.      | (설명 참조)        |

### 액션 필드

| 필드                                  | 설명                                                                              | 기본값           |
|---------------------------------------|-----------------------------------------------------------------------------------|------------------|
| `image`                               | 입력 이미지 (또는 이미지 리스트/스트림).                                          | —                |
| `seed`                                | 재현성을 위한 시드. 미설정 시 호출마다 새로운 샘플.                               | (없음)           |
| `batch_size`                          | 입력이 리스트/스트림일 때 한 번에 처리할 개수.                                    | `1`              |
| `params.manual_fov`                   | 카메라 FOV(라디안). 미설정 시 MoGe-2가 자동 추정.                                 | (자동 추정)      |
| `params.mesh_scale`                   | 카메라 거리 계산에 사용하는 목표 메시 스케일.                                      | `1.0`            |
| `params.image_resolution`             | 카메라 추정 시 사용하는 작업 이미지 해상도.                                        | `512`            |
| `params.ss_sampling_steps`            | Sparse-structure 확산 샘플 스텝 (거친 복셀 배치).                                  | `12`             |
| `params.ss_guidance_strength`         | Sparse-structure classifier-free guidance 강도.                                    | `7.5`            |
| `params.ss_guidance_rescale`          | Sparse-structure guidance rescale 계수.                                            | `0.7`            |
| `params.ss_rescale_t`                 | Sparse-structure 타임스텝 rescale 계수.                                            | `5.0`            |
| `params.shape_slat_sampling_steps`    | 형상 latent 샘플 스텝 (지오메트리 정제).                                            | `12`             |
| `params.shape_slat_guidance_strength` | 형상 latent classifier-free guidance 강도.                                          | `7.5`            |
| `params.shape_slat_guidance_rescale`  | 형상 latent guidance rescale 계수.                                                 | `0.5`            |
| `params.shape_slat_rescale_t`         | 형상 latent 타임스텝 rescale 계수.                                                 | `3.0`            |
| `params.tex_slat_sampling_steps`      | 텍스처 latent 샘플 스텝 (PBR colour / metallic / roughness).                        | `12`             |
| `params.tex_slat_guidance_strength`   | 텍스처 latent classifier-free guidance 강도.                                        | `1.0`            |
| `params.tex_slat_guidance_rescale`    | 텍스처 latent guidance rescale 계수.                                                | `0.0`            |
| `params.tex_slat_rescale_t`           | 텍스처 latent 타임스텝 rescale 계수.                                                | `3.0`            |
| `params.max_num_tokens`               | 스테이지당 최대 sparse 토큰 수. 크게 잡을수록 지오메트리가 세밀해지고 VRAM도 커집니다. | `49152`          |
| `params.texture_size`                 | GLB 내보내기 시 베이크되는 텍스처 해상도(픽셀).                                    | `4096`           |
| `params.decimation_target`            | GLB 내보내기 전 메시 데시메이션에서 노리는 목표 면 수.                              | `1000000`        |

## 참고사항

- **첫 실행이 느립니다**: 최초 시작 시 격리된 `.venv/pixal3d` 환경을 만들고, Pixal3D의 고정된 의존성을 설치하고, neighborhood attention CUDA 커널(natten)을 컴파일하고, 약 15 GB의 가중치를 내려받습니다. 컨트롤러 준비까지 20-30분 정도 걸립니다. 이후 실행은 캐시된 venv와 산출물을 재사용합니다.
- **격리된 런타임**: 모델 워커는 전용 virtualenv(`runtime.type: virtualenv`, `path: .venv/pixal3d`)에서 실행됩니다. Pixal3D가 하드핀한 transformers / diffusers / kornia 버전이 컨트롤러의 site-packages와 충돌하지 않도록 하기 위해서입니다. 컨트롤러의 native 환경에서는 드라이버가 로딩을 거부합니다.
- **CUDA 필수**: Pixal3D는 CUDA 디바이스 배치와 CUDA 전용 커널을 하드코딩합니다. 드라이버는 CUDA가 아닌 호스트에서는 무너진 경로로 폴백하지 않고 즉시 로딩을 거부합니다.
- **VRAM 계획**: `low_vram: true`는 최대 VRAM(~10-12 GB)을 대기 시간(약 2-3배 느림)과 맞바꿉니다. `resolution: 1536` 표준 모드에서는 최대 VRAM이 약 18 GB로, A100 40GB나 RTX 6000 Ada가 편안하게 처리합니다.
- **카메라 FOV**: 자동 추정 결과가 이상해 보이면(피사체가 유난히 늘어지거나 눌린 느낌) `manual_fov`로 직접 지정하세요. `0.2`(좁은 렌즈, 약 11.5°)에서 시작해 `~0.05`씩 조정합니다.
- **배경 견고성**: Pixal3D는 배경을 자동으로 제거하는 전처리 단계를 포함하지만, 피사체가 프레임 가장자리에 붙거나 심하게 가려진 경우 지오메트리가 왜곡될 수 있습니다. 자동 전처리가 깔끔하지 않으면 `image-background-removal`을 상류에 배치하는 것도 방법입니다.
- **샘플러 튜닝**: 스테이지당 기본 12 스텝은 균형이 좋습니다. 최종 자산에서는 shape / texture 스텝을 24로 올리는 게 유리하며, sparse-structure 스텝은 추가 이득이 상대적으로 적습니다.
- **출력**: 입력당 `.glb` 파일 1개(또는 배치 입력에 대한 리스트)를 반환합니다. glTF 호환 뷰어(`<model-viewer>`, Blender, three.js, Unity의 glTFast 등)에서 곧바로 열립니다.
