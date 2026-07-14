# 웹 페이지 분석 에이전트 예제

이 예제는 web-scraper 도구를 사용하여 웹 페이지를 스크래핑하고 분석하는 자율 에이전트를 보여줍니다. URL과 페이지에 대한 질문을 주면 에이전트가 어떤 도구를 호출할지 결정하여 답변합니다.

## 개요

에이전트는 ReAct 루프를 통해 작동합니다:

1. **요청 수신**: 사용자가 웹 페이지 URL을 포함한 질문 제공
2. **페이지 수집**: 에이전트가 `fetch_page`로 전체 페이지 텍스트를 읽고 구조 파악
3. **추출**: 필요에 따라 `extract_elements` 또는 `extract_links`로 특정 부분 추출
4. **답변**: 충분한 컨텍스트를 수집한 후 명확하고 잘 정리된 답변 생성

### 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `fetch_page` | 웹 페이지 URL에서 본문 텍스트 콘텐츠 조회 |
| `extract_links` | 웹 페이지의 모든 하이퍼링크(href URL) 추출 |
| `extract_elements` | CSS 셀렉터로 특정 요소의 텍스트 콘텐츠 추출 |

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- OpenAI API 키

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/agents/web-page-analyzer
   ```

2. 샘플 환경 파일 복사:
   ```bash
   cp .env.sample .env
   ```

3. `.env` 파일을 편집하여 OpenAI API 키 추가:
   ```env
   OPENAI_API_KEY=your-openai-api-key
   ```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"question": "https://example.com/blog/post의 주요 내용을 요약해줘"}'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 질문을 입력하고 "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"question": "https://example.com의 모든 H2 제목을 나열해줘"}'
   ```

## 컴포넌트 세부사항

### OpenAI GPT-4o 컴포넌트 (gpt-4o)
- **유형**: HTTP client 컴포넌트
- **목적**: 에이전트 추론 및 답변 생성용 LLM
- **API**: OpenAI GPT-4o Chat Completions (function calling)

### Web Scraper 컴포넌트 (page-scraper, link-scraper, element-scraper)
- **유형**: Web scraper 컴포넌트
- **목적**: CSS 셀렉터를 통한 HTML 스크래핑
- **추출 모드**: 콘텐츠 추출용 `text`, 링크 추출용 `attribute`

### 분석 에이전트 컴포넌트 (analyzer-agent)
- **유형**: Agent 컴포넌트
- **목적**: 웹 페이지를 스크래핑하고 분석하는 자율 에이전트
- **최대 반복 횟수**: 10

## 워크플로우 세부사항

### 도구: fetch_page

**설명**: 웹 페이지 URL에서 본문 텍스트 콘텐츠를 조회합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | string | 예 | - | 조회할 웹 페이지의 URL |

### 도구: extract_links

**설명**: 웹 페이지의 모든 하이퍼링크(href URL)를 추출합니다. 페이지에서 발견된 URL의 JSON 목록을 반환합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | string | 예 | - | 링크를 추출할 웹 페이지의 URL |

### 도구: extract_elements

**설명**: CSS 셀렉터로 웹 페이지에서 특정 요소의 텍스트 콘텐츠를 추출합니다. 매칭된 요소 텍스트의 JSON 목록을 반환합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | string | 예 | - | 웹 페이지의 URL |
| `selector` | string | 예 | - | 대상 요소의 CSS 셀렉터 (예: "h2", ".title", "#main p") |

## 참고사항

- 에이전트는 클래스 이름을 추측하는 대신 간단한 태그 기반 셀렉터(예: `h1`, `h2`, `p`, `li`, `a`, `table tr`)를 우선 사용하도록 지시받습니다.
- 셀렉터가 빈 결과를 반환하면 에이전트는 다른 클래스 이름을 추측하는 대신 더 단순하거나 넓은 셀렉터를 시도합니다.

## 사용자 정의

- `gpt-4o`를 function calling을 지원하는 다른 모델로 교체
- 더 많은 스크래핑 도구 추가 (예: 이미지 추출기, 테이블 파서)
- `max_iteration_count`를 조정하여 더 깊은 페이지 탐색 허용
- 봇 차단 사이트 대응을 위해 스크래퍼에 User-Agent 헤더나 타임아웃 추가
