# 디스크 분석 에이전트 예제

이 예제는 셸 명령을 도구로 사용하여 시스템 디스크 사용량을 분석하고 상세한 권장사항을 제공하는 자율 에이전트를 보여줍니다. `analyze-disk-usage` 예제의 에이전트 버전입니다.

## 개요

에이전트는 ReAct 루프를 통해 작동합니다:

1. **질문 수신**: 사용자가 디스크 분석 질문을 제공 (또는 기본값 사용)
2. **조사**: 에이전트가 자율적으로 셸 명령을 실행하여 디스크 사용량, 디렉토리 크기, 파일 목록을 확인
3. **분석**: 충분한 정보를 수집한 후 상세한 분석과 권장사항 생성

### 사용 가능한 도구

| 도구 | 설명 |
|------|------|
| `get_disk_usage` | 모든 마운트된 파일시스템의 디스크 사용량 조회 (`df -h`) |
| `get_directory_sizes` | 특정 디렉토리의 총 크기 조회 (`du -sh`) |
| `list_files` | 파일 및 디렉토리 세부 정보 목록 조회 (`ls -la`) |

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- OpenAI API 키

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/agents/disk-analyzer
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
     -d '{"question": "/home 아래에서 디스크 공간을 가장 많이 사용하는 디렉토리는?"}'
   ```

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 질문을 입력하고 "Run Workflow" 버튼 클릭

   **CLI 사용:**
   ```bash
   model-compose run --input '{"question": "디스크 사용량을 분석하고 큰 파일을 찾아줘"}'
   ```

## 컴포넌트 세부사항

### OpenAI GPT-4o 컴포넌트 (gpt-4o)
- **유형**: HTTP client 컴포넌트
- **목적**: 에이전트 추론 및 도구 사용을 위한 LLM
- **API**: OpenAI GPT-4o Chat Completions (function calling)

### Shell 컴포넌트 (disk-usage, directory-sizes, file-lister)
- **유형**: Shell 컴포넌트
- **목적**: 디스크 분석을 위한 시스템 명령 실행
- **명령**: `df -h`, `du -sh`, `ls -la`

### 디스크 분석 에이전트 컴포넌트 (disk-analyzer)
- **유형**: Agent 컴포넌트
- **목적**: 디스크 사용량을 조사하는 자율 에이전트
- **최대 반복 횟수**: 10

## 워크플로우 세부사항

### 도구: get_disk_usage

**설명**: 모든 마운트된 파일시스템의 디스크 사용량 정보를 가져옵니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| - | - | - | - | 이 도구는 입력 매개변수가 필요하지 않습니다 |

### 도구: get_directory_sizes

**설명**: 특정 디렉토리의 총 크기를 가져옵니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `path` | string | 예 | - | 크기를 측정할 디렉토리의 절대 경로 |

### 도구: list_files

**설명**: 주어진 경로의 파일 및 디렉토리 세부 정보를 나열합니다.

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `path` | string | 예 | - | 목록을 조회할 디렉토리의 절대 경로 |

## 사용자 정의

- `gpt-4o`를 function calling을 지원하는 다른 모델로 교체
- 더 많은 셸 도구 추가 (예: `find`로 파일 검색, `top`으로 프로세스 정보)
- `max_iteration_count`를 조정하여 더 깊은 조사 허용
- 운영 체제에 맞게 셸 명령 수정
