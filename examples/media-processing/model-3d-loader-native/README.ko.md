# Model 3D Loader (Native) 예제

이 예제는 trimesh를 사용해 3D 모델 파일(GLB, OBJ, PLY, STL, GLTF, DAE, 3MF, OFF 등)을 파이프라인에 `Model3DStreamResource`로 로드합니다.

## 개요

`model-3d-loader`는 3D 자산의 파이프라인 진입점으로, PDF의 `document-loader`, 자막의 `subtitle-loader`, MIDI/MusicXML의 `music-score-loader`와 같은 계열입니다. `native` 드라이버는 trimesh를 사용하므로 trimesh가 파싱할 수 있는 모든 포맷이 유효한 입력이 되며, 요청한 포맷(기본 GLB)으로 재내보냅니다.

이 컴포넌트는 다음 상황에서 사용합니다:

1. **AI 파이프라인에 공급**: 임의 포맷의 입력을 메쉬를 받는 모델(예: 리파인먼트용 `image-to-3d-hi3d`)에 넘기기 전 표준 GLB로 변환합니다.
2. **입력 포맷 정규화**: 사용자가 올리는 어떤 포맷(`.obj`, `.fbx`, `.ply`)이든 받아, 다운스트림에는 하나의 일관된 포맷으로 내보냅니다.
3. **데이터셋 결합**: `source`에 자산 경로 리스트를 지정하면 메쉬 리스트를 배치로 돌려받습니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능.
- `trimesh`를 설치할 수 있는 Python 환경 (첫 실행 시 자동 설치).
- GPU 불필요.

### Native vs Blender 선택

- **Native (이 예제)**: trimesh가 일반적인 교환 포맷을 깔끔히 처리합니다. 외부 소프트웨어 불필요. 포맷 지원 범위는 trimesh가 결정합니다 (GLB/GLTF/OBJ/PLY/STL/DAE/3MF/OFF 외 소수).
- **Blender** (참고: `../model-3d-loader-blender/`): `.blend` 씬을 열고 내보내기 전에 모디파이어를 적용합니다. 입력이 Blender 프로젝트 파일이거나, 더 큰 씬에서 특정 오브젝트/컬렉션을 선택해야 할 때 필요합니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 — .obj를 GLB로 로드
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/model.obj" \
     -F 'input={"file": "@file"}' \
     -o output.glb

   # 출력 포맷 명시
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/model.glb" \
     -F 'input={"file": "@file", "format": "ply"}' \
     -o output.ply
   ```

   **웹 UI 사용:**
   - http://localhost:8081 열기
   - 3D 모델 파일 업로드
   - 출력 포맷 선택 (기본 `glb`)
   - "Run Workflow" 클릭

## 설정 레퍼런스

### 컴포넌트 필드

| 필드     | 설명                                                                 | 기본값   |
|----------|----------------------------------------------------------------------|----------|
| `type`   | `model-3d-loader` 고정.                                              | —        |
| `driver` | `native` 지정 (또는 생략 — `native`가 기본 드라이버).                | `native` |

### Action 필드

| 필드         | 설명                                                                                             | 기본값  |
|--------------|--------------------------------------------------------------------------------------------------|---------|
| `source`     | 3D 모델 소스 (경로, URL, 업로드 스트림, raw 바이트). 리스트는 배치 처리.                         | —       |
| `format`     | 출력 포맷: `glb`, `gltf`, `obj`, `ply`, `fbx`, `stl`.                                            | `glb`   |
| `batch_size` | 입력이 리스트일 때 배치당 처리할 소스 수.                                                        | `1`     |

## 참고

- **GLB 기본값**: 텍스처가 임베드된 단일 바이너리를 생성합니다. 단일 파일을 기대하는 다운스트림에 가장 쉬운 포맷입니다.
- **trimesh의 `.fbx` 내보내기는 제한적**: FBX는 독점 포맷이며 trimesh의 라이터는 지오메트리만 다룹니다. 아마튜어나 복잡한 재질이 있는 씬은 Blender 드라이버를 사용하세요.
- **애니메이션 미지원**: trimesh는 지오메트리 중심입니다. 입력의 애니메이션 데이터(키프레임, 아마튜어)는 버려집니다. 애니메이션 데이터를 보존해야 한다면 Blender 드라이버에 `include_animations: true`를 설정하세요.
- **지원되지 않는 출력 포맷에서의 오류**: trimesh가 로드된 메쉬 타입에서 요청 포맷으로 내보낼 수 없으면 `ValueError`를 던집니다 (예: 다중 지오메트리 씬에서의 STL). 드라이버는 명확한 오류 메시지로 표면화합니다.
- **체이닝 예시**: `model-3d-loader` → `model-3d-converter` (포맷 변환) → `model-3d-renderer` (이미지 프리뷰)는 사용자가 올린 3D 자산을 미리볼 때 흔한 파이프라인입니다.
