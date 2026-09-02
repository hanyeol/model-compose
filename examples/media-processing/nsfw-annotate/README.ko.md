# NSFW Annotate 예제

입력 이미지에서 NSFW 영역을 검출하고, 각 검출 위에 라벨과 함께 색상 있는 bounding box를 그린 이미지를 반환하는 워크플로우 예제입니다 — **`*_EXPOSED` 클래스는 빨강**, **`*_COVERED` 클래스는 노랑**, **그 외(`FACE_*` 등)는 회색**.

[nsfw-mosaic](../nsfw-mosaic/)의 짝이 되는 예제 — 같은 검출기를 사용하지만, 영역을 픽셀화하는 대신 시각적으로 그려서 모델이 무엇을 어느 신뢰도로 보았는지 눈으로 검사할 수 있게 합니다.

> **모델은 직접 준비**: 이 예제는 NSFW 가중치를 자동 다운로드하지 않습니다. NSFW 클래스로 학습된 YOLO 포맷 검출기를 `./models/nsfw_detector.pt`에 두어야 합니다 — `nsfw-mosaic` 예제가 사용하는 것과 같은 파일. 다운로드 명령은 [nsfw-mosaic/README.ko.md](../nsfw-mosaic/README.ko.md#검출-모델-준비) 참고.

## 개요

입력 이미지를 받아 두 개의 필드를 반환합니다: `annotated_image` (원본 이미지 위에 검출별 색상 박스와 라벨이 그려진 결과)와 `objects` (다운스트림 처리를 위한 원본 검출 레코드 — 라벨, 스코어, bounding box).

전략:

1. **업로드를 세 브랜치로 spool** — `fan-out` 작업을 `spool: true` 모드로 사용. 업로드는 1회성이지만 세 개의 작업이 읽어야 함: `measure`는 자기 브랜치를 즉시 소진, `brighten`은 `factor`를 기다림, `annotate`는 `detect`를 기다림 — 상당한 시간차. Spool은 업로드를 한 번 임시 파일로 떨어뜨려 각 브랜치가 자기 페이스로 파일을 열도록 하고, 임시 파일은 모든 브랜치가 닫힌 뒤 삭제됩니다.
2. **원본의 평균 휘도 측정** — `image-analyzer analyze-brightness`로 0–255 ITU-R BT.601 스케일의 `mean_brightness` 반환.
3. **밝기 보정 계수 계산** (`target_luma / mean_brightness`) — 한 줄짜리 Python `shell` 스텝. 완전히 검은 입력이거나 `target_luma: 0`(옵트아웃)일 때는 `1.0`으로 폴백.
4. **원본 밝기 보정** — `image-processor adjust-brightness`. PIL의 선형 밝기 배율. 극단적인 시프트는 클리핑되므로 매우 어두운 원본을 luma 200으로 정규화하면 목표보다 살짝 아래에 착륙 — 검출기 입력용으로는 문제없음.
5. **밝기 보정된 이미지에 NSFW 검출 실행** — Ultralytics YOLO 모델. `{objects: [{label, label_id, confidence, bounding_box: {x, y, width, height}}], width, height}` 반환.
6. **손대지 않은 원본 이미지 위에 검출당 라벨된 박스 하나씩 접기** — 인라인 `accumulate` 잡. 각 iteration은 두 스텝 inner 파이프라인을 실행: 테두리 사각형을 그리고, 박스 바로 위에 라벨 텍스트를 그림. 테두리와 텍스트 색상은 라벨의 접미어를 매칭하는 조건으로 검출별로 선택 — `*_EXPOSED`는 빨강, `*_COVERED`는 노랑, 그 외는 회색.

### 검출 전에 밝기를 정규화하는 이유

NudeNet(그리고 공개된 다른 모든 NSFW YOLO)은 정상 노출 범위의 사진으로 학습되었습니다. 매우 어둡거나 매우 밝은 입력은 그 분포 밖에 있어 신뢰도 점수가 전반적으로 떨어지고 — 때로는 `min_confidence` 아래로 — "당연히 잡혀야 할" 영역이 miss로 바뀝니다. 상대적 배수(`1.5×` 등)가 아니라 절대 목표 luma로 정규화한다는 것은, 원본 노출과 무관하게 모든 입력이 같은 밝기 대역으로 수렴한다는 뜻이고, 검출기는 자신이 학습한 것과 비슷한 입력을 보게 됩니다.

밝기 보정은 검출기 입력에만 적용됩니다. 어노테이션은 손대지 않은 원본 위에 그려지므로 반환되는 이미지가 호출자가 업로드한 것과 일치 — 보낸 픽셀 위에 박스가 그려진 결과를 보게 됩니다.

### 밝기 보정본이 아니라 원본에 그리는 이유

두 가지:

1. **출력이 호출자 파일의 라벨링된 버전이어야 함** — "검출 위치가 어디냐"만 원했는데 밝기 보정된 픽셀이 돌아오면 놀랍습니다.
2. **스윕 스타일 비교가 깔끔하게 유지됨** — 다른 `target_luma` 값으로 재실행하면서 반환된 `objects` 배열을 diff 할 때, 반환되는 이미지의 형태까지 변하지 않아야 비교가 쉽습니다.

검출기가 본 것(밝기 보정된 프레임 위에 박스)을 *보고 싶다면* annotate 작업의 accumulator를 `${jobs.fanout-image.output.for-annotate}` 대신 `${jobs.brighten.output as image}`로 분기하세요.

### inner 파이프라인을 두 스텝으로 두는 이유

`image-drawing`은 액션 호출당 하나의 그리기 연산만 노출(사각형, 텍스트, 선, …)하므로 "사각형 + 라벨" 콤보는 두 번의 호출이 필요합니다. `accumulate`는 iteration당 하나의 `do:`를 실행하며, 두 번의 그리기 호출을 iteration 안에서 자연스럽게 이어붙이는 방법은 인라인 `pipeline` — 스텝 1이 실행 중인 accumulator에 사각형을 그리고, 스텝 2가 그 위에 라벨을 그림. 파이프라인의 출력이 `accumulate`로 돌아가 다음 iteration의 accumulator가 됩니다.

### 색상에 접미어 매칭을 쓰는 이유

NudeNet의 18개 클래스는 전부 `_EXPOSED`, `_COVERED`로 끝나거나 `FACE_MALE` / `FACE_FEMALE`입니다. 색상 조건문에 모든 클래스를 열거(18개 분기)하는 대신, `ends-with` 연산자로 접미어를 키로 사용 — 두 개의 분기(`_EXPOSED`, `_COVERED`)와 회색 폴백으로 전체를 커버하며 가독성도 유지됩니다.

## 준비

### 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- Ultralytics YOLO Python 의존성:
  ```bash
  pip install ultralytics
  ```

### 검출 모델 준비

[nsfw-mosaic](../nsfw-mosaic/README.ko.md#검출-모델-준비)와 동일. 권장: Hugging Face 미러의 NudeNet v3.4 640m:

```bash
mkdir -p models
curl -fL -o models/nsfw_detector.pt \
  https://huggingface.co/vladmandic/nudenet/resolve/main/nudenet-v34-640m.pt
```

파일이 ~52 MB인지 확인하세요 (`file models/nsfw_detector.pt`가 `Zip archive data`를 보고해야 합니다). 이미 옆의 `nsfw-mosaic/models/` 디렉토리에 파일이 있다면 심볼릭 링크도 가능:

```bash
mkdir -p models
ln -s ../../nsfw-mosaic/models/nsfw_detector.pt models/nsfw_detector.pt
```

### 설정

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/media-processing/nsfw-annotate
   ```

2. 검출기 가중치를 `./models/nsfw_detector.pt`에 배치.

3. 어노테이션할 이미지 준비.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 이미지 업로드, 필요시 `min_confidence` / `line_width` / `bounding_box_padding` 조정
   - "Run Workflow" 클릭
   - 응답에 `annotated_image` (색상 라벨 박스가 그려진 입력)와 `objects` (원본 검출 레코드) 포함.

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F 'input={"min_confidence": 0.35};type=application/json' \
     -F 'image=@./photo.jpg'
   ```

   **CLI 사용:**
   ```bash
   model-compose run --input '{
     "image": "./photo.jpg",
     "min_confidence": 0.35
   }'
   ```

## 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `image` | image (파일) | 예 | - | NSFW 영역을 검출하고 어노테이션할 입력 이미지 |
| `target_luma` | number | 아니오 | `130` | 목표 평균 luma (0–255, BT.601). 검출기 입력을 이 평균 luma에 맞도록 스케일. `0`으로 두면 정규화를 건너뛰고 원본 픽셀에서 검출. 일반적인 대역: 사진 콘텐츠에는 `100`–`160`; `40` 아래는 그림자를 뭉갬, `215` 위는 하이라이트를 날림 |
| `min_confidence` | number | 아니오 | `0.35` | 최소 검출 신뢰도 (0.0 – 1.0). 모델 검사 중 경계 검출까지 보고 싶으면 낮추세요 (예: `0.2`) |
| `bounding_box_padding` | number | 아니오 | `0.0` | 그리기 전에 각 검출 박스를 사방으로 확장하는 비율. 여기서는 `0.0`으로 유지(`nsfw-mosaic`과 달리) — 그려진 박스가 검출기 원본 출력과 정확히 일치하므로 시각적 디버깅에 유용 |
| `line_width` | number | 아니오 | `3` | 사각형 테두리 두께 (픽셀) |
| `text_stroke_width` | number | 아니오 | `2` | 텍스트 스트로크 두께 (픽셀) — 라벨 주위의 검은 아웃라인으로 어떤 배경에서도 가독성 유지 |

## 출력 형태

```json
{
  "annotated_image": "<image PNG>",
  "objects": [
    {
      "label": "FEMALE_BREAST_EXPOSED",
      "label_id": 3,
      "confidence": 0.87,
      "bounding_box": { "x": 412, "y": 180, "width": 220, "height": 260 }
    },
    {
      "label": "FACE_FEMALE",
      "label_id": 16,
      "confidence": 0.94,
      "bounding_box": { "x": 380, "y": 40, "width": 160, "height": 200 }
    }
  ]
}
```

- `annotated_image` — 검출당 bounding box + 라벨 하나씩 그려진 원본 이미지.
- `objects[].label` — NSFW 클래스 이름 (모델 종속. NudeNet v3.4는 `FEMALE_BREAST_EXPOSED`, `MALE_GENITALIA_EXPOSED`, `BUTTOCKS_COVERED`, `FACE_MALE` 등의 이름 사용).
- `objects[].confidence` — 검출기 신뢰도 (0.0 – 1.0).
- `objects[].bounding_box` — 원본 이미지 좌표계에서의 `{x, y, width, height}` (픽셀).

## 작업 상세

### Fan-Out (`fanout-image`)
- **Type**: `fan-out` (`spool: true`)
- **기능**: 1회성 이미지 업로드를 세 개의 독립 브랜치로 티(tee) — `for-measure`(brightness analyser 공급), `for-brighten`(`factor` 완료 후 검출기 입력 공급), `for-annotate`(`detect` 완료 후 accumulate 작업의 초기 accumulator에 시드). `spool: true`로 업로드가 한 번 임시 파일로 떨어지고 각 브랜치는 자기 페이스로 파일을 오픈; 모든 브랜치가 닫히면 임시 파일 삭제. 세 브랜치 중 둘이 `measure`가 한참 지난 뒤에야 소비를 시작하기 때문에 일반 fan-out 경로가 겪는 큐 backpressure를 spool이 회피합니다.

## 컴포넌트 상세

### Image Analyzer (`image-analyzer`)
- **Type**: `image-analyzer` (`analyze-brightness` 액션)
- **Driver**: `native`
- **기능**: 0–255 BT.601 luma 스케일의 `mean_brightness` 반환. `factor-calc` 작업이 `target_luma`를 이 값으로 나누어 `adjust-brightness`가 필요로 하는 배수를 만듭니다. `min_brightness` / `max_brightness` / `std_brightness`도 반환하지만 워크플로우는 노출하지 않음 — 콘트라스트도 함께 키로 쓰고 싶다면 사용 가능.

### Factor Calc (`factor-calc`)
- **Type**: `shell`
- **기능**: `target / original`을 출력하는 한 줄짜리 Python (둘 중 하나라도 0이면 `1.0`으로 폴백). DSL은 산술 연산을 하지 않으므로 이것이 최소한의 우회. 출력은 `as number`로 디코딩되어 밝기 보정 컴포넌트가 실제 float를 소비.

### Image Processor (`image-processor`, `adjust-brightness` 액션)
- **Type**: `image-processor`
- **Driver**: `native`
- **기능**: PIL의 `ImageEnhance.Brightness`로 픽셀 값에 계산된 배수를 곱함. 배수 `1.0`은 no-op이므로 `target_luma: 0`(→ `factor-calc`가 `1.0` 반환)은 별도의 특수 케이스 배선 없이 정규화를 완전히 단락시킵니다.

### NSFW Detector (`nsfw-detector`)
- **Type**: `model` — `object-detection` task
- **Driver**: `custom` (Ultralytics YOLO family)
- **기능**: 사용자가 제공한 NSFW YOLO 가중치를 입력 이미지에 실행하고 표준 object-detection 응답 형태를 반환. `max_concurrent_count: 1`로 GPU 측 작업을 직렬화. `bounding_box_padding`을 노출하여 호출자가 검출을 다시 돌리지 않고도 그려진 박스를 시각적 명료도를 위해 넓힐 수 있음.

### Box Drawer (`box-drawer`)
- **Type**: `image-drawing` (`rectangle` 메서드)
- **Driver**: `native`
- **기능**: 실행 중인 accumulator에 테두리 사각형 하나를 그림. 테두리 색상은 라벨 접미어에 대한 조건으로 검출별로 선택.

### Text Drawer (`text-drawer`)
- **Type**: `image-drawing` (`text` 메서드)
- **Driver**: `native`
- **기능**: 사각형 바로 위에 라벨 문자열을 그림. `anchor: ld`(left / descender)로 텍스트의 베이스라인이 사각형의 위쪽 가장자리에 오게 하여 라벨이 박스 바로 위에 앉음. 검은 스트로크의 `stroke_width: 2`가 어떤 배경에서도 텍스트 가독성 유지.

## 참고 및 튜닝

- **비용**: 이미지당 `analyze-brightness` 1회, `adjust-brightness` 1회, YOLO forward 1회, 검출당 `image-drawing` 2회. 전처리 스텝은 순수 NumPy / PIL이라 검출에 비하면 사실상 공짜.
- **`target_luma` 조정 시점**: 기본 `130`(미드톤)은 대부분의 YOLO 검출기의 학습 세트 노출 대역과 일치. 입력이 지속적으로 어둡고 영역을 놓친다면 올리세요 (`150`–`180`). 지속적으로 밝고 클리핑이 하이라이트를 삼키기 시작한다면 낮추세요 (`100`–`120`). `target_luma: 0`을 넘기면 정규화를 완전히 건너뜀 — 원본 대비 A/B 비교에 유용.
- **정규화가 오히려 해가 되는 경우**: 노출이 잘 맞은 입력은 재정규화로 이득 없이 PIL의 선형 클립에 살색 그라데이션을 조금 잃을 수 있음. 입력이 이미 정상 노출 범위임을 안다면 `target_luma: 0`을 넘기세요.
- **누락된 검출**: 기본 임계값이 감추는 경계 검출을 보고 싶으면 `min_confidence`를 낮추세요 (예: `0.2`). 특정 영역이 왜 안 잡혔는지 디버깅할 때 유용.
- **텍스트 겹침**: 두 검출이 세로로 가깝게 위치하면, 둘 다 박스 좌상단에 앵커되어 라벨이 겹칠 수 있음. 이것은 "모델을 검사한다"는 용도에 부합하는 의도된 동작 — 충돌을 피하려고 라벨을 재정렬/재배치하려면 전체 검출 리스트에 대해 두 번째 패스가 필요하고, 디버깅 도구에는 그만한 복잡도가 아깝습니다.
- **색상 스킴**: 팔레트를 두 개의 조건문이 인코딩(사각형용 하나, 텍스트용 하나). 인라인 RGB hex 코드를 바꿔 리맵. 두 계층 그루핑이 세밀하지 않다면 분기를 추가(예: `FACE_*` 클래스에 별도 색상)하세요.
- **`nsfw-mosaic`과의 비교**: 두 예제 모두 같은 검출기와 같은 `bounding_box` 필드를 사용. 모자이크 워크플로우의 `min_confidence` / `iou_threshold` / 클래스 라벨 필터를 반복 조정할 때 먼저 이 워크플로우로 돌려 보세요 — 정지 이미지에서 검출 세트를 시각적으로 검증하는 편이 전체 비디오를 재인코딩하고 모자이크 결과를 검사하는 것보다 훨씬 빠릅니다.
- **Spool 임시 파일**: fan-out spool은 `tempfile.NamedTemporaryFile`이 반환하는 OS 임시 디렉토리(TMPDIR 존중)에 씀. 모든 브랜치가 닫힌 뒤 삭제되므로 수동 정리 불필요. 임시 파티션이 작고 입력이 크다면 `TMPDIR`을 더 큰 디스크로 지정하세요.
