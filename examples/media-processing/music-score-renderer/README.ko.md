# 음악 악보 렌더러 예제

이 예제는 model-compose의 `music-score-renderer` 컴포넌트를 사용하여 MusicXML 악보(`.xml`/`.musicxml`/`.mxl`)를 페이지별 이미지로 래스터화하는 방법을 보여줍니다. 출력은 페이지 단위의 리스트 — SVG 문자열, 페이지당 한 장짜리 PDF, 또는 지정한 DPI의 PNG — 이며, 내부적으로는 모두 [Verovio](https://www.verovio.org/)가 처리합니다.

손으로 작성한 MusicXML 악보, 악보 편집기에서 내보낸 파일, 혹은 이전 단계(예: [`music-score-loader`](../music-score-loader/))의 출력을 리뷰 UI, PDF 결과물, 썸네일 파이프라인 등에서 시각적으로 보여주고 싶을 때, Verovio를 직접 연결하지 않고도 바로 사용할 수 있습니다.

## 개요

이 예제는 3개의 워크플로우를 제공합니다:

1. **악보를 SVG로 렌더링** (기본) — 페이지당 SVG 1개. 손실 없이 확대/축소되어 웹 뷰어에 적합
2. **악보를 PDF로 렌더링** — 페이지당 단일 페이지 PDF 1개, A4에 가까운 Verovio 치수. 한 문서로 합치려면 외부 도구로 결합
3. **악보를 PNG로 렌더링** — 지정한 DPI의 페이지별 PNG. 썸네일이나 SVG를 표시할 수 없는 클라이언트에 유용

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- Python 의존성은 첫 실행 시 자동 설치:
  - `verovio` — 렌더링 엔진 (항상 설치)
  - `svglib`, `reportlab` — `pdf` 액션이 선언된 경우에만 설치
  - `resvg-py` — `png` 액션이 선언된 경우에만 설치

### 설정

이 예제 디렉토리로 이동:
```bash
cd examples/media-processing/music-score-renderer
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   서비스가 시작되면:
   - API 엔드포인트: http://localhost:8080/api
   - 웹 UI: http://localhost:8081

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 드롭다운에서 워크플로우 선택
   - MusicXML 파일(`.xml`, `.musicxml`, 또는 압축된 `.mxl`) 업로드
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   # 페이지별 SVG로 렌더링 (기본)
   model-compose run render-score-svg --input '{"score": "/path/to/score.musicxml"}'

   # 페이지별 단일 페이지 PDF로 렌더링
   model-compose run render-score-pdf --input '{"score": "/path/to/score.musicxml"}'

   # 300 DPI PNG로 렌더링
   model-compose run render-score-png --input '{"score": "/path/to/score.musicxml"}'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=render-score-svg" \
     -F "score=@/path/to/score.musicxml"
   ```

## 컴포넌트 상세

### Music Score Renderer 컴포넌트

- **타입**: `music-score-renderer`
- **용도**: Verovio의 조판 레이아웃을 사용하여 MusicXML 악보를 페이지별 이미지 시퀀스(SVG, PDF, PNG)로 변환
- **드라이버**:
  - `verovio` — Verovio 기반 렌더링 (기본)

페이지 크기는 **Verovio 단위**로 지정하며, 1 단위 ≈ 0.1 mm입니다. 기본값(`page_width: 2100`, `page_height: 2970`)은 이 단위에서 A4에 해당합니다. `scale`은 퍼센트(100 = Verovio 기본 크기)이며, `margin`은 단일 스칼라(네 면 모두 동일) 혹은 `top`/`right`/`bottom`/`left`를 각각 지정하는 객체 모두 지원합니다.

MIDI 파일이나 기존 악보로부터 MusicXML 입력 자체를 만들려면 [`music-score-loader`](../music-score-loader/)를 상위에 둘 수 있지만, 로더는 구조화된 `MusicScore` 데이터를 내보내므로 MIDI 소스로부터 렌더링하려면 중간에 MusicXML로 직렬화하는 단계가 추가로 필요합니다.

## 워크플로우 상세

### 1. 악보를 SVG로 렌더링

**ID**: `render-score-svg`

페이지당 SVG 1개를 생성합니다. SVG는 손실 없이 확대/축소되며 Verovio의 네이티브 출력입니다 — 다른 두 포맷은 이 결과로부터 파생됩니다.

#### 입력 매개변수

| 매개변수 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `score` | file | 예 | - | 렌더링할 MusicXML 파일(`.xml`, `.musicxml`, 또는 `.mxl`) |

#### 출력

페이지 순서대로 정렬된 SVG 파일 리스트(`page-1.svg`, `page-2.svg`, …), 콘텐츠 타입은 `image/svg+xml`.

---

### 2. 악보를 PDF로 렌더링

**ID**: `render-score-pdf`

페이지당 단일 페이지 PDF 1개를 생성합니다. YAML에서 A4에 가까운 페이지 크기(`page_width: 2100`, `page_height: 2970`)와 네 면 동일한 60-단위 여백을 설정합니다.

PDF 생성은 `svglib` + `reportlab`을 거칩니다: Verovio가 만든 각 SVG 페이지가 ReportLab 드로잉으로 변환된 뒤 개별 PDF로 출력됩니다. 하나의 다중 페이지 PDF가 필요하면 `pdfunite`, `pypdf` 등 외부 도구로 결합하세요.

#### 입력 매개변수

| 매개변수 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `score` | file | 예 | - | 렌더링할 MusicXML 파일 |

#### 출력

페이지 순서대로 정렬된 PDF 파일 리스트(`page-1.pdf`, `page-2.pdf`, …), 콘텐츠 타입은 `application/pdf`.

---

### 3. 악보를 PNG로 렌더링

**ID**: `render-score-png`

Verovio의 각 SVG 페이지를 `resvg-py`로 설정된 DPI에 맞춰 래스터화하여 페이지당 PNG 1개를 생성합니다. 썸네일, 프리뷰, SVG 렌더링을 지원하지 않는 환경에 유용합니다.

예제는 인쇄 품질의 래스터화를 위해 `dpi: 300`을 설정하고, 네 면별 객체 형식을 보여주기 위해 비대칭 여백(`top: 80`, `right: 60`, `bottom: 80`, `left: 60`)을 사용합니다.

#### 입력 매개변수

| 매개변수 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `score` | file | 예 | - | 렌더링할 MusicXML 파일 |

#### 출력

페이지 순서대로 정렬된 PNG 이미지 리스트(`page-1.png`, `page-2.png`, …).

---

### 액션 옵션 레퍼런스

세 액션은 동일한 옵션 체계를 공유하며, `format`과 포맷별 일부 기본값만 다릅니다.

| 옵션 | 타입 | 기본값 | 적용 대상 | 설명 |
|--------|------|---------|------------|-------------|
| `source` | file / file 리스트 | 필수 | 전체 | MusicXML 입력; 경로, 업로드 스트림, 또는 원시 바이트 |
| `format` | `svg` \| `pdf` \| `png` | `svg` | 전체 | 각 페이지의 출력 포맷 |
| `page_width` | 숫자 | `2100` | 전체 | 페이지 폭(Verovio 단위, 1 단위 ≈ 0.1 mm) |
| `page_height` | 숫자 | `2970` | 전체 | 페이지 높이(Verovio 단위) |
| `scale` | 숫자 | `100` | 전체 | 렌더링 스케일 퍼센트; 100이 Verovio 기본 크기 |
| `margin` | 숫자 또는 `{top,right,bottom,left}` | `50` | 전체 | 스칼라는 네 면 모두에 적용, 객체는 면별로 지정 |
| `dpi` | 숫자 | `150` | `png` 전용 | 래스터화 해상도. `svg`와 `pdf`에서는 무시됨 |
