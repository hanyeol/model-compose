# Face Gender Annotate 예제

입력 이미지에서 모든 얼굴을 검출하고, 같은 검출기의 genderage 헤드로 성별을 남/여로 분류한 뒤, 원본 이미지 위에 성별별 색상 bounding box를 그려 반환하는 워크플로우 예제입니다 — **남성은 파랑**, **여성은 빨강**, 검출기가 성별을 결정하지 못한 경우 회색.

## 개요

입력 이미지를 받아 두 개의 필드를 반환합니다: `annotated_image` (원본 이미지 위에 얼굴별 색상 박스가 그려진 결과)와 `faces` (다운스트림 처리를 위한 원본 검출 레코드 — bounding box, score, gender, age).

전략:

1. **업로드를 두 브랜치로 spool** — `fan-out` 작업을 `spool: true` 모드로 사용. 업로드는 1회성이지만 두 소비자가 매우 다른 시점에 소비함: `detect`는 자기 브랜치를 즉시 소진하는 반면, `annotate`는 `detect` 완료 후에야 accumulator 초기값으로 자기 브랜치를 오픈. Spool은 업로드를 한 번 임시 파일로 떨어뜨려 각 브랜치가 자기 페이스로 파일을 열도록 하고, 임시 파일은 모든 브랜치가 닫힌 뒤 삭제됩니다.
2. **얼굴 검출 실행** — InsightFace `antelopev2` 팩으로. `return_gender_age: true`를 켜면 팩의 내장 genderage 헤드가 각 검출에 `face.gender` (`"male"` 또는 `"female"`)와 `face.age`를 채워줍니다. 별도 분류기 필요 없음.
3. **얼굴별 bounding box를 원본에 folding** — 인라인 `accumulate` 작업으로. 각 iteration이 running image(`${accumulator}`)를 받아 rectangle 하나를 추가로 그려서 다음 iteration에 넘김. Rectangle 색상은 `item.gender`에 대한 조건식으로 얼굴마다 선택됨.

### 왜 `face-detection`에 gender를 넣나 (별도 분류기가 아니라)

InsightFace의 `antelopev2` 팩은 SCRFD 검출기 *와* genderage 분류기를 함께 배포 — 얼굴을 찾는 forward pass가 동시에 gender와 age를 배정. 이걸 `face-detection`에 노출(`return_gender_age: true`, `face-embedding` / `face-tracking`과 동일 패턴)하면, 각 얼굴을 crop해서 두 번째 모델에 넣어 "남/여?"만 답 받는 왕복을 피할 수 있음. genderage를 배포하지 않는 팩으로 교체하면 `gender`와 `age` 필드가 에러 없이 그냥 누락됩니다.

### 왜 draw step은 인라인 accumulate인가

`image-drawing`은 액션 호출당 하나의 draw 연산만 노출 (rectangle, text, line, …) — 그래서 N개 박스는 N번 호출이 필요. `accumulate`는 iteration마다 `do:` 하나를 실행하며 running image를 다음 iteration의 `${accumulator}`로 넘겨줍니다. 그래서 N개 박스를 원본 위에 쌓는 자연스러운 방법은 `accumulate` 작업으로 각 검출을 accumulator 위에 folding하는 것. 검출된 gender가 없는 얼굴은 조건식의 `if_false` 회색 fallback이 적용 — 박스는 그대로 그려집니다.

## 준비

### 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- InsightFace 검출을 위한 Python 의존성:
  ```bash
  pip install insightface opencv-python onnxruntime pillow
  ```
- InsightFace **antelopev2** 팩은 첫 실행 시 model-compose의 모델 캐시로 자동 다운로드. 수동 다운로드 불필요.

### 설정

1. 예제 디렉터리로 이동:
   ```bash
   cd examples/media-processing/face-gender-annotate
   ```

2. 얼굴이 최소 하나 이상 보이는 이미지 준비.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **Web UI:**
   - Web UI 열기: http://localhost:8081
   - 이미지 업로드하고 필요 시 `min_confidence` / `line_width` 조정
   - "Run Workflow" 클릭
   - 응답에는 `annotated_image` (입력 이미지 + 성별 색상 박스)와 `faces` (원본 검출 레코드)가 포함됩니다.

   **API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"min_confidence": 0.5};type=application/json' \
     -F 'image=@./people.jpg'
   ```

   **CLI:**
   ```bash
   model-compose run --input '{
     "image": "./people.jpg",
     "min_confidence": 0.5
   }'
   ```

## 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `image` | image (file) | Yes | - | 얼굴 검출 및 어노테이트할 입력 이미지 |
| `min_confidence` | number | No | `0.5` | 최소 검출 신뢰도 (0.0 – 1.0). 낮추면(예: `0.35`) 경계선/부분 가림 얼굴을 더 잡지만 오탐지가 몇 개 늘어남 |
| `line_width` | number | No | `3` | Rectangle outline 두께(픽셀) |

## 출력 형태

```json
{
  "annotated_image": "<image PNG>",
  "faces": [
    {
      "bounding_box": { "x": 120, "y": 84, "width": 156, "height": 202 },
      "score": 0.94,
      "gender": "male",
      "age": 34
    },
    {
      "bounding_box": { "x": 380, "y": 96, "width": 148, "height": 194 },
      "score": 0.91,
      "gender": "female",
      "age": 28
    }
  ]
}
```

- `annotated_image` — 검출된 얼굴마다 bounding box 하나가 그려진 원본 이미지. `"male"`은 파랑(`#1E90FF`), `"female"`은 빨강(`#DC143C`), 팩이 gender를 반환하지 않은 얼굴은 회색(`#808080`).
- `faces[].gender` — `"male"` 또는 `"female"`. 검출기의 genderage 헤드가 값을 내지 않았다면 부재.
- `faces[].age` — 추정 나이(정수, 세). 사용할 수 없으면 부재.
- `faces[].bounding_box` — 원본 이미지 좌표계 픽셀 단위의 `{x, y, width, height}`.
- `faces[].score` — 검출기 신뢰도 (0.0 – 1.0).

## 잡 상세

### Fan-Out (`fanout-image`)
- **타입**: `fan-out` (`spool: true`)
- **역할**: 1회성 이미지 업로드를 두 개의 독립 브랜치로 tee — `for-detect` (검출기로 흐름)와 `for-annotate` (`detect` 완료 후 `accumulate` 작업의 초기 accumulator 시딩). `spool: true`이므로 업로드가 tempfile에 한 번 랜딩되고 각 브랜치가 각자 파일을 오픈; 두 브랜치가 모두 close되면 tempfile 삭제. annotate 브랜치는 detector 완료 후에야 소비 시작하므로 일반 fan-out 경로였다면 큐 backpressure에 걸림 — spool이 그 문제를 회피.

## 컴포넌트 상세

### Face Detector (`face-detector`)
- **타입**: `model` — `face-detection` 태스크
- **드라이버**: `custom` (InsightFace family, `antelopev2` 팩)
- **역할**: 입력 이미지에서 모든 얼굴을 검출하고, `return_gender_age: true`로 각 검출에 팩의 genderage 예측(`"male"` / `"female"` + 정수 나이)을 태깅. `max_concurrent_count: 1`로 추론을 직렬화해 ONNX Runtime 메모리를 유계 유지. `detection_size`를 `(960, 960)` 또는 `(1280, 1280)`로 올리면 더 작은/멀리 있는 얼굴을 잡을 수 있음 (이미지당 비용 비례 증가).

### Box Drawer (`box-drawer`)
- **타입**: `image-drawing` (`rectangle` 메서드)
- **드라이버**: `native`
- **역할**: 하나의 outlined rectangle을 running accumulator 위에 그림. Outline 색상은 `item.gender` 조건식으로 검출마다 선택: male → dodger blue (`#1E90FF`), female → crimson (`#DC143C`), 그 외 → gray (`#808080`). `line_width`는 outline 두께(픽셀).

## 참고와 튜닝

- **비용**: 이미지당 InsightFace forward pass 한 번. CPU 전용 추론에서는 검출이 지배적; genderage 헤드는 검출된 얼굴당 작은 추가 비용. Apple Silicon에서는 CoreML execution provider가 사용 가능하면 우선 선택되어, HD 입력 기준 이미지당 지연시간이 대개 1초 이하.
- **Gender가 반환 안 됨**: `gender` 필드는 로드된 팩이 genderage 모델을 배포할 때만 채워짐. `antelopev2` (이 예제 기본값)는 배포함. `model.url`을 detection-only 팩으로 교체하면 박스는 여전히 그려지지만 전부 회색 (fallback 색) — genderage가 요청됐지만 팩이 답할 수 없다는 어노테이터의 신호.
- **놓친 얼굴**: 기본 `min_confidence: 0.5`에서 얼굴을 놓치면 먼저 `0.35`로 낮춰보세요. 어느 임계값에서도 놓친다면 기본 `(640, 640)` 검출 입력에 비해 너무 작을 가능성 — `face-detector` 컴포넌트의 `detection_size`를 올리세요.
- **오탐지**: 매우 높은 `min_confidence`(예: `0.85`)는 가려짐/측면 얼굴을 어노테이션 전에 떨어냅니다. 기본 임계값에서 잡음이 보이면 `0.05`씩 올리는 것으로 보통 충분.
- **커스텀 색상**: 색상 팔레트는 `annotate` 작업의 `outline` 조건식에 인라인 — 남성 파랑 `#1E90FF`, 여성 빨강 `#DC143C`, unknown 회색 `#808080`. hex 문자열을 편집해 스킴 변경, `"?"` 리스트에 분기를 더 추가하면 (예: 나이 구간별로) 확장 가능.
- **Spool tempfile**: fan-out spool은 `tempfile.NamedTemporaryFile`이 반환하는 OS 임시 디렉터리에 씀 (`TMPDIR` 존중). 모든 브랜치가 close되면 파일 삭제 — 수동 정리 불필요. 임시 파티션이 작고 입력이 크다면 `TMPDIR`을 큰 디스크로 지정하세요.
