# 이미지-3D 가우시안 스플랫 예제

이 예제는 model-compose의 내장 `image-to-3d` 태스크를 통해 **TripoSplat**(TripoAI)으로 단일 이미지를 3D 가우시안 스플랫으로 변환하는 방법을 보여줍니다.

## 개요

TripoSplat은 한 장의 2D 이미지에서 3D Gaussian Splatting 자산(`.ply` 또는 `.splat`)을 생성합니다. 메시 기반 image-to-3D 모델과 달리 출력이 지향성 가우시안들의 집합이므로 브라우저 기반 뷰어(SparkJS, SuperSplat, Three.js)에서 깔끔하게 렌더링되고 인터랙티브 씬에 잘 합성됩니다.

이 워크플로우는 다음을 제공합니다:

1. **로컬 단일 이미지 가우시안 스플랫 생성**: flow-matching 파이프라인 + VAE 디코더가 외부 API 없이 end-to-end로 실행됩니다.
2. **가변 가우시안 수**: `num_gaussians`로 `[32768, 262144]` 범위(32의 배수로 자동 반올림) 안에서 자유 설정 — 시각 품질과 렌더링·저장 비용의 트레이드오프를 조율합니다.
3. **배경 제거 내장**: BiRefNet이 파이프라인 일부로 로드되므로 복잡한 배경도 flow 모델이 보기 전에 자동으로 제거됩니다.
4. **듀얼 출력 포맷**: `.ply`(일반적인 가우시안 뷰어 입력) 또는 `.splat`(브라우저 뷰어가 선호하는 콤팩트 바이너리)로 내보냅니다.
5. **자동 모델 관리**: `VAST-AI/TripoSplat`(~5 GB, `diffusion_models/`·`vae/`·`clip_vision/`·`background_removal/` 하위 5개 safetensors 파일)이 첫 실행 시 다운로드되어 로컬에 캐시됩니다.

## 사전 준비

### 요구 사항

- model-compose가 PATH에서 실행 가능해야 합니다.
- CUDA GPU가 필요합니다. 파이프라인은 bfloat16 / float16 가중치로 실행되므로 CPU와 MPS(Apple Silicon)는 지원하지 않습니다.
- `torch`, `torchvision`, `numpy`, `safetensors`, `pillow`, `tqdm`을 설치할 수 있는 파이썬 환경이 필요합니다 — 첫 실행 시 격리된 `.venv/triposplat`에 자동 설치됩니다. transformers, diffusers, flash-attn, spconv 모두 필요 없습니다.
- HuggingFace 토큰은 필수가 아닙니다 — `VAST-AI/TripoSplat`은 공개 저장소입니다.

### 라이선스

TripoSplat 코드와 가중치는 **MIT License**로 공개되어 있어 추가 통지 없이 상업적 사용이 가능합니다. 전체 조항은 [upstream LICENSE](https://github.com/VAST-AI-Research/TripoSplat/blob/main/LICENSE)에서 확인하세요.

### 가우시안 스플랫을 쓰는 이유

메시 기반 image-to-3D 출력과 비교:

- **빠른 브라우저 렌더링**: 순수 점 구름 래스터화 — 삼각형 세팅, UV 베이킹, PBR 셰이딩 파이프라인 불필요.
- **높은 시각 충실도**: 메시가 다루기 어려운 부드러운 실루엣, 머리카락, 식물, 반투명 표면을 잘 포착합니다.
- **메시 대체 아님**: 게임 엔진, DCC, 물리 파이프라인은 여전히 메시를 요구합니다. 웹 뷰어·AR/VR·시각화에는 TripoSplat을, GLB가 필요하면 Pixal3D·AniGen·Hi3D를 사용하세요.

### 환경 설정

1. 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/image-to-3d-triposplat
   ```

2. (선택) HuggingFace 요청 수 제한에 걸리면 `HF_TOKEN`을 설정하세요:
   ```bash
   export HF_TOKEN=hf_xxx
   ```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 실행 시 `.venv/triposplat` 생성, 최소 의존성 설치, TripoSplat 추론 코드(두 개의 파이썬 파일 ~2k LOC) 클론, 약 5 GB 가중치 다운로드를 수행합니다. 컨트롤러 준비 완료까지 수 분이 걸립니다. 이후 실행은 캐시된 venv와 아티팩트를 재사용합니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 호출 — 기본 설정으로 .ply 스플랫 생성
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img"}' \
     -o output.ply

   # 시드 고정으로 재현 가능한 샘플링
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img", "seed": 42}' \
     -o output.ply

   # 브라우저 렌더링 속도를 위해 가우시안 수 낮추기
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img", "num_gaussians": 65536}' \
     -o output.ply

   # Three.js용 콤팩트 바이너리 .splat으로 내보내기
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "img=@/path/to/subject.webp" \
     -F 'input={"image": "@img", "format": "splat"}' \
     -o output.splat
   ```

   **Web UI 사용:**
   - Web UI 접속: http://localhost:8081
   - `image` 업로드(배경은 임의 — BiRefNet이 제거함)
   - 선택적으로 `seed`, `num_gaussians`(32768 / 65536 / 131072 / 262144), `format`(`ply` / `splat`) 설정
   - "Run Workflow" 클릭 시 스플랫 파일을 받습니다

3. **결과 확인**: `.ply` 또는 `.splat` 파일을 [SparkJS](https://sparkjs.dev) 또는 [SuperSplat](https://superspl.at/editor)에 드래그하거나, Three.js 씬에서 `@mkkellogg/gaussian-splats-3d`로 로드하세요.

## 설정 레퍼런스

### 컴포넌트 필드

| 필드     | 설명                                                                                | 기본값  |
|----------|-------------------------------------------------------------------------------------|---------|
| `task`   | `image-to-3d`로 고정.                                                               | —       |
| `driver` | `custom`으로 고정.                                                                  | —       |
| `family` | `triposplat`으로 고정.                                                              | —       |
| `model`  | TripoSplat 모델 저장소(HuggingFace repo 또는 로컬 경로).                            | —       |
| `device` | 컴퓨트 디바이스. `cuda`로 해석되어야 함 — bfloat16 / fp16 가중치 전용.              | `auto`  |

### 액션 필드

| 필드                   | 설명                                                                                        | 기본값     |
|------------------------|---------------------------------------------------------------------------------------------|------------|
| `image`                | 입력 이미지(단일, 리스트, 또는 스트림).                                                     | —          |
| `seed`                 | 재현 가능한 샘플링을 위한 랜덤 시드.                                                        | `42`       |
| `batch_size`           | 입력이 리스트·스트림일 때 배치당 처리할 아이템 수.                                          | `1`        |
| `format`               | 출력 포맷: `ply` 또는 `splat`.                                                              | `ply`      |
| `params.steps`         | flow-matching 샘플러 스텝 수. 10-20 권장.                                                   | `20`       |
| `params.guidance_scale`| classifier-free guidance 강도. `<= 1.0`은 CFG 비활성화. 3.0 권장.                           | `3.0`      |
| `params.shift`         | flow-matching 타임스텝 스케줄 shift. `1.0`은 균일, 높을수록 초반에 가중.                    | `3.0`      |
| `params.num_gaussians` | 목표 가우시안 수. `[32768, 262144]` 범위, 32의 배수로 반올림.                               | `262144`   |
| `params.erode_radius`  | 배경 제거 후 알파 매트의 침식 반경. `0`은 비활성화, `1`은 3x3 최소값 필터.                  | `1`        |

## 참고 사항

- **최소 의존성**: TripoSplat은 의도적으로 `transformers`, `diffusers`, `flash-attn`, `spconv`를 피합니다. 첫 실행 설치가 다른 image-to-3d 파이프라인(pixal3d, anigen, hi3d)보다 눈에 띄게 빠릅니다.
- **pip 패키지 아님**: upstream은 `triposplat.py`와 `model.py`를 `setup.py`나 `pyproject.toml` 없이 top-level 파일로 배포합니다. 드라이버가 `mindor` 옆에 `triposplat_pipeline/` 패키지로 복사하면서 내부 `from model import ...`를 `from triposplat_pipeline.model import ...`로 리라이팅합니다.
- **격리 런타임**: 모델 워커가 `.venv/triposplat`에서 실행되므로 TripoSplat의 torch 빌드가 컨트롤러의 site-packages와 충돌하지 않습니다.
- **CUDA 필수**: DINOv3·VAE 인코더는 bfloat16, BiRefNet·flow 모델·디코더는 float16으로 로드됩니다. CPU·MPS 경로는 없습니다.
- **가우시안 수 granularity**: `num_gaussians`는 디코더의 `gaussians_per_point`(보통 32)의 가장 가까운 배수로 반올림됩니다. 드라이버는 사용자 값을 그대로 전달하고, TripoSplat이 실제 사용된 값을 출력합니다.
- **결과 시청**: `.ply`가 가장 보편적인 가우시안 스플랫 포맷이고, `.splat`은 Three.js가 선호하는 콤팩트 바이너리입니다. 둘 다 Blender나 Unity glTFast에서는 열리지 않습니다 — 그쪽은 메시를 기대하므로.
- **출력**: 입력당 `.ply` 또는 `.splat` 파일 하나(배치 입력이면 리스트).
