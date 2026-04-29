# Human-in-the-Loop 에이전트 예제

이 예제는 위험한 작업(쓰기, 삭제)을 실행하기 전에 사람의 승인을 요구하고, 안전한 작업(읽기, 목록)은 중단 없이 실행하는 파일 관리 에이전트를 보여줍니다.

## 개요

에이전트는 인터럽트 메커니즘이 포함된 ReAct 루프를 통해 동작합니다:

1. **요청 수신**: 사용자가 에이전트에게 파일 작업을 요청합니다
2. **도구 선택**: 에이전트가 사용할 도구를 결정합니다
3. **안전한 작업**: 읽기와 목록 조회는 중단 없이 즉시 실행됩니다
4. **위험한 작업**: 쓰기와 삭제는 실행 전 사람의 승인을 기다립니다
5. **응답**: 작업 완료 후 결과 요약을 생성합니다

### 사용 가능한 도구

| 도구 | 설명 | 승인 필요 |
|------|------|:---------:|
| `read_file` | 파일 내용 읽기 | 아니오 |
| `list_directory` | 파일 및 디렉토리 목록 조회 | 아니오 |
| `write_file` | 파일에 내용 쓰기 | 예 |
| `delete_file` | 파일 삭제 | 예 |

## 준비

### 사전 요구 사항

- model-compose가 설치되어 있고 PATH에서 사용 가능해야 합니다
- OpenAI API 키

### 환경 설정

1. 이 예제 디렉토리로 이동합니다:
   ```bash
   cd examples/agents/human-in-the-loop
   ```

2. 샘플 환경 파일을 복사합니다:
   ```bash
   cp .env.sample .env
   ```

3. `.env` 파일을 편집하여 API 키를 추가합니다:
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
     -d '{"request": "List the files in the current directory."}'
   ```

   **Web UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 요청을 입력하고 "Run Workflow"를 클릭합니다
   - 위험한 작업이 트리거되면 확인 대화 상자가 나타납니다

   **CLI 사용:**
   ```bash
   model-compose run --input '{"request": "Create a file called hello.txt with the content Hello World"}'
   ```

## 컴포넌트 상세

### OpenAI GPT-4o 컴포넌트 (gpt-4o)
- **유형**: HTTP 클라이언트 컴포넌트
- **목적**: 에이전트의 추론 및 도구 선택을 위한 LLM
- **API**: 함수 호출을 지원하는 OpenAI GPT-4o Chat Completions

### 파일 리더 컴포넌트 (file-reader)
- **유형**: 셸 컴포넌트
- **목적**: `cat`을 사용한 파일 내용 읽기

### 디렉토리 리스터 컴포넌트 (directory-lister)
- **유형**: 셸 컴포넌트
- **목적**: `ls -la`를 사용한 디렉토리 내용 목록 조회

### 파일 라이터 컴포넌트 (file-writer)
- **유형**: 셸 컴포넌트
- **목적**: 셸 리디렉션을 사용한 파일 내용 쓰기

### 파일 딜리터 컴포넌트 (file-deleter)
- **유형**: 셸 컴포넌트
- **목적**: `rm`을 사용한 파일 삭제

### 파일 매니저 에이전트 컴포넌트 (file-manager)
- **유형**: 에이전트 컴포넌트
- **목적**: 위험한 작업에 대한 사람의 승인을 포함한 파일 작업 오케스트레이션
- **최대 반복 횟수**: 15

## 인터럽트 동작 방식

`interrupt` 기능은 위험한 작업이 실행되기 전에 워크플로우 실행을 일시 중지합니다:

```yaml
interrupt:
  before:
    message: "The agent wants to write to a file. Please review and approve."
    metadata:
      path: ${job.input.path}
      content: ${job.input.content}
```

- **`before`**: 작업이 실행 전 일시 중지되고 사용자에게 메시지를 표시합니다
- **`metadata`**: 승인 대화 상자에 표시되는 추가 컨텍스트 (예: 파일 경로, 내용)
- 사용자는 **승인**하여 진행하거나 **거부**하여 작업을 취소할 수 있습니다

이 패턴은 에이전트가 명시적인 사람의 동의 없이 파괴적인 작업을 수행할 수 없도록 보장합니다.

## 커스터마이징

- `gpt-4o`를 함수 호출을 지원하는 다른 모델로 교체할 수 있습니다
- 인터럽트 가드를 포함하거나 포함하지 않고 더 많은 도구를 추가할 수 있습니다 (예: 이름 변경, 이동, 복사)
- `max_iteration_count`를 조정하여 에이전트가 수행할 수 있는 도구 호출 횟수를 제어할 수 있습니다
- `system_prompt`를 수정하여 에이전트의 동작을 변경하거나 허용 경로를 제한할 수 있습니다
