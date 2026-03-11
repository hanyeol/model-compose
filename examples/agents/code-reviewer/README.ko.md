# 코드 리뷰 에이전트 예제

이 예제는 파일을 읽고, 디렉토리를 탐색하고, 코드를 검색하여 코드 리뷰를 수행하고 개선 제안을 제공하는 자율 에이전트를 보여줍니다.

## 개요

에이전트는 ReAct 루프를 통해 작동합니다:

1. **요청 수신**: 사용자가 코드 리뷰 요청과 대상 경로를 제공
2. **탐색**: 에이전트가 디렉토리를 나열하고 관련 파일을 읽음
3. **검색**: 에이전트가 코드베이스에서 특정 패턴을 검색
4. **리뷰**: 코드를 이해한 후 상세한 리뷰 결과 생성

### 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `read_file` | 파일 내용 읽기 |
| `list_directory` | 파일 및 디렉토리 세부 정보 목록 조회 |
| `search_code` | grep을 사용한 파일 내 패턴 검색 |

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- OpenAI API 키

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/agents/code-reviewer
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
     -d '{"request": "이 코드에서 잠재적인 버그를 찾고 개선 사항을 제안해줘", "target_path": "/path/to/project/src"}'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 리뷰 요청과 대상 경로를 입력하고 "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"request": "보안 취약점 찾기", "target_path": "./src"}'
   ```

## 컴포넌트 세부사항

### OpenAI GPT-4o 컴포넌트 (gpt-4o)
- **유형**: HTTP client 컴포넌트
- **목적**: 에이전트 추론 및 코드 분석을 위한 LLM
- **API**: OpenAI GPT-4o Chat Completions (function calling)

### Shell 컴포넌트 (file-reader, dir-lister, code-searcher)
- **유형**: Shell 컴포넌트
- **목적**: 코드 탐색을 위한 파일 시스템 작업
- **명령**: `cat`, `ls -la`, `grep -rn`

### 코드 리뷰 에이전트 컴포넌트 (code-reviewer)
- **유형**: Agent 컴포넌트
- **목적**: 코드를 탐색하고 리뷰하는 자율 에이전트
- **최대 반복 횟수**: 15

## 워크플로우 세부사항

### 도구: read_file

**설명**: 파일의 내용을 읽어서 반환합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `path` | string | 예 | - | 읽을 파일의 경로 |

### 도구: list_directory

**설명**: 주어진 경로의 모든 파일과 디렉토리를 세부 정보와 함께 나열합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `path` | string | 예 | - | 목록을 조회할 디렉토리 경로 |

### 도구: search_code

**설명**: grep을 사용하여 파일에서 패턴을 재귀적으로 검색합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `pattern` | string | 예 | - | 검색할 패턴 또는 정규식 |
| `path` | string | 아니오 | `.` | 검색할 디렉토리 경로 |

## 사용자 정의

- `gpt-4o`를 function calling을 지원하는 다른 모델로 교체
- 더 많은 도구 추가 (예: `wc`로 줄 수 세기, `diff`로 파일 비교)
- `max_iteration_count`를 조정하여 더 깊은 코드 탐색 허용
- 필요에 따라 셸 명령 수정 (예: `grep` 대신 `rg` 사용)
