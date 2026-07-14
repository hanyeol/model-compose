# 웹 스크레이퍼 예제

이 예제는 다양한 스크레이핑 시나리오를 위한 여러 워크플로우를 통해 `web-scraper` 컴포넌트의 다양한 웹 스크레이핑 기능을 보여줍니다.

## 개요

이 예제는 7가지의 서로 다른 웹 스크레이핑 워크플로우를 제공합니다:

1. **기본 스크레이핑**: CSS 셀렉터를 사용하여 텍스트 콘텐츠 추출
2. **링크 추출**: 웹 페이지의 모든 하이퍼링크 추출
3. **JavaScript 렌더링**: Playwright로 동적으로 로드된 콘텐츠 스크레이핑
4. **폼 제출**: 폼을 채우고 제출한 뒤 결과 추출
5. **다중 요소**: 일치하는 여러 요소에서 콘텐츠 추출
6. **XPath 추출**: XPath 표현식을 사용한 정밀한 요소 타겟팅
7. **HTML 추출**: 추가 처리를 위한 원본 HTML 마크업 추출

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- 웹 스크레이핑 의존성:
  ```bash
  pip install playwright beautifulsoup4 lxml
  playwright install chromium
  ```

### 설정

이 예제 디렉토리로 이동:
```bash
cd examples/web-scraper
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   서비스는 다음을 시작합니다:
   - API 엔드포인트: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   # 기본 스크레이핑
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow": "basic-scraping",
       "input": {
         "url": "https://example.com",
         "selector": "h1"
       }
     }'

   # 링크 추출
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow": "extract-links",
       "input": {
         "url": "https://example.com"
       }
     }'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 드롭다운에서 워크플로우 선택
   - 입력 매개변수 입력
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   # 기본 스크레이핑
   model-compose run basic-scraping --input '{
     "url": "https://example.com",
     "selector": "h1"
   }'

   # JavaScript 렌더링
   model-compose run javascript-rendering --input '{
     "url": "https://spa-example.com",
     "selector": ".content",
     "wait_for": ".loaded"
   }'
   ```

## 컴포넌트 세부사항

### Web Scraper 컴포넌트

- **유형**: Web scraper 컴포넌트
- **목적**: 웹 페이지에서 콘텐츠 추출
- **기능**:
  - CSS 셀렉터 및 XPath 지원
  - Playwright를 통한 JavaScript 렌더링
  - 폼 채우기 및 제출
  - 여러 추출 모드 (text, HTML, attribute)
  - 사용자 정의 헤더 및 타임아웃 구성

## 워크플로우 세부사항

### 1. Basic Scraping 워크플로우

**ID**: `basic-scraping`
**설명**: CSS 셀렉터를 사용해 웹 페이지에서 텍스트 콘텐츠 추출

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | text | 예 | - | 스크레이핑할 웹 페이지 URL |
| `selector` | text | 아니오 | `"body"` | 요소를 찾을 CSS 셀렉터 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `content` | text | 추출된 텍스트 콘텐츠 |

---

### 2. Extract Links 워크플로우

**ID**: `extract-links`
**설명**: 속성 추출을 사용해 웹 페이지의 모든 링크 추출

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | text | 예 | - | 스크레이핑할 웹 페이지 URL |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `links` | array | 추출된 href 속성 목록 |

---

### 3. JavaScript Rendering 워크플로우

**ID**: `javascript-rendering`
**설명**: Playwright를 사용해 JavaScript로 렌더링된 웹 페이지에서 콘텐츠 추출

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | text | 예 | - | 스크레이핑할 웹 페이지 URL |
| `selector` | text | 아니오 | `".content"` | 요소를 찾을 CSS 셀렉터 |
| `wait_for` | text | 아니오 | - | 추출 전에 기다릴 CSS 셀렉터 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `content` | text | JavaScript로 렌더링된 페이지에서 추출된 텍스트 콘텐츠 |

**참고**: 이 워크플로우는 JavaScript 실행을 위해 Playwright를 사용하므로 SPA(Single Page Application) 및 동적으로 로드된 콘텐츠에 적합합니다.

---

### 4. Form Submission 워크플로우

**ID**: `form-submission`
**설명**: 웹 폼을 채우고 제출한 뒤 결과 콘텐츠 추출

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | text | 예 | - | 폼이 있는 웹 페이지 URL |
| `username` | text | 예 | - | 채울 사용자 이름 값 |
| `password` | text | 예 | - | 채울 비밀번호 값 |
| `form_selector` | text | 아니오 | `"form"` | 폼의 CSS 셀렉터 |
| `result_selector` | text | 아니오 | `".result"` | 제출 후 기다릴 CSS 셀렉터 |
| `content_selector` | text | 아니오 | `".result"` | 콘텐츠 추출용 CSS 셀렉터 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `result` | text | 폼 제출 후 추출된 콘텐츠 |

---

### 5. Multiple Elements 워크플로우

**ID**: `multiple-elements`
**설명**: 셀렉터와 일치하는 여러 요소에서 텍스트 추출

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | text | 예 | - | 스크레이핑할 웹 페이지 URL |
| `selector` | text | 아니오 | `"article h2"` | 요소를 찾을 CSS 셀렉터 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `titles` | array | 일치하는 요소에서 추출된 텍스트 콘텐츠 목록 |

**참고**: 이 워크플로우는 사용자 정의 User-Agent 헤더를 자동으로 포함합니다.

---

### 6. XPath Extraction 워크플로우

**ID**: `xpath-extraction`
**설명**: XPath 표현식을 사용해 웹 페이지에서 특정 콘텐츠 추출

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | text | 예 | - | 스크레이핑할 웹 페이지 URL |
| `xpath` | text | 아니오 | `"//div[@class='content']//p"` | 요소를 찾을 XPath 표현식 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `paragraphs` | array | 일치하는 요소에서 추출된 텍스트 콘텐츠 목록 |

---

### 7. HTML Extraction 워크플로우

**ID**: `html-extraction`
**설명**: 추가 처리를 위해 특정 요소의 HTML 마크업 추출

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | text | 예 | - | 스크레이핑할 웹 페이지 URL |
| `selector` | text | 아니오 | `"article"` | 요소를 찾을 CSS 셀렉터 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| `html` | text | 추출된 HTML 마크업 |

---

## 사용자 정의

### 추출 모드 수정

다양한 유형의 콘텐츠를 추출하도록 `extract_mode` 변경:

```yaml
component:
  type: web-scraper
  action:
    extract_mode: text    # 옵션: text, html, attribute
    attribute: href       # extract_mode가 "attribute"일 때 필요
```

### 사용자 정의 헤더 추가

인증 또는 식별을 위해 사용자 정의 HTTP 헤더 포함:

```yaml
component:
  type: web-scraper
  headers:
    Authorization: Bearer ${env.API_TOKEN}
    User-Agent: MyCustomBot/1.0
```

### 타임아웃 조정

느리게 로드되는 페이지를 위한 타임아웃 구성:

```yaml
component:
  type: web-scraper
  timeout: 120s  # 2분
```

### 입력 없이 폼 제출

폼 필드를 채우지 않고 제출 버튼만 클릭하려면:

```yaml
submit:
  selector: button[type="submit"]
  # 폼 필드 미지정 - 버튼만 클릭
```

## 모범 사례

- **robots.txt 존중**: 항상 웹사이트 크롤링 정책을 확인하고 존중하세요
- **속도 제한**: 여러 페이지를 스크레이핑할 때 요청 사이에 지연 추가
- **User-Agent**: 스크레이퍼를 식별할 수 있는 설명적인 User-Agent 사용
- **오류 처리**: 요소를 찾을 수 없는 경우 처리
- **JavaScript 렌더링**: 리소스를 더 많이 소비하므로 필요할 때만 사용
- **인증**: 자격 증명을 하드코딩하지 말고 환경 변수 사용

## 문제 해결

### Playwright 설치

Playwright 오류가 발생하는 경우:
```bash
playwright install chromium
```

### 타임아웃 오류

느리게 로드되는 페이지의 경우 타임아웃 증가:
```yaml
timeout: 120s
```

### 요소를 찾을 수 없음

- 브라우저 DevTools로 셀렉터 확인
- 요소가 동적으로 로드되는지 확인 (`enable_javascript: true` 사용)
- `wait_for`를 사용하여 특정 요소 대기

## 고급 사용법

### 다단계 스크레이핑

워크플로우에서 여러 컴포넌트 조합:

```yaml
workflows:
  - id: multi-step-scraping
    jobs:
      - id: get-links
        component: link-extractor
      - id: scrape-each-page
        component: page-scraper
        input:
          url: ${jobs.get-links.output.links[0]}
```

### 동적 폼 값

동적 폼 제출을 위해 워크플로우 입력 사용:

```yaml
submit:
  form:
    input[name="search"]: ${input.query}
    select[name="category"]: ${input.category}
```
