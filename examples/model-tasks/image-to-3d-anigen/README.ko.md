# 이미지-리그드-3D 모델 작업 예제

이 예제는 model-compose의 내장 image-to-3d 작업을 통해 AniGen으로 단일 이미지에서 뼈대와 스키닝 가중치가 포함된 리그드 GLB 메시와, 스켈레톤만 시각화한 별도 GLB를 함께 생성하는 방법을 보여줍니다.

## 개요

이 워크플로는 로컬 단일 이미지 애니메이션 가능 3D 자산 생성을 제공합니다:

1. **로컬 AniGen 파이프라인**: AniGen의 sparse-structure와 structured-latent flow-matching 단계를 처음부터 끝까지 실행 — 외부 API 사용 안 함.
2. **리그드 메시**: 출력 GLB에 본, 계층적 부모, 정점별 스키닝 가중치가 표준 glTF skinned-mesh로 구워져 있음 — Blender, Unity, Unreal, three.js에 바로 넣어 임의의 모션 클립으로 구동 가능.
3. **스켈레톤 시각화**: 예측된 스켈레톤을 눈에 보이는 뼈로 렌더링한 두 번째 GLB — 리그드 메시로 확정하기 전에 관절 배치를 디버깅할 때 유용.
4. **설정 가능한 샘플링**: 단계별 CFG 스케일, 샘플링 스텝, 관절 밀도, 텍스처 크기로 리그 정확도 / 메시 디테일 / VRAM / 시간을 자유롭게 조율.
5. **자동 모델 관리**: AniGen 가중치(SS-Flow + SLAT-Flow + DAE + DINOv2 + DSINE + VGG)를 첫 실행 시 HuggingFace Hub에서 다운로드하고 로컬에 캐시.

## 준비

### 사전 요구 사항

- model-compose가 설치되어 PATH에 있음.
- **VRAM 18 GB 이상**의 CUDA GPU (업스트림에서 A800, RTX 3090, RTX 4090, A100 동작 확인). Apple Silicon(MPS)과 CPU-only 추론은 지원하지 않음 — AniGen 커널이 CUDA-only.
- CUDA 툴킷(11.8 또는 12.x)이 설치된 Linux 호스트. 첫 실행에서 pytorch3d와 nvdiffrast를 nvcc로 빌드하므로 런타임만이 아닌 툴킷이 필요.
- `torch`, `spconv`, `pytorch3d`, `nvdiffrast` 등 AniGen 부속 패키지를 설치할 수 있는 Python 환경 — 첫 실행 시 자동 설치.

### 왜 로컬 리그드-3D 생성인가

클라우드 호스팅 3D-with-rig 서비스와 비교했을 때:

**로컬 처리의 장점:**
- **프라이버시**: 참조 이미지와 생성 자산이 기기 밖으로 나가지 않음.
- **비용**: 생성당 API 비용 없음.
- **반복성**: 샘플링 스텝, CFG 스케일, 관절 밀도, 스키닝 스무딩을 호출마다 자유롭게 조율.
- **파이프라인 친화적**: 다른 model-compose 작업(상류의 image-background-removal, 하류의 file-store 등)과 조합해 리그드 자산 파이프라인 구성 가능.

**절충점:**
- **하드웨어 요구사항**: VRAM 18 GB의 CUDA GPU 필수.
- **첫 실행 비용**: AniGen HuggingFace 스냅샷(SS-Flow / SLAT-Flow / DAE / 보조 모델 합쳐 10 GB 이상) 다운로드와 CUDA 커널 컴파일 — 컨트롤러가 준비 완료를 보고할 때까지 20-30분 소요.
- **라이선스**: AniGen과 각 구성 모델이 자체 라이선스를 가짐. 업스트림 저장소는 `extensions/CUBVH/`를 비상업적/연구용으로 표시(추론이 아닌 학습에만 관련). 상용 사용 전 검토 요망.

### 환경 설정

1. 이 예제 디렉터리로 이동:
   ```bash
   cd examples/model-tasks/image-to-3d-anigen
   ```

2. HuggingFace 토큰은 기본적으로 필요 없음 — `VAST-AI/AniGen` 스냅샷은 공개 다운로드. 인증 미러 뒤에 호스팅한다면 평소처럼 `.env`에 `HF_TOKEN`을 설정.

3. `model-compose.yml`에서 SS-Flow / SLAT-Flow 변형 선택:
   - `ss_variant: solo` (기본) — 정확한 지오메트리, 대부분의 입력에 잘 동작
   - `ss_variant: duet` — 더 자세한 스켈레톤(손가락 등), 지오메트리는 조금 부드러움
   - `ss_variant: epic` — 균형
   - `slat_variant: auto` (기본) — 네트워크가 관절 수를 스스로 결정
   - `slat_variant: control` — 관절 수가 `params.joints_density` (0-4)를 따름

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행은 AniGen HF 스냅샷 다운로드와 CUDA 커널 컴파일이 필요. 컨트롤러 준비까지 20-30분 예상.

2. **워크플로 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 이미지 하나에서 리그드 메시와 스켈레톤 생성
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img"}' \
     -o response.json

   # 시드 고정으로 재현 가능한 샘플링
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "seed": 42}' \
     -o response.json

   # 스텝 수를 늘리고 SLAT 가이던스를 강화한 고품질 샘플링
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "ss_steps": 50, "slat_steps": 50, "cfg_scale_slat": 4.0}' \
     -o response.json

   # 더 촘촘한 스켈레톤 (`slat_variant: control`일 때만 의미 있음)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.png" \
     -F 'input={"image": "@img", "joints_density": 3}' \
     -o response.json
   ```

   응답은 두 개의 GLB 리소스(`mesh` — 리그드 메시, `skeleton` — 스켈레톤 시각화)를 참조하는 JSON 객체이며, 반환된 URL로 스트리밍 또는 다운로드 가능.

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `image` 업로드 (깔끔한 배경의 피사체가 최적 — AniGen이 자동으로 배경을 제거)
   - 재현성을 원하면 `seed` 설정
   - "Run Workflow" 클릭으로 `mesh.glb`와 `skeleton.glb`를 함께 수신

## 설정 참조

### 컴포넌트 필드

| 필드           | 설명                                                                                                    | 기본값  |
|----------------|--------------------------------------------------------------------------------------------------------|---------|
| `task`         | `image-to-3d`이어야 함.                                                                                | —       |
| `driver`       | `custom`이어야 함.                                                                                     | —       |
| `family`       | `anigen`이어야 함.                                                                                     | —       |
| `model`        | AniGen 모델 저장소 (HuggingFace 저장소 또는 로컬 경로).                                                 | —       |
| `device`       | 연산 장치. `cuda`로 해결되어야 함 — AniGen은 CPU/MPS 미지원.                                            | `auto`  |
| `ss_variant`   | SS-Flow 체크포인트 변형 (`solo`, `epic`, `duet`).                                                       | `solo`  |
| `slat_variant` | SLAT-Flow 체크포인트 변형 (`auto`, `control`).                                                          | `auto`  |

### 액션 필드

| 필드                               | 설명                                                                                          | 기본값  |
|------------------------------------|-----------------------------------------------------------------------------------------------|---------|
| `image`                            | 입력 이미지 (또는 이미지 리스트/스트림).                                                     | —       |
| `seed`                             | 재현성을 위한 난수 시드. 미지정 시 호출마다 새 샘플.                                          | (없음)  |
| `batch_size`                       | 입력이 리스트/스트림일 때 배치당 처리 수.                                                     | `1`     |
| `return_mesh`                      | 결과에 리그드 메시 GLB 포함.                                                                 | `true`  |
| `return_skeleton`                  | 결과에 스켈레톤 시각화 GLB 포함.                                                             | `true`  |
| `return_image`                     | 결과에 배경 제거된 조건 이미지 포함.                                                          | `false` |
| `params.cfg_scale_ss`              | Sparse-structure classifier-free guidance 스케일.                                            | `7.5`   |
| `params.cfg_scale_slat`            | Structured-latent classifier-free guidance 스케일.                                           | `3.0`   |
| `params.ss_steps`                  | Sparse-structure flow-matching 샘플링 스텝.                                                   | `25`    |
| `params.slat_steps`                | Structured-latent flow-matching 샘플링 스텝.                                                  | `25`    |
| `params.joints_density`            | 관절 밀도 수준 (0-4) — `slat_variant: control`에서만 사용.                                    | `1`     |
| `params.simplify_ratio`            | 후처리 단계의 메시 단순화 비율.                                                              | `0.95`  |
| `params.fill_holes`                | 후처리 시 홀 채움 여부.                                                                       | `true`  |
| `params.no_smooth_skin_weights`    | 스키닝 가중치 스무딩 비활성.                                                                  | `false` |
| `params.smooth_skin_weights_iters` | 스키닝 가중치 스무딩 반복 횟수.                                                              | `100`   |
| `params.smooth_skin_weights_alpha` | 스키닝 가중치 스무딩 알파.                                                                    | `1.0`   |
| `params.no_filter_skin_weights`    | 메시 스키닝 가중치의 지오데식 필터링 비활성.                                                   | `false` |
| `params.texture_size`              | 베이크된 텍스처 크기 (픽셀). `0`이면 텍스처 베이킹 비활성.                                     | `1024`  |

## 노트

- **첫 실행은 느림**: 첫 시작 시 `.venv/anigen` 격리 환경 생성, AniGen 고정 의존성 설치, pytorch3d / nvdiffrast 컴파일, AniGen HF 스냅샷 다운로드가 이루어짐. 컨트롤러 준비까지 20-30분 예상. 이후 실행은 캐시된 venv와 아티팩트 재사용.
- **격리 런타임**: 모델 워커가 전용 virtualenv(`runtime.type: virtualenv`, `path: .venv/anigen`)에서 실행되어 AniGen의 torch 2.4/2.5 고정과 CUDA 확장이 컨트롤러의 site-packages와 충돌하지 않음. 드라이버는 컨트롤러의 네이티브 환경에서 실행을 거부.
- **CUDA 필수**: AniGen이 CUDA 장치 배치와 CUDA-only 커널을 하드코딩. 드라이버는 비-CUDA 호스트에서 조용히 깨진 경로로 폴백하는 대신 로딩을 거부.
- **두 개의 GLB 출력**: 워크플로는 `mesh`(리그드, 스키닝, 텍스처링)와 `skeleton`(뼈만 시각화)을 노출. 리그드 메시만 필요하면 `return_skeleton: false`. 배경 제거된 조건 이미지도 함께 받으려면 `return_image: true`.
- **변형 절충**: `ss_variant: solo`는 정확한 지오메트리 우선(README 기본 권장). 피사체에 미세 관절(손가락, 복잡한 기계류)이 있으면 `duet`로 전환. 결정적인 관절 수가 필요할 때만 `slat_variant: control` + `params.joints_density`; 기본 `auto`는 피사체별로 합리적인 값을 선택.
- **배경 견고성**: AniGen이 전처리 단계에서 자동으로 배경을 제거하지만 프레임 가장자리에 닿거나 심하게 가려진 피사체는 왜곡된 지오메트리를 낳을 수 있음. 자동 전처리가 깔끔하지 않으면 상류에 `image-background-removal`을 두는 것을 고려.
- **샘플러 튜닝**: 단계당 기본 25 스텝은 품질과 속도의 균형. 최종 자산은 `ss_steps`와 `slat_steps`를 모두 50으로 상향; 추가 `ss_steps`보다 추가 `slat_steps`의 효과가 큼.
- **출력**: 각 결과는 `return_*` 플래그에 따라 `mesh`, `skeleton`, `image` 필드를 담음. 모든 glTF 호환 뷰어(`<model-viewer>`, Blender, three.js, Unity의 glTFast)가 GLB 파일을 바로 로딩하고 리그를 기성 모션 클립으로 재생 가능.
