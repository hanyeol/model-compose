# Face Swap Model Task 예제

이 예제는 model-compose의 내장 face-swap 작업을 사용하여 InsightFace의 inswapper로 소스 이미지의 얼굴 아이덴티티를 타겟 이미지에서 감지된 모든 얼굴로 전이하는 방법을 보여주며, 오프라인 얼굴 스왑 기능을 제공합니다.

## 개요

이 워크플로우는 다음과 같은 로컬 얼굴 스왑을 제공합니다:

1. **로컬 얼굴 스왑 모델**: 외부 API 없이 InsightFace의 `inswapper_128` 모델을 로컬에서 실행
2. **아이덴티티 전이**: 소스 이미지에서 지배적인 얼굴을 추출하고 그 아이덴티티를 타겟 이미지의 얼굴에 적용
3. **다중 얼굴 스왑**: 타겟에서 감지된 모든 얼굴을 교체하거나, 인덱스로 선택한 특정 얼굴만 선택적으로 교체
4. **자동 정렬**: `buffalo_l` 얼굴 분석 팩을 사용해 감지, 랜드마크, 정렬 수행
5. **우아한 폴백**: 타겟에서 얼굴이 감지되지 않으면 원본 타겟 이미지를 그대로 반환
6. **자동 모델 관리**: 첫 사용 시 스왑퍼와 감지기 팩을 모두 자동으로 다운로드하고 캐시

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- onnxruntime 실행을 위한 충분한 시스템 리소스 (권장: 4GB+ RAM)
- `insightface`, `opencv-python`, `onnxruntime`이 있는 Python 환경 (첫 실행 시 자동 설치)

### 로컬 얼굴 스왑을 사용하는 이유

클라우드 얼굴 스왑 서비스와 달리 InsightFace를 로컬에서 실행하는 것은 다음을 제공합니다:

**로컬 처리의 이점:**
- **프라이버시**: 모든 이미지가 로컬에서 처리되며 외부 서비스로 얼굴이 업로드되지 않음
- **비용**: 이미지당 또는 API 사용 요금 없음
- **오프라인**: 초기 모델 다운로드 후 인터넷 연결 없이 작동
- **지연시간**: 매 추론마다 네트워크 왕복 없음
- **파이프라인 친화적**: 다른 model-compose 작업(포즈 감지, 이미지 업스케일 등)과 자연스럽게 조합되어 다운스트림 비디오 파이프라인 구성 가능

**트레이드오프:**
- **하드웨어 요구사항**: 적절한 CPU/GPU 리소스 필요; 배치 또는 비디오 사용 시 onnxruntime-gpu 권장
- **모델 제한**: `inswapper_128`은 다시 붙여넣기 전에 128×128 얼굴 크롭을 생성 — 매우 고해상도 타겟은 추가 얼굴 복원 패스(예: GFPGAN, CodeFormer)의 도움을 받을 수 있음
- **라이센스**: `inswapper_128` 가중치는 **비상업적 연구 용도 전용**으로 배포됨

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/model-tasks/face-swap
   ```

2. 추가 환경 구성 불필요 — 스왑퍼 모델과 `buffalo_l` 감지기 팩 모두 첫 실행 시 자동으로 다운로드 및 캐시됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 소스의 아이덴티티로 타겟의 모든 얼굴 스왑
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "source=@/path/to/source_face.jpg" \
     -F "target=@/path/to/target_image.jpg" \
     -F 'input={"source_image": "@source", "target_image": "@target"}'

   # 타겟에서 특정 얼굴만 스왑 (index 0 = 가장 높은 감지 점수)
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "source=@/path/to/source_face.jpg" \
     -F "target=@/path/to/group_photo.jpg" \
     -F 'input={"source_image": "@source", "target_image": "@target", "swap_all_faces": false, "face_index": 1}'

   # 어려운 케이스(작거나 부분적으로 가려진 얼굴)를 위한 감지 민감도 조정
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "source=@/path/to/source_face.jpg" \
     -F "target=@/path/to/target_image.jpg" \
     -F 'input={"source_image": "@source", "target_image": "@target", "detection_threshold": 0.3}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - `source_image` (전이할 얼굴)와 `target_image` (수정할 이미지) 업로드
   - 선택적으로 `swap_all_faces` 토글, `face_index` 설정, 또는 어려운 케이스에서 `detection_threshold` 낮추기
   - "Run Workflow" 버튼 클릭

## 설정 참조

### 컴포넌트 필드

| 필드            | 설명                                                                                     | 기본값        |
|------------------|-------------------------------------------------------------------------------------------|----------------|
| `task`           | `face-swap`이어야 함.                                                                     | —              |
| `driver`         | `custom`이어야 함.                                                                        | —              |
| `family`         | 얼굴 스왑 모델 패밀리. 현재는 `insightface`만 지원.                                       | —              |
| `model`          | 스왑퍼 모델 소스. `inswapper_128.onnx` 가중치를 지정 (URL 또는 로컬 경로).                | —              |
| `detector_model` | 소스 및 타겟에서 감지/랜드마크/정렬에 사용되는 InsightFace 얼굴 분석 팩.                  | `buffalo_l`    |

### 액션 필드

| 필드                   | 설명                                                                                        | 기본값        |
|------------------------|--------------------------------------------------------------------------------------------|---------------|
| `source_image`         | 전이할 얼굴 아이덴티티를 제공하는 이미지. 최소 1개의 얼굴을 포함해야 함.                    | —             |
| `target_image`         | 얼굴이 교체될 이미지 (또는 배치/스트림).                                                    | —             |
| `swap_all_faces`       | `true`이면 타겟에서 감지된 모든 얼굴이 교체됨. `false`이면 `face_index`만 사용됨.           | `true`        |
| `face_index`           | `swap_all_faces`가 `false`일 때 스왑할 타겟 얼굴. 얼굴은 감지 점수로 정렬됨 (0 = 최고).     | `0`           |
| `detection_threshold`  | 최소 얼굴 감지 신뢰도 (0.0 – 1.0). 낮은 값은 어려운 얼굴을 잡지만 오탐지 위험 증가.         | `0.5`         |
| `detection_size`       | 감지 입력 크기 `[width, height]`.                                                          | `[640, 640]`  |
| `batch_size`           | `target_image`가 리스트 또는 스트림일 때 배치당 처리되는 타겟 이미지 수.                    | `1`           |

## 참고사항

- **소스 이미지**: 액션은 감지 점수가 가장 높은 하나의 얼굴을 선택합니다. 소스에서 얼굴이 감지되지 않으면 워크플로우는 명확한 오류로 실패합니다.
- **얼굴이 없는 타겟 이미지**: 원본 타겟이 그대로 반환됩니다 — 일부 프레임에 사람이 포함되지 않을 수 있는 프레임 단위 비디오 처리에 유용합니다.
- **배치 / 비디오 사용**: `target_image`는 이미지 리스트나 스트림을 받아들이므로 이 컴포넌트는 추가 접착 코드 없이 비디오 파이프라인 (예: 모션 전이 생성 이후)에 바로 투입됩니다.
- **후처리**: 고해상도에서 더 높은 충실도를 위해 이 뒤에 `image-upscale` (또는 얼굴 복원) 컴포넌트를 체인으로 연결하세요.
