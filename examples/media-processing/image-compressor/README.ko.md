# Image Compressor 예제

이 예제는 `image-compressor` 컴포넌트를 사용한 PNG 압축을 보여주며, 함께 제공되는 세 가지 드라이버인 Pillow(`native`), `oxipng`, `pngquant`를 모두 시연합니다. 각 드라이버는 크기, 속도, 의존성 부담 사이에서 서로 다른 트레이드오프를 가집니다.

## 개요

세 가지 드라이버를 각각 감싸는 세 개의 워크플로우를 제공합니다:

1. **Compress PNG (Pillow)** — Pillow만 사용하는 순수 DEFLATE 인코딩. 추가 의존성 없음.
2. **Lossless Shrink (oxipng)** — Pillow로 인코딩된 PNG 위에 oxipng를 추가로 실행하여 10–30% 추가 무손실 압축.
3. **Lossy Palette Quantization (pngquant)** — ≤256색 적응형 팔레트로 축소. 사진이나 그라데이션이 많은 이미지에서 무손실 대비 50–70% 작으면서 시각적으로 유사한 품질 유지.

모든 워크플로우는 압축된 PNG를 base64 이미지로 반환합니다.

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- `oxipng` 워크플로우는 `pyoxipng` Python 패키지 필요
- `pngquant` 워크플로우는 `pngquant` 바이너리가 `PATH`에 있어야 함:
  - macOS: `brew install pngquant`
  - Debian/Ubuntu: `apt install pngquant`

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/media-processing/image-compressor
   ```

2. 추가 환경 구성 불필요 - 모든 처리가 로컬에서 수행됩니다.

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 워크플로우 선택 (Compress PNG, Lossless Shrink, Lossy Palette Quantization)
   - 이미지를 업로드하고 드라이버별 매개변수 설정
   - "Run Workflow" 버튼 클릭
   - 압축된 PNG 확인 및 다운로드

   **API 사용:**
   ```bash
   # Pillow — 최대 DEFLATE 레벨
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow_id=compress-native" \
     -F "image=@input.png" \
     -F "compress_level=9"

   # oxipng — 추가 무손실 압축
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow_id=compress-oxipng" \
     -F "image=@input.png" \
     -F "level=4"

   # pngquant — 손실 팔레트 양자화
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow_id=compress-pngquant" \
     -F "image=@input.png" \
     -F "min_quality=65" \
     -F "max_quality=85"
   ```

   **CLI 사용:**
   ```bash
   model-compose run compress-native   --input '{"image": "input.png", "compress_level": 9}'
   model-compose run compress-oxipng   --input '{"image": "input.png", "level": 4}'
   model-compose run compress-pngquant --input '{"image": "input.png", "min_quality": 65, "max_quality": 85}'
   ```

## 컴포넌트 세부사항

### Image Compressor 컴포넌트
- **유형**: `image-compressor`
- **드라이버**: `native` (Pillow), `oxipng`, `pngquant`
- **출력**: 압축된 PNG 바이트 (워크플로우에는 base64 이미지로 반환됨)

하나의 `image-compressor` 컴포넌트는 하나의 드라이버에만 바인딩되므로, 이 예제는 드라이버당 하나씩 총 세 개의 컴포넌트 인스턴스를 선언하고 각 워크플로우를 해당 인스턴스로 라우팅합니다.

## 워크플로우 세부사항

### "Compress PNG (Pillow)" 워크플로우

**설명**: 입력 이미지를 `optimize=True` 옵션으로 Pillow를 사용해 PNG로 인코딩합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `image` | image | 예 | - | 압축할 이미지 |
| `compress_level` | integer | 아니오 | `9` | DEFLATE 압축 레벨 (0 = 저장, 9 = 최대) |
| `strip_metadata` | boolean | 아니오 | `true` | 부속 PNG 메타데이터 청크(tEXt, eXIf, iCCP 등) 제거 여부 |

### "Lossless Shrink (oxipng)" 워크플로우

**설명**: Pillow로 인코딩된 PNG에 대해 oxipng로 DEFLATE 필터 탐색을 재실행합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `image` | image | 예 | - | 압축할 이미지 |
| `level` | integer | 아니오 | `4` | Oxipng 최적화 레벨 (0 = 빠름, 6 = 최대) |
| `strip_metadata` | boolean | 아니오 | `true` | 부속 PNG 메타데이터 청크 제거 여부 |

### "Lossy Palette Quantization (pngquant)" 워크플로우

**설명**: pngquant로 ≤256색 적응형 팔레트를 생성합니다.

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `image` | image | 예 | - | 압축할 이미지 |
| `speed` | integer | 아니오 | `3` | Pngquant 속도, 1(가장 느림/최고 품질)부터 11(가장 빠름)까지 |
| `min_quality` | integer | 아니오 | `65` | 최소 허용 품질 (0–100); 이 값 미만이면 인코딩 실패 |
| `max_quality` | integer | 아니오 | `85` | 인코더가 목표로 하는 최대 품질 (0–100) |
| `strip_metadata` | boolean | 아니오 | `true` | 부속 PNG 메타데이터 청크 제거 여부 |

### 출력 포맷

| 필드 | 유형 | 설명 |
|------|------|------|
| `output` | image (base64) | 압축된 PNG |

## 드라이버 선택 가이드

- **native** — 안전한 기본값; 추가 설치 없이 어디서나 동작하며, 적절한 크기 감소 제공.
- **oxipng** — 모든 바이트가 중요한 무손실 파이프라인 뒤에 체인(아이콘, 스크린샷, UI 에셋 등).
- **pngquant** — 사진/그라데이션이 많은 PNG에서 가장 큰 이득. 손실 압축이므로 결과 품질 확인 필요.

## 문제 해결

### 일반적인 문제

1. **`pyoxipng`를 찾을 수 없음** — model-compose와 동일한 환경에 Python 패키지 설치 (`pip install pyoxipng`).
2. **`pngquant`를 찾을 수 없음** — CLI 설치 (`brew install pngquant` 또는 `apt install pngquant`) 후 `PATH`에 있는지 확인.
3. **pngquant 인코딩 실패** — 입력이 `min_quality`를 충족하지 못한 경우. `min_quality`를 낮추거나 생략해 pngquant가 생성하는 어떤 품질이든 수용.
4. **예상보다 결과물이 큼** — PNG 압축 이득은 입력에 크게 의존. 사진은 pngquant를, 이미 최적화된 PNG는 추가 이득이 작음을 감안.
