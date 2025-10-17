# Slack Bot MCP Server 예제

이 예제는 model-compose의 MCP (Model Context Protocol) server 기능을 사용하여 Slack bot을 생성하는 방법을 보여줍니다. Slack 채널 관리 및 메시징을 위한 여러 워크플로우를 제공합니다.

## 개요

이 MCP server는 다음과 같은 Slack 통합 워크플로우를 제공합니다:

1. **메시지 전송**: 첨부 파일 지원과 함께 Slack 채널에 메시지 전송
2. **채널 관리**: 사용 가능한 채널 목록 조회 및 새 채널 참여
3. **MCP Server**: Model Context Protocol을 통해 AI 에이전트 통합을 위한 워크플로우 노출
4. **다중 워크플로우**: 단일 MCP server에서 여러 관련 워크플로우 시연

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- 적절한 권한을 가진 Slack App
- Slack App Token (Bot User OAuth Token)

### Slack App 구성

1. https://api.slack.com/apps 에서 새 Slack App 생성
2. "OAuth & Permissions"에서 다음 OAuth scope 추가:
   - `channels:read` - 공개 채널에 대한 기본 정보 보기
   - `channels:join` - 공개 채널 참여
   - `chat:write` - bot으로 메시지 전송
   - `groups:read` - 비공개 채널에 대한 기본 정보 보기 (선택사항)

3. 워크스페이스에 앱 설치
4. "Bot User OAuth Token" 복사 (`xoxb-`로 시작)

### 환경 구성

1. 이 예제 디렉토리로 이동:
   ```bash
   cd examples/mcp-servers/slack-bot
   ```

2. 샘플 환경 파일 복사:
   ```bash
   cp .env.sample .env
   ```

3. `.env` 파일을 편집하여 Slack 자격 증명 추가:
   ```env
   SLACK_APP_TOKEN=xoxb-your-actual-bot-token
   DEFAULT_SLACK_CHANNEL_ID=C1234567890
   ```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```
2. **워크플로우 실행:**

   **MCP Client 사용:**
   - MCP server 연결: http://localhost:8080/mcp
   - 사용 가능한 워크플로우: send-message, list-channels, join-channel
   - MCP 호환 클라이언트를 사용하여 워크플로우 실행

   **웹 UI 사용:**
   - Web UI 열기: http://localhost:8081
   - 원하는 워크플로우 선택 (send-message, list-channels, join-channel)
   - 필요한 매개변수 입력
   - "Run" 버튼 클릭

   **CLI 사용:**
   ```bash
   # 기본 채널에 메시지 전송
   model-compose run send-message --input '{"messsage": "Hello from model-compose!"}'

   # 특정 채널에 전송
   model-compose run send-message --input '{
     "channel": "C1234567890",
     "messsage": "Hello specific channel!"
   }'

   # 채널 목록 조회
   model-compose run list-channels

   # 채널 참여
   model-compose run join-channel --input '{"channel": "C1234567890"}'
   ```

## 컴포넌트 세부사항

### Slack API HTTP Client 컴포넌트 (기본)
- **유형**: 여러 action을 가진 HTTP client 컴포넌트
- **목적**: Slack Web API 통합
- **Base URL**: `https://slack.com/api`
- **인증**: `SLACK_APP_TOKEN`을 사용한 Bearer token
- **Actions**:
  - **chat-post-message**: 채널에 메시지 전송
  - **conversations-list**: 채널 목록 조회
  - **conversations-join**: 공개 채널 참여
- **기능**:
  - 자동 OAuth token 처리
  - JSON 및 URL 인코딩 요청 지원
  - 응답 데이터 필터링 및 변환
  - Slack API 응답에 대한 오류 처리

## 워크플로우 세부사항

### "Send Message to Slack Channel" 워크플로우

**설명**: Slack Web API를 사용하여 지정된 Slack 채널에 텍스트 메시지 전송

#### 작업 흐름

```mermaid
graph TD
    %% Default job (implicit)
    J1((send-message<br/>작업))

    %% Component
    C1[Slack API<br/>컴포넌트]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |API response| J1

    %% Input/Output
    Input((입력)) --> J1
    J1 --> Output((출력))
```

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `channel` | text | 아니오 | `DEFAULT_SLACK_CHANNEL_ID` | 메시지를 전송할 Slack 채널 ID |
| `message` | text | 예 | - | Slack으로 전송할 메시지 |
| `attachments` | object[] | 아니오 | - | 선택적 메시지 첨부 파일 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| - | json | 메시지 메타데이터를 포함한 완전한 Slack API 응답 |

### "List Slack Channels" 워크플로우

**설명**: Slack 워크스페이스에서 사용 가능한 모든 채널 목록 조회

#### 작업 흐름

```mermaid
graph TD
    %% Default job (implicit)
    J1((list-channels<br/>작업))

    %% Component
    C1[Slack API<br/>컴포넌트]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |channel list| J1

    %% Input/Output
    Input((입력)) --> J1
    J1 --> Output((출력))
```

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `limit` | integer | 아니오 | 200 | 조회할 최대 채널 수 |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| - | object[] | `id`와 `name` 필드를 가진 채널 객체 배열 |

### "Join Slack Channel" 워크플로우

**설명**: bot 사용자가 지정된 Slack 채널 참여

#### 작업 흐름

```mermaid
graph TD
    %% Default job (implicit)
    J1((join-channel<br/>작업))

    %% Component
    C1[Slack API<br/>컴포넌트]

    %% Job to component connections
    J1 --> C1
    C1 -.-> |join result| J1

    %% Input/Output
    Input((입력)) --> J1
    J1 --> Output((출력))
```

#### 입력 매개변수

| 매개변수 | 유형 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `channel` | text | 아니오 | `DEFAULT_SLACK_CHANNEL_ID` | 참여할 Slack 채널 ID |

#### 출력 형식

| 필드 | 유형 | 설명 |
|-----|------|------|
| - | json | 채널 참여 상태를 포함한 완전한 Slack API 응답 |

## MCP Server 통합

이 예제는 Model Context Protocol을 지원하는 AI 에이전트 및 도구와 통합할 수 있는 MCP server 역할을 합니다:

### 연결 세부사항
- **전송**: HTTP
- **엔드포인트**: `http://localhost:8080/mcp`
- **프로토콜**: Model Context Protocol v1.0

### 사용 가능한 도구
AI 에이전트는 다음 워크플로우를 도구로 액세스할 수 있습니다:
- `send-message`: Slack에 메시지 전송
- `list-channels`: 사용 가능한 채널 조회
- `join-channel`: 공개 채널 참여

## Slack Web API 참조

### 사용된 엔드포인트

1. **chat.postMessage**
   - **목적**: 채널에 메시지 전송
   - **문서**: https://api.slack.com/methods/chat.postMessage

2. **conversations.list**
   - **목적**: 대화(채널) 목록 조회
   - **문서**: https://api.slack.com/methods/conversations.list

3. **conversations.join**
   - **목적**: 대화 참여
   - **문서**: https://api.slack.com/methods/conversations.join

## 오류 처리

일반적인 Slack API 오류 및 해결책:

### 인증 오류
- **invalid_auth**: `SLACK_APP_TOKEN`이 올바른지 확인
- **token_revoked**: Slack App 설정에서 bot token 재생성

### 권한 오류
- **missing_scope**: Slack App에 필요한 OAuth scope 추가
- **channel_not_found**: 채널 ID가 올바른지 확인
- **not_in_channel**: Bot이 비공개 채널에 추가되어야 함

### Rate Limiting
- Slack API에는 rate limit가 있음 - 초과 시 bot이 `rate_limited` 오류 수신
- 재시도 로직 구현 또는 요청 빈도 감소

## 사용자 정의

### Slack Action 추가
추가 Slack API 메서드로 컴포넌트 확장:

```yaml
actions:
  - id: users-list
    path: /users.list
    method: GET
    headers:
      Content-Type: application/x-www-form-urlencoded
    output: ${response.members}
```

### 사용자 정의 워크플로우 생성
단일 워크플로우에서 여러 action 결합:

```yaml
workflows:
  - id: notify-and-join
    jobs:
      - id: join
        action: conversations-join
        input:
          channel: ${input.channel}
      - id: notify
        action: chat-post-message
        input:
          channel: ${input.channel}
          text: "Bot has joined the channel!"
        depends_on: [join]
```

### 환경별 구성
다양한 환경에 대해 서로 다른 token 사용:

```yaml
headers:
  Authorization: Bearer ${env.SLACK_BOT_TOKEN_PROD | ${env.SLACK_BOT_TOKEN_DEV}}
```

## 보안 고려사항

- **Token 보안**: 버전 관리에 token 커밋하지 않기
- **Scope 제한**: 필요한 OAuth scope만 요청
- **채널 권한**: 공개 vs 비공개 채널 액세스 인식
- **메시지 내용**: 전송 전 사용자 입력 검증 및 정제
- **Rate Limiting**: 적절한 요청 조절 구현

## 문제 해결

### 일반적인 문제

1. **Token Invalid**: bot token이 `xoxb-`로 시작하고 올바른 권한이 있는지 확인
2. **Channel Not Found**: 채널 이름이 아닌 채널 ID (`C`로 시작) 사용
3. **Bot Not in Channel**: 비공개 채널에 수동으로 bot 추가 또는 공개 채널 사용
4. **MCP Connection Issues**: MCP server가 올바른 포트에서 실행 중인지 확인

### 디버깅 팁

- Slack의 API 테스터 사용: https://api.slack.com/methods
- 권한 문제에 대해 Slack App 이벤트 로그 확인
- 요청/응답 세부사항에 대해 MCP server 로그 모니터링
- MCP 컨텍스트에서 사용하기 전에 개별 워크플로우 테스트
