# Model 3D Loader (Blender) 예제

이 예제는 헤드리스 Blender 세션에서 `.blend` 씬(또는 `.fbx`/`.obj`/`.glb`/`.ply`/`.stl`)을 열고, 선택적으로 하나의 오브젝트나 컬렉션을 고르고, 모디파이어를 적용한 뒤 결과를 GLB로 내보내 메쉬를 소비하는 AI 파이프라인에 공급합니다.

## 개요

Blender 드라이버는 trimesh의 한계를 넘어 `model-3d-loader`를 확장합니다:

1. **`.blend` 네이티브 지원**: Blender 씬을 직접 엽니다. trimesh는 파싱할 수 없습니다.
2. **오브젝트 선택**: 더 큰 씬에서 명명된 하나의 오브젝트나 컬렉션을 고를 수 있습니다. trimesh는 파일에 들어 있는 모든 걸 내보내며 선택 단위가 없습니다.
3. **모디파이어**: Subdivision Surface, Mirror, Array, Solidify 등의 모디파이어를 내보내기 전에 적용합니다. 출력 메쉬는 완전히 평가된 지오메트리입니다.
4. **재질과 애니메이션**: GLB/FBX 출력에서 PBR 재질과 (선택적으로) 아마튜어 + 애니메이션 데이터를 보존합니다.

이 컴포넌트는 사람이 작성한 씬에서 특정 자산을 AI 파이프라인이 소비해야 하는 경우를 위한 것입니다 — 예: 게임 스튜디오가 캐릭터 50명이 들어있는 `.blend`를 주고, 그중 주인공에만 Hi3D 리파인먼트를 돌리고 싶을 때.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능.
- **호스트 머신에 Blender 설치**. https://blender.org 에서 다운로드 (무료, GPL). Blender 4.0+ 에서 테스트됨.
  - macOS: `.dmg` 설치; 드라이버가 `/Applications/Blender.app/Contents/MacOS/Blender`를 자동 탐색.
  - Linux: 패키지 매니저 또는 공식 tarball로 설치; 드라이버가 PATH의 `blender`와 `/usr/bin/blender`, `/usr/local/bin/blender`를 확인.
  - Windows: `.msi` 또는 포터블 zip 설치; PATH에 없으면 `binary`에 실행 파일 경로를 지정.
- GPU 불필요 (헤드리스 모드는 CPU로 내보냄).

### 설치 탐색

드라이버는 다음 순서로 시도합니다:

1. `component.binary`가 명시되어 있으면 그 경로.
2. `shutil.which("blender")` (PATH).
3. 플랫폼별 표준 설치 경로 (`/Applications/Blender.app/...`, `C:\Program Files\Blender Foundation\...`, `/usr/bin/blender`, `/usr/local/bin/blender`).

어느 것도 일치하지 않으면 설치 페이지를 가리키는 명확한 오류와 함께 시작이 실패합니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
   > 첫 호출은 Blender 서브프로세스를 띄웁니다 (부팅 ~1-3초). 이후 호출마다 자체 서브프로세스를 띄우므로 호출당 피크 RAM이 제한됩니다.

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 최소 — .blend 씬을 로드하고 씬 전체를 GLB로 내보냄
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/scene.blend" \
     -F 'input={"file": "@file"}' \
     -o scene.glb

   # "Hero" 오브젝트만 모디파이어 적용해서 내보냄
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/scene.blend" \
     -F 'input={"file": "@file", "object_name": "Hero"}' \
     -o hero.glb

   # 컬렉션 하나를 애니메이션 유지하고 FBX로 내보냄
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/scene.blend" \
     -F 'input={"file": "@file", "object_name": "Characters", "format": "fbx", "include_animations": true}' \
     -o characters.fbx

   # .fbx를 모디파이어 적용된 깨끗한 GLB로 변환
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/model.fbx" \
     -F 'input={"file": "@file"}' \
     -o output.glb
   ```

   **웹 UI 사용:**
   - http://localhost:8081 열기
   - `.blend` (또는 `.fbx`/`.obj`/`.glb`/`.ply`/`.stl`) 업로드
   - 선택적으로 `object_name`, `format`, `include_animations` 설정
   - "Run Workflow" 클릭

## 설정 레퍼런스

### 컴포넌트 필드

| 필드      | 설명                                                                                   | 기본값    |
|-----------|----------------------------------------------------------------------------------------|-----------|
| `type`    | `model-3d-loader` 고정.                                                                | —         |
| `driver`  | `blender` 지정.                                                                        | —         |
| `binary`  | blender 실행 파일 경로. 생략 시 자동 탐색.                                             | (auto)    |
| `timeout` | 각 blender 서브프로세스의 타임아웃(초).                                                | `120.0`   |

### Action 필드

| 필드                 | 설명                                                                                                      | 기본값  |
|----------------------|-----------------------------------------------------------------------------------------------------------|---------|
| `source`             | 3D 모델 소스 (`.blend`, `.fbx`, `.obj`, `.glb`, `.ply`, `.stl`). 경로, URL, 업로드, raw 바이트.           | —       |
| `format`             | 출력 포맷: `glb`, `gltf`, `obj`, `ply`, `fbx`, `stl`.                                                     | `glb`   |
| `object_name`        | 씬에서 내보낼 특정 오브젝트 또는 컬렉션. 생략 시 씬 전체.                                                 | (전체)  |
| `apply_modifiers`    | 내보내기 전에 모디파이어(Subdivision, Mirror, Array 등) 적용.                                             | `true`  |
| `include_materials`  | 재질과 텍스처를 내보낸 메쉬에 포함.                                                                       | `true`  |
| `include_animations` | 아마튜어와 애니메이션 데이터 포함 (GLB/FBX만).                                                            | `false` |
| `batch_size`         | 입력이 리스트일 때 배치당 처리할 소스 수. Blender는 어쨌든 순차 실행됨.                                   | `1`     |

## 참고

- **작은 작업은 Blender 부팅 시간이 지배적**: 호출마다 새 Blender 프로세스(~1-3초)가 뜹니다. 하나의 컴포넌트 호출에 소스를 묶는다고 이 비용이 분산되지 않습니다 — Blender는 소스마다 한 번씩 실행됩니다. 처리량이 중요한 경우 워크플로우 레벨에서 배치하고 컨트롤러를 재사용하세요.
- **오브젝트 또는 컬렉션, 둘 중 하나**: `object_name`은 먼저 `bpy.data.objects[name]`을 매칭하고, 없으면 `bpy.data.collections[name]`으로 폴백합니다. 같은 이름의 둘이 모두 존재하면 오브젝트가 승리합니다. 모호함을 피하려면 하나의 이름을 바꾸세요.
- **모디파이어 평가**: `apply_modifiers: true`는 Blender에서 전체 모디파이어 스택을 실행한 뒤 내보냅니다. 출력 메쉬는 원본 지오메트리보다 무거울 수 있습니다 (Subdivision은 폴리곤 수를 크게 증가시킴).
- **FBX 라운드트립**: Blender의 FBX 임포터와 익스포터는 모두 손실이 있습니다. 트랜스폼 베이킹과 단위 변환이 라운드트립 간 피봇, 스케일, 회전을 바꿀 수 있습니다. 다른 DCC 툴과 교환할 때는 GLB를 쓰세요.
- **애니메이션 내보내기는 GLB 또는 FBX 필요**: `include_animations: true`는 OBJ/PLY/STL(정적 포맷)에서는 무시됩니다.
- **타임아웃 조정**: 기본 120초는 작은 씬을 커버합니다. Subdivision 모디파이어가 많이 들어간 대규모 프로덕션 씬은 이를 초과할 수 있으니 필요 시 `component.timeout`을 늘리세요.
- **파이프라인 예시**: `model-3d-loader` (Blender) → `image-to-3d-hi3d` (레퍼런스 이미지 기반 리파인먼트) → `model-3d-renderer` (프리뷰)는 AI 보조 자산 다듬기에 자연스러운 흐름입니다.
