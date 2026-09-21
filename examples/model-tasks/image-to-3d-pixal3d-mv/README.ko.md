# 멀티뷰 이미지-3D 모델 태스크 예제

이 예제는 model-compose의 내장 image-to-3d 태스크를 통해 Pixal3D의 MV 브랜치로 포즈가 있는 멀티뷰 이미지 리그에서 텍스처가 입혀진 GLB 메시를 생성하는 방법을 보여줍니다.

## 개요

단일뷰 Pixal3D 파이프라인은 입력 이미지의 카메라를 MoGe-2로 추정해야 하지만, 멀티뷰 버전은 같은 오브젝트의 포즈가 있는 여러 뷰를 한 번에 받습니다. 뷰별 `transform_matrix`와 `camera_angle_x` 값이 주어지면 파이프라인은 cascade denoiser 안에서 뷰들을 융합해 하나의 고품질 GLB를 출력합니다.

이 워크플로우는 로컬 멀티뷰 3D 자산 생성을 제공합니다:

1. **Pixal3D MV 파이프라인**: 단일뷰 Pixal3D와 동일한 HuggingFace 저장소에서 `ckpts/*_mv` 체크포인트를 `pipeline_mv.json`을 통해 로드합니다.
2. **포즈가 있는 뷰**: 각 입력 뷰는 이미지와 4x4 camera-to-world 매트릭스(NeRF/Blender 컨벤션: Z-up 월드, 카메라는 -Z 방향을 보며 +Y가 위)를 함께 가집니다. Frame 0은 canonical front view(`(0, -d, 0)`에 위치해 원점을 바라보고 월드 +Z가 위)이어야 하며, 그렇지 않으면 결과 메시가 그 뷰의 프레임에 맞춰 회전된 상태로 나옵니다.
3. **자동 매팅**: 알파 채널이 없는 뷰는 단일뷰 경로와 동일한 `briaai/RMBG-2.0` 모델로 매팅됩니다. 이미 non-opaque 알파 채널이 있는 뷰는 그대로 사용됩니다.
4. **PBR 텍스처**: 생성된 GLB에는 base colour, metallic, roughness 맵이 함께 구워져 있습니다.
5. **디테일 조절**: `resolution`(1024 또는 1536), `max_num_tokens`, 단계별 샘플링 스텝으로 메시 디테일 / 텍스처 품질 / VRAM·시간을 조율할 수 있습니다.

## 사전 준비

### 요구 사항

- model-compose가 PATH에서 실행 가능해야 합니다.
- CUDA GPU가 필요합니다. VRAM 요구량은 단일뷰 Pixal3D와 동일합니다 (1536에서 약 18 GB, `low_vram: true` + 1024에서 약 10-12 GB).
- CUDA 툴킷이 설치된 Linux 호스트가 필요합니다.
- Pixal3D의 rembg 단계가 사용하는 게이트된 `briaai/RMBG-2.0` 모델의 이용 약관을 수락한 HuggingFace 액세스 토큰이 필요합니다. `HF_TOKEN` 환경 변수로 설정하세요.

### 입력 형식

액션은 두 개의 병렬 배열과 공유 FOV를 기대합니다:

- **`image`**: 뷰 이미지 리스트. `i`번째 원소가 `i`번째 뷰의 이미지.
- **`transform_matrix`**: `image`와 병렬인 4x4 camera-to-world 매트릭스 리스트.
- **`camera_angle_x`**: 수평 FOV(라디안). 모든 뷰에서 공유되는 스칼라, 또는 뷰별 값이 담긴 `image`와 같은 길이의 리스트.
- **`mesh_scale`**: 카메라 거리 정규화용 전역 메시 스케일. 기본값 `1.0`.

Pixal3D에서 배포되는 데이터셋 컨벤션(눈높이 orbit, 방위각 0°/90°/180°/270°, 앙각 0°, 20° FOV)으로 렌더링된 뷰라면 transform은 다음과 같습니다:

```yaml
camera_angle_x: 0.349
transform_matrix:
  - [[ 1.0,  0.0,  0.0,  0.0],
     [ 0.0,  0.0, -1.0, -3.1192],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
  - [[ 0.0,  0.0,  1.0,  3.1192],
     [ 1.0,  0.0,  0.0,  0.0],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
  - [[-1.0,  0.0,  0.0,  0.0],
     [ 0.0,  0.0,  1.0,  3.1192],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
  - [[ 0.0,  0.0, -1.0, -3.1192],
     [-1.0,  0.0,  0.0,  0.0],
     [ 0.0,  1.0,  0.0,  0.0],
     [ 0.0,  0.0,  0.0,  1.0]]
```

### 환경 설정

1. 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/image-to-3d-pixal3d-mv
   ```

2. https://huggingface.co/briaai/RMBG-2.0 에서 `briaai/RMBG-2.0`의 라이선스를 수락하고, `.env.sample`을 복사해 토큰을 입력하세요:
   ```bash
   cp .env.sample .env
   # .env 파일에서 HF_TOKEN=hf_xxx 로 수정
   ```

3. 추론 속도를 희생하고 VRAM을 줄이려면 `model-compose.yml`에서 `low_vram: true`로 설정하세요. 텍스처 품질을 낮추고 속도를 얻으려면 `resolution: 1024`로 설정합니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행 시 Pixal3D 체크포인트(MV 브랜치 포함)를 내려받고 CUDA 커널을 컴파일합니다. 컨트롤러 준비 완료까지 수 분이 걸립니다.

2. **네 장의 orbit 뷰로 워크플로우 실행:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "front=@/path/to/front.png" \
     -F "right=@/path/to/right.png" \
     -F "back=@/path/to/back.png" \
     -F "left=@/path/to/left.png" \
     -F 'input={
       "image": ["@front", "@right", "@back", "@left"],
       "transform_matrix": [
         [[1,0,0,0],[0,0,-1,-3.1192],[0,1,0,0],[0,0,0,1]],
         [[0,0,1,3.1192],[1,0,0,0],[0,1,0,0],[0,0,0,1]],
         [[-1,0,0,0],[0,0,1,3.1192],[0,1,0,0],[0,0,0,1]],
         [[0,0,-1,-3.1192],[-1,0,0,0],[0,1,0,0],[0,0,0,1]]
       ],
       "camera_angle_x": 0.349
     }' \
     -o output.glb
   ```

## 구성 참조

### 컴포넌트 필드

| 필드         | 설명                                                                                                       | 기본값             |
|--------------|------------------------------------------------------------------------------------------------------------|--------------------|
| `task`       | `image-to-3d`이어야 합니다.                                                                                | —                  |
| `driver`     | `custom`이어야 합니다.                                                                                     | —                  |
| `family`     | `pixal3d-mv`이어야 합니다.                                                                                 | —                  |
| `model`      | Pixal3D 모델 저장소 (HuggingFace repo 또는 로컬 경로).                                                     | —                  |
| `device`     | 컴퓨트 디바이스. `cuda`로 해석되어야 합니다 — Pixal3D는 CPU / MPS 미지원.                                  | `auto`             |
| `low_vram`   | 스테이지별 모델을 CPU에 두고 필요할 때만 GPU로 옮김.                                                       | `false`            |
| `resolution` | 파이프라인 그리드 해상도 (`1024` 또는 `1536`).                                                             | (설명 참조)        |

### 액션 필드

| 필드                                  | 설명                                                                              | 기본값           |
|---------------------------------------|-----------------------------------------------------------------------------------|------------------|
| `image`                               | 뷰 이미지 리스트. 0번 원소는 canonical front view여야 합니다.                     | —                |
| `transform_matrix`                    | `image`와 병렬인 4x4 camera-to-world 매트릭스 리스트.                             | —                |
| `camera_angle_x`                      | 수평 FOV(라디안). 스칼라(공유) 또는 뷰별 리스트.                                   | —                |
| `mesh_scale`                          | 카메라 거리 정규화용 전역 메시 스케일.                                             | `1.0`            |
| `seed`                                | 재현성을 위한 시드. 미설정 시 호출마다 새로운 샘플.                               | (없음)           |
| `params.image_resolution`             | 전처리 중 사용되는 작업 이미지 해상도.                                             | `512`            |
| `params.ss_sampling_steps`            | Sparse-structure 확산 샘플 스텝.                                                   | `12`             |
| `params.ss_guidance_strength`         | Sparse-structure classifier-free guidance 강도.                                    | `7.5`            |
| `params.ss_guidance_rescale`          | Sparse-structure guidance rescale 계수.                                            | `0.7`            |
| `params.ss_rescale_t`                 | Sparse-structure 타임스텝 rescale 계수.                                            | `5.0`            |
| `params.shape_slat_sampling_steps`    | 형상 latent 샘플 스텝.                                                             | `12`             |
| `params.shape_slat_guidance_strength` | 형상 latent classifier-free guidance 강도.                                         | `7.5`            |
| `params.shape_slat_guidance_rescale`  | 형상 latent guidance rescale 계수.                                                 | `0.5`            |
| `params.shape_slat_rescale_t`         | 형상 latent 타임스텝 rescale 계수.                                                 | `3.0`            |
| `params.tex_slat_sampling_steps`      | 텍스처 latent 샘플 스텝.                                                           | `12`             |
| `params.tex_slat_guidance_strength`   | 텍스처 latent classifier-free guidance 강도.                                       | `1.0`            |
| `params.tex_slat_guidance_rescale`    | 텍스처 latent guidance rescale 계수.                                               | `0.0`            |
| `params.tex_slat_rescale_t`           | 텍스처 latent 타임스텝 rescale 계수.                                               | `3.0`            |
| `params.max_num_tokens`               | 스테이지당 최대 sparse 토큰 수.                                                    | `49152`          |
| `params.texture_size`                 | 베이크되는 텍스처 해상도(픽셀).                                                    | `4096`           |
| `params.decimation_target`            | GLB 내보내기 전 메시 데시메이션에서 노리는 목표 면 수.                              | `1000000`        |

## 참고사항

- **Frame 0이 메인 뷰**: 파이프라인은 `calc_mat_i = F @ inv(C_0) @ C_i`로 다른 모든 뷰를 canonical front pose에 스냅합니다. Frame 0 자체가 canonical front view가 아니면 리그 전체가 오브젝트를 기준으로 회전한 상태가 되어, 생성된 메시가 모델이 학습한 프레임과 다른 프레임으로 나옵니다.
- **`transform_matrix`와 `image`는 같은 길이**: DSL validator가 이를 강제합니다. `camera_angle_x`도 스칼라이거나 같은 길이의 리스트여야 합니다.
- **거리는 매트릭스 translation에서 유도됨**: 파이프라인은 `camera_distance`를 `‖transform_matrix[:, :3, 3]‖`로 계산합니다. 별도의 `distance` 필드는 없습니다.
- **좌표 컨벤션**: NeRF/Blender — Z-up 월드, 각 카메라는 자신의 -Z 방향을 보고 자신의 +Y가 위. 학습 렌더가 사용한 컨벤션과 동일하므로 데이터셋 `transforms.json`을 이 액션에 1:1로 매핑할 수 있습니다.
- **알파를 마스크로**: 이미 non-opaque 알파 채널이 있는 뷰는 rembg 단계를 건너뜁니다. 완전 불투명하거나 알파가 없는 경우 `briaai/RMBG-2.0`으로 자동 세그멘테이션이 실행됩니다.
- **첫 실행이 느립니다**: 단일뷰 Pixal3D와 동일한 셋업 비용이 발생합니다 — 격리된 virtualenv는 별도의 `.venv/pixal3d-mv` 디렉토리이지만, 같은 고정 의존성과 CUDA 확장을 설치합니다.
