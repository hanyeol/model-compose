# 웹 리서치 에이전트 예제

이 예제는 웹을 검색하고 페이지 콘텐츠를 가져와 주제를 조사한 후 종합적인 답변을 제공하는 자율 에이전트를 보여줍니다.

## 개요

에이전트는 ReAct 루프를 통해 작동합니다:

1. **질문 수신**: 사용자가 리서치 질문을 제공
2. **검색 및 수집**: 에이전트가 자율적으로 도구를 사용하여 웹을 검색하고 관련 페이지를 읽음
3. **종합**: 충분한 정보를 수집한 후 종합적인 답변 생성

### 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `search_web` | Tavily API를 사용한 웹 검색 |
| `fetch_page` | URL에서 텍스트 콘텐츠 추출 |

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- OpenAI API 키
- Tavily API 키 ([tavily.com](https://tavily.com))

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/agents/web-researcher
   ```

2. 샘플 환경 파일 복사:
   ```bash
   cp .env.sample .env
   ```

3. `.env` 파일을 편집하여 API 키 추가:
   ```env
   OPENAI_API_KEY=your-openai-api-key
   TAVILY_API_KEY=your-tavily-api-key
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
     -d '{"question": "양자 컴퓨팅의 최신 발전 사항은 무엇인가요?"}'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 리서치 질문을 입력하고 "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"question": "양자 컴퓨팅의 최신 발전 사항은 무엇인가요?"}'
   ```

## 컴포넌트 세부사항

### OpenAI GPT-4o 컴포넌트 (gpt-4o)
- **유형**: HTTP client 컴포넌트
- **목적**: 에이전트 추론 및 도구 사용을 위한 LLM
- **API**: OpenAI GPT-4o Chat Completions (function calling)

### Tavily 검색 컴포넌트 (tavily)
- **유형**: HTTP client 컴포넌트
- **목적**: 웹 검색 API
- **API**: Tavily Search API

### 웹 스크래퍼 컴포넌트 (scraper)
- **유형**: Web scraper 컴포넌트
- **목적**: 웹 페이지에서 텍스트 콘텐츠 추출

### 리서치 에이전트 컴포넌트 (research-agent)
- **유형**: Agent 컴포넌트
- **목적**: 도구를 조율하는 자율 리서치 에이전트
- **최대 반복 횟수**: 10

## 워크플로우 세부사항

### 도구: search_web

**설명**: 주어진 쿼리에 대해 웹에서 정보를 검색합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `query` | string | 예 | - | 검색 쿼리 문자열 |
| `max_results` | integer | 아니오 | `5` | 반환할 최대 검색 결과 수 |

### 도구: fetch_page

**설명**: 웹 페이지 URL에서 텍스트 콘텐츠를 가져옵니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | string | 예 | - | 가져올 웹 페이지의 URL |

## 사용자 정의

- `gpt-4o`를 function calling을 지원하는 다른 모델(예: Claude, Llama 3.1+)로 교체
- `max_iteration_count`를 조정하여 에이전트 탐색 깊이 제어
- 추가 워크플로우를 정의하여 더 많은 도구(예: 이미지 분석, 번역) 추가
