# Camera Pose Estimator 예제

이 예제는 COLMAP 백엔드를 사용하는 `camera-pose-estimator` 컴포넌트를 시연하며, model-compose가 겹치는 사진들로부터 카메라 내부 파라미터와 이미지별 포즈를 복원하는 방식을 보여줍니다.

## 개요

이 워크플로우는 다음을 수행하는 Structure-from-Motion(SfM) 서비스를 제공합니다:

1. **특징점 추출 및 매칭**: 모든 입력 이미지에서 SIFT 키포인트를 검출하고 이미지 쌍 간에 매칭합니다.
2. **점진적 재구성**: 점진적 sparse 재구성을 번들 조정(bundle adjustment)하여 이미지별 카메라 포즈와 sparse 3D 포인트 클라우드를 생성합니다.
3. **COLMAP 포맷 워크스페이스**: `workspace_dir/sparse/0/`에 COLMAP 바이너리 포맷(`cameras.bin`, `images.bin`, `points3D.bin`)으로 결과를 기록하여, 다운스트림 작업(3D Gaussian Splatting 학습기, NeRF 파이프라인, 메쉬 추출기)이 별도 변환 없이 바로 소비할 수 있습니다.

두 개의 워크플로우가 제공되며, 각각 다른 입력 방식에 대응합니다:

- `estimate-from-images`: 이미지를 직접 전달합니다(비디오 프레임 추출기, 다운로더, 웹 스크레이퍼 등 업스트림 작업에서 오는 경우가 일반적). 워크스페이스는 자동으로 생성됩니다.
- `estimate-from-workspace`: 이미 `images/` 서브폴더를 포함한 워크스페이스를 지정합니다 — 표준 COLMAP 데이터셋이 배포되는 형태입니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- `pycolmap` 설치 (`pip install pycolmap`)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/media-processing/camera-pose-estimator
   ```

2. pycolmap 설치 확인:
   ```bash
   python -c "import pycolmap; print(pycolmap.__version__)"
   ```

3. `estimate-from-workspace` 흐름을 위한 테스트 데이터셋 준비. COLMAP 프로젝트에서 배포하는 작고 잘 동작하는 데이터셋으로 시작하는 것이 좋습니다:
   ```bash
   mkdir -p ./data
   curl -L -o ./data/gerrard-hall.zip https://demuc.de/colmap/datasets/gerrard-hall.zip
   unzip -q ./data/gerrard-hall.zip -d ./data
   ```
   데이터셋은 `./data/gerrard-hall/`로 압축 해제되며 `images/` 서브폴더를 포함합니다 — 이 폴더가 두 번째 워크플로우에서 바로 사용 가능한 워크스페이스입니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **업로드한 이미지 세트로 추정 (Web UI):**
   - Web UI 열기: http://localhost:8081
   - `estimate-from-images` 워크플로우 선택
   - 씬을 커버하는 이미지 파일들 업로드
   - "Run Workflow" 버튼 클릭

   **업로드한 이미지 세트로 추정 (API):**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/estimate-from-images/runs \
     -F "images=@scene/img_0001.jpg" \
     -F "images=@scene/img_0002.jpg" \
     -F "images=@scene/img_0003.jpg"
   ```

   **기존 워크스페이스로 추정 (CLI):**
   ```bash
   model-compose run estimate-from-workspace \
     --input '{"workspace_dir": "./data/gerrard-hall"}'
   ```

3. **결과 확인:**

   워크플로우는 `summary` JSON과 함께 `points` GLB(sparse cloud + 카메라 frustum)를 반환합니다. 웹 UI가 활성화되어 있으면 Gradio Model3D 뷰어가 GLB를 그대로 렌더링합니다:
   ```json
   {
     "summary": {
       "workspace_dir": "./data/gerrard-hall/sparse/0",
       "images_count": 100,
       "points_count": 15234,
       "cameras": [ { "id": 1, "model": "OPENCV", "width": 1920, "height": 1080, "params": [...] } ],
       "poses": [ { "image": "0001.jpg", "camera_id": 1, "quaternion": [qw, qx, qy, qz], "translation": [tx, ty, tz] } ]
     },
     "points": "<GLB 파일>"
   }
   ```

   전체 재구성 결과는 디스크의 `workspace_dir/sparse/0/`에 COLMAP 바이너리 포맷으로 저장됩니다. 하나 이상의 부분 재구성(partial reconstruction)이 생성된 경우, 추가 폴더(`sparse/1/`, `sparse/2/`, ...)가 확인용으로 남습니다.

## 컴포넌트 상세

### `estimator` — Camera Pose Estimator (COLMAP)

이미지 세트에 대해 COLMAP의 특징점 추출, 매칭, 점진적 매핑 파이프라인을 실행합니다.

주요 옵션:

- `camera_model` (기본값 `opencv`): 입력 이미지에 대해 가정할 COLMAP 카메라 모델. 왜곡이 미미한 사진은 `pinhole`, 어안 렌즈는 `opencv-fisheye` 또는 `radial-fisheye`, 캘리브레이션 정보가 없을 때는 `simple-pinhole` 사용.
- `matcher` (기본값 `exhaustive`): 이미지 쌍 선택 전략. `sequential`은 비디오에서 추출한 프레임에 훨씬 빠름(인접 프레임만 매칭); `spatial`은 GPS 메타데이터 사용.
- `single_camera` (기본값 `true`): 모든 입력 이미지가 하나의 물리적 카메라와 하나의 내부 파라미터 세트를 공유한다고 가정. 여러 소스가 섞인 데이터셋에서는 해제.
- `use_gpu` (기본값 `false`): SIFT 추출 및 매칭을 GPU로 처리. `pycolmap`이 CUDA 지원으로 빌드되어 있어야 함(일반 `pycolmap` wheel은 CPU 전용; Linux에서는 `pycolmap-cuda12` 사용).

### 액션 입력

- `images`: 하나의 씬(또는 씬들의 배치/스트림)을 구성하는 이미지들. 각 요소는 렌더링된 이미지이며, 일반적으로 업스트림 작업(`${jobs.frame-extractor.output}`)이나 업로드된 이미지 배열에서 전달됩니다.
- `workspace_dir`: COLMAP 워크스페이스를 담는 디렉토리(`images/`, `database.db`, `sparse/`). 생략 시 `.workspace/<component-id>/<run-id>/`가 사용됩니다. `images`까지 생략된 경우 `workspace_dir/images/`에 이미 있는 이미지들이 재사용됩니다.
- `images` 또는 `workspace_dir` 중 최소 하나(또는 둘 다)가 반드시 제공되어야 합니다.

### 액션 출력

- `return_cameras` (기본값 `true`): 복원된 카메라 내부 파라미터를 JSON 결과에 포함. 계산 비용이 미미하므로 HTTP 응답을 가볍게 유지할 필요가 있을 때만 끕니다.
- `return_poses` (기본값 `true`): 이미지별 world-from-camera 포즈를 JSON 결과에 포함. 계산 비용이 미미하므로 HTTP 응답을 가볍게 유지할 필요가 있을 때만 끕니다.
- `return_points` (기본값 `false`): sparse point cloud + 이미지별 카메라 frustum을 하나의 GLB로 묶어 `result["points"]`로 붙입니다. Gradio `Model3D` 뷰어 등 GLB 소비자에게 결과를 넘길 때 켭니다. 다운스트림 잡이 `workspace_dir`만 읽는 경우(3DGS 트레이너, 메쉬 추출기 등)에는 끄는 편이 좋습니다.
- `return_metadata` (기본값 `true`): 재구성 요약(`workspace_dir`, `images_count`, `points_count`)을 JSON 결과에 포함. 다운스트림이 워크스페이스 경로를 스스로 조합한다면 끕니다.

### 배치 / 스트리밍

`images`가 이미지 배열의 리스트나 스트림인 경우, 각 항목은 별도의 씬으로 취급되어 독립적으로 재구성됩니다. `workspace_dir`이 스칼라(또는 생략)일 때는 씬별 워크스페이스에 `-N` 접미사가 run-id에 붙습니다(`{run-id}-0/`, `{run-id}-1/`, ...) — 씬끼리 서로 덮어쓰지 않도록. `workspace_dir` 자체가 리스트나 스트림일 때는 각 항목이 `images`와 슬롯 단위로 zip되어 그대로 사용됩니다.

## 참고 사항

- 재구성 품질은 이미지 겹침에 크게 의존합니다. 인접 사진 간 최소 60% 겹침을 목표로 하고 씬을 여러 각도에서 촬영하세요.
- 특징이 부족한 표면(하얀 벽, 물, 유리, 균일한 잔디)은 SIFT가 처리하기 어렵고 부분적 또는 완전한 재구성 실패로 이어지기 쉽습니다.
- CPU 파이프라인은 ~100장 이미지 기준 최신 노트북에서 몇 분 정도 소요됩니다. 비디오 프레임의 경우 매칭 시간을 이미지 수에 선형으로 유지하기 위해 `matcher: sequential`을 사용하세요.
- 드라이버는 원본 이미지 바이트를 그대로 유지해 EXIF(초점 거리, GPS)를 보존합니다. 단, 이미지가 디코딩되지 않은 스트림 형태로 도착해야 합니다. 업스트림 단계에서 이미 PIL로 디코딩됐다면 드라이버가 받을 때는 이미 EXIF가 사라져 있고, `matcher: spatial`은 정렬할 GPS 정보가 없습니다. GPS 기반 매칭이 중요한 경우 파일을 디스크에 두고 `estimate-from-workspace`를 사용하세요.
