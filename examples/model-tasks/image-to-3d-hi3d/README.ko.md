# 이미지-3D 메시 리파인먼트 예제

이 예제는 model-compose의 내장 `image-to-3d` 태스크를 통해 **Hi3D v1.0**(Sparc3D 기반)으로 거친 3D 메시를 고해상도 지오메트리로 다듬는 방법을 보여줍니다.

## 개요

Hi3D v1.0은 생성 모델이 아니라 **리파인먼트** 모델입니다. 각 요청은 참조 이미지와 상위 단계에서 생성된 입력 메시를 함께 받고, Hi3D가 이미지의 실루엣에 맞춰 지오메트리를 다듬습니다. 출력은 지오메트리만 포함된 GLB(텍스처·머티리얼·버텍스 컬러 없음)입니다.

이 워크플로우는 다음을 제공합니다:

1. **참조 이미지 조건부 리파인먼트**: flow-matching 스택이 입력 메시를 1024³ (또는 1536³) sparse 추출 그리드로 업그레이드하며, DINOv2 + CLIP 피처로 참조 이미지에 정렬합니다.
2. **입력 메시 소스 자유**: trimesh가 읽을 수 있는 어떤 포맷이든 사용 가능합니다(GLB, OBJ, PLY, STL). 임의의 upstream image-to-3d 컴포넌트(`pixal3d`, `world-mirror`, Hunyuan3D-2 mini 등)로 생성한 메시를 사용할 수 있습니다.
3. **자동 모델 관리**: Hi3D 체크포인트(`hi3d-official/Hi3Dv1.0`)는 첫 실행 시 HuggingFace Hub에서 자동 다운로드되고, DINOv2·CLIP도 파이프라인이 첫 사용 시점에 함께 받아옵니다.

## 사전 준비

### 요구 사항

- model-compose가 PATH에서 실행 가능해야 합니다.
- compute capability **8.0 이상**(Ampere 세대 이후)의 CUDA GPU가 필요합니다. CPU, MPS(Apple Silicon), AMD ROCm은 지원하지 않습니다 — Hi3D의 spconv/flash-attention 커널은 CUDA 전용입니다.
- **CUDA 툴킷 12.0–12.5**가 설치된 Linux 호스트가 필요합니다. 파이프라인이 설치된 nvcc를 기반으로 spconv와 flash-attn을 빌드하므로 CUDA 버전이 맞지 않으면 설치 단계에서 실패합니다.
- `torch==2.5.0`, `flash-attn==2.7.4.post1`, `spconv-cu120==2.3.6`, Hi3D의 `sparc3d` 패키지를 설치할 수 있는 파이썬 환경이 필요합니다 — 첫 실행 시 격리된 `.venv/hi3d`에 자동 설치됩니다.
- Upstream에서 입력 메시를 공급해야 합니다. 아래 [입력 메시 생성](#입력-메시-생성) 섹션을 참고하세요.

### 라이선스

Hi3D v1.0은 Apache나 MIT가 아니라 **Hi3D Open License Agreement v1.0** 하에 배포됩니다. 상업적 사용은 가능하지만 제품의 **월간 활성 사용자가 20만 명을 초과**하거나 **월 매출이 100만 달러를 초과**하면 별도 라이선스가 필요합니다. 배포 전에 [Hi3D v1.0 저장소](https://github.com/hi3d-official/Hi3Dv1.0)에서 조항을 확인하세요.

### 입력 메시 생성

Hi3D는 생성 모델이 아니라 리파이너입니다. 임의의 image-to-3d 결과물을 `mesh` 입력으로 연결하세요:

- **`image-to-3d-pixal3d`** — 약 1k face의 PBR GLB을 생성합니다. 결과 `.glb`를 그대로 전달하면 됩니다.
- **`image-to-3d-world-mirror`** — 씬·환경용. `points.ply`를 바로 쓰거나 변환기로 메시를 추출하세요.
- **Hunyuan3D-2 mini** — Hi3D 공식 파이프라인이 추천하는 upstream입니다. 별도의 model-compose 컴포넌트로 포팅하거나 Hi3D 저장소의 `demo/coarse_stage.py`를 수동으로 실행하세요.

입력 메시가 깔끔하거나 watertight일 필요는 없습니다 — 실루엣이 참조 이미지와 어느 정도 맞기만 하면 Hi3D의 리파인먼트가 토폴로지 아티팩트를 상당 부분 흡수합니다.

### 환경 설정

1. 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/image-to-3d-hi3d
   ```

2. (선택) HuggingFace 계정이 요청 수 제한에 걸린다면 `HF_TOKEN`을 설정하세요:
   ```bash
   export HF_TOKEN=hf_xxx
   ```
   `hi3d-official/Hi3Dv1.0`, `facebook/dinov2-large`, `openai/clip-vit-large-patch14` 는 모두 공개 저장소이므로 토큰이 필수는 아닙니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행 시 `.venv/hi3d`를 생성하고 Hi3D의 핀 고정 의존성 설치, 로컬 CUDA 툴킷으로 spconv/flash-attn 빌드, Hi3D 체크포인트와 DINOv2·CLIP 다운로드(총 ~10 GB)를 수행합니다. 컨트롤러 준비 완료까지 10-20분이 걸립니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 참조 이미지로 입력 메시를 리파인
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/reference.png" \
     -F "src=@/path/to/coarse.glb" \
     -F 'input={"image": "@img", "mesh": "@src"}' \
     -o refined.glb

   # 시드 고정으로 재현 가능한 리파인먼트
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/reference.png" \
     -F "src=@/path/to/coarse.glb" \
     -F 'input={"image": "@img", "mesh": "@src", "seed": 0}' \
     -o refined.glb

   # 고해상도 리파인먼트(1536 그리드) — 더 선명한 지오메트리, 더 많은 VRAM
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/reference.png" \
     -F "src=@/path/to/coarse.glb" \
     -F 'input={"image": "@img", "mesh": "@src", "resolution": 1536}' \
     -o refined.glb
   ```

   **Web UI 사용:**
   - Web UI 접속: http://localhost:8081
   - 참조 `image`와 `mesh`(GLB/OBJ/PLY/STL)를 업로드
   - 선택적으로 `seed`, `resolution`(512 / 1024 / 1536), `num_inference_steps`를 설정
   - "Run Workflow" 클릭 시 리파인된 `.glb` 파일을 받습니다

## 설정 레퍼런스

### 컴포넌트 필드

| 필드     | 설명                                                                      | 기본값  |
|----------|---------------------------------------------------------------------------|---------|
| `task`   | `image-to-3d` 로 고정.                                                    | —       |
| `driver` | `custom` 으로 고정.                                                       | —       |
| `family` | `hi3d` 로 고정.                                                           | —       |
| `model`  | Hi3D v1.0 모델 저장소(HuggingFace repo 또는 로컬 경로).                   | —       |
| `device` | 컴퓨트 디바이스. `cuda`로 해석되어야 함 — CPU·MPS 미지원.                 | `auto`  |

### 액션 필드

| 필드                        | 설명                                                                                          | 기본값  |
|-----------------------------|-----------------------------------------------------------------------------------------------|---------|
| `image`                     | 참조 이미지(단일, 리스트, 또는 스트림).                                                       | —       |
| `mesh`                      | 리파인할 입력 메시(trimesh가 읽을 수 있는 어떤 포맷이든: GLB, OBJ, PLY, STL).                 | —       |
| `seed`                      | 재현 가능한 리파인먼트를 위한 랜덤 시드.                                                      | `0`     |
| `batch_size`                | 입력이 리스트·스트림일 때 배치당 처리할 아이템 수.                                            | `1`     |
| `params.resolution`         | sparse 추출 그리드 해상도. `512`, `1024`, `1536` 중 하나.                                     | `1024`  |
| `params.num_inference_steps`| flow-matching 리파인먼트 스텝 수.                                                             | `25`    |

## 참고 사항

- **리파인먼트 전용**: Hi3D는 이미지만으로는 실행되지 않습니다. `mesh`를 생략하면 생성 중이 아니라 요청 시점에 즉시 검증 오류가 발생합니다.
- **지오메트리만 출력**: 결과 GLB에는 버텍스 위치와 face만 포함되며 텍스처·노멀·머티리얼·버텍스 컬러는 생성되지 않습니다. 필요하다면 upstream 텍스처링 파이프라인으로 보완하세요.
- **초기 실행이 느림**: 첫 실행 시 venv 준비, extension 빌드(spconv, flash-attn), 가중치 다운로드로 10-20분이 소요됩니다. 이후 실행은 캐시된 venv와 아티팩트를 재사용합니다.
- **격리 런타임**: 모델 워커가 `.venv/hi3d`에서 실행되므로 Hi3D의 핀 고정(`torch==2.5.0`, `flash-attn==2.7.4.post1`, `spconv-cu120==2.3.6`)이 컨트롤러의 site-packages와 충돌하지 않습니다. 드라이버는 컨트롤러 환경에서의 실행을 거부합니다.
- **CUDA 필수**: Hi3D는 CUDA 디바이스 배치를 하드코딩하고 CUDA 12.0–12.5용으로 컴파일된 spconv 커널에 의존합니다. 비-CUDA 환경에서는 로드 시점에 명시적으로 실패하도록 되어 있습니다.
- **입력 메시 정렬**: Hi3D 리파인먼트의 한계는 입력 메시가 참조 이미지의 실루엣과 얼마나 잘 맞느냐에 따라 결정됩니다. 입력이 어긋나 있으면(잘못된 비율, 잘못된 방향) 결과도 그 어긋남을 유지합니다. 리파인 전에 참조 이미지와의 정렬을 반드시 확인하세요.
- **VRAM**: `resolution: 1024` 기준 최대 VRAM은 약 20 GB, `1536`은 약 30 GB입니다. 24 GB 소비자용 GPU는 1024 경로에 적합하고, 1536은 A100 40GB 또는 RTX 6000 Ada급을 권장합니다.
- **출력**: 입력당 `.glb` 파일 하나(배치 입력이면 리스트)가 결과입니다. Blender, three.js, Unity glTFast 등 glTF 호환 뷰어에서 바로 로드할 수 있습니다.
