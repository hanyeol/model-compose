# RAG 어시스턴트 에이전트 예제

이 예제는 ChromaDB 벡터 스토어에서 지식을 검색하고 추가하여 질문에 답변하는 RAG(Retrieval-Augmented Generation) 자율 에이전트를 보여줍니다.

## 개요

에이전트는 ReAct 루프를 통해 작동합니다:

1. **질문 수신**: 사용자가 질문을 제공
2. **지식 검색**: 에이전트가 벡터 스토어에서 관련 정보를 검색
3. **지식 추가**: 에이전트가 새로운 지식을 스토어에 추가 가능
4. **답변**: 관련 컨텍스트를 검색한 후 정보에 기반한 답변 생성

### 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `search_knowledge` | 지식 베이스에서 관련 문서 검색 |
| `add_knowledge` | 지식 베이스에 새로운 지식 추가 |

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- OpenAI API 키
- ChromaDB (의존성으로 자동 설치)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/agents/rag-assistant
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
     -d '{"question": "model-compose에 대해 뭘 알고 있어?"}'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 질문을 입력하고 "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"question": "model-compose에 대해 뭘 알고 있어?"}'
   ```

## 컴포넌트 세부사항

### OpenAI GPT-4o 컴포넌트 (gpt-4o)
- **유형**: HTTP client 컴포넌트
- **목적**: 에이전트 추론(chat 액션) 및 텍스트 임베딩(embedding 액션)을 위한 LLM
- **API**: OpenAI Chat Completions + Embeddings API

### 벡터 스토어 컴포넌트 (vector-store)
- **유형**: Vector store 컴포넌트
- **목적**: 지식 임베딩 저장 및 검색
- **드라이버**: ChromaDB
- **컬렉션**: `knowledge`

### RAG 어시스턴트 에이전트 컴포넌트 (rag-assistant)
- **유형**: Agent 컴포넌트
- **목적**: 지식을 검색하고 관리하는 자율 RAG 에이전트
- **최대 반복 횟수**: 5

## 워크플로우 세부사항

### 도구: search_knowledge

**설명**: 지식 베이스에서 관련 정보를 검색합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `query` | string | 예 | - | 관련 지식을 찾기 위한 검색 쿼리 |

### 도구: add_knowledge

**설명**: 지식 베이스에 새로운 지식을 추가합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `text` | string | 예 | - | 지식 베이스에 추가할 텍스트 콘텐츠 |
| `source` | string | 아니오 | `user-input` | 지식의 출처 또는 원본 |

## 사용자 정의

- `text-embedding-3-small`을 다른 임베딩 모델로 교체
- ChromaDB를 Milvus 또는 다른 벡터 스토어 드라이버로 전환
- `max_iteration_count`를 조정하여 검색 깊이 제어
- 더 많은 도구(예: 웹 검색) 추가하여 RAG와 실시간 데이터 결합
