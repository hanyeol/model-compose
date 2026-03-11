# 멀티 도구 어시스턴트 에이전트 예제

이 예제는 웹 검색, 날씨 조회, 계산기, 시계 등 여러 도구를 조합하여 다양한 질문에 답변하는 범용 어시스턴트 에이전트를 보여줍니다.

## 개요

에이전트는 ReAct 루프를 통해 작동합니다:

1. **질문 수신**: 사용자가 질문을 제공
2. **도구 선택**: 에이전트가 질문에 따라 사용할 도구를 결정
3. **실행 및 결합**: 에이전트가 도구를 호출하고 결과를 결합하며 추론
4. **답변**: 수집된 정보를 사용하여 종합적인 답변 생성

### 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `search_web` | Tavily API를 사용한 웹 검색 |
| `get_weather` | 도시의 현재 날씨 조회 |
| `run_calculation` | 수학 계산을 위한 Python 표현식 실행 |
| `get_current_time` | 현재 날짜 및 시간 조회 |

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- OpenAI API 키
- Tavily API 키 ([tavily.com](https://tavily.com))
- OpenWeatherMap API 키 ([openweathermap.org](https://openweathermap.org/api))

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/agents/multi-tool
   ```

2. 샘플 환경 파일 복사:
   ```bash
   cp .env.sample .env
   ```

3. `.env` 파일을 편집하여 API 키 추가:
   ```env
   OPENAI_API_KEY=your-openai-api-key
   TAVILY_API_KEY=your-tavily-api-key
   OPENWEATHER_API_KEY=your-openweathermap-api-key
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
     -d '{"question": "도쿄의 날씨와 현재 시간은?"}'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 질문을 입력하고 "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"question": "2의 64승을 계산하고 그 숫자가 뭘 의미하는지 검색해줘"}'
   ```

## 컴포넌트 세부사항

### OpenAI GPT-4o 컴포넌트 (gpt-4o)
- **유형**: HTTP client 컴포넌트
- **목적**: 에이전트 추론 및 도구 선택을 위한 LLM
- **API**: OpenAI GPT-4o Chat Completions (function calling)

### Tavily 검색 컴포넌트 (tavily)
- **유형**: HTTP client 컴포넌트
- **목적**: 웹 검색 API
- **API**: Tavily Search API

### 날씨 API 컴포넌트 (weather-api)
- **유형**: HTTP client 컴포넌트
- **목적**: 현재 날씨 데이터
- **API**: OpenWeatherMap API

### 계산기 컴포넌트 (calculator)
- **유형**: Shell 컴포넌트
- **목적**: 계산을 위한 Python 표현식 실행

### 시계 컴포넌트 (clock)
- **유형**: Shell 컴포넌트
- **목적**: 현재 날짜 및 시간 조회

### 어시스턴트 에이전트 컴포넌트 (assistant)
- **유형**: Agent 컴포넌트
- **목적**: 모든 도구를 조율하는 멀티 도구 어시스턴트
- **최대 반복 횟수**: 10

## 워크플로우 세부사항

### 도구: search_web

**설명**: 주어진 쿼리에 대해 웹에서 정보를 검색합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `query` | string | 예 | - | 검색 쿼리 문자열 |
| `max_results` | integer | 아니오 | `5` | 최대 검색 결과 수 |

### 도구: get_weather

**설명**: 도시의 현재 날씨를 가져옵니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `city` | string | 예 | - | 도시명, 예: "Tokyo" 또는 "London,UK" |

### 도구: run_calculation

**설명**: 수학 계산을 위한 Python 표현식을 실행합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `expression` | string | 예 | - | 평가할 Python 표현식, 예: "print(2 ** 10)" |

### 도구: get_current_time

**설명**: 타임존 정보가 포함된 현재 날짜와 시간을 가져옵니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| - | - | - | - | 이 도구는 입력 매개변수가 필요하지 않습니다 |

## 사용자 정의

- `gpt-4o`를 function calling을 지원하는 다른 모델로 교체
- 추가 워크플로우를 정의하여 더 많은 도구(예: 번역, 이미지 생성) 추가
- 간단한 사용 사례에 맞게 불필요한 도구 제거
- `max_iteration_count`를 조정하여 에이전트 탐색 깊이 제어
