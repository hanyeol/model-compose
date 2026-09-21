# 이미지-3D 모델 태스크 예제

이 예제는 model-compose의 내장 image-to-3d 태스크를 통해 HunyuanWorld-Mirror 2.0으로 이미지 세트에서 3D 씬(Gaussian splats, depth 기반 point cloud, 카메라 파라미터)을 재구성하는 방법을 보여줍니다.

## 개요

Pixal3D 계열이 이미지가 암시하는 형상을 *생성*하는 반면, WorldMirror는 이미지에 이미 담긴 지오메트리를 *재구성*합니다. 같은 씬의 포즈가 없는 이미지 세트를 입력하면 단 한 번의 feed-forward pass로 여러 정렬된 산출물을 한꺼번에 생성합니다.

이 워크플로우는 로컬 다중 이미지 3D 씬 재구성을 제공합니다:

1. **WorldMirror 2.0 파이프라인**: 통합된 WorldMirror 모델을 end-to-end로 실행합니다 — depth, normal, 카메라 포즈, point cloud, 3D Gaussian Splatting이 한 번의 forward pass로 모두 산출됩니다.
2. **한 번 호출, 여러 산출물**: 단일 요청이 결과 딕셔너리를 반환합니다 — Gaussian splats (`.ply`), point cloud (`.ply`), 카메라 파라미터(JSON), 그리고 선택적으로 뷰별 depth / normal 맵. `return_*` 플래그로 각 항목을 켜고 끕니다.
3. **선택적인 카메라 / depth prior**: 알려진 카메라 포즈(WorldMirror의 `camera_params.json` 스키마를 그대로 사용하는 JSON 파일) 또는 뷰별 depth 맵을 재구성 조건으로 주입할 수 있습니다. Prior는 순수한 conditioning 입력이라 생략해도 모델은 그대로 동작합니다.
4. **강건한 필터링**: 하늘 마스킹(ONNX + 모델 융합), depth/normal 불연속점 근처의 edge 필터링, 신뢰도 백분위 마스크로 point cloud와 Gaussian이 깔끔하게 유지됩니다.
5. **Point cloud / Gaussian 압축**: Voxel 병합과 구성 가능한 서브샘플링으로 point와 Gaussian 개수를 시각적 저하 없이 제한합니다.
6. **자동 모델 관리**: WorldMirror 2.0 체크포인트는 첫 실행 시 HuggingFace Hub에서 다운로드되어 로컬에 캐시됩니다.

## 사전 준비

### 요구 사항

- model-compose가 PATH에서 실행 가능해야 합니다.
- CUDA GPU가 필요합니다. 최대 VRAM은 대상 해상도와 `enable_bf16` 설정에 따라 달라집니다 — 기본 952픽셀 대상에 bf16을 켠 경우 대략 **12-16 GB**, 끄면 더 필요합니다. Apple Silicon(MPS)과 CPU 전용 추론은 현재 지원되지 않습니다 — WorldMirror의 op는 CUDA 전용입니다.
- CUDA 툴킷이 설치된 Linux 호스트가 필요합니다. 첫 실행 시 커스텀 `gsplat` 변형과 벤더링된 CUDA 확장을 컴파일하므로 런타임만으로는 부족합니다.
- `torch`, `gsplat`, `flash-attn` 등 WorldMirror의 부수 패키지를 설치할 수 있는 파이썬 환경이 필요합니다 — 첫 실행 시 자동으로 설치됩니다.
- `tencent/HY-World-2.0` 저장소를 읽을 수 있는 HuggingFace 액세스 토큰이 필요합니다. model-compose 실행 전 `HF_TOKEN` 환경 변수로 설정하세요.

### 로컬 3D 재구성의 장점

클라우드 재구성 서비스와 비교했을 때:

**로컬 처리의 장점:**
- **프라이버시**: 참조 이미지와 재구성된 지오메트리가 로컬을 벗어나지 않습니다.
- **비용**: 씬당 API 요금이 없습니다.
- **반복 실험**: 필터 임계값, 압축 목표, 산출물 선택을 호출마다 자유롭게 조정할 수 있습니다.
- **파이프라인 결합**: 다른 model-compose 태스크와 연결해(상류의 image-background-removal, 하류의 file-store, `.glb` 변환용 model-3d-converter 등) 촬영-투-자산 파이프라인을 구성할 수 있습니다.

**단점:**
- **하드웨어 요구**: CUDA GPU가 필수이며, 기본 해상도에서는 최소 12 GB VRAM이 편안한 기준입니다.
- **초기 실행 비용**: 파이프라인은 WorldMirror 체크포인트를 다운로드하고 CUDA 확장을 컴파일합니다 — 최초 실행 시 컨트롤러가 준비를 마치기까지 수 분이 걸립니다.
- **라이선스**: WorldMirror 2.0과 사용된 하위 모델 각각의 라이선스를 상업적 사용 전에 반드시 확인하세요.

### 환경 설정

1. 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/image-to-3d-world-mirror
   ```

2. `.env.sample`을 복사해 `tencent/HY-World-2.0`에 접근 가능한 HuggingFace 토큰을 입력하세요:
   ```bash
   cp .env.sample .env
   # .env 파일에서 HF_TOKEN=hf_xxx 로 수정
   ```

3. 수치 정밀도를 조금 희생하고 VRAM을 낮추려면 `model-compose.yml`에서 `enable_bf16: true`로 설정하세요. 사용하지 않는 예측 헤드는 `disable_heads`로 비활성화합니다(예: `disable_heads: [normal]`은 약 200M 파라미터를 해제).

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행 시 WorldMirror 체크포인트를 내려받고 CUDA 확장을 컴파일합니다. 컨트롤러 준비 완료까지 수 분이 걸립니다.

2. **뷰 세트로 워크플로우 실행:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "view0=@/path/to/view_00.png" \
     -F "view1=@/path/to/view_01.png" \
     -F "view2=@/path/to/view_02.png" \
     -F "view3=@/path/to/view_03.png" \
     -F 'input={"image": ["@view0", "@view1", "@view2", "@view3"]}'
   ```

   응답은 요청한 산출물이 담긴 JSON 객체입니다 — Gaussian splats와 point cloud가 `.ply` 스트림, 카메라 파라미터가 인라인 JSON 딕셔너리, 그리고 플래그가 켜졌다면 뷰별 depth / normal 이미지가 포함됩니다.

3. **이전 실행의 카메라 재사용** (WorldMirror의 `camera_params.json` 스키마이므로 한 호출의 반환 JSON을 다른 호출에 그대로 넣을 수 있음):
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "view0=@/path/to/view_00.png" \
     -F "view1=@/path/to/view_01.png" \
     -F 'input={"image": ["@view0", "@view1"], "prior_cameras": "/path/to/camera_params.json"}'
   ```

4. **지오메트리만 필요할 때 큰 산출물 스킵:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "view0=@/path/to/view_00.png" \
     -F "view1=@/path/to/view_01.png" \
     -F 'input={"image": ["@view0", "@view1"], "return_gaussians": false, "return_normal": false}'
   ```

## 구성 참조

### 컴포넌트 필드

| 필드           | 설명                                                                                                       | 기본값               |
|----------------|------------------------------------------------------------------------------------------------------------|----------------------|
| `task`         | `image-to-3d`이어야 합니다.                                                                                | —                    |
| `driver`       | `custom`이어야 합니다.                                                                                     | —                    |
| `family`       | `world-mirror`이어야 합니다.                                                                               | —                    |
| `model`        | WorldMirror 모델 저장소 (HuggingFace repo 또는 로컬 경로).                                                 | —                    |
| `subfolder`    | 저장소 안에서 WorldMirror 체크포인트가 있는 하위 폴더.                                                     | `HY-WorldMirror-2.0` |
| `device`       | 컴퓨트 디바이스. `cuda`로 해석되어야 합니다 — WorldMirror는 CPU / MPS 미지원.                              | `auto`               |
| `enable_bf16`  | 모델을 bfloat16으로 캐스팅해 VRAM을 낮춥니다(비-임계 레이어에서 약간의 정밀도 손실).                        | `false`              |
| `disable_heads`| 비활성화하고 메모리에서 해제할 예측 헤드. 옵션: `camera`, `depth`, `normal`, `points`, `gs`.                | `[]`                 |

### 액션 필드

| 필드                              | 설명                                                                                       | 기본값           |
|-----------------------------------|--------------------------------------------------------------------------------------------|------------------|
| `image`                           | 하나의 씬을 이루는 이미지 경로 / URL 리스트(또는 디렉토리 경로 하나).                     | —                |
| `priors.cameras`                  | 선택적 카메라 prior — WorldMirror의 `camera_params.json` 스키마를 따르는 JSON 파일 경로. | (없음)           |
| `priors.depths`                   | 선택적 depth prior — 뷰별 depth 맵(.npy / .exr / .png)이 담긴 디렉토리 경로.               | (없음)           |
| `return_gaussians`                | 결과에 3D Gaussian Splatting `.ply` 포함.                                                 | `true`           |
| `return_points`                   | 결과에 depth 기반 point cloud `.ply` 포함.                                                | `true`           |
| `return_cameras`                  | 결과에 카메라 extrinsics / intrinsics를 JSON 딕셔너리로 포함.                              | `true`           |
| `return_depth`                    | 결과에 뷰별 depth 맵 이미지 포함.                                                          | `false`          |
| `return_normal`                   | 결과에 뷰별 surface normal 맵 이미지 포함.                                                 | `false`          |
| `params.target_size`              | 추론 최대 해상도(긴 변). 이미지는 리사이즈 + 센터 크롭 후 14의 배수로 맞춰집니다.          | `952`            |
| `params.apply_sky_mask`           | Point cloud와 Gaussian에서 하늘 영역 필터링.                                              | `true`           |
| `params.apply_edge_mask`          | Depth / normal 불연속점 근처의 point 필터링.                                              | `true`           |
| `params.apply_confidence_mask`    | 예측 신뢰도가 낮은 하위 백분위 point 필터링.                                              | `false`          |
| `params.sky_mask_source`          | 하늘 마스크 소스: `auto`(ONNX + 모델), `model`, `onnx`.                                    | `auto`           |
| `params.model_sky_threshold`      | 모델 기반 하늘 감지 임계값.                                                                | `0.45`           |
| `params.confidence_percentile`    | `apply_confidence_mask`가 켜졌을 때 제거되는 하위 백분위.                                  | `10.0`           |
| `params.edge_normal_threshold`    | Normal edge 검출 관용도.                                                                   | `1.0`            |
| `params.edge_depth_threshold`     | Depth edge 검출 상대 관용도.                                                               | `0.03`           |
| `params.compress_pts`             | Depth 기반 point cloud를 voxel 병합 + 서브샘플링으로 압축.                                | `true`           |
| `params.compress_pts_max_points`  | Point cloud 압축 후 최대 point 수.                                                        | `2000000`        |
| `params.compress_pts_voxel_size`  | Point 병합에 사용하는 voxel 크기.                                                          | `0.002`          |
| `params.compress_gs_max_points`   | Voxel 프루닝 후 최대 Gaussian 수.                                                          | `5000000`        |
| `params.max_resolution`           | 저장되는 이미지 출력(depth / normal PNG)의 최대 해상도.                                    | `1920`           |

## 참고사항

- **첫 실행이 느립니다**: 최초 시작 시 격리된 `.venv/world-mirror` 환경을 만들고, WorldMirror의 고정된 의존성을 설치하고, 커스텀 `gsplat` 변형을 컴파일하고, WorldMirror 체크포인트를 다운로드합니다. 컨트롤러 준비까지 10-20분 정도 걸립니다. 이후 실행은 캐시된 venv와 산출물을 재사용합니다.
- **격리된 런타임**: 모델 워커는 전용 virtualenv(`runtime.type: virtualenv`, `path: .venv/world-mirror`)에서 실행되어 WorldMirror가 고정한 transformers / diffusers / cupy / open3d 버전이 컨트롤러의 site-packages와 충돌하지 않도록 합니다.
- **CUDA 필수**: WorldMirror는 CUDA 디바이스 배치와 CUDA 전용 커널을 하드코딩합니다. 드라이버는 CUDA가 아닌 호스트에서는 로딩을 거부합니다.
- **비디오 입력 미지원**: 이 예제는 이미지 세트만 받습니다. 소스가 비디오라면 상류에 `video-frame-extractor` 같은 컴포넌트를 두어 프레임으로 변환한 뒤 넣으세요.
- **카메라를 데이터로 다룸**: `return_cameras: true`이면 카메라 딕셔너리가 응답에 인라인으로 포함됩니다 — 파일은 쓰이지 않습니다. WorldMirror의 `camera_params.json`과 동일한 스키마이므로 반환된 dict을 `file-store` 컴포넌트로 저장한 뒤 나중에 `priors.cameras`로 다시 넣을 수 있습니다.
- **VRAM 계획**: `enable_bf16: true`는 모델의 activation 메모리를 대략 절반으로 줄여줍니다. `disable_heads`와 조합하는 것이 12 GB 카드에서 실행할 때의 주요 조정 지렛대입니다. 24 GB 이상이면 기본값으로 편안하게 돌아갑니다.
- **출력 활용**: `.ply` 파일은 MeshLab, Blender(애드온 필요), CloudCompare 그리고 대부분의 Gaussian splatting 뷰어에서 열립니다. Depth / normal PNG는 입력과 동일한 순서로 정렬된 뷰별 이미지입니다.
